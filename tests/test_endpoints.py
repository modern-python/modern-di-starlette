import typing

import pytest
from starlette import status
from starlette.applications import Starlette
from starlette.endpoints import HTTPEndpoint, WebSocketEndpoint
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocket

from modern_di_starlette import FromDI, inject
from tests.dependencies import Dependencies, DependentCreator, SimpleCreator


def test_http_endpoint_method_resolves_markers(client: TestClient, app: Starlette) -> None:
    class Endpoint(HTTPEndpoint):
        @inject
        async def get(
            self,
            request: Request,
            app_factory_instance: typing.Annotated[SimpleCreator, FromDI(SimpleCreator)],
            request_factory_instance: typing.Annotated[DependentCreator, FromDI(Dependencies.request_factory)],
            method: typing.Annotated[str, FromDI(Dependencies.request_method)],
        ) -> PlainTextResponse:
            assert isinstance(self, Endpoint)
            assert isinstance(request, Request)
            assert isinstance(app_factory_instance, SimpleCreator)
            assert isinstance(request_factory_instance, DependentCreator)
            assert request_factory_instance.dep1 is not app_factory_instance
            return PlainTextResponse(method)

    app.router.routes.append(Route("/", Endpoint))
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.text == "GET"


def test_websocket_endpoint_hooks_resolve_markers(client: TestClient, app: Starlette) -> None:
    seen: list[str] = []

    class Endpoint(WebSocketEndpoint):
        encoding = "text"

        @inject
        async def on_connect(
            self,
            websocket: WebSocket,
            session_factory_instance: typing.Annotated[DependentCreator, FromDI(Dependencies.session_factory)],
            path: typing.Annotated[str, FromDI(Dependencies.websocket_path)],
        ) -> None:
            assert isinstance(self, Endpoint)
            assert isinstance(session_factory_instance, DependentCreator)
            await websocket.accept()
            await websocket.send_text(path)

        @inject
        async def on_receive(
            self,
            websocket: WebSocket,
            data: str,
            app_factory_instance: typing.Annotated[SimpleCreator, FromDI(SimpleCreator)],
        ) -> None:
            assert isinstance(websocket, WebSocket)
            await websocket.send_text(f"{data}:{app_factory_instance.dep1}")

        @inject
        async def on_disconnect(
            self,
            websocket: WebSocket,
            close_code: int,
            path: typing.Annotated[str, FromDI(Dependencies.websocket_path)],
        ) -> None:
            assert isinstance(websocket, WebSocket)
            seen.append(f"{path}:{close_code}")

    app.router.routes.append(WebSocketRoute("/ws", Endpoint))
    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_text() == "/ws"
        websocket.send_text("ping")
        assert websocket.receive_text() == "ping:original"
    assert seen == [f"/ws:{status.WS_1000_NORMAL_CLOSURE}"]


async def test_inject_without_connection_argument_raises_clear_error() -> None:
    @inject
    async def handler(
        value: str,
        app_factory_instance: typing.Annotated[SimpleCreator, FromDI(SimpleCreator)],
    ) -> str:
        return f"{value}:{app_factory_instance.dep1}"  # pragma: no cover -- TypeError precedes this call

    with pytest.raises(TypeError, match="Request or WebSocket"):
        await handler("value")
