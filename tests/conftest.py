"""테스트 픽스처: PromptServer 모킹."""

import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_server(monkeypatch):
    """PromptServer.instance를 모킹하여 ComfyUI 없이 테스트 가능하게 한다."""
    # server 모듈 모킹
    server_module = types.ModuleType("server")
    mock_instance = MagicMock()
    mock_instance.send = AsyncMock()
    mock_instance.send_sync = MagicMock()

    # aiohttp 라우트 테이블 모킹
    mock_routes = MagicMock()
    registered_routes = {}

    def make_route_decorator(method):
        def decorator(path):
            def wrapper(func):
                registered_routes[(method, path)] = func
                return func
            return wrapper
        return decorator

    mock_routes.post = make_route_decorator("POST")
    mock_routes.get = make_route_decorator("GET")
    mock_instance.routes = mock_routes

    server_module.PromptServer = MagicMock()
    server_module.PromptServer.instance = mock_instance

    monkeypatch.setitem(sys.modules, "server", server_module)

    # nodes 모듈 모킹 (NODE_CLASS_MAPPINGS용)
    nodes_module = types.ModuleType("nodes")
    nodes_module.NODE_CLASS_MAPPINGS = {}
    monkeypatch.setitem(sys.modules, "nodes", nodes_module)

    # folder_paths 모듈 모킹
    folder_paths_module = types.ModuleType("folder_paths")
    folder_paths_module.base_path = "/tmp/comfyui_test"
    monkeypatch.setitem(sys.modules, "folder_paths", folder_paths_module)

    # 반환: 테스트에서 mock_server 접근 가능
    return mock_instance
