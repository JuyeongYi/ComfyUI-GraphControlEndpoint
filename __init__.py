"""ComfyUI-GraphControlEndpoint: HTTP/WebSocket을 통한 LiteGraph 원격 제어 익스텐션."""

WEB_DIRECTORY = "./web"

# ComfyUI custom_nodes 로더에 의해 패키지로 임포트될 때만 라우트 등록
try:
    from .nodes import graph_control  # noqa: F401, E402
    from .ws import graph_ws  # noqa: F401, E402
except ImportError:
    pass

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
