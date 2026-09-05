"""Production ASGI hardening for the OpenVoice API.

The upstream application remains unchanged; this wrapper adds deployment-level
controls without coupling them to the realtime pipeline implementation.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections import defaultdict, deque
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.api.server import app as application

MAX_HTTP_BODY = int(os.getenv("OPENVOICE_MAX_HTTP_BODY_BYTES", "1048576"))
RATE_LIMIT = int(os.getenv("OPENVOICE_RATE_LIMIT", "60"))
RATE_WINDOW = int(os.getenv("OPENVOICE_RATE_WINDOW_SECONDS", "60"))
MAX_CONNECTIONS = int(os.getenv("OPENVOICE_MAX_CONNECTIONS", "20"))
API_KEY = os.getenv("OPENVOICE_API_KEY", "").strip()
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("OPENVOICE_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]


class SecurityMiddleware:
    """Small dependency-free ASGI security boundary for HTTP + WebSocket traffic."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self.active_connections = 0
        self.lock = asyncio.Lock()

    @staticmethod
    def _client(scope: Scope) -> str:
        client = scope.get("client")
        return str(client[0]) if client else "unknown"

    @staticmethod
    def _headers(scope: Scope) -> dict[str, str]:
        return {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }

    def _authorized(self, scope: Scope) -> bool:
        if not API_KEY:
            return True  # Local development remains frictionless.
        headers = self._headers(scope)
        token = headers.get("x-api-key") or headers.get("authorization", "")
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        if token == API_KEY:
            return True
        # Browser WebSocket clients cannot set arbitrary headers; support a
        # short-lived deployment API key via ?api_key=... when explicitly used.
        if scope["type"] == "websocket":
            query = parse_qs(scope.get("query_string", b"").decode("utf-8"))
            return query.get("api_key", [""])[0] == API_KEY
        return False

    async def _rate_allowed(self, client: str) -> bool:
        now = time.monotonic()
        async with self.lock:
            bucket = self.hits[client]
            cutoff = now - RATE_WINDOW
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= RATE_LIMIT:
                return False
            bucket.append(now)
            return True

    @staticmethod
    async def _send_http(send: Send, status: int, body: bytes) -> None:
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        })
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        if not self._authorized(scope):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008, "reason": "Unauthorized"})
                return
            await self._send_http(send, 401, b'{"detail":"Unauthorized"}')
            return

        client = self._client(scope)
        if not await self._rate_allowed(client):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1013, "reason": "Rate limit exceeded"})
                return
            await self._send_http(send, 429, b'{"detail":"Rate limit exceeded"}')
            return

        if scope["type"] == "websocket":
            async with self.lock:
                if self.active_connections >= MAX_CONNECTIONS:
                    await send({"type": "websocket.close", "code": 1013, "reason": "Server busy"})
                    return
                self.active_connections += 1
            try:
                await self.app(scope, receive, send)
            finally:
                async with self.lock:
                    self.active_connections = max(0, self.active_connections - 1)
            return

        # Enforce a bounded request body before the application sees it.
        content_length = next(
            (int(v) for k, v in scope.get("headers", []) if k.lower() == b"content-length"),
            0,
        )
        if content_length > MAX_HTTP_BODY:
            await self._send_http(send, 413, b'{"detail":"Request body too large"}')
            return

        await self.app(scope, receive, send)


# Security middleware is outermost; CORS stays inside it and is constrained to
# explicit origins instead of the original wildcard configuration.
application.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)
app = SecurityMiddleware(application)
