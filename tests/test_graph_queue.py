"""POST /comfy/graph/queue 엔드포인트 테스트."""

from unittest.mock import AsyncMock, patch, MagicMock

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


async def test_queue_missing_prompt(client):
    """prompt 없으면 400."""
    resp = await client.post("/comfy/graph/queue", json={})
    assert resp.status == 400
    data = await resp.json()
    assert "prompt" in data["error"]


async def test_queue_requests_graph_then_queues(client):
    """prompt 제공 시 내부 /prompt 호출."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"prompt_id": "abc-123"})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("nodes.graph_control.aiohttp.ClientSession", return_value=mock_session):
        resp = await client.post(
            "/comfy/graph/queue",
            json={"prompt": {"1": {"class_type": "KSampler"}}},
        )

    assert resp.status == 200
    data = await resp.json()
    assert data["ok"] is True
    assert data["prompt_id"] == "abc-123"
