"""MCP sunucusu: resmî SDK istemcisiyle gerçek HTTP üzerinden, çekirdek API sahte sunucu."""

import json
import socket
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from uuid import uuid4

import httpx
import httpx2
import pytest
import uvicorn
from fastapi import FastAPI
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from meridian_ai.mcp_server import ApiGate, create_mcp

TENANT = str(uuid4())
KEY = "mrd_gecerli"


class FakeApi(BaseHTTPRequestHandler):
    calls: list[tuple[str, str, str | None]] = []

    def _respond(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode() if length else None
        FakeApi.calls.append((self.command, self.path, self.headers.get("X-API-Key")))
        if self.headers.get("X-API-Key") != KEY:
            status, payload = 401, {}
        elif self.path.endswith("/collections"):
            status, payload = 200, [{"id": "c1", "name": "Belgeler", "createdAt": "x"}]
        elif self.path.endswith("/search"):
            query = json.loads(body)["query"]
            status, payload = (
                (429, {})
                if query == "sınır"
                else (403, {})
                if query == "kapsam"
                else (200, {"hits": [{"content": query}]})
            )
        elif "documents?path=a.md" in self.path:
            status, payload = 200, {"path": "a.md", "title": "A", "content": "metin"}
        else:
            status, payload = 404, {}
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = _respond  # noqa: N815
    do_POST = _respond  # noqa: N815

    def log_message(self, *args) -> None:
        pass


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def mcp_url() -> Iterator[str]:
    api = HTTPServer(("127.0.0.1", 0), FakeApi)
    threading.Thread(target=api.serve_forever, daemon=True).start()

    http = httpx.AsyncClient(timeout=5)
    server, asgi = create_mcp(f"http://127.0.0.1:{api.server_port}", http, ["127.0.0.1:*"])

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(_):
        async with server.session_manager.run():
            yield

    app = FastAPI(lifespan=lifespan)
    app.mount("/mcp", ApiGate(asgi))
    port = free_port()
    uv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=uv.run, daemon=True)
    thread.start()
    for _ in range(100):
        if uv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/mcp/"
    uv.should_exit = True
    thread.join(5)
    api.shutdown()


async def call(url: str, key: str, tool: str | None, arguments: dict | None = None, tenant: str = TENANT):
    headers = {"X-API-Key": key, "X-Tenant-Id": tenant}
    async with (
        httpx2.AsyncClient(headers=headers, timeout=10) as client,
        streamable_http_client(url, http_client=client) as streams,
        ClientSession(streams[0], streams[1]) as session,
    ):
        await session.initialize()
        if tool is None:
            return await session.list_tools()
        return await session.call_tool(tool, arguments or {})


async def test_tools_are_listed_and_read_only(mcp_url: str) -> None:
    tools = (await call(mcp_url, KEY, None)).tools
    assert {tool.name for tool in tools} == {"list_collections", "search_knowledge", "fetch_document"}
    assert all(tool.annotations and tool.annotations.read_only_hint for tool in tools)


async def test_search_goes_through_the_api_with_the_callers_key(mcp_url: str) -> None:
    FakeApi.calls.clear()
    result = await call(mcp_url, KEY, "search_knowledge", {"query": "başvuru"})

    assert not result.is_error
    assert "başvuru" in result.content[0].text
    method, path, key = FakeApi.calls[-1]
    assert (method, path, key) == ("POST", f"/v1/tenants/{TENANT}/search", KEY)


async def test_collections_and_documents(mcp_url: str) -> None:
    collections = await call(mcp_url, KEY, "list_collections")
    assert "Belgeler" in collections.content[0].text
    document = await call(mcp_url, KEY, "fetch_document", {"path": "a.md"})
    assert "metin" in document.content[0].text
    missing = await call(mcp_url, KEY, "fetch_document", {"path": "yok.md"})
    assert missing.is_error and "bulunamadı" in missing.content[0].text


async def test_api_decisions_reach_the_client_without_leaking_the_key(mcp_url: str) -> None:
    denied = await call(mcp_url, "mrd_yanlis", "search_knowledge", {"query": "x"})
    assert denied.is_error and "geçersiz" in denied.content[0].text
    assert "mrd_yanlis" not in denied.content[0].text

    scope = await call(mcp_url, KEY, "search_knowledge", {"query": "kapsam"})
    assert scope.is_error and "sources:read" in scope.content[0].text
    limit = await call(mcp_url, KEY, "search_knowledge", {"query": "sınır"})
    assert limit.is_error and "çok fazla" in limit.content[0].text


async def test_missing_credentials_are_refused_before_any_session(mcp_url: str) -> None:
    async with httpx.AsyncClient() as client:
        body = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        no_key = await client.post(mcp_url, json=body, headers={"X-Tenant-Id": TENANT})
        assert no_key.status_code == 401
        bad_tenant = await client.post(
            mcp_url, json=body, headers={"X-API-Key": KEY, "X-Tenant-Id": "../../x"}
        )
        assert bad_tenant.status_code == 400


async def test_foreign_host_header_is_refused(mcp_url: str) -> None:
    """DNS yeniden bağlama: başka bir alan adından gelen istek yerel sunucuya ulaşmaz."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            mcp_url,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={
                "X-API-Key": KEY,
                "X-Tenant-Id": TENANT,
                "Host": "evil.test",
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )
    assert response.status_code in (400, 421)
