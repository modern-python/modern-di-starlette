import typing

from modern_di import Container, Group, Scope, providers
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route
from starlette.testclient import TestClient

from modern_di_starlette import FromDI, inject, setup_di


class _Request:
    pass


def _container(label: str, events: list[str]) -> Container:
    def create_value() -> str:
        events.append(f"{label} created")
        return label

    def create_request() -> _Request:
        return _Request()

    class Values(Group):
        value = providers.Factory(
            scope=Scope.APP,
            creator=create_value,
            bound_type=str,
            cache=providers.CacheSettings(finalizer=lambda value: events.append(f"{value} finalized")),
        )
        request = providers.Factory(
            scope=Scope.REQUEST,
            creator=create_request,
            cache=providers.CacheSettings(finalizer=lambda _: events.append(f"{label} request finalized")),
        )

    return Container(groups=[Values])


@inject
async def view(
    request: Request,  # noqa: ARG001
    value: typing.Annotated[str, FromDI(str)],
    per_request: typing.Annotated[_Request, FromDI(_Request)],
) -> PlainTextResponse:
    assert isinstance(per_request, _Request)
    return PlainTextResponse(value)


def _app(routes: list[typing.Any] | None = None) -> Starlette:
    return Starlette(routes=[Route("/x", view), *(routes or [])])


def test_manage_lifespan_false_leaves_the_root_open() -> None:
    events: list[str] = []
    container = _container("root", events)
    app = _app()
    setup_di(app, container, manage_lifespan=False)

    with TestClient(app) as client:
        assert client.get("/x").text == "root"

    assert not container.closed
    assert "root finalized" not in events


def test_manage_lifespan_false_still_closes_the_child_container() -> None:
    events: list[str] = []
    app = _app()
    setup_di(app, _container("root", events), manage_lifespan=False)

    with TestClient(app) as client:
        assert client.get("/x").text == "root"
        assert events.count("root request finalized") == 1


async def test_manage_lifespan_false_lets_the_user_own_the_root() -> None:
    events: list[str] = []
    container = _container("root", events)
    app = _app()
    setup_di(app, container, manage_lifespan=False)

    async with container:
        with TestClient(app) as client:
            assert client.get("/x").text == "root"
        assert "root finalized" not in events

    assert events.count("root finalized") == 1


def test_mounted_app_with_manage_lifespan_false_keeps_its_root_open() -> None:
    events: list[str] = []
    inner_container = _container("inner", events)
    inner = _app()
    setup_di(inner, inner_container, manage_lifespan=False)
    outer = _app([Mount("/sub", app=inner)])
    outer_container = _container("outer", events)
    setup_di(outer, outer_container)

    with TestClient(outer) as client:
        assert client.get("/sub/x").text == "inner"

    assert not inner_container.closed
    assert "inner finalized" not in events
    assert outer_container.closed


def test_outer_manage_lifespan_false_still_closes_mounted_roots() -> None:
    events: list[str] = []
    inner_container = _container("inner", events)
    inner = _app()
    setup_di(inner, inner_container)
    outer_container = _container("outer", events)
    outer = _app([Mount("/sub", app=inner)])
    setup_di(outer, outer_container, manage_lifespan=False)

    with TestClient(outer) as client:
        assert client.get("/sub/x").text == "inner"
        assert client.get("/x").text == "outer"

    assert inner_container.closed
    assert "inner finalized" in events
    assert not outer_container.closed
    assert "outer finalized" not in events
