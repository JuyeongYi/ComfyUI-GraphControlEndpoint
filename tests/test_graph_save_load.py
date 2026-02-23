"""POST /comfy/graph/save, /load 엔드포인트 테스트."""

import json
import os
import tempfile

import pytest
from aiohttp import web

import nodes.graph_control as graph_control_module
from nodes.graph_control import routes


@pytest.fixture
def save_dir(tmp_path):
    """임시 저장 디렉토리를 사용한다."""
    d = tmp_path / "saved_graphs"
    d.mkdir()
    original = graph_control_module.SAVE_DIR
    graph_control_module.SAVE_DIR = str(d)
    yield d
    graph_control_module.SAVE_DIR = original


@pytest.fixture
def app(mock_server, save_dir):
    application = web.Application()
    application.router.add_routes(routes)
    return application


@pytest.fixture
async def client(app, aiohttp_client):
    return await aiohttp_client(app)


# --- Save 테스트 ---

async def test_save_missing_filename(client):
    """filename 누락 시 400."""
    resp = await client.post("/comfy/graph/save", json={"graph": {}})
    assert resp.status == 400


async def test_save_missing_graph(client):
    """graph 누락 시 400."""
    resp = await client.post("/comfy/graph/save", json={"filename": "test.json"})
    assert resp.status == 400


async def test_save_success(client, save_dir):
    """파일 저장 성공."""
    graph_data = {"nodes": [{"id": 1}], "links": []}
    resp = await client.post(
        "/comfy/graph/save",
        json={"filename": "my_graph.json", "graph": graph_data},
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["ok"] is True

    saved_file = save_dir / "my_graph.json"
    assert saved_file.exists()
    with open(saved_file) as f:
        assert json.load(f) == graph_data


async def test_save_rejects_path_traversal(client):
    """../ 포함 시 400."""
    resp = await client.post(
        "/comfy/graph/save",
        json={"filename": "../../../etc/evil.json", "graph": {}},
    )
    assert resp.status == 400
    data = await resp.json()
    assert "path" in data["error"].lower() or "filename" in data["error"].lower()


# --- Load 테스트 ---

async def test_load_missing_filename(client):
    """filename 누락 시 400."""
    resp = await client.post("/comfy/graph/load", json={})
    assert resp.status == 400


async def test_load_file_not_found(client):
    """파일 없으면 404."""
    resp = await client.post(
        "/comfy/graph/load",
        json={"filename": "nonexistent.json"},
    )
    assert resp.status == 404


async def test_load_success(client, mock_server, save_dir):
    """그래프 로드 성공 + 브라우저 전달."""
    graph_data = {"nodes": [{"id": 1}], "links": []}
    graph_file = save_dir / "test_load.json"
    with open(graph_file, "w") as f:
        json.dump(graph_data, f)

    resp = await client.post(
        "/comfy/graph/load",
        json={"filename": "test_load.json"},
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["ok"] is True
    assert data["graph"] == graph_data

    # 브라우저에 load_graph 명령 전달 확인
    mock_server.send.assert_called_once()
    call_data = mock_server.send.call_args[0][1]
    assert call_data["type"] == "load_graph"
    assert call_data["graph_data"] == graph_data
