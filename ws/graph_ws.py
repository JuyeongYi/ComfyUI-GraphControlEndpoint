"""WebSocket 엔드포인트: /comfy/graph/ws 양방향 요청-응답."""

import asyncio
import json

from aiohttp import web
from server import PromptServer

from nodes.graph_control import state_store

routes = web.RouteTableDef()

# 테스트에서 조절 가능하도록 모듈 레벨 상수
DEFAULT_TIMEOUT = 5.0


async def process_ws_request(request_data, timeout=None):
    """WS 요청을 처리하고 브라우저 응답을 기다린다."""
    if timeout is None:
        timeout = DEFAULT_TIMEOUT

    request_id = request_data.get("request_id")
    if not request_id:
        return {"status": "error", "message": "missing field: request_id"}

    event = state_store.register_pending(request_id)
    await PromptServer.instance.send("graph_ws_request", request_data)

    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        state_store.get_and_cleanup(request_id)
        return {
            "request_id": request_id,
            "status": "error",
            "message": "timeout",
        }

    data = state_store.get_and_cleanup(request_id)
    return {
        "request_id": request_id,
        "status": "ok",
        "data": data,
    }


@routes.get("/comfy/graph/ws")
async def ws_handler(request):
    """WebSocket 핸들러: JSON 메시지 수신 → process_ws_request → JSON 응답."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            try:
                request_data = json.loads(msg.data)
            except json.JSONDecodeError:
                await ws.send_json({"status": "error", "message": "invalid JSON"})
                continue

            result = await process_ws_request(request_data)
            await ws.send_json(result)

    return ws


# 서버에 라우트 등록
PromptServer.instance.app.router.add_routes(routes)
