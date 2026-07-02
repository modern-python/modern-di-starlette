import typing

from starlette.applications import Starlette
from starlette.testclient import TestClient
from starlette.websockets import WebSocket

from modern_di_starlette import FromDI, inject
from tests.dependencies import Dependencies, DependentCreator, SimpleCreator


async def test_factories(client: TestClient, app: Starlette) -> None:
    @inject
    async def websocket_endpoint(
        websocket: WebSocket,
        app_factory_instance: typing.Annotated[SimpleCreator, FromDI(SimpleCreator)],
        session_factory_instance: typing.Annotated[DependentCreator, FromDI(Dependencies.session_factory)],
    ) -> None:
        assert isinstance(app_factory_instance, SimpleCreator)
        assert isinstance(session_factory_instance, DependentCreator)
        assert session_factory_instance.dep1 is not app_factory_instance
        await websocket.accept()
        await websocket.send_text("test")
        await websocket.close()

    app.router.add_websocket_route("/ws", websocket_endpoint)
    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_text() == "test"


async def test_context_provider_reads_websocket(client: TestClient, app: Starlette) -> None:
    @inject
    async def websocket_endpoint(
        websocket: WebSocket,
        path: typing.Annotated[str, FromDI(Dependencies.websocket_path)],
    ) -> None:
        assert path == "/ws"
        await websocket.accept()
        await websocket.send_text("test")
        await websocket.close()

    app.router.add_websocket_route("/ws", websocket_endpoint)
    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_text() == "test"
