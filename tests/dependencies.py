import dataclasses

from modern_di import Group, Scope, providers
from starlette.requests import Request
from starlette.websockets import WebSocket


@dataclasses.dataclass(kw_only=True, slots=True)
class SimpleCreator:
    dep1: str


@dataclasses.dataclass(kw_only=True, slots=True)
class DependentCreator:
    dep1: SimpleCreator


def fetch_method_from_request(request: Request) -> str:
    assert isinstance(request, Request)
    return request.method


def fetch_path_from_websocket(websocket: WebSocket) -> str:
    assert isinstance(websocket, WebSocket)
    return websocket.url.path


class Dependencies(Group):
    app_factory = providers.Factory(creator=SimpleCreator, kwargs={"dep1": "original"})
    session_factory = providers.Factory(scope=Scope.SESSION, creator=DependentCreator, bound_type=None)
    request_factory = providers.Factory(scope=Scope.REQUEST, creator=DependentCreator, bound_type=None)
    request_method = providers.Factory(scope=Scope.REQUEST, creator=fetch_method_from_request, bound_type=None)
    websocket_path = providers.Factory(scope=Scope.SESSION, creator=fetch_path_from_websocket, bound_type=None)
