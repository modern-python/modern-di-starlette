from modern_di import Container, Scope
from starlette import status
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

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
