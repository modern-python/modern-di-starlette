"""modern-di integration for Starlette."""

import contextlib
import dataclasses
import enum
import functools
import typing

from modern_di import Container, Scope, providers
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.types import ASGIApp, Lifespan, Receive, Send
from starlette.types import Scope as ASGIScope
from starlette.websockets import WebSocket


T_co = typing.TypeVar("T_co", covariant=True)
T = typing.TypeVar("T")

starlette_request_provider = providers.ContextProvider(scope=Scope.REQUEST, context_type=Request)
starlette_websocket_provider = providers.ContextProvider(scope=Scope.SESSION, context_type=WebSocket)

# Single source of the connection-kind mapping: each provider pairs a Starlette
# connection type with the scope its child container opens at. The middleware
# dispatches off this tuple; add a connection kind by adding its provider here.
_CONNECTION_PROVIDERS = (starlette_request_provider, starlette_websocket_provider)

# Key under which the per-connection child container lives in the ASGI scope dict.
# `_DIMiddleware` writes it; `inject` (Task 3) reads it back.
_CONTAINER_SCOPE_KEY = "modern_di_container"


def fetch_di_container(app: Starlette) -> Container:
    return typing.cast(Container, app.state.di_container)


def _compose_lifespan(original: Lifespan[Starlette]) -> Lifespan[Starlette]:
    """Wrap ``original`` so the root container opens/closes around it.

    ``async with`` reopens the container on each startup and closes it on
    shutdown, so a second lifespan cycle against the same container works
    instead of raising ``ContainerClosedError``. The original lifespan stays
    the outer context and its yielded state passes straight through.
    """

    @contextlib.asynccontextmanager
    async def composed(app: Starlette) -> typing.AsyncIterator[typing.Mapping[str, typing.Any] | None]:
        async with original(app) as state, fetch_di_container(app):
            yield state

    return typing.cast(Lifespan[Starlette], composed)


class _DIMiddleware:
    def __init__(self, app: ASGIApp, container: Container) -> None:
        self.app = app
        self.container = container

    async def __call__(self, scope: ASGIScope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        connection: Request | WebSocket = (
            Request(scope, receive) if scope["type"] == "http" else WebSocket(scope, receive, send)
        )
        context: dict[type[typing.Any], typing.Any] = {}
        # `enum.IntEnum`, not `Scope`: `AbstractProvider.scope` is typed broadly to
        # support custom scope enums, and `build_child_container(scope=...)` takes
        # the same broad type — matching it here keeps `ty` happy without a cast.
        connection_scope: enum.IntEnum | None = None
        for provider in _CONNECTION_PROVIDERS:
            if isinstance(connection, provider.context_type):
                context[provider.context_type] = connection
                connection_scope = provider.scope
                break

        child_container = self.container.build_child_container(context=context, scope=connection_scope)
        scope[_CONTAINER_SCOPE_KEY] = child_container
        try:
            await self.app(scope, receive, send)
        finally:
            await child_container.close_async()


def setup_di(app: Starlette, container: Container) -> Container:
    app.state.di_container = container
    container.providers_registry.add_providers(*_CONNECTION_PROVIDERS)
    app.router.lifespan_context = _compose_lifespan(app.router.lifespan_context)
    app.add_middleware(_DIMiddleware, container=container)
    return container


@dataclasses.dataclass(slots=True, frozen=True)
class _FromDI(typing.Generic[T_co]):
    dependency: providers.AbstractProvider[T_co] | type[T_co]


def FromDI(dependency: providers.AbstractProvider[T_co] | type[T_co]) -> T_co:  # noqa: N802
    return typing.cast(T_co, _FromDI(dependency))


def _parse_inject_params(func: typing.Callable[..., typing.Any]) -> dict[str, _FromDI[typing.Any]]:
    hints = typing.get_type_hints(func, include_extras=True)
    di_params: dict[str, _FromDI[typing.Any]] = {}
    for name, hint in hints.items():
        if name == "return":
            continue
        if typing.get_origin(hint) is typing.Annotated:
            for meta in typing.get_args(hint)[1:]:
                if isinstance(meta, _FromDI):
                    di_params[name] = meta
                    break
    return di_params


def _resolve_di_params(container: Container, di_params: dict[str, _FromDI[typing.Any]]) -> dict[str, typing.Any]:
    return {
        name: (
            container.resolve_provider(marker.dependency)
            if isinstance(marker.dependency, providers.AbstractProvider)
            else container.resolve(dependency_type=marker.dependency)
        )
        for name, marker in di_params.items()
    }


def inject(func: typing.Callable[..., typing.Awaitable[T]]) -> typing.Callable[..., typing.Awaitable[T]]:
    di_params = _parse_inject_params(func)

    @functools.wraps(func)
    async def wrapper(connection: Request | WebSocket) -> T:
        try:
            child_container: Container = connection.scope[_CONTAINER_SCOPE_KEY]
        except KeyError:
            msg = (
                "No modern-di container found in the request scope. "
                "Call setup_di(app, container) so requests pass through the modern-di middleware "
                "before using @inject."
            )
            raise RuntimeError(msg) from None
        return await func(connection, **_resolve_di_params(child_container, di_params))

    return wrapper
