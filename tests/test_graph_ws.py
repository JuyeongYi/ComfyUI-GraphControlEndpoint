"""WebSocket /comfy/graph/ws 엔드포인트 테스트."""

import asyncio
import json

import pytest
from aiohttp import web

from nodes.graph_control import state_store
import ws.graph_ws as graph_ws_module
from ws.graph_ws import routes as ws_routes, process_ws_request


@pytest.fixture
def app(mock_server):
    application = web.Application()
    application.router.add_routes(ws_routes)
    return application


@pytest.fixture
async def client(app, aiohttp_client):
    return await aiohttp_client(app)


@pytest.fixture(autouse=True)
def clean_state_store():
    """매 테스트마다 StateStore 정리 + 타임아웃 단축."""
    original_timeout = graph_ws_module.DEFAULT_TIMEOUT
    graph_ws_module.DEFAULT_TIMEOUT = 0.3  # 테스트용 짧은 타임아웃
    yield
    graph_ws_module.DEFAULT_TIMEOUT = original_timeout
    state_store._pending.clear()
    state_store._results.clear()
    state_store.last_state = None


async def test_ws_handler_registered(client):
    """GET /comfy/graph/ws가 WebSocket으로 등록되어 있다."""
    async with client.ws_connect("/comfy/graph/ws") as ws:
        assert not ws.closed


async def test_ws_get_graph_request(client, mock_server):
    """요청→응답 정상 흐름."""
    async with client.ws_connect("/comfy/graph/ws") as ws:
        # 클라이언트가 요청 전송
        request_data = {"request_id": "test-ws-1", "type": "get_graph"}
        await ws.send_json(request_data)

        # 브라우저 역할: state_store에 결과 제공 (시뮬레이션)
        await asyncio.sleep(0.05)
        state_store.resolve_pending("test-ws-1", {"nodes": [], "links": []})

        # WS 응답 수신
        msg = await ws.receive_json()
        assert msg["request_id"] == "test-ws-1"
        assert msg["status"] == "ok"
        assert msg["data"] == {"nodes": [], "links": []}


async def test_ws_timeout(client, mock_server):
    """브라우저 무응답 시 타임아웃 에러."""
    async with client.ws_connect("/comfy/graph/ws") as ws:
        request_data = {"request_id": "test-ws-timeout", "type": "get_graph"}
        await ws.send_json(request_data)

        # 아무 응답도 보내지 않음 → 타임아웃
        msg = await ws.receive_json()
        assert msg["request_id"] == "test-ws-timeout"
        assert msg["status"] == "error"
        assert "timeout" in msg["message"]


async def test_ws_missing_request_id(client, mock_server):
    """request_id 누락 시 에러."""
    async with client.ws_connect("/comfy/graph/ws") as ws:
        await ws.send_json({"type": "get_graph"})

        msg = await ws.receive_json()
        assert msg["status"] == "error"
        assert "request_id" in msg["message"]
