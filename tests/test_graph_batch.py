"""POST /comfy/graph/batch 엔드포인트 테스트."""

import pytest
from aiohttp import web

from nodes.graph_control import routes


@pytest.fixture
def app(mock_server):
    application = web.Application()
    application.router.add_routes(routes)
    return application


@pytest.fixture
async def client(app, aiohttp_client):
    return await aiohttp_client(app)


async def test_batch_missing_commands(client):
    """commands 필드 누락 시 400 반환."""
    resp = await client.post("/comfy/graph/batch", json={})
    assert resp.status == 400
    data = await resp.json()
    assert "commands" in data["error"]


async def test_batch_not_list(client):
    """commands가 리스트가 아닌 경우 400 반환."""
    resp = await client.post("/comfy/graph/batch", json={"commands": "not_a_list"})
    assert resp.status == 400
    data = await resp.json()
    assert "list" in data["error"]


async def test_batch_success(client, mock_server):
    """유효한 배치 → 각 명령마다 send 호출."""
    commands = [
        {"type": "create_node", "node_type": "KSampler"},
        {"type": "set_widget", "node_id": 1, "name": "steps", "value": 30},
    ]
    resp = await client.post("/comfy/graph/batch", json={"commands": commands})
    assert resp.status == 200
    data = await resp.json()
    assert data["ok"] is True
    assert data["count"] == 2
    assert data["errors"] == []
    assert mock_server.send.call_count == 2


async def test_batch_skips_invalid_commands(client, mock_server):
    """type 없는 명령은 건너뛰고 errors에 포함."""
    commands = [
        {"type": "create_node", "node_type": "KSampler"},
        {"no_type": "invalid"},  # type 누락
        {"type": "clear_graph"},
    ]
    resp = await client.post("/comfy/graph/batch", json={"commands": commands})
    assert resp.status == 200
    data = await resp.json()
    assert data["count"] == 2  # 유효한 명령만 카운트
    assert len(data["errors"]) == 1
    assert data["errors"][0]["index"] == 1
    assert mock_server.send.call_count == 2
