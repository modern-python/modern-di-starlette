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
    container = modern_di.Container(groups=[Dependencies], validate=True)
    modern_di_starlette.setup_di(app_, container=container)
    return app_


@pytest.fixture
def client(app: Starlette) -> typing.Iterator[TestClient]:
    with TestClient(app=app) as test_client:
        yield test_client
