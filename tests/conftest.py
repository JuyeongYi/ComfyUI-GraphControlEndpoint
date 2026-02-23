"""테스트 픽스처: PromptServer 모킹.

모듈 레벨에서 sys.modules를 설정하여 import 시점에 server/nodes 모듈이 존재하도록 한다.
"""

import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

# --- 모듈 레벨 모킹 (import 시점에 필요) ---

_server_module = types.ModuleType("server")
_mock_prompt_server_class = MagicMock()
_mock_instance = MagicMock()
_mock_instance.send = AsyncMock()
_mock_instance.send_sync = MagicMock()
_mock_instance.routes = MagicMock()  # 데코레이터 라우트용 플레이스홀더
_mock_prompt_server_class.instance = _mock_instance
_server_module.PromptServer = _mock_prompt_server_class
sys.modules["server"] = _server_module

_folder_paths_module = types.ModuleType("folder_paths")
_folder_paths_module.base_path = "/tmp/comfyui_test"
sys.modules["folder_paths"] = _folder_paths_module

# ComfyUI의 nodes 모듈 (NODE_CLASS_MAPPINGS)은 comfy_nodes로 모킹
# 로컬 nodes/ 패키지와 이름 충돌 방지
_comfy_nodes_module = types.ModuleType("comfy_nodes")
_comfy_nodes_module.NODE_CLASS_MAPPINGS = {}
sys.modules["comfy_nodes"] = _comfy_nodes_module


# --- 픽스처 ---

@pytest.fixture(autouse=True)
def mock_server():
    """매 테스트마다 mock 상태를 리셋하고 mock_instance를 반환한다."""
    _mock_instance.send.reset_mock()
    _mock_instance.send_sync.reset_mock()
    yield _mock_instance
