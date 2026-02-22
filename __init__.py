"""ComfyUI-GraphControlEndpoint: HTTP/WebSocket을 통한 LiteGraph 원격 제어 익스텐션."""

WEB_DIRECTORY = "./web"

from .nodes import graph_control  # noqa: F401, E402 — 라우트 등록
from .ws import graph_ws  # noqa: F401, E402 — WS 라우트 등록

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
