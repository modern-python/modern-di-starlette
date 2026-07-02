<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)"  srcset="https://raw.githubusercontent.com/modern-python/.github/main/brand/projects/modern-di-starlette/lockup-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/modern-python/.github/main/brand/projects/modern-di-starlette/lockup-light.svg">
    <img alt="modern-di-starlette" src="https://raw.githubusercontent.com/modern-python/.github/main/brand/projects/modern-di-starlette/lockup.png" width="420">
  </picture>
</p>

[![PyPI version](https://img.shields.io/pypi/v/modern-di-starlette.svg)](https://pypi.org/project/modern-di-starlette/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/modern-di-starlette.svg)](https://pypi.org/project/modern-di-starlette/)
[![Downloads](https://static.pepy.tech/badge/modern-di-starlette/month)](https://pepy.tech/projects/modern-di-starlette)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)](https://github.com/modern-python/modern-di-starlette/actions/workflows/ci.yml)
[![CI](https://github.com/modern-python/modern-di-starlette/actions/workflows/ci.yml/badge.svg)](https://github.com/modern-python/modern-di-starlette/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/modern-python/modern-di-starlette.svg)](https://github.com/modern-python/modern-di-starlette/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/modern-python/modern-di-starlette)](https://github.com/modern-python/modern-di-starlette/stargazers)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)

[Modern-DI](https://github.com/modern-python/modern-di) integration for [Starlette](https://www.starlette.io).

## Installation

```bash
uv add modern-di-starlette      # or: pip install modern-di-starlette
```

## Usage

`setup_di` registers the container, composes the lifespan, and installs middleware that builds a per-connection child container. Decorate an endpoint with `@inject` and mark parameters with `FromDI` to receive resolved dependencies. Starlette has no native DI, so `@inject` is required (there is no `Depends`).

```python
import dataclasses
import typing

from modern_di import Container, Group, Scope, providers
from modern_di_starlette import FromDI, inject, setup_di
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


@dataclasses.dataclass(kw_only=True)
class Settings:
    debug: bool = True


@dataclasses.dataclass(kw_only=True)
class UserService:
    settings: Settings  # auto-injected by type


class Dependencies(Group):
    settings = providers.Factory(scope=Scope.APP, creator=Settings)
    user_service = providers.Factory(scope=Scope.REQUEST, creator=UserService)


@inject
async def homepage(
    request: Request,
    service: typing.Annotated[UserService, FromDI(Dependencies.user_service)],
) -> JSONResponse:
    return JSONResponse({"debug": service.settings.debug})


app = Starlette(routes=[Route("/", homepage)])
container = Container(groups=[Dependencies], validate=True)
setup_di(app, container)
```

## Part of `modern-python`

Built on [`modern-di`](https://github.com/modern-python/modern-di). See the
[docs](https://modern-di.modern-python.org/integrations/) for all integrations.
