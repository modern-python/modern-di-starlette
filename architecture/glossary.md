# Glossary

The ubiquitous language of `modern-di-starlette`.

**Root container**:
The application-lifetime `modern_di.Container` passed to `setup_di` and stored on
`app.state.di_container`; opened and closed around the app lifespan.
_Avoid_: app container (in prose), global container.

**Child container**:
The per-connection container built by the middleware — `Scope.REQUEST` for an
HTTP request, `Scope.SESSION` for a WebSocket — and closed when the connection
ends.
_Avoid_: request container (ambiguous across scopes), sub-container.

**Connection provider**:
A `ContextProvider` pairing a Starlette connection type (`Request`, `WebSocket`)
with the scope its child container opens at.

**FromDI marker**:
The inert `Annotated` metadata (`_FromDI`) that flags an endpoint parameter for
resolution by `@inject`.
_Avoid_: Depends (that is FastAPI's mechanism, not Starlette's).
