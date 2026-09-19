# The per-connection child container has no public accessor

The child container is reachable only through `@inject` and `FromDI`: the ASGI scope key it lives
under stays private, and there is no `fetch_di_child_container(connection)` beside the root
container's `fetch_di_container(app)`. The middleware deletes its scope entry in a `finally` when
the connection ends, because the container's context holds the connection, the connection owns the
`scope` dict, and the dict held the container: a cycle per request that left finished requests to
the garbage collector. An accessor advertises that entry as something a caller may hold, and a
holder that outlives the connection either revives the cycle or reads a deleted entry, so no
version of it is both safe and useful. Class-based `HTTPEndpoint` and `WebSocketEndpoint` were once
the gap this left, but `@inject` now binds as a method, so that was a missing decorator path rather
than a missing accessor.
