"""Bound untrusted bytes before Starlette parses/spools multipart content."""

from starlette.responses import JSONResponse
import asyncio
from .core import settings

MAX_REQUEST = 9 * 1024 * 1024


class DemoResourceMiddleware:
    """Serialize public computations on the single 512 MB demo instance."""

    def __init__(self, app):
        self.app = app
        self.slot = asyncio.Semaphore(1)

    async def __call__(self, scope, receive, send):
        if (
            not settings.public_demo
            or scope["type"] != "http"
            or scope["method"] == "OPTIONS"
            or scope.get("path") == "/api/v1/health"
            or not scope.get("path", "").startswith("/api/")
        ):
            return await self.app(scope, receive, send)
        async with self.slot:
            await self.app(scope, receive, send)


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ["POST", "PATCH", "PUT"]:
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            if int(headers.get(b"content-length", b"0")) > MAX_REQUEST:
                return await JSONResponse(
                    {"detail": "Maximum request size is 9 MB"}, status_code=413
                )(scope, receive, send)
        except ValueError:
            return await JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)(
                scope, receive, send
            )
        messages, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > MAX_REQUEST:
                return await JSONResponse(
                    {"detail": "Maximum request size is 9 MB"}, status_code=413
                )(scope, receive, send)
            messages.append(message)
            if not message.get("more_body", False):
                break
        index = 0

        async def replay():
            nonlocal index
            if index < len(messages):
                m = messages[index]
                index += 1
                return m
            return await receive()

        await self.app(scope, replay, send)
