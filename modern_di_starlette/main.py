"""modern-di integration for Starlette."""

import contextlib
import functools
import typing

from modern_di import Container, Scope, integrations, providers
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.types import ASGIApp, Lifespan, Receive, Send
from starlette.types import Scope as ASGIScope
from starlette.websockets import WebSocket


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
        match = integrations.classify_connection(connection, _CONNECTION_PROVIDERS)
        async with self.container.build_child_container(
            scope=match.scope if match else None,
            context=match.context if match else None,
        ) as child_container:
            scope[_CONTAINER_SCOPE_KEY] = child_container
            await self.app(scope, receive, send)


def setup_di(app: Starlette, container: Container) -> Container:
    app.state.di_container = container
    container.add_providers(*_CONNECTION_PROVIDERS)
    app.router.lifespan_context = _compose_lifespan(app.router.lifespan_context)
    app.add_middleware(_DIMiddleware, container=container)
    return container


FromDI = integrations.from_di


def inject(func: typing.Callable[..., typing.Awaitable[T]]) -> typing.Callable[..., typing.Awaitable[T]]:
    markers = integrations.parse_markers(func)

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
        return await func(connection, **integrations.resolve_markers(child_container, markers))

    return wrapper
