# modern-di-starlette

A [`modern-di`](https://github.com/modern-python/modern-di) integration for
[Starlette](https://www.starlette.io): ASGI middleware opens a scoped child container per
connection, and an `@inject` decorator resolves the parameters an endpoint marks with `FromDI`.

## Language

A term is listed only when there is a synonym to reject, or a meaning subtle enough that code and
docs must agree on it. General programming vocabulary does not belong here, however heavily this
package uses it.

The domain terms are `modern-di`'s — `Container`, `Provider`, `Group`, `Scope`, `Resolution`,
`Override`, `Connection`. That project's `CONTEXT.md` is the authority for all of them; nothing here
redefines one. Starlette owns `Request`, `WebSocket`, `lifespan`, `middleware` and the ASGI `scope`
dict. The three below are this package's own.

**Root container**:
The application-lifetime container handed to `setup_di` and stored on `app.state.di_container`.
Every sentence in this repo that says "container" without qualifying it is wrong: there are always
two, and this is the one a user constructs.

**Child container**:
The container the middleware opens for one connection and closes when it ends. Which scope it opens
at is this package's decision, not modern-di's: `Scope.REQUEST` for HTTP, `Scope.SESSION` for a
WebSocket. Naming it for a single scope hides that.

**Connection provider**:
A `ContextProvider` pairing a Starlette connection type with the scope its child container opens
at. `_CONNECTION_PROVIDERS` is the single source of that pairing — the middleware's dispatch table
and the set `setup_di` registers are the same tuple, so a new connection kind is one entry, not two.

**FromDI**:
The inert `Annotated` metadata marking an endpoint parameter for resolution by `@inject`.
_Avoid_: `Depends` — Starlette has none, and a reader arriving from FastAPI will assume otherwise;
say so rather than borrowing the word.
