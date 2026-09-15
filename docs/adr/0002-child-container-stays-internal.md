# The per-connection child container has no public accessor

**Decision:** the child container is reachable only through `@inject` + `FromDI`; the ASGI scope
key it lives under stays private and there is no `fetch_di_child_container(connection)`. The
middleware deletes its scope entry in a `finally` when the connection ends, because the container's
context holds the connection, the connection owns the `scope` dict, and the dict held the container:
a cycle per request that left finished requests to the garbage collector. An accessor advertises the
entry as something a caller may hold, and any holder that outlives the connection either revives the
cycle or reads a deleted entry, so there is no version of it that is both safe and useful. Class-based
`HTTPEndpoint` / `WebSocketEndpoint` were once the gap this left; `@inject` now binds as a method
(modern-python/modern-di-starlette#28), so it was a missing decorator path, not a missing accessor.
**Revisit trigger:** a use for the child container appears outside the connection's own call stack;
the lifetime question above has to be answered first, and the answer is the accessor's contract.
