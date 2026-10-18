import logging

import anyio
import pytest
from modern_di import Container, Group, Scope, providers
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Route

import modern_di_starlette
from modern_di_starlette import main
from tests import asgi


class _First: ...


class _Second: ...


def _app(log: list[str], *, second_finalizer_delay: float) -> Starlette:
    async def finalize_first(_: _First) -> None:
        await anyio.sleep(0.01)
        log.append("first")

    async def finalize_second(_: _Second) -> None:
        await anyio.sleep(second_finalizer_delay)
        log.append("second")

    class G(Group):
        first = providers.Factory(
            scope=Scope.REQUEST, creator=_First, cache=providers.CacheSettings(finalizer=finalize_first)
        )
        second = providers.Factory(
            scope=Scope.REQUEST, creator=_Second, cache=providers.CacheSettings(finalizer=finalize_second)
        )

    async def endpoint(request: Request) -> None:
        container = request.scope[main._CONTAINER_SCOPE_KEY]  # noqa: SLF001
        container.resolve(_First)
        container.resolve(_Second)
        await anyio.sleep_forever()

    app = Starlette(routes=[Route("/", endpoint)])
    modern_di_starlette.setup_di(app, Container(groups=[G]), manage_lifespan=False)
    return app


async def _call_cancelled_mid_handler(app: Starlette) -> None:
    with anyio.move_on_after(0.05):
        await asgi.get(app)


async def test_a_cancelled_request_still_runs_every_child_finalizer() -> None:
    log: list[str] = []

    await _call_cancelled_mid_handler(_app(log, second_finalizer_delay=0.01))

    assert log == ["second", "first"]


async def test_a_hung_child_finalizer_is_abandoned_after_the_bound(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(main, "_CHILD_CLOSE_TIMEOUT", 0.05)
    log: list[str] = []

    with anyio.fail_after(1), caplog.at_level(logging.WARNING, logger=main.__name__):
        await _call_cancelled_mid_handler(_app(log, second_finalizer_delay=10))

    assert log == []
    assert [record.getMessage() for record in caplog.records] == [
        "Closing the child container did not finish within 0.05 s; its remaining finalizers did not run"
    ]
