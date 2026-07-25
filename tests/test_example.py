from starlette import status
from starlette.testclient import TestClient

from examples.app import app


def test_example_resolves_and_greets() -> None:
    with TestClient(app) as client:
        response = client.get("/greet/world")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"greeting": "Hello, world!"}
