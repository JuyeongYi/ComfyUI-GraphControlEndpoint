"""GET /comfy/graph/node_types 엔드포인트 테스트."""

import sys

import pytest
from aiohttp import web

from nodes.graph_control import routes


# --- 테스트용 가짜 노드 클래스 ---

class FakeKSampler:
    CATEGORY = "sampling"
    RETURN_TYPES = ("LATENT",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "steps": ("INT", {"default": 20}),
            }
        }


class FakeCheckpoint:
    CATEGORY = "loaders"
    RETURN_TYPES = ("MODEL", "CLIP", "VAE")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "ckpt_name": ("STRING",),
            }
        }


@pytest.fixture(autouse=True)
def register_fake_nodes():
    """테스트 전에 가짜 노드를 등록한다."""
    # conftest에서 모킹한 comfy_nodes 대신, graph_control이 참조하는 모듈 사용
    import nodes as comfy_nodes_ref
    comfy_nodes_ref.NODE_CLASS_MAPPINGS = {
        "KSampler": FakeKSampler,
        "CheckpointLoaderSimple": FakeCheckpoint,
    }
    yield
    comfy_nodes_ref.NODE_CLASS_MAPPINGS = {}


@pytest.fixture
def app(mock_server):
    application = web.Application()
    application.router.add_routes(routes)
    return application


@pytest.fixture
async def client(app, aiohttp_client):
    return await aiohttp_client(app)


async def test_node_types_returns_all(client):
    """모든 등록 노드를 반환한다."""
    resp = await client.get("/comfy/graph/node_types")
    assert resp.status == 200
    data = await resp.json()
    assert "KSampler" in data
    assert "CheckpointLoaderSimple" in data


async def test_node_types_includes_io_info(client):
    """각 노드에 input, output, category 정보를 포함한다."""
    resp = await client.get("/comfy/graph/node_types")
    data = await resp.json()
    ks = data["KSampler"]
    assert ks["category"] == "sampling"
    assert ks["output"] == ["LATENT"]
    assert "required" in ks["input"]
    assert "model" in ks["input"]["required"]


async def test_node_types_filter_by_category(client):
    """?category=loaders로 필터링한다."""
    resp = await client.get("/comfy/graph/node_types?category=loaders")
    assert resp.status == 200
    data = await resp.json()
    assert "CheckpointLoaderSimple" in data
    assert "KSampler" not in data
