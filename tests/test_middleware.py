import gc
import sys

from modern_di import Container, Scope
from starlette import status
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient
from starlette.types import Scope as ASGIScope

from modern_di_starlette.main import _CONTAINER_SCOPE_KEY
from tests.dependencies import Dependencies, DependentCreator


def test_middleware_opens_request_scoped_child(client: TestClient, app: Starlette) -> None:
    def endpoint(request: Request) -> PlainTextResponse:
        child = request.scope[_CONTAINER_SCOPE_KEY]
        assert isinstance(child, Container)
        assert child.scope is Scope.REQUEST
        instance = child.resolve_provider(Dependencies.request_factory)
        assert isinstance(instance, DependentCreator)
        return PlainTextResponse("ok")

    app.add_route("/", endpoint)
    assert client.get("/").status_code == status.HTTP_200_OK


def test_finished_request_leaves_no_cyclic_garbage(client: TestClient, app: Starlette) -> None:
    """INVARIANT: a completed connection leaves no reference cycle behind.

    Broken by anything that lets the child container stay reachable from the ASGI scope past the
    middleware's ``async with`` -- skipping the ``del`` on some path, stashing the container on the
    connection or on an object the context holds, or handing the scope entry out for a caller to
    keep. The container's context holds the connection and the connection owns the scope dict, so
    one surviving reference closes ``container -> context -> connection -> scope -> container`` and
    the whole request graph drops out of refcounting into the collector. The test keeps only the
    last scope, so every earlier request is unreachable and fair game. On a GIL build bare Starlette
    produces no cyclic garbage, so the collector must find nothing at all; deleting the entry took it
    from 34 objects per request to zero, and it is the only reason the number is zero.

    The free-threaded build cannot promise zero: ``TestClient`` runs the app on a worker thread, and
    that build defers cross-thread refcount releases to the collector, so bare Starlette alone hands
    it the last response's objects. There the check is that nothing the collector reclaims is ours --
    no container and no scope dict still carrying the entry -- which is what a surviving cycle would
    put in front of it.
    """
    last_scope: list[ASGIScope] = []

    def endpoint(request: Request) -> PlainTextResponse:
        assert isinstance(request.scope[_CONTAINER_SCOPE_KEY], Container)
        last_scope[:] = [request.scope]
        return PlainTextResponse("ok")

    app.add_route("/", endpoint)
    for _ in range(5):  # let one-time allocations settle before measuring
        client.get("/")

    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    gc.set_debug(gc.DEBUG_SAVEALL)
    try:
        requests = 20
        for _ in range(requests):
            assert client.get("/").status_code == status.HTTP_200_OK
        collected = gc.collect()
        reclaimed = list(gc.garbage)
    finally:
        gc.garbage.clear()
        gc.set_debug(0)
        if was_enabled:
            gc.enable()

    ours = [o for o in reclaimed if isinstance(o, Container) or (isinstance(o, dict) and _CONTAINER_SCOPE_KEY in o)]
    assert ours == []
    gil_enabled = getattr(sys, "_is_gil_enabled", lambda: True)()
    assert collected == 0 or not gil_enabled

    # The entry is gone once the request is over — that is what breaks the cycle.
    assert _CONTAINER_SCOPE_KEY not in last_scope[0]
