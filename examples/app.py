# Minimal modern-di + starlette example.
# Run for real: uvicorn examples.app:app
import dataclasses
import typing

from modern_di import Container, Group, Scope, providers
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from modern_di_starlette import FromDI, inject, setup_di


@dataclasses.dataclass(kw_only=True)
class Settings:
    greeting: str = "Hello"


@dataclasses.dataclass(kw_only=True)
class GreetingService:
    settings: Settings  # auto-injected by type

    def greet(self, name: str) -> str:
        return f"{self.settings.greeting}, {name}!"


class Dependencies(Group):
    settings = providers.Factory(scope=Scope.APP, creator=Settings)
    service = providers.Factory(scope=Scope.REQUEST, creator=GreetingService)


@inject
async def greet(
    request: Request,
    service: typing.Annotated[GreetingService, FromDI(Dependencies.service)],
) -> JSONResponse:
    name = request.path_params["name"]
    return JSONResponse({"greeting": service.greet(name)})


app = Starlette(routes=[Route("/greet/{name}", greet)])
container = Container(groups=[Dependencies])
setup_di(app, container)
container.validate()  # optional fail-fast; must come after setup_di registers its providers
