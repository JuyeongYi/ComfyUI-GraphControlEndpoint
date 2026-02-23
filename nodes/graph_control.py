"""HTTP 엔드포인트: /comfy/graph/* 라우트 정의."""

import asyncio
import json
import os
import re
import sys

import aiohttp
from aiohttp import web
from server import PromptServer

SAVE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "saved_graphs")


def _get_node_class_mappings():
    """ComfyUI의 NODE_CLASS_MAPPINGS를 반환한다."""
    nodes_mod = sys.modules.get("nodes")
    return getattr(nodes_mod, "NODE_CLASS_MAPPINGS", {})


class StateStore:
    """WS 양방향 통신을 위한 request_id 기반 상태 저장소."""

    def __init__(self):
        self._pending = {}   # request_id → asyncio.Event
        self._results = {}   # request_id → data
        self.last_state = None

    def register_pending(self, request_id):
        """pending 요청을 등록하고 Event를 반환한다."""
        event = asyncio.Event()
        self._pending[request_id] = event
        return event

    def resolve_pending(self, request_id, data):
        """pending 요청에 결과를 설정하고 대기 중인 핸들러를 깨운다."""
        self._results[request_id] = data
        event = self._pending.get(request_id)
        if event:
            event.set()

    def get_and_cleanup(self, request_id):
        """결과를 반환하고 정리한다."""
        self._pending.pop(request_id, None)
        return self._results.pop(request_id, None)


state_store = StateStore()

routes = web.RouteTableDef()


@routes.post("/comfy/graph/command")
async def post_command(request):
    """단일 그래프 명령을 브라우저에 브로드캐스트한다."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)

    if "type" not in data:
        return web.json_response({"error": "missing field: type"}, status=400)

    await PromptServer.instance.send("graph_command", data)
    return web.json_response({"ok": True})


@routes.post("/comfy/graph/batch")
async def post_batch(request):
    """여러 그래프 명령을 순서대로 브로드캐스트한다."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)

    commands = data.get("commands")
    if commands is None:
        return web.json_response({"error": "missing field: commands"}, status=400)
    if not isinstance(commands, list):
        return web.json_response({"error": "commands must be a list"}, status=400)

    count = 0
    errors = []
    for i, cmd in enumerate(commands):
        if not isinstance(cmd, dict) or "type" not in cmd:
            errors.append({"index": i, "error": "missing field: type"})
            continue
        await PromptServer.instance.send("graph_command", cmd)
        count += 1

    return web.json_response({"ok": True, "count": count, "errors": errors})


@routes.get("/comfy/graph/node_types")
async def get_node_types(request):
    """등록된 노드 타입과 입출력 정보를 반환한다."""
    category_filter = request.query.get("category")
    mappings = _get_node_class_mappings()
    result = {}

    for name, cls in mappings.items():
        try:
            cat = getattr(cls, "CATEGORY", "")
            if category_filter and not re.search(category_filter, cat):
                continue

            input_types = {}
            if hasattr(cls, "INPUT_TYPES"):
                input_types = cls.INPUT_TYPES()

            output_types = list(getattr(cls, "RETURN_TYPES", ()))

            result[name] = {
                "input": input_types,
                "output": output_types,
                "category": cat,
            }
        except Exception:
            result[name] = {"input": {}, "output": [], "category": ""}

    return web.json_response(result)


@routes.get("/comfy/graph/all_nodes")
async def get_all_nodes(request):
    """전체 노드 타입 이름 + 설명 + 카테고리를 반환한다. AI 컨텍스트용."""
    mappings = _get_node_class_mappings()
    result = {}

    for name, cls in mappings.items():
        try:
            description = getattr(cls, "DESCRIPTION", "")
            if not description:
                description = (cls.__doc__ or "").strip()

            cat = getattr(cls, "CATEGORY", "")
            output_types = list(getattr(cls, "RETURN_TYPES", ()))

            input_names = []
            if hasattr(cls, "INPUT_TYPES"):
                input_types = cls.INPUT_TYPES()
                for section in ("required", "optional"):
                    if section in input_types:
                        for key, val in input_types[section].items():
                            type_name = val[0] if isinstance(val, (list, tuple)) else str(val)
                            input_names.append({"name": key, "type": type_name})

            result[name] = {
                "description": description,
                "category": cat,
                "inputs": input_names,
                "outputs": output_types,
            }
        except Exception:
            result[name] = {"description": "", "category": "", "inputs": [], "outputs": []}

    return web.json_response(result)


@routes.post("/comfy/graph/state")
async def post_state(request):
    """브라우저에서 WS 요청 결과를 수신한다 (내부용)."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)

    request_id = data.get("request_id")
    result_data = data.get("data")

    if request_id:
        state_store.resolve_pending(request_id, result_data)
    else:
        state_store.last_state = result_data

    return web.json_response({"ok": True})


@routes.post("/comfy/graph/queue")
async def post_queue(request):
    """prompt를 ComfyUI 실행 큐에 전달한다."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)

    prompt = data.get("prompt")
    if not prompt:
        return web.json_response({"error": "missing field: prompt"}, status=400)

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://127.0.0.1:8188/prompt",
            json={"prompt": prompt},
        ) as resp:
            result = await resp.json()

    return web.json_response({"ok": True, "prompt_id": result.get("prompt_id")})


@routes.post("/comfy/graph/save")
async def post_save(request):
    """그래프를 JSON 파일로 저장한다."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)

    filename = data.get("filename")
    graph = data.get("graph")

    if not filename:
        return web.json_response({"error": "missing field: filename"}, status=400)
    if graph is None:
        return web.json_response({"error": "missing field: graph"}, status=400)

    # 경로 탐색 방지
    safe_name = os.path.basename(filename)
    if safe_name != filename:
        return web.json_response({"error": "invalid filename: path traversal"}, status=400)

    os.makedirs(SAVE_DIR, exist_ok=True)
    filepath = os.path.join(SAVE_DIR, safe_name)
    with open(filepath, "w") as f:
        json.dump(graph, f)

    return web.json_response({"ok": True})


@routes.post("/comfy/graph/load")
async def post_load(request):
    """JSON 파일에서 그래프를 로드하고 브라우저에 전달한다."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)

    filename = data.get("filename")
    if not filename:
        return web.json_response({"error": "missing field: filename"}, status=400)

    safe_name = os.path.basename(filename)
    filepath = os.path.join(SAVE_DIR, safe_name)

    if not os.path.exists(filepath):
        return web.json_response({"error": "file not found"}, status=404)

    with open(filepath) as f:
        graph_data = json.load(f)

    await PromptServer.instance.send("graph_command", {
        "type": "load_graph",
        "graph_data": graph_data,
    })

    return web.json_response({"ok": True, "graph": graph_data})


# 서버에 라우트 등록 (app.router에 직접 추가해야 동작함)
PromptServer.instance.app.router.add_routes(routes)
