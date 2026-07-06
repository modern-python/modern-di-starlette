import contextlib
import typing

import modern_di
from starlette import status
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.testclient import TestClient

import modern_di_starlette
from modern_di_starlette import fetch_di_container
from tests.dependencies import Dependencies


def _plain(request: Request) -> PlainTextResponse:  # noqa: ARG001
    return PlainTextResponse("ok")


def test_lifespan_reopens_container_across_cycles(app: Starlette) -> None:
    app.add_route("/", _plain)
    container = fetch_di_container(app)

    with TestClient(app=app) as client:
        assert client.get("/").status_code == status.HTTP_200_OK
    assert container.closed

    with TestClient(app=app) as client:
        assert client.get("/").status_code == status.HTTP_200_OK


def test_setup_di_composes_with_existing_lifespan() -> None:
    events: list[str] = []

    @contextlib.asynccontextmanager
    async def user_lifespan(app_: Starlette) -> typing.AsyncIterator[dict[str, str]]:
        assert isinstance(app_, Starlette)
        events.append("startup")
        yield {"marker": "from-user-lifespan"}
        events.append("shutdown")

    app = Starlette(lifespan=user_lifespan)
    container = modern_di.Container(groups=[Dependencies], validate=True)
    modern_di_starlette.setup_di(app, container)

    async def read_marker(request: Request) -> JSONResponse:
        return JSONResponse(request.state.marker)

    app.add_route("/", read_marker)

    with TestClient(app=app) as client:
        assert events == ["startup"]
        assert not container.closed
        assert client.get("/").json() == "from-user-lifespan"
    assert events == ["startup", "shutdown"]
    assert container.closed
