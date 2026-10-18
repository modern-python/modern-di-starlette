import typing

from starlette.types import ASGIApp, Message


async def get(app: ASGIApp, path: str = "/") -> list[int]:
    """Send one GET straight to ``app``, with no test client in between; return the statuses it sent."""
    statuses: list[int] = []

    async def receive() -> Message:
        return {
            "type": "http.request",
            "body": b"",
            "more_body": False,
        }  # pragma: no cover -- GET handlers never read the body

    async def send(message: Message) -> None:
        if message["type"] == "http.response.start":
            statuses.append(message["status"])

    scope: dict[str, typing.Any] = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "scheme": "http",
        "query_string": b"",
        "headers": [],
        "client": ("testclient", 1),
        "server": ("testserver", 80),
    }
    await app(scope, receive, send)
    return statuses
