# The container is opened in pure ASGI middleware, not `BaseHTTPMiddleware`

**Decision:** `_DIMiddleware` is a plain ASGI callable, not a `BaseHTTPMiddleware` subclass.
`BaseHTTPMiddleware` is the ergonomic choice, but it runs the downstream app in a separate anyio
task, so `contextvars` set around `call_next` are not visible in the endpoint, and it handles `http`
only, so a `Scope.SESSION` child for a WebSocket would need a second mechanism. The plain callable
costs about fifteen lines of raw-protocol handling and in return has the ASGI `scope` dict in hand,
which is how the child container reaches `@inject` without a `contextvar`. **Revisit trigger:**
Starlette ships a supported middleware base that shares context with the downstream app *and*
covers `websocket` scopes; either half alone leaves this integration writing the raw protocol.
