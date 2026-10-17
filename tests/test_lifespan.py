import collections.abc
import contextlib

import modern_di
from modern_di import Group, Scope, providers
from starlette import status
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Mount
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
    async def user_lifespan(app_: Starlette) -> collections.abc.AsyncGenerator[dict[str, str]]:
        assert isinstance(app_, Starlette)
        events.append("startup")
        yield {"marker": "from-user-lifespan"}
        events.append("shutdown")

    app = Starlette(lifespan=user_lifespan)
    container = modern_di.Container(groups=[Dependencies])
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


def _container(label: str, events: list[str]) -> modern_di.Container:
    def create() -> str:
        events.append(f"{label} created")
        return label

    def finalize(value: str) -> None:
        events.append(f"{value} finalized")

    class Values(Group):
        value = providers.Factory(
            scope=Scope.APP,
            creator=create,
            bound_type=str,
            cache=providers.CacheSettings(finalizer=finalize),
        )

    return modern_di.Container(groups=[Values])


def _resolving_lifespan(
    containers: list[modern_di.Container], events: list[str]
) -> collections.abc.Callable[[Starlette], contextlib.AbstractAsyncContextManager[None]]:
    @contextlib.asynccontextmanager
    async def lifespan(_: Starlette) -> collections.abc.AsyncGenerator[None]:
        events.extend(f"startup sees {container.resolve(str)}" for container in containers)
        yield
        events.extend(f"shutdown sees {container.resolve(str)}" for container in containers)

    return lifespan


def test_user_lifespan_resolves_app_dependencies_before_finalizers_run() -> None:
    events: list[str] = []
    container = _container("root", events)
    app = Starlette(lifespan=_resolving_lifespan([container], events))
    modern_di_starlette.setup_di(app, container)

    with TestClient(app=app):
        pass

    assert events == ["root created", "startup sees root", "shutdown sees root", "root finalized"]
    assert container.closed


def test_mounted_root_closes_after_user_shutdown() -> None:
    events: list[str] = []
    inner_container = _container("inner", events)
    inner = Starlette()
    modern_di_starlette.setup_di(inner, inner_container)
    outer = Starlette(routes=[Mount("/sub", app=inner)], lifespan=_resolving_lifespan([inner_container], events))
    modern_di_starlette.setup_di(outer, _container("outer", events))

    with TestClient(app=outer):
        pass

    assert events == ["inner created", "startup sees inner", "shutdown sees inner", "inner finalized"]
    assert inner_container.closed


def test_lifespan_order_holds_across_two_cycles() -> None:
    events: list[str] = []
    container = _container("root", events)
    app = Starlette(lifespan=_resolving_lifespan([container], events))
    modern_di_starlette.setup_di(app, container)

    for _ in range(2):
        with TestClient(app=app):
            pass

    assert events == ["root created", "startup sees root", "shutdown sees root", "root finalized"] * 2


async def test_manage_lifespan_false_keeps_the_user_owned_root_open_around_user_lifespan() -> None:
    events: list[str] = []
    container = _container("root", events)
    app = Starlette(lifespan=_resolving_lifespan([container], events))
    modern_di_starlette.setup_di(app, container, manage_lifespan=False)

    async with container:
        with TestClient(app=app):
            pass
        assert not container.closed
        assert events == ["root created", "startup sees root", "shutdown sees root"]

    assert events[-1] == "root finalized"
