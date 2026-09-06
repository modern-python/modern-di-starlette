# The per-connection child container has no public accessor

**Decision:** the child container is reachable only through `@inject` + `FromDI`. The ASGI scope key
it lives under stays private, and we will not add a `fetch_di_child_container(connection)` (or
equivalent) to the public surface. `fetch_di_container(app)` returns the root container and is
deliberately the only container accessor a user gets.

The obvious counterpart to `fetch_di_container(app)` is a per-connection twin, and it would be two
lines. It was declined at v1 as unneeded, and a later change turned that from a preference into a
constraint. The middleware now deletes its scope entry in a `finally` when the connection ends,
because the container's context holds the connection, the connection owns the ASGI `scope` dict, and
the `scope` dict held the container — a cycle per request, leaving a finished request reclaimable
only by the garbage collector rather than by refcounting. Clearing the entry took that from 34
cyclic objects per request to zero.

A public accessor advertises the entry as a thing callers may hold. The moment one is handed out and
kept — stored on an object, closed over by a background task, read after the response — the entry is
either still present and the cycle is back, or it is gone and the accessor raises. There is no
version of the accessor that is both safe and useful, because the lifetime it exposes is strictly
shorter than the object a caller would want to attach it to. The bound is the point: nothing may
read the entry after the middleware's `async with` block exits.

The one real gap this leaves is class-based `HTTPEndpoint` / `WebSocketEndpoint`, which `@inject`
does not cover. That is a missing decorator path, not a missing accessor, and is tracked as its own
work.

**Revisit trigger:** a use for the child container appears that `@inject` genuinely cannot serve —
not a class-based endpoint, which wants its own injection path, but something outside the
connection's own call stack. At that point the lifetime question above has to be answered first, and
the answer is what the accessor's contract would be.
