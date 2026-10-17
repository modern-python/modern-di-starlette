"""modern-di integration for Starlette."""

import collections.abc
import contextlib
import functools
import inspect
import typing

from modern_di import Container, Scope, integrations, providers
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import BaseRoute, Host, Mount
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
_CONTAINER_SCOPE_KEY = "modern_di_container"
_MISSING = object()
_MANAGE_LIFESPAN_KEY = "di_manage_lifespan"


def fetch_di_container(app: Starlette) -> Container:
    return typing.cast(Container, app.state.di_container)


def _managed_containers(app: Starlette) -> collections.abc.Iterator[Container]:
    try:
        container = fetch_di_container(app)
    except AttributeError:
        return
    if getattr(app.state, _MANAGE_LIFESPAN_KEY, True):
        yield container


def _mounted_containers(routes: collections.abc.Iterable[BaseRoute]) -> collections.abc.Iterator[Container]:
    for route in routes:
        if not isinstance(route, Mount | Host):
            continue
        # Mount(middleware=...) wraps route.app; Starlette keeps the unwrapped app on the private _base_app.
        app = getattr(route, "_base_app", route.app)
        if isinstance(app, Starlette):
            yield from _managed_containers(app)
        yield from _mounted_containers(route.routes)


def _compose_lifespan(original: Lifespan[Starlette]) -> Lifespan[Starlette]:
    """Wrap ``original`` so the root container opens/closes around it.

    ``async with`` reopens the container on each startup and closes it on
    shutdown, so a second lifespan cycle against the same container works
    instead of raising ``ContainerClosedError``. The containers are the outer
    context: they open before the original lifespan's startup code and close
    after its shutdown code, so that code can resolve ``APP`` dependencies and
    their finalizers run last. The original lifespan's yielded state passes
    straight through.

    Starlette runs only the outermost app's lifespan, so the root containers of
    mounted apps that called ``setup_di`` are opened and closed here too. The
    routes are walked at startup, and each container is entered once. An app
    whose ``setup_di`` got ``manage_lifespan=False`` is skipped, its own root
    included.
    """

    @contextlib.asynccontextmanager
    async def composed(app: Starlette) -> collections.abc.AsyncGenerator[typing.Mapping[str, typing.Any] | None]:
        async with contextlib.AsyncExitStack() as stack:
            entered: list[Container] = []
            for container in (*_managed_containers(app), *_mounted_containers(app.routes)):
                if not any(container is seen for seen in entered):
                    entered.append(container)
                    await stack.enter_async_context(container)
            async with original(app) as state:
                yield state

    return typing.cast(Lifespan[Starlette], composed)


class _DIMiddleware:
    def __init__(self, app: ASGIApp, di_app: Starlette) -> None:
        self.app = app
        self.di_app = di_app

    async def __call__(self, scope: ASGIScope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        connection: Request | WebSocket = (
            Request(scope, receive) if scope["type"] == "http" else WebSocket(scope, receive, send)
        )
        match = integrations.classify_connection(connection, _CONNECTION_PROVIDERS)
        async with fetch_di_container(self.di_app).build_child_container(
            scope=match.scope if match else None,
            context=match.context if match else None,
        ) as child_container:
            previous = scope.get(_CONTAINER_SCOPE_KEY, _MISSING)
            scope[_CONTAINER_SCOPE_KEY] = child_container
            try:
                await self.app(scope, receive, send)
            finally:
                # The container's context holds the connection, which owns this scope — leaving the
                # entry behind closes a cycle, so the request could only be reclaimed by the GC.
                if previous is _MISSING:
                    del scope[_CONTAINER_SCOPE_KEY]
                else:
                    scope[_CONTAINER_SCOPE_KEY] = previous


def setup_di(app: Starlette, container: Container, *, manage_lifespan: bool = True) -> Container:
    app.state.di_container = container
    setattr(app.state, _MANAGE_LIFESPAN_KEY, manage_lifespan)
    container.add_providers(*_CONNECTION_PROVIDERS)
    app.router.lifespan_context = _compose_lifespan(app.router.lifespan_context)
    if not any(middleware.cls is _DIMiddleware for middleware in app.user_middleware):
        app.add_middleware(_DIMiddleware, di_app=app)
    return container


FromDI = integrations.from_di


def _find_connection(handler_name: str, args: tuple[typing.Any, ...]) -> Request | WebSocket:
    for arg in args:
        if isinstance(arg, Request | WebSocket):
            return arg
    msg = f"@inject requires {handler_name} to receive a Request or WebSocket as a positional argument."
    raise TypeError(msg)


def _fetch_child_container(connection: Request | WebSocket) -> Container:
    try:
        return typing.cast(Container, connection.scope[_CONTAINER_SCOPE_KEY])
    except KeyError:
        msg = (
            "No modern-di container found in the request scope. "
            "Call setup_di(app, container) so requests pass through the modern-di middleware "
            "before using @inject."
        )
        raise RuntimeError(msg) from None


def inject(func: typing.Callable[..., T]) -> typing.Callable[..., T]:
    markers = integrations.parse_markers(func)
    handler_name = getattr(func, "__qualname__", repr(func))

    def resolve(args: tuple[typing.Any, ...]) -> dict[str, typing.Any]:
        child_container = _fetch_child_container(_find_connection(handler_name, args))
        return integrations.resolve_markers(child_container, markers)

    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:  # noqa: ANN401
            return await func(*args, **kwargs, **resolve(args))

        return typing.cast(typing.Callable[..., T], async_wrapper)

    @functools.wraps(func)
    def wrapper(*args: typing.Any, **kwargs: typing.Any) -> T:  # noqa: ANN401
        return func(*args, **kwargs, **resolve(args))

    return wrapper
