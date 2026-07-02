# Dependency resolution

Starlette has no dependency-injection system of its own, so `modern-di-starlette`
uses an inert marker plus a decorator (the decorator path from modern-di's
"Writing an integration" guide).

## FromDI

`FromDI(dependency)` marks an endpoint parameter for injection inside an
`Annotated` hint:

    service: typing.Annotated[Service, FromDI(Deps.service)]

It returns `typing.cast(T, _FromDI(dependency))`: type checkers see the resolved
type `T`, while at runtime it is a frozen `_FromDI` marker the decorator detects.
The argument is a provider (`AbstractProvider`) or a bare type — resolution
handles both (`resolve_provider` vs `resolve`).

## @inject

`inject` wraps an endpoint. At decoration time it reads
`typing.get_type_hints(func, include_extras=True)` and collects the parameters
whose `Annotated` metadata holds a `_FromDI`. Starlette calls an endpoint with
just the connection (`endpoint(request)` / `endpoint(websocket)`) and does not
introspect its signature, so — unlike a CLI integration — no signature rewrite is
needed.

At call time the wrapper:

1. Reads the request's child container from
   `connection.scope[_CONTAINER_SCOPE_KEY]` (put there by `_DIMiddleware`).
2. Resolves each marked parameter.
3. Calls the endpoint with the connection plus the resolved parameters by
   keyword.

The endpoint's first parameter is the connection; every `FromDI` parameter
follows and is filled by keyword. `FromDI` parameters coexist with plain ones.
