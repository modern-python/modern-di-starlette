# Container lifecycle

`modern-di-starlette` wires a `modern_di.Container` into a Starlette app, opens
and closes it around the app's lifespan, and builds a scoped child container per
HTTP request / WebSocket connection.

## setup_di

`setup_di(app, container)` does four things and returns the container:

1. Stashes the root container on `app.state.di_container` (read back with
   `fetch_di_container(app)`).
2. Registers the connection providers (`starlette_request_provider`,
   `starlette_websocket_provider`) on the container's providers registry.
3. Composes the container's open/close around the app's existing lifespan.
4. Installs `_DIMiddleware`, the pure ASGI middleware that builds the
   per-connection child container.

Call it once, after creating the app and before it starts serving — middleware
cannot be added after startup.

## Composed lifespan

`_compose_lifespan` wraps the app's current `lifespan_context` so the root
container is opened inside it and closed on shutdown:

    async with original(app) as state, fetch_di_container(app):
        yield state

`async with container` reopens the container on each startup and closes it on
shutdown, so a second lifespan cycle (test-client re-entry, reload) works
instead of raising `ContainerClosedError`. The original lifespan stays the outer
context and its yielded state passes straight through.

## Per-connection child container

`_DIMiddleware` is pure ASGI middleware (chosen over `BaseHTTPMiddleware`, which
breaks `contextvars` propagation). For each `http` / `websocket` connection it:

1. Builds the connection object (`Request` / `WebSocket`) from the ASGI scope.
2. Matches it against the connection providers: a `Request` opens a
   `Scope.REQUEST` child; a `WebSocket` opens a `Scope.SESSION` child.
3. Builds the child container with the connection injected as context and
   stashes it in the ASGI `scope` dict under the internal `_CONTAINER_SCOPE_KEY`.
4. Closes the child container (`close_async`) when the connection finishes.

Other scope types (`lifespan`) pass straight through untouched.
