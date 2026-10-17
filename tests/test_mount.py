import typing

import pytest
from modern_di import Container, Group, Scope, providers
from starlette import status
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.testclient import TestClient
from starlette.types import ASGIApp, Receive, Send
from starlette.types import Scope as ASGIScope
from starlette.websockets import WebSocket

from modern_di_starlette import FromDI, inject, setup_di
from modern_di_starlette.main import _CONTAINER_SCOPE_KEY


class Outer(Group):
    value = providers.Factory(scope=Scope.APP, creator=lambda: "outer", bound_type=str)


class Inner(Group):
    value = providers.Factory(scope=Scope.APP, creator=lambda: "inner", bound_type=str)


@inject
async def view(request: Request, value: typing.Annotated[str, FromDI(str)]) -> PlainTextResponse:  # noqa: ARG001
    return PlainTextResponse(value)


@inject
async def websocket_view(websocket: WebSocket, value: typing.Annotated[str, FromDI(str)]) -> None:
    await websocket.accept()
    await websocket.send_text(value)
    await websocket.close()


class _Recorder:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.before: list[Container] = []
        self.after: list[Container] = []

    async def __call__(self, scope: ASGIScope, receive: Receive, send: Send) -> None:
        self.before.append(scope[_CONTAINER_SCOPE_KEY])
        await self.app(scope, receive, send)
        self.after.append(scope[_CONTAINER_SCOPE_KEY])


def _build(*, inner_di: bool) -> tuple[Starlette, _Recorder]:
    inner = Starlette(routes=[Route("/x", view), WebSocketRoute("/ws", websocket_view)])
    if inner_di:
        setup_di(inner, Container(groups=[Inner]))
    recorder = _Recorder(inner)
    outer = Starlette(
        routes=[Route("/x", view), WebSocketRoute("/ws", websocket_view), Mount("/sub", app=recorder)],
    )
    setup_di(outer, Container(groups=[Outer]))
    return outer, recorder


@pytest.mark.parametrize(("path", "expected"), [("/sub/x", "inner"), ("/x", "outer")])
def test_nested_setup_di_resolves_from_innermost_app(path: str, expected: str) -> None:
    outer, _ = _build(inner_di=True)
    with TestClient(outer, raise_server_exceptions=True) as client:
        response = client.get(path)
    assert response.status_code == status.HTTP_200_OK
    assert response.text == expected


@pytest.mark.parametrize(("path", "expected"), [("/sub/ws", "inner"), ("/ws", "outer")])
def test_nested_setup_di_websocket_resolves_from_innermost_app(path: str, expected: str) -> None:
    outer, _ = _build(inner_di=True)
    with TestClient(outer, raise_server_exceptions=True) as client, client.websocket_connect(path) as websocket:
        assert websocket.receive_text() == expected


def test_outer_setup_di_only_serves_mounted_route() -> None:
    outer, _ = _build(inner_di=False)
    with TestClient(outer, raise_server_exceptions=True) as client:
        response = client.get("/sub/x")
    assert response.text == "outer"


def test_nested_setup_di_restores_and_closes_both_child_containers() -> None:
    inner_children: list[Container] = []

    async def capture(request: Request) -> PlainTextResponse:
        inner_children.append(request.scope[_CONTAINER_SCOPE_KEY])
        return PlainTextResponse("ok")

    outer, recorder = _build(inner_di=True)
    inner = typing.cast(Starlette, recorder.app)
    inner.router.routes.append(Route("/capture", capture))
    with TestClient(outer, raise_server_exceptions=True) as client:
        assert client.get("/sub/capture").status_code == status.HTTP_200_OK

    [outer_child] = recorder.before
    [inner_child] = inner_children
    assert inner_child is not outer_child
    assert recorder.after == [outer_child]
    assert outer_child.closed
    assert inner_child.closed
