"""POST /comfy/graph/state + StateStore 테스트."""

import asyncio

import pytest
from aiohttp import web

from nodes.graph_control import routes, state_store


@pytest.fixture
def app(mock_server):
    application = web.Application()
    application.router.add_routes(routes)
    return application


@pytest.fixture
async def client(app, aiohttp_client):
    return await aiohttp_client(app)


@pytest.fixture(autouse=True)
def clean_state_store():
    """매 테스트 후 StateStore를 정리한다."""
    yield
    state_store._pending.clear()
    state_store._results.clear()
    state_store.last_state = None


async def test_state_stores_data(client):
    """데이터가 정상적으로 저장된다."""
    resp = await client.post(
        "/comfy/graph/state",
        json={"request_id": "abc", "data": {"nodes": []}},
    )
    assert resp.status == 200
    result = state_store.get_and_cleanup("abc")
    assert result == {"nodes": []}


async def test_state_with_request_id():
    """pending request가 있으면 event.set()이 호출된다."""
    event = state_store.register_pending("test-123")
    assert not event.is_set()

    state_store.resolve_pending("test-123", {"graph": "data"})
    assert event.is_set()

    result = state_store.get_and_cleanup("test-123")
    assert result == {"graph": "data"}
    # cleanup 후 None
    assert state_store.get_and_cleanup("test-123") is None


async def test_state_without_request_id(client):
    """request_id가 없으면 last_state에만 저장된다."""
    resp = await client.post(
        "/comfy/graph/state",
        json={"data": {"some": "state"}},
    )
    assert resp.status == 200
    assert state_store.last_state == {"some": "state"}
