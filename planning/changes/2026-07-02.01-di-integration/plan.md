# modern-di-starlette Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `modern-di-starlette`, a zero-extra-dependency modern-di integration for Starlette, wired via pure-ASGI middleware (per-connection child-container lifecycle) plus an `@inject`/`FromDI` decorator (resolution), at full repo parity with `modern-di-fastapi`.

**Architecture:** Starlette has no native DI, so this is the guide's decorator path. `setup_di` attaches the root container, registers connection providers, composes the app lifespan, and installs `_DIMiddleware`. The middleware builds a `Scope.REQUEST` (HTTP) / `Scope.SESSION` (WebSocket) child container per connection and stashes it in the ASGI `scope` dict; `@inject` reads it back and resolves `FromDI`-marked endpoint params.

**Tech Stack:** Python ≥3.10, Starlette 1.x, modern-di ≥2.21, uv (build + deps), just, pytest + pytest-asyncio + pytest-cov, httpx2 (Starlette TestClient), ruff, ty, eof-fixer.

**Reference repo (read, do not modify):** `/Users/kevinsmith/src/pypi/modern-di-fastapi` — closest sibling; copy its scaffolding.

**Design spec:** `scratchpad/2026-07-02-modern-di-starlette-design.md` (this session).

**Target local dir:** `/Users/kevinsmith/src/pypi/modern-di-starlette`
**Target GitHub repo:** `modern-python/modern-di-starlette` (public).

## Global Constraints

- Line length 120. Ruff `select = ["ALL"]` with the exact ignores copied from the reference `pyproject.toml`. Type-check with `ty`; suppress with `# ty: ignore[<rule>]`, never `# type: ignore`.
- All imports at module level. Annotate every function argument.
- Resolution is sync-only. No runtime dependency beyond `starlette` and `modern-di`.
- `requires-python = ">=3.10,<4"`. Dependencies: `starlette>=0.40,<1`, `modern-di>=2.21.0,<3`. Dev dep for the test client is `httpx2` (Starlette 1.x `TestClient` does `import httpx2 as httpx`).
- The 100% line-coverage gate is `just test-ci`; run it only at the end of Task 3 and after. Intermediate tasks use `just test <paths>` (no gate). `just lint-ci` must stay green after every task (it also validates the planning bundle).
- Public API, re-exported from `__init__.py` with an explicit `__all__`: `FromDI`, `inject`, `setup_di`, `fetch_di_container`, `starlette_request_provider`, `starlette_websocket_provider`.
- Shipping: Task 1 lands the scaffold on `main` and creates+pushes the repo (greenfield bootstrap). Tasks 2–4 go on branch `feat/di-integration` → PR → merge → sync. Task 6 is a separate PR in the `modern-di` repo. (If the user prefers the scaffold also go through a PR, split accordingly — flag at handoff.)

---

### Task 1: Scaffold the repo, tooling, CI, and planning bundle

**Files:**
- Create dir: `/Users/kevinsmith/src/pypi/modern-di-starlette`
- Create: `pyproject.toml`, `Justfile`, `.gitignore`, `LICENSE`, `README.md`, `CLAUDE.md`
- Create: `modern_di_starlette/py.typed` (empty), `modern_di_starlette/__init__.py`, `modern_di_starlette/main.py`
- Create: `tests/__init__.py` (empty), `tests/test_import.py`
- Create: `.github/workflows/{ci,_checks,release,scheduled}.yml`, `.github/scripts/report-scheduled-failure.sh`
- Create: `architecture/README.md` (+ capability files land in Task 4)
- Create: `planning/` — copy convention scaffolding + the initial bundle `planning/changes/2026-07-02.01-di-integration/{design.md,plan.md}`

**Interfaces:**
- Produces: an installable, lint-clean, CI-ready repo skeleton. `modern_di_starlette` imports cleanly with an empty public surface (filled in Tasks 2–3).

- [ ] **Step 1: Create the directory and copy verbatim scaffolding**

