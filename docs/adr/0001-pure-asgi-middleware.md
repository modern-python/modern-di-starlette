# The container is opened in pure ASGI middleware, not `BaseHTTPMiddleware`

`_DIMiddleware` is a plain ASGI callable rather than a `BaseHTTPMiddleware` subclass.
`BaseHTTPMiddleware` is the ergonomic choice, but it runs the downstream app in a separate anyio
task, so `contextvars` set around `call_next` are not visible in the endpoint, and it handles
`http` scopes only, so the `Scope.SESSION` child a WebSocket needs would take a second mechanism.
The plain callable costs about fifteen lines of raw-protocol handling and in return holds the ASGI
`scope` dict, which is how the child container reaches `@inject` without a `contextvar`. That trade
only flips if Starlette ships a supported middleware base that both shares context with the
downstream app and covers `websocket` scopes; either half alone leaves this integration writing the
raw protocol anyway.
