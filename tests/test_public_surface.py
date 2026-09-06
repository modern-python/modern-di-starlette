import types

import modern_di_starlette


def test_public_surface_is_setup_fetch_inject_fromdi_and_the_two_connection_providers() -> None:
    """INVARIANT: the package exports exactly these six names and no seventh.

    Broken by promoting an internal to a public name, in ``__all__`` or as an unprefixed binding in
    ``__init__`` -- the latter is public whether or not it was meant to be. The names most likely to
    drift in are the ones this package deliberately keeps private: ``_CONTAINER_SCOPE_KEY`` and a
    per-connection container accessor beside it, which ``docs/adr/0002-child-container-stays-internal.md``
    rejects because the entry is deleted when the connection ends. Publishing either turns a
    lifetime that the middleware bounds into one a caller may outlive, and a major release then has
    to keep it working.
    """
    public = sorted(
        name
        for name, value in vars(modern_di_starlette).items()
        if not name.startswith("_") and not isinstance(value, types.ModuleType)
    )

    assert public == [
        "FromDI",
        "fetch_di_container",
        "inject",
        "setup_di",
        "starlette_request_provider",
        "starlette_websocket_provider",
    ]
    assert sorted(modern_di_starlette.__all__) == public
