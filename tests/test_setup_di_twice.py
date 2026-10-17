import typing

import modern_di
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from modern_di_starlette import FromDI, inject, setup_di
from tests.dependencies import Dependencies, SimpleCreator


@inject
async def read_dep1(
    request: Request,  # noqa: ARG001
    instance: typing.Annotated[SimpleCreator, FromDI(Dependencies.app_factory)],
) -> JSONResponse:
    return JSONResponse(instance.dep1)


def _container(dep1: str) -> modern_di.Container:
    container = modern_di.Container(groups=[Dependencies])
    container.override(Dependencies.app_factory, SimpleCreator(dep1=dep1))
    return container


@pytest.mark.parametrize("started", [False, True], ids=["before-startup", "after-startup"])
def test_last_setup_di_wins(started: bool) -> None:
    app = Starlette(routes=[Route("/", read_dep1)])
    first = _container("first")
    setup_di(app, first)
    if started:
        with TestClient(app=app) as client:
            assert client.get("/").json() == "first"

    second = _container("second")
    setup_di(app, second)

    with TestClient(app=app) as client:
        assert client.get("/").json() == "second"
    assert second.closed
    assert len(app.user_middleware) == 1
