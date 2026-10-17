import asyncio
import inspect
import typing

import pytest
from starlette import status
from starlette.applications import Starlette
from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from modern_di_starlette import FromDI, inject
from tests.dependencies import Dependencies, DependentCreator, SimpleCreator


def _on_event_loop() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


def test_sync_function_endpoint_resolves_markers_in_threadpool(client: TestClient, app: Starlette) -> None:
    seen: list[bool] = []

    @inject
    def read_root(
        request: Request,  # noqa: ARG001
        app_factory_instance: typing.Annotated[SimpleCreator, FromDI(SimpleCreator)],
        method: typing.Annotated[str, FromDI(Dependencies.request_method)],
    ) -> PlainTextResponse:
        seen.append(_on_event_loop())
        return PlainTextResponse(f"{method}:{app_factory_instance.dep1}")

    app.add_route("/", read_root)
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.text == "GET:original"
    assert seen == [False]


def test_sync_http_endpoint_method_resolves_markers_in_threadpool(client: TestClient, app: Starlette) -> None:
    seen: list[bool] = []

    class Endpoint(HTTPEndpoint):
        @inject
        def get(
            self,
            request: Request,
            request_factory_instance: typing.Annotated[DependentCreator, FromDI(Dependencies.request_factory)],
            method: typing.Annotated[str, FromDI(Dependencies.request_method)],
        ) -> PlainTextResponse:
            assert isinstance(self, Endpoint)
            assert isinstance(request, Request)
            assert isinstance(request_factory_instance, DependentCreator)
            seen.append(_on_event_loop())
            return PlainTextResponse(method)

    app.router.routes.append(Route("/", Endpoint))
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.text == "GET"
    assert seen == [False]


def test_async_endpoint_runs_on_event_loop(client: TestClient, app: Starlette) -> None:
    seen: list[bool] = []

    @inject
    async def read_root(
        request: Request,  # noqa: ARG001
        method: typing.Annotated[str, FromDI(Dependencies.request_method)],
    ) -> PlainTextResponse:
        seen.append(_on_event_loop())
        return PlainTextResponse(method)

    app.add_route("/", read_root)
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.text == "GET"
    assert seen == [True]


def test_inject_keeps_sync_and_async_kinds() -> None:
    def sync_handler(request: Request) -> None: ...

    async def async_handler(request: Request) -> None: ...

    assert not inspect.iscoroutinefunction(inject(sync_handler))
    assert inspect.iscoroutinefunction(inject(async_handler))


def test_sync_inject_without_connection_argument_raises_clear_error() -> None:
    @inject
    def handler(
        value: str,
        app_factory_instance: typing.Annotated[SimpleCreator, FromDI(SimpleCreator)],
    ) -> str:
        return f"{value}:{app_factory_instance.dep1}"  # pragma: no cover -- TypeError precedes this call

    with pytest.raises(TypeError, match="Request or WebSocket"):
        handler("value")


def test_sync_inject_without_setup_di_raises_clear_error() -> None:
    @inject
    def read_root(
        request: Request,  # noqa: ARG001
        app_factory_instance: typing.Annotated[SimpleCreator, FromDI(SimpleCreator)],
    ) -> PlainTextResponse:
        return PlainTextResponse(app_factory_instance.dep1)  # pragma: no cover -- RuntimeError precedes this call

    app = Starlette()
    app.add_route("/", read_root)

    with pytest.raises(RuntimeError, match="setup_di"):
        TestClient(app).get("/")
