---
summary: New modern-di integration for Starlette — pure-ASGI middleware for per-connection child containers plus an @inject/FromDI decorator path.
---

# modern-di-starlette — design spec

Date: 2026-07-02
Status: approved design, pre-implementation

## Goal

A new integration library, `modern-di-starlette`, wiring
[`modern-di`](https://github.com/modern-python/modern-di) into
[Starlette](https://www.starlette.io). Built by following the repo's
[Writing an integration](https://modern-di.modern-python.org/integrations/writing-integrations/)
guide, using `modern-di-fastapi` as the closest structural reference.

Its second purpose is to **validate the guide's decorator path** on a real
framework: Starlette has no native dependency injection (FastAPI's `Depends`
is a FastAPI addition, not Starlette's), so injection uses an inert `FromDI`
marker plus an `@inject` decorator.

## Key facts (verified against Starlette docs)

- Starlette has **no DI**. Endpoints are `async def endpoint(request)` /
  `async def endpoint(websocket)`; the router calls them with exactly the
  connection object and does **not** introspect the signature.
- Lifespan: `Starlette(lifespan=...)`, stored as `app.router.lifespan_context`.
  The FastAPI integration's `_compose_lifespan` wrapper transfers verbatim.
- Middleware: **pure ASGI middleware** is recommended over `BaseHTTPMiddleware`
  (which breaks `contextvars` propagation). A pure ASGI middleware is a callable
  `async def __call__(self, scope, receive, send)`; it may construct
  `Request(scope, receive)` / `WebSocket(scope, receive, send)` and shares
  per-request objects with endpoints by writing into the `scope` dict (a
  documented convention).

## Architecture — the decorator path, middleware for lifecycle

Two responsibilities, split:
- **Middleware** owns the per-unit-of-work container lifecycle (build at the
  connection's scope, inject the connection as context, close in `finally`).
- **`@inject` + `FromDI`** own resolution (read the child container from the
  ASGI scope, resolve marked params, pass them to the endpoint).

This is a hybrid: middleware role like `modern-di-faststream`, decorator role
like `modern-di-typer`. It is the first decorator-path integration where
middleware (not the decorator) builds the container.

### Public API (`modern_di_starlette`, re-exported from `__init__` with `__all__`)

- `FromDI(dependency)` — inert `Annotated` marker
- `inject` — decorator resolving `FromDI` params
- `setup_di(app, container) -> Container`
- `fetch_di_container(app) -> Container` — the root container
- `starlette_request_provider`, `starlette_websocket_provider`

Internal: `_FromDI` dataclass, `_DIMiddleware`, `_compose_lifespan`,
`_CONNECTION_PROVIDERS`, `_CONTAINER_SCOPE_KEY`.

### 1. Connection providers

```python
starlette_request_provider   = providers.ContextProvider(scope=Scope.REQUEST, context_type=starlette.requests.Request)
starlette_websocket_provider = providers.ContextProvider(scope=Scope.SESSION, context_type=starlette.websockets.WebSocket)
_CONNECTION_PROVIDERS = (starlette_request_provider, starlette_websocket_provider)
_CONTAINER_SCOPE_KEY = "modern_di_container"   # namespaced key in the ASGI scope dict
```

### 2. `setup_di(app, container)`

```python
app.state.di_container = container
container.providers_registry.add_providers(*_CONNECTION_PROVIDERS)
app.router.lifespan_context = _compose_lifespan(app.router.lifespan_context)
app.add_middleware(_DIMiddleware, container=container)
return container
```

`_compose_lifespan` is the FastAPI wrapper: `async with original(app) as state,
fetch_di_container(app): yield state` — reopens the root container on each
startup so restarts don't raise `ContainerClosedError`.

### 3. `_DIMiddleware` (pure ASGI)

```python
async def __call__(self, scope, receive, send):
    if scope["type"] not in ("http", "websocket"):
        return await self.app(scope, receive, send)
    connection = Request(scope, receive) if scope["type"] == "http" else WebSocket(scope, receive, send)
    context, di_scope = {}, None
    for p in _CONNECTION_PROVIDERS:
        if isinstance(connection, p.context_type):
            context[p.context_type], di_scope = connection, p.scope
            break
    child = self.container.build_child_container(context=context, scope=di_scope)
    scope[_CONTAINER_SCOPE_KEY] = child
    try:
        await self.app(scope, receive, send)
    finally:
        await child.close_async()
```

Dispatch mirrors FastAPI's `build_di_container` (iterate providers, match by
`isinstance`). Non-http/websocket scopes (including `lifespan`) pass straight
through, so the composed lifespan still reaches the router.

### 4. `fetch_di_container(app)` → `app.state.di_container`

### 5. `inject` decorator

Starlette calls `endpoint(connection)` positionally and does not parse the
signature, so — unlike Typer — **no `__signature__` rewrite is needed**. The
wrapper takes the connection, resolves DI params by name, and forwards.

```python
def inject(func):
    di_params = _parse_inject_params(func)  # name -> _FromDI, from Annotated hints
    @functools.wraps(func)
    async def wrapper(connection):           # Request or WebSocket
        child = connection.scope[_CONTAINER_SCOPE_KEY]
        di = {
            name: (child.resolve_provider(m.provider)
                   if isinstance(m.provider, providers.AbstractProvider)
                   else child.resolve(dependency_type=m.provider))
            for name, m in di_params.items()
        }
        return await func(connection, **di)
    return wrapper
```

Contract: the endpoint's first parameter is the connection (Request/WebSocket);
all `FromDI`-marked parameters follow and are filled by keyword.

### 6. `FromDI` + `_FromDI`

Identical to Typer: `FromDI(dependency) -> typing.cast(T, _FromDI(dependency))`,
frozen slotted `_FromDI`, used as `Annotated[T, FromDI(...)]`. Accepts an
`AbstractProvider` or a bare type; resolution dispatches `resolve_provider`
vs `resolve`.

## Scopes & lifecycle

- `Request` → `Scope.REQUEST`; `WebSocket` → `Scope.SESSION` (matches
  FastAPI/Litestar).
- Root container reopens on startup via the composed lifespan (`async with`).
- Async close throughout (`close_async`).

## Out of scope for v1 (YAGNI)

- `action_scope` (a Typer-only convenience).
- Class-based `HTTPEndpoint` / `WebSocketEndpoint` injection — the decorator
  targets function endpoints. (Class-based endpoints could read the child
  container from `request.scope` manually; not a documented v1 feature.)
- A public per-request container accessor — the scope key stays internal.

## Testing (mirror `modern-di-fastapi/tests`)

- `conftest.py` — Starlette app fixture calling `setup_di` with
  `Container(groups=[Dependencies])`; `TestClient` fixture.
- `dependencies.py` — a `Group` with `Factory` providers at APP/SESSION/REQUEST
  scopes, plus providers that read the request (method) and websocket (url) to
  prove context injection.
- `test_routes.py`, `test_websockets.py`, `test_lifespan.py` (incl. a
  second lifespan cycle to prove restart works). 100% coverage gate.

## Repo scaffolding (full parity with `modern-di-fastapi`)

- Package `modern_di_starlette/` + `py.typed`.
- `pyproject.toml`: `name = "modern-di-starlette"`,
  `description = "modern-di integration for Starlette"`,
  `dependencies = ["starlette>=0.40,<1", "modern-di>=2.21.0,<3"]` (confirm the
  Starlette floor against the APIs used — `lifespan_context`, `add_middleware`,
  pure ASGI middleware are all long-stable), standard classifiers +
  `[project.urls]`, `version = "0"`.
- `.github/workflows/{ci,_checks,release,scheduled}.yml` + `scripts/` copied
  and repointed to the new repo.
- `architecture/`: `README.md`, `container-lifecycle.md`,
  `dependency-resolution.md` (middleware + `@inject` + `FromDI`), `glossary.md`.
- `planning/` bundle per the
  [planning-convention](https://github.com/lesnik512/planning-convention);
  this spec seeds the initial change bundle.
- `CLAUDE.md`, `Justfile`, `README.md` (brand banner + badges), `LICENSE` (MIT).

## Repo creation & shipping

- Create `modern-python/modern-di-starlette` (public) via `gh repo create`.
- Scaffold locally at `/Users/kevinsmith/src/pypi/modern-di-starlette`, get CI
  green locally (`just test-ci`, `just lint-ci`), then push.

## Docs in the `modern-di` repo (separate PR)

- `docs/integrations/starlette.md` usage page + `mkdocs.yml` nav entry.

## Follow-up (not part of this work)

The guide's decorator-path section implies the decorator builds the per-call
container (as Typer does). This integration builds it in middleware instead.
Worth a small guide amendment later to record the middleware+decorator hybrid.