```bash
cd /Users/kevinsmith/src/pypi
mkdir -p modern-di-starlette/modern_di_starlette modern-di-starlette/tests \
         modern-di-starlette/.github/workflows modern-di-starlette/.github/scripts \
         modern-di-starlette/architecture \
         modern-di-starlette/planning/_templates \
         modern-di-starlette/planning/changes/2026-07-02.01-di-integration \
         modern-di-starlette/planning/decisions modern-di-starlette/planning/releases
cd modern-di-starlette
R=../modern-di-fastapi
# Verbatim copies (no repo-specific strings):
cp $R/Justfile Justfile
cp $R/.gitignore .gitignore
cp $R/LICENSE LICENSE
cp $R/.github/workflows/ci.yml .github/workflows/ci.yml
cp $R/.github/workflows/_checks.yml .github/workflows/_checks.yml
cp $R/.github/workflows/scheduled.yml .github/workflows/scheduled.yml
cp $R/.github/scripts/report-scheduled-failure.sh .github/scripts/report-scheduled-failure.sh
cp $R/planning/index.py planning/index.py
cp $R/planning/.convention-version planning/.convention-version
cp $R/planning/deferred.md planning/deferred.md
cp $R/planning/_templates/*.md planning/_templates/
touch modern_di_starlette/py.typed
touch tests/__init__.py
touch planning/decisions/.gitkeep planning/releases/.gitkeep
chmod +x .github/scripts/report-scheduled-failure.sh
```

- [ ] **Step 2: Copy `release.yml`, substituting the project name in comments**

```bash
cd /Users/kevinsmith/src/pypi/modern-di-starlette
sed 's/modern-di-fastapi/modern-di-starlette/g' ../modern-di-fastapi/.github/workflows/release.yml > .github/workflows/release.yml
```

  (Only comments name the project; the workflow logic is repo-agnostic and derives the version from `$GITHUB_REF_NAME`.)

- [ ] **Step 3: Copy `planning/README.md` and `CLAUDE.md`, substituting the project name**

```bash
cd /Users/kevinsmith/src/pypi/modern-di-starlette
sed 's/modern-di-fastapi/modern-di-starlette/g' ../modern-di-fastapi/planning/README.md > planning/README.md
```

  Write `CLAUDE.md` (adapted from the reference — same structure, Starlette wording and Starlette-specific capability names):

```markdown
# CLAUDE.md

Guidance for agents working in `modern-di-starlette` — the
[modern-di](https://modern-di.modern-python.org) integration for Starlette.

## Workflow

Before making a change, follow the **Quick path** in
[`planning/README.md`](planning/README.md) — the authoritative planning
convention. Pick a lane (Full / Lightweight / Tiny), create the change bundle
under `planning/changes/` when the lane calls for one, and run
`just check-planning` before pushing.

## Architecture

[`architecture/`](architecture/) holds the living truth about what the system
does **now** — one file per capability, plus `glossary.md`. **When a change
alters a capability's behavior, update the matching
`architecture/<capability>.md` in the same PR**, alongside the code; the *why*
stays in the change bundle under `planning/changes/`.

- `container-lifecycle.md` — `setup_di`, the composed lifespan, and the
  per-connection child container built by `_DIMiddleware` (pure ASGI).
- `dependency-resolution.md` — `FromDI` + the `@inject` decorator.

## Build & checks

- `just lint` / `just lint-ci` — format, ruff, `ty`; `lint-ci` also runs
  `check-planning`.
- `just test` — pytest (100% coverage required via `just test-ci`).
- `just index` — print the generated planning index.
```

- [ ] **Step 4: Write `pyproject.toml`**

```toml
[project]
name = "modern-di-starlette"
description = "modern-di integration for Starlette"
authors = [{ name = "Artur Shiriev", email = "me@shiriev.ru" }]
requires-python = ">=3.10,<4"
license = "MIT"
readme = "README.md"
keywords = ["dependency-injection", "di", "ioc-container", "modern-di", "starlette", "python"]
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Typing :: Typed",
    "Topic :: Software Development :: Libraries",
]
dependencies = ["starlette>=0.40,<1", "modern-di>=2.21.0,<3"]
version = "0"

[project.urls]
Homepage = "https://modern-di.modern-python.org"
Documentation = "https://modern-di.modern-python.org"
Repository = "https://github.com/modern-python/modern-di-starlette"
Issues = "https://github.com/modern-python/modern-di-starlette/issues"
Changelog = "https://github.com/modern-python/modern-di-starlette/releases"

[dependency-groups]
dev = [
    "pytest",
    "pytest-cov",
    "pytest-asyncio",
    "httpx2",
]
lint = [
    "ty",
    "ruff",
    "eof-fixer",
    "typing-extensions",
]

[build-system]
requires = ["uv_build>=0.11,<1.0"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "modern_di_starlette"
module-root = ""


[tool.ruff]
fix = false
unsafe-fixes = true
line-length = 120
target-version = "py310"

[tool.ruff.format]
docstring-code-format = true

[tool.ruff.lint]
select = ["ALL"]
ignore = [
    "D1", # allow missing docstrings
    "S101", # allow asserts
    "TCH", # ignore flake8-type-checking
    "FBT", # allow boolean args
    "D203", # "one-blank-line-before-class" conflicting with D211
    "D213", # "multi-line-summary-second-line" conflicting with D212
    "COM812", # flake8-commas "Trailing comma missing"
    "ISC001", # flake8-implicit-str-concat
    "G004", # allow f-strings in logging
]
isort.lines-after-imports = 2
isort.no-lines-before = ["standard-library", "local-folder"]

[tool.pytest.ini_options]
addopts = ""
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"

[tool.coverage.report]
exclude_also = [
    "if typing.TYPE_CHECKING:",
]
```

