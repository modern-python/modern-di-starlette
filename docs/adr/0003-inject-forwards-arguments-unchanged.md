# `@inject` forwards every argument unchanged and finds the connection by type

**Decision:** the `@inject` wrapper is `async def wrapper(*args, **kwargs)`. It locates the
connection as the first positional argument that is a `Request` or `WebSocket`, resolves the marked
parameters from that connection's child container, and calls the handler with everything it was
given plus the resolved values. There is one decorator for function endpoints and for the methods of
`HTTPEndpoint` / `WebSocketEndpoint`; we will not add a sibling `inject_method`, and we will not try
to reject a method at decoration time.

The v1 wrapper took exactly one argument, the connection. Bound as a method it received `self` and
the connection and failed with `TypeError: takes 1 positional argument but 2 were given` on the first
request, which is a request-time failure with no DI context and nothing in the message that points at
`@inject`. Two alternatives were on the table.

A sibling decorator for methods is rejected because it makes the caller carry a distinction the
wrapper can absorb. Starlette's own dispatch shapes already differ per hook — `on_connect(ws)`,
`on_receive(ws, data)`, `on_disconnect(ws, close_code)` — so a method-specific decorator would still
have to forward trailing arguments, at which point it is the general decorator with a second name.
The Flask and aiogram integrations in this org already wrap with `*args, **kwargs` for the same
reason; this is the org's shape, not a new one.

Failing loudly at decoration time is rejected because it cannot be done reliably. A function defined
in a class body is an ordinary function when the decorator sees it; the only signal that it will be
bound is a first parameter named `self`, which is a convention, not a fact. The reliable check is at
call time, and at call time the passthrough simply works.

Finding the connection by `isinstance` rather than by position is what makes the hook shapes above
fall out for free. Position would have to know whether `self` is present and where the connection
sits among the trailing arguments; type does not. The cost is that a handler which receives no
connection at all fails with a `TypeError` naming the handler, which is the same class of error as
before but now says what is missing.

**Revisit trigger:** Starlette passes a handler something that is a `Request` or `WebSocket` and is
not the connection the child container was opened for, so the first match is the wrong one. Nothing
in Starlette 0.40–1.x does, and a second connection object in one call stack would be a new
Starlette feature before it is a problem here.
