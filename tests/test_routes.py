import typing

import pytest
from starlette import status
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from modern_di_starlette import FromDI, inject
from tests.dependencies import Dependencies, DependentCreator, SimpleCreator


def test_factories_by_type_and_provider(client: TestClient, app: Starlette) -> None:
    @inject
    async def read_root(
        request: Request,  # noqa: ARG001
        app_factory_instance: typing.Annotated[SimpleCreator, FromDI(SimpleCreator)],
        request_factory_instance: typing.Annotated[DependentCreator, FromDI(Dependencies.request_factory)],
    ) -> PlainTextResponse:
        assert isinstance(app_factory_instance, SimpleCreator)
        assert isinstance(request_factory_instance, DependentCreator)
        assert request_factory_instance.dep1 is not app_factory_instance
        return PlainTextResponse("ok")

    app.add_route("/", read_root)
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.text == "ok"


def test_context_provider_reads_request(client: TestClient, app: Starlette) -> None:
    @inject
    async def read_root(
        request: Request,  # noqa: ARG001
        method: typing.Annotated[str, FromDI(Dependencies.request_method)],
    ) -> PlainTextResponse:
        assert method == "GET"
        return PlainTextResponse(method)

    app.add_route("/", read_root)
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.text == "GET"


def test_inject_without_setup_di_raises_clear_error() -> None:
    @inject
    async def read_root(
        request: Request,  # noqa: ARG001
        app_factory_instance: typing.Annotated[SimpleCreator, FromDI(SimpleCreator)],
    ) -> PlainTextResponse:
        return PlainTextResponse(app_factory_instance.dep1)  # pragma: no cover -- RuntimeError precedes this call

    app = Starlette()
    app.add_route("/", read_root)

    with pytest.raises(RuntimeError, match="setup_di"):
        TestClient(app).get("/")