- [ ] **Step 5: Write the package skeleton (empty public surface)**

  `modern_di_starlette/main.py`:

```python
"""modern-di integration for Starlette."""
```

  `modern_di_starlette/__init__.py`:

```python
__all__: list[str] = []
```

- [ ] **Step 6: Write `README.md`**

```markdown
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
```

- [ ] **Step 7: Write the initial planning bundle**

  Copy the approved design spec into `planning/changes/2026-07-02.01-di-integration/design.md` — prepend the required frontmatter, keep the body:

```bash
cd /Users/kevinsmith/src/pypi/modern-di-starlette
{
  printf -- '---\nsummary: New modern-di integration for Starlette — pure-ASGI middleware for per-connection child containers plus an @inject/FromDI decorator path.\n---\n\n';
  cat "$SCRATCH/2026-07-02-modern-di-starlette-design.md";
} > planning/changes/2026-07-02.01-di-integration/design.md
```

  (`$SCRATCH` = this session's scratchpad dir. Then copy this plan file to `planning/changes/2026-07-02.01-di-integration/plan.md`.)

```bash
cp "$SCRATCH/2026-07-02-modern-di-starlette-plan.md" planning/changes/2026-07-02.01-di-integration/plan.md
```

- [ ] **Step 8: Write `architecture/README.md`**

```markdown
# Architecture

The living truth about what `modern-di-starlette` does **now**. One file per
capability, plus a single [`glossary.md`](glossary.md) (the ubiquitous
language) — living prose, no frontmatter, dated by git.

**Promotion rule:** when a change alters a capability's behavior, the
implementing PR hand-edits the matching `architecture/<capability>.md` in the
same diff, alongside the code. That hand-edit is what keeps this directory true;
the *why* lives in the change bundle under [`planning/changes/`](../planning/changes/).

Capability files and `glossary.md` are authored lazily — each appears when the
first capability or term is worth pinning down.

## Capabilities

- [`container-lifecycle.md`](container-lifecycle.md) — wiring the container into
  the app, the composed lifespan, and the per-connection scoped child container
  built by the ASGI middleware.
- [`dependency-resolution.md`](dependency-resolution.md) — `FromDI` + the
  `@inject` decorator, and how endpoints declare and receive resolved
  dependencies.
- [`glossary.md`](glossary.md) — the ubiquitous language.
```

- [ ] **Step 9: Install, lint, and run the import test**

  Write `tests/test_import.py`:

```python
def test_public_surface_importable() -> None:
    import modern_di_starlette

    assert modern_di_starlette.__all__ == []
```

  Run:

```bash
cd /Users/kevinsmith/src/pypi/modern-di-starlette
just install
just lint-ci
just test
```

  Expected: `just install` syncs; `just lint-ci` prints `planning: OK` and passes ruff/ty/eof-fixer; `just test` collects and passes `test_import.py`.

- [ ] **Step 10: Init git, commit, create the GitHub repo, push**

```bash
cd /Users/kevinsmith/src/pypi/modern-di-starlette
git init -b main
git add -A
git commit -m "chore: scaffold modern-di-starlette repo (tooling, CI, planning)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
gh repo create modern-python/modern-di-starlette --public \
  --description "modern-di integration for Starlette" --source . --remote origin --push
```

  Expected: repo created, `main` pushed, CI (`main` workflow) starts. Verify with `gh run watch` or `gh pr checks` after later pushes.

---

### Task 2: Container lifecycle — providers, `setup_di`, composed lifespan, middleware

**Files:**
- Modify: `modern_di_starlette/main.py`
- Modify: `modern_di_starlette/__init__.py`
- Create: `tests/conftest.py`, `tests/dependencies.py`, `tests/test_lifespan.py`, `tests/test_middleware.py`

**Interfaces:**
- Produces:
  - `starlette_request_provider: providers.ContextProvider` (scope `REQUEST`, `context_type=Request`)
  - `starlette_websocket_provider: providers.ContextProvider` (scope `SESSION`, `context_type=WebSocket`)
  - `setup_di(app: Starlette, container: Container) -> Container`
  - `fetch_di_container(app: Starlette) -> Container`
  - internal `_DIMiddleware`, `_compose_lifespan`, `_CONNECTION_PROVIDERS`, `_CONTAINER_SCOPE_KEY = "modern_di_container"` (the ASGI-scope key holding the per-connection child container)
- Consumes: nothing from other tasks.

- [ ] **Step 1: Do this on a feature branch**

```bash
cd /Users/kevinsmith/src/pypi/modern-di-starlette
git checkout -b feat/di-integration
```

- [ ] **Step 2: Write `tests/dependencies.py`**

```python
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
```

- [ ] **Step 3: Write `tests/conftest.py`**

```python
import typing

import modern_di
import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

import modern_di_starlette
from tests.dependencies import Dependencies


@pytest.fixture
def app() -> Starlette:
    app_ = Starlette()
    container = modern_di.Container(groups=[Dependencies])
    modern_di_starlette.setup_di(app_, container=container)
    return app_


@pytest.fixture
def client(app: Starlette) -> typing.Iterator[TestClient]:
    with TestClient(app=app) as test_client:
        yield test_client
```

- [ ] **Step 4: Write the failing lifecycle + middleware tests**

  `tests/test_lifespan.py`:

```python
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
```

  `tests/test_middleware.py` (proves the middleware builds a scoped child container and exposes it in the ASGI scope):

```python
from starlette import status
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from modern_di import Container, Scope
from modern_di_starlette.main import _CONTAINER_SCOPE_KEY
from tests.dependencies import Dependencies, DependentCreator


def test_middleware_opens_request_scoped_child(client: TestClient, app: Starlette) -> None:
    def endpoint(request: Request) -> PlainTextResponse:
        child = request.scope[_CONTAINER_SCOPE_KEY]
        assert isinstance(child, Container)
        assert child.scope is Scope.REQUEST
        instance = child.resolve_provider(Dependencies.request_factory)
        assert isinstance(instance, DependentCreator)
        return PlainTextResponse("ok")

    app.add_route("/", endpoint)
    assert client.get("/").status_code == status.HTTP_200_OK
```

- [ ] **Step 5: Run the tests to verify they fail**

```bash
just test tests/test_lifespan.py tests/test_middleware.py
```

Expected: FAIL (`AttributeError`/`ImportError` — `setup_di`, `fetch_di_container`, `_CONTAINER_SCOPE_KEY` not defined).

- [ ] **Step 6: Implement the lifecycle half in `main.py`**

```python
"""modern-di integration for Starlette."""

import contextlib
import typing

from modern_di import Container, Scope, providers
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.types import ASGIApp, Lifespan, Receive
from starlette.types import Scope as ASGIScope
from starlette.types import Send
from starlette.websockets import WebSocket


starlette_request_provider = providers.ContextProvider(scope=Scope.REQUEST, context_type=Request)
starlette_websocket_provider = providers.ContextProvider(scope=Scope.SESSION, context_type=WebSocket)

# Single source of the connection-kind mapping: each provider pairs a Starlette
# connection type with the scope its child container opens at. The middleware
# dispatches off this tuple; add a connection kind by adding its provider here.
_CONNECTION_PROVIDERS = (starlette_request_provider, starlette_websocket_provider)

# Key under which the per-connection child container lives in the ASGI scope dict.
# `_DIMiddleware` writes it; `inject` (Task 3) reads it back.
_CONTAINER_SCOPE_KEY = "modern_di_container"


def fetch_di_container(app: Starlette) -> Container:
    return typing.cast(Container, app.state.di_container)


def _compose_lifespan(original: Lifespan[Starlette]) -> Lifespan[Starlette]:
    """Wrap ``original`` so the root container opens/closes around it.

    ``async with`` reopens the container on each startup and closes it on
    shutdown, so a second lifespan cycle against the same container works
    instead of raising ``ContainerClosedError``. The original lifespan stays
    the outer context and its yielded state passes straight through.
    """

    @contextlib.asynccontextmanager
    async def composed(app: Starlette) -> typing.AsyncIterator[typing.Mapping[str, typing.Any] | None]:
        async with original(app) as state, fetch_di_container(app):
            yield state

    return typing.cast(Lifespan[Starlette], composed)


class _DIMiddleware:
    def __init__(self, app: ASGIApp, container: Container) -> None:
        self.app = app
        self.container = container

    async def __call__(self, scope: ASGIScope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        connection: Request | WebSocket = (
            Request(scope, receive) if scope["type"] == "http" else WebSocket(scope, receive, send)
        )
        context: dict[type[typing.Any], typing.Any] = {}
        connection_scope: Scope | None = None
        for provider in _CONNECTION_PROVIDERS:
            if isinstance(connection, provider.context_type):
                context[provider.context_type] = connection
                connection_scope = provider.scope
                break

        child_container = self.container.build_child_container(context=context, scope=connection_scope)
        scope[_CONTAINER_SCOPE_KEY] = child_container
        try:
            await self.app(scope, receive, send)
        finally:
            await child_container.close_async()


def setup_di(app: Starlette, container: Container) -> Container:
    app.state.di_container = container
    container.providers_registry.add_providers(*_CONNECTION_PROVIDERS)
    app.router.lifespan_context = _compose_lifespan(app.router.lifespan_context)
    app.add_middleware(_DIMiddleware, container=container)
    return container
```

  Note: if `ty` flags `app.add_middleware(_DIMiddleware, container=container)` (ParamSpec forwarding), append `# ty: ignore[invalid-argument-type]` on that line, mirroring `modern-di-faststream`. Only add the suppression if `just lint-ci` actually reports it.

- [ ] **Step 7: Update `__init__.py` to export the lifecycle surface**

```python
from modern_di_starlette.main import (
    fetch_di_container,
    setup_di,
    starlette_request_provider,
    starlette_websocket_provider,
)


__all__ = [
    "fetch_di_container",
    "setup_di",
    "starlette_request_provider",
    "starlette_websocket_provider",
]
```

  Delete `tests/test_import.py` (its `__all__ == []` assertion is now obsolete):

```bash
git rm tests/test_import.py
```

- [ ] **Step 8: Run the tests to verify they pass**

```bash
just test tests/test_lifespan.py tests/test_middleware.py
```

Expected: PASS. Then `just lint-ci` — clean.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: container lifecycle — setup_di, composed lifespan, ASGI middleware

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Resolution — `FromDI` marker and the `@inject` decorator

**Files:**
- Modify: `modern_di_starlette/main.py`
- Modify: `modern_di_starlette/__init__.py`
- Create: `tests/test_routes.py`, `tests/test_websockets.py`

**Interfaces:**
- Consumes: `_CONTAINER_SCOPE_KEY`, `_DIMiddleware` (Task 2).
- Produces:
  - `FromDI(dependency: providers.AbstractProvider[T_co] | type[T_co]) -> T_co` — inert `Annotated` marker.
  - `inject(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]` — endpoint decorator.
  - internal `_FromDI`, `_parse_inject_params`, `_resolve_di_params`.

- [ ] **Step 1: Write the failing resolution tests**

  `tests/test_routes.py`:

```python
import typing

from starlette import status
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from modern_di_starlette import FromDI, inject
from tests.dependencies import Dependencies, DependentCreator, SimpleCreator


def test_factories_by_type_and_provider(client: TestClient, app: Starlette) -> None:
    @inject
    async def read_root(
        request: Request,
        app_factory_instance: typing.Annotated[SimpleCreator, FromDI(SimpleCreator)],
        request_factory_instance: typing.Annotated[DependentCreator, FromDI(Dependencies.request_factory)],
    ) -> PlainTextResponse:
        assert isinstance(app_factory_instance, SimpleCreator)
        assert isinstance(request_factory_instance, DependentCreator)
        assert request_factory_instance.dep1 is not app_factory_instance
        return PlainTextResponse("ok")

    app.add_route("/", read_root)
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.text == "ok"


def test_context_provider_reads_request(client: TestClient, app: Starlette) -> None:
    @inject
    async def read_root(
        request: Request,
        method: typing.Annotated[str, FromDI(Dependencies.request_method)],
    ) -> PlainTextResponse:
        assert method == "GET"
        return PlainTextResponse(method)

    app.add_route("/", read_root)
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.text == "GET"
```

  `tests/test_websockets.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
just test tests/test_routes.py tests/test_websockets.py
```

Expected: FAIL (`ImportError` — `FromDI`, `inject` not exported).

- [ ] **Step 3: Add resolution to `main.py`**

  Add imports at the top (module level, merged with the existing import block):

```python
import dataclasses
import functools
```

  Add near the top after the `TypeVar`s (introduce them if not present):

```python
T_co = typing.TypeVar("T_co", covariant=True)
T = typing.TypeVar("T")
```

  Append the resolution code:

```python
@dataclasses.dataclass(slots=True, frozen=True)
class _FromDI(typing.Generic[T_co]):
    dependency: providers.AbstractProvider[T_co] | type[T_co]


def FromDI(dependency: providers.AbstractProvider[T_co] | type[T_co]) -> T_co:  # noqa: N802
    return typing.cast(T_co, _FromDI(dependency))


def _parse_inject_params(func: typing.Callable[..., typing.Any]) -> dict[str, _FromDI[typing.Any]]:
    hints = typing.get_type_hints(func, include_extras=True)
    di_params: dict[str, _FromDI[typing.Any]] = {}
    for name, hint in hints.items():
        if name == "return":
            continue
        if typing.get_origin(hint) is typing.Annotated:
            for meta in typing.get_args(hint)[1:]:
                if isinstance(meta, _FromDI):
                    di_params[name] = meta
                    break
    return di_params


def _resolve_di_params(container: Container, di_params: dict[str, _FromDI[typing.Any]]) -> dict[str, typing.Any]:
    return {
        name: (
            container.resolve_provider(marker.dependency)
            if isinstance(marker.dependency, providers.AbstractProvider)
            else container.resolve(dependency_type=marker.dependency)
        )
        for name, marker in di_params.items()
    }


def inject(func: typing.Callable[..., typing.Awaitable[T]]) -> typing.Callable[..., typing.Awaitable[T]]:
    di_params = _parse_inject_params(func)

    @functools.wraps(func)
    async def wrapper(connection: Request | WebSocket) -> T:
        child_container: Container = connection.scope[_CONTAINER_SCOPE_KEY]
        return await func(connection, **_resolve_di_params(child_container, di_params))

    return wrapper
```

- [ ] **Step 4: Export `FromDI` and `inject` from `__init__.py`**

```python
from modern_di_starlette.main import (
    FromDI,
    fetch_di_container,
    inject,
    setup_di,
    starlette_request_provider,
    starlette_websocket_provider,
)


__all__ = [
    "FromDI",
    "fetch_di_container",
    "inject",
    "setup_di",
    "starlette_request_provider",
    "starlette_websocket_provider",
]
```

- [ ] **Step 5: Run the new tests to verify they pass**

```bash
just test tests/test_routes.py tests/test_websockets.py
```

Expected: PASS.

- [ ] **Step 6: Run the full gated suite and lint**

```bash
just test-ci
just lint-ci
```

Expected: `just test-ci` → all tests pass, `Total coverage: 100.00%`. `just lint-ci` → clean + `planning: OK`. If coverage < 100%, add a targeted test for the missing line (do not add `# pragma: no cover`).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: FromDI marker and @inject decorator (resolution)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Promote to `architecture/` and finalize docs prose

**Files:**
- Create: `architecture/container-lifecycle.md`, `architecture/dependency-resolution.md`, `architecture/glossary.md`

**Interfaces:** none (documentation).

- [ ] **Step 1: Write `architecture/container-lifecycle.md`**

```markdown
# Container lifecycle

`modern-di-starlette` wires a `modern_di.Container` into a Starlette app, opens
and closes it around the app's lifespan, and builds a scoped child container per
HTTP request / WebSocket connection.

## setup_di

`setup_di(app, container)` does four things and returns the container:

1. Stashes the root container on `app.state.di_container` (read back with
   `fetch_di_container(app)`).
2. Registers the connection providers (`starlette_request_provider`,
   `starlette_websocket_provider`) on the container's providers registry.
3. Composes the container's open/close around the app's existing lifespan.
4. Installs `_DIMiddleware`, the pure ASGI middleware that builds the
   per-connection child container.

Call it once, after creating the app and before it starts serving — middleware
cannot be added after startup.

## Composed lifespan

`_compose_lifespan` wraps the app's current `lifespan_context` so the root
container is opened inside it and closed on shutdown:

    async with original(app) as state, fetch_di_container(app):
        yield state

`async with container` reopens the container on each startup and closes it on
shutdown, so a second lifespan cycle (test-client re-entry, reload) works
instead of raising `ContainerClosedError`. The original lifespan stays the outer
context and its yielded state passes straight through.

## Per-connection child container

`_DIMiddleware` is pure ASGI middleware (chosen over `BaseHTTPMiddleware`, which
breaks `contextvars` propagation). For each `http` / `websocket` connection it:

1. Builds the connection object (`Request` / `WebSocket`) from the ASGI scope.
2. Matches it against the connection providers: a `Request` opens a
   `Scope.REQUEST` child; a `WebSocket` opens a `Scope.SESSION` child.
3. Builds the child container with the connection injected as context and
   stashes it in the ASGI `scope` dict under the internal `_CONTAINER_SCOPE_KEY`.
4. Closes the child container (`close_async`) when the connection finishes.

Other scope types (`lifespan`) pass straight through untouched.
```

- [ ] **Step 2: Write `architecture/dependency-resolution.md`**

```markdown
# Dependency resolution

Starlette has no dependency-injection system of its own, so `modern-di-starlette`
uses an inert marker plus a decorator (the decorator path from modern-di's
"Writing an integration" guide).

## FromDI

`FromDI(dependency)` marks an endpoint parameter for injection inside an
`Annotated` hint:

    service: typing.Annotated[Service, FromDI(Deps.service)]

It returns `typing.cast(T, _FromDI(dependency))`: type checkers see the resolved
type `T`, while at runtime it is a frozen `_FromDI` marker the decorator detects.
The argument is a provider (`AbstractProvider`) or a bare type — resolution
handles both (`resolve_provider` vs `resolve`).

## @inject

`inject` wraps an endpoint. At decoration time it reads
`typing.get_type_hints(func, include_extras=True)` and collects the parameters
whose `Annotated` metadata holds a `_FromDI`. Starlette calls an endpoint with
just the connection (`endpoint(request)` / `endpoint(websocket)`) and does not
introspect its signature, so — unlike a CLI integration — no signature rewrite is
needed.

At call time the wrapper:

1. Reads the request's child container from
   `connection.scope[_CONTAINER_SCOPE_KEY]` (put there by `_DIMiddleware`).
2. Resolves each marked parameter.
3. Calls the endpoint with the connection plus the resolved parameters by
   keyword.

The endpoint's first parameter is the connection; every `FromDI` parameter
follows and is filled by keyword. `FromDI` parameters coexist with plain ones.
```

- [ ] **Step 3: Write `architecture/glossary.md`**

```markdown
# Glossary

The ubiquitous language of `modern-di-starlette`.

**Root container**:
The application-lifetime `modern_di.Container` passed to `setup_di` and stored on
`app.state.di_container`; opened and closed around the app lifespan.
_Avoid_: app container (in prose), global container.

**Child container**:
The per-connection container built by the middleware — `Scope.REQUEST` for an
HTTP request, `Scope.SESSION` for a WebSocket — and closed when the connection
ends.
_Avoid_: request container (ambiguous across scopes), sub-container.

**Connection provider**:
A `ContextProvider` pairing a Starlette connection type (`Request`, `WebSocket`)
with the scope its child container opens at.

**FromDI marker**:
The inert `Annotated` metadata (`_FromDI`) that flags an endpoint parameter for
resolution by `@inject`.
_Avoid_: Depends (that is FastAPI's mechanism, not Starlette's).
```

- [ ] **Step 4: Verify lint and commit**

```bash
just lint-ci
git add -A
git commit -m "docs: promote container-lifecycle, dependency-resolution, glossary to architecture/

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Open the PR, watch CI, merge, and sync

**Files:** none (VCS/CI).

- [ ] **Step 1: Push the branch and open the PR**

```bash
cd /Users/kevinsmith/src/pypi/modern-di-starlette
git push -u origin feat/di-integration
gh pr create --title "feat: modern-di integration for Starlette" \
  --body "Implements the integration per planning/changes/2026-07-02.01-di-integration. Pure-ASGI middleware for per-connection child containers + @inject/FromDI decorator path. 100% coverage.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

- [ ] **Step 2: Watch CI to green**

```bash
until [ -z "$(gh pr checks 2>/dev/null | grep -i pending)" ]; do sleep 10; done
gh pr checks
```

Expected: `lint` + `pytest (3.10–3.14)` all pass.

- [ ] **Step 3: Merge, sync main, clean up**

```bash
gh pr merge --squash --delete-branch
git checkout main && git pull --ff-only
git remote prune origin
```

---

### Task 6: Add the Starlette usage page to the `modern-di` docs (separate repo, separate PR)

**Files (in `/Users/kevinsmith/src/pypi/modern-di`):**
- Create: `docs/integrations/starlette.md`
- Modify: `mkdocs.yml` (nav)

- [ ] **Step 1: Branch in the modern-di repo**

```bash
cd /Users/kevinsmith/src/pypi/modern-di
git checkout main && git pull --ff-only
git checkout -b docs/starlette-integration
```

- [ ] **Step 2: Write `docs/integrations/starlette.md`**

```markdown
# Usage with `Starlette`

Starlette has no dependency-injection system of its own, so `modern-di-starlette`
uses the `@inject` decorator with `FromDI` markers (there is no `Depends`).
`setup_di` composes the lifespan and installs middleware that opens a
per-connection child container automatically.

## How to use

### 1. Install `modern-di-starlette`

=== "uv"

      ```bash
      uv add modern-di-starlette
      ```

=== "pip"

      ```bash
      pip install modern-di-starlette
      ```

### 2. Apply to your application

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


class AppGroup(Group):
    settings = providers.Factory(scope=Scope.APP, creator=Settings)


@inject
async def homepage(
    request: Request,
    settings: typing.Annotated[Settings, FromDI(AppGroup.settings)],
) -> JSONResponse:
    return JSONResponse({"debug": settings.debug})


app = Starlette(routes=[Route("/", homepage)])
setup_di(app, Container(groups=[AppGroup], validate=True))
```

### 3. Scopes

An HTTP request opens a `Scope.REQUEST` child container; a WebSocket connection
opens a `Scope.SESSION` one. Providers resolve from the connection's child
container, so `Scope.REQUEST` providers live for exactly one request.
```

- [ ] **Step 3: Add the nav entry in `mkdocs.yml`**

  Under the `Integrations:` block, add (after `FastAPI` to keep alphabetical-ish grouping with the others):

```yaml
      - Starlette: integrations/starlette.md
```

- [ ] **Step 4: Strict build, commit, PR**

```bash
just docs-build
git add docs/integrations/starlette.md mkdocs.yml
git commit -m "docs: add Starlette integration usage page

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
git push -u origin docs/starlette-integration
gh pr create --title "docs: add Starlette integration page" --body "Usage page for the new modern-di-starlette integration + nav entry.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

Expected: `just docs-build` passes `--strict` (broken links / nav warnings fail it).

---

## Operations (out-of-repo, do before the first release — not part of merge)

- Add a PyPI **Trusted Publisher** for the `modern-di-starlette` project: environment `pypi`, workflow `release.yml` (mirrors the reference; `just publish` uses OIDC, no token).
- Create brand assets under `modern-python/.github/brand/projects/modern-di-starlette/` (README banner) or the badge images 404 until they exist.

## Self-review notes (author)

- Spec coverage: providers (T2), setup_di/lifespan/middleware (T2), fetch_di_container (T2), FromDI/inject (T3), scopes REQUEST/SESSION (T2 middleware test + T3), out-of-scope items (action_scope, class-based endpoints, public per-request accessor) intentionally absent. Repo scaffolding (T1), architecture promotion (T4), docs page (T6). All spec sections map to a task.
- No placeholders: every file has complete content or an exact `cp`/`sed` from a real reference file.
- Type consistency: `_CONTAINER_SCOPE_KEY`, `_CONNECTION_PROVIDERS`, `_FromDI.dependency`, `resolve_provider`/`resolve(dependency_type=...)` names are identical across Tasks 2–3 and the tests.
