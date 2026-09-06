# The container is opened in pure ASGI middleware, not `BaseHTTPMiddleware`

**Decision:** `_DIMiddleware` is a plain ASGI callable
(`async def __call__(self, scope, receive, send)`). We will not implement it as a Starlette
`BaseHTTPMiddleware` subclass.

`BaseHTTPMiddleware` is the ergonomic choice and the one Starlette's own tutorial reaches for
first: it hands you a `Request` and a `call_next`, and the child container would open and close
around a single `await call_next(request)`. It is rejected because it runs the downstream app in a
separate anyio task. `contextvars` set on one side of that boundary are not visible on the other,
and a DI container whose scope does not survive into the endpoint is not a DI container. Starlette's
own middleware documentation carries the warning; this is not a subtlety we discovered.

Two further consequences follow from the plain-callable form, and both are load-bearing rather than
incidental. WebSockets are reachable at all: `BaseHTTPMiddleware` handles `http` only, so a
`Scope.SESSION` child container for a WebSocket connection would need a second, differently shaped
mechanism. And the ASGI `scope` dict is in hand, which is how the child container reaches `@inject`
without a `contextvar` in the first place.

The cost is that the middleware is written against the raw ASGI three-argument protocol and must
construct its own `Request` / `WebSocket`, pass non-connection scope types (`lifespan`) straight
through, and close the child container on the exception path itself. That is roughly fifteen lines,
paid once.

**Revisit trigger:** Starlette makes `BaseHTTPMiddleware` share a context with the downstream app —
or ships a supported middleware base that does — *and* it covers `websocket` scopes. Both halves
have to land: either one alone leaves this integration writing the raw protocol anyway.
