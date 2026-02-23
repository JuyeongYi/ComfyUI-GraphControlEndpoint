"""POST /comfy/graph/command 엔드포인트 테스트."""

import json

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, TestClient, TestServer

from nodes.graph_control import routes


@pytest.fixture
def app(mock_server):
    """테스트용 aiohttp 앱 생성."""
    application = web.Application()
    application.router.add_routes(routes)
    return application


@pytest.fixture
async def client(app, aiohttp_client):
    """테스트 클라이언트."""
    return await aiohttp_client(app)


async def test_command_invalid_json(client):
    """JSON 파싱 실패 시 400 반환."""
    resp = await client.post(
        "/comfy/graph/command",
        data="not json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status == 400
    data = await resp.json()
    assert "error" in data


async def test_command_missing_type(client):
    """type 필드 누락 시 400 반환."""
    resp = await client.post(
        "/comfy/graph/command",
        json={"node_type": "KSampler"},
    )
    assert resp.status == 400
    data = await resp.json()
    assert "type" in data["error"]


async def test_command_success(client, mock_server):
    """유효한 명령 시 send 호출 + 200 반환."""
    resp = await client.post(
        "/comfy/graph/command",
        json={"type": "create_node", "node_type": "KSampler", "x": 200, "y": 300},
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["ok"] is True

    # send가 호출되었는지 확인
    mock_server.send.assert_called_once()
    call_args = mock_server.send.call_args
    assert call_args[0][0] == "graph_command"
    assert call_args[0][1]["type"] == "create_node"


COMMAND_TYPES = [
    "create_node", "remove_node", "connect", "disconnect",
    "set_widget", "move_node", "clear_graph", "get_graph",
]


@pytest.mark.parametrize("cmd_type", COMMAND_TYPES)
async def test_command_broadcasts_all_types(client, mock_server, cmd_type):
    """모든 command type이 브로드캐스트된다."""
    mock_server.send.reset_mock()
    resp = await client.post(
        "/comfy/graph/command",
        json={"type": cmd_type},
    )
    assert resp.status == 200
    mock_server.send.assert_called_once()
    assert mock_server.send.call_args[0][1]["type"] == cmd_type
