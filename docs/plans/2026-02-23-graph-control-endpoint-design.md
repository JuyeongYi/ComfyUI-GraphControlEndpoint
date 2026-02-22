# ComfyUI Graph Control Endpoint - Design Document

## Purpose

MCP 서버를 통해 AI 에이전트가 ComfyUI의 LiteGraph 노드 에디터를 HTTP/WebSocket으로 원격 제어할 수 있는 ComfyUI 커스텀 익스텐션.

## Architecture

듀얼 채널 방식: 명령 전송은 HTTP, 상태 조회는 WebSocket.

```
MCP 서버 / 외부 클라이언트
    │
    ├── POST /comfy/graph/command     → 단일 명령 (fire-and-forget)
    ├── POST /comfy/graph/batch       → 배치 명령
    ├── GET  /comfy/graph/node_types  → 노드 타입 조회 (서버 직접 응답)
    ├── POST /comfy/graph/queue       → 큐 실행
    ├── POST /comfy/graph/save        → 그래프 저장
    ├── POST /comfy/graph/load        → 그래프 로드
    │
    └── WS   /comfy/graph/ws          → 양방향 (상태 조회, 이벤트)
                │
                ▼
    ComfyUI 서버 (Python, aiohttp)
                │
                ▼
    브라우저 (JavaScript extension) → LiteGraph API
```

### Data Flow

**명령 전송 (단방향):**
1. 외부 → HTTP POST → 서버
2. 서버 → `PromptServer.instance.send("graph_command", data)` → WebSocket 브로드캐스트
3. 브라우저 → `api.addEventListener("graph_command", handler)` → LiteGraph 조작

**상태 조회 (양방향):**
1. 외부 → WS 연결 `/comfy/graph/ws`
2. 외부 → WS 요청 `{"request_id": "abc", "type": "get_graph"}`
3. 서버 → 브라우저에 명령 브로드캐스트
4. 브라우저 → 서버에 결과 POST `/comfy/graph/state`
5. 서버 → WS로 응답 반환 `{"request_id": "abc", "status": "ok", "data": {...}}`

## HTTP Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/comfy/graph/command` | POST | 단일 그래프 명령 전송 |
| `/comfy/graph/batch` | POST | 여러 명령을 순서대로 실행 |
| `/comfy/graph/node_types` | GET | 등록된 노드 타입 + 입출력 정보 |
| `/comfy/graph/queue` | POST | 현재 그래프를 큐에 넣어 실행 |
| `/comfy/graph/save` | POST | 그래프를 JSON 파일로 저장 |
| `/comfy/graph/load` | POST | JSON 파일에서 그래프 로드 |
| `/comfy/graph/state` | POST | 브라우저→서버 상태 수신 (내부용) |

## WebSocket Endpoint

| Endpoint | Protocol | Description |
|----------|----------|-------------|
| `/comfy/graph/ws` | WS | 양방향 요청-응답, request_id 기반 |

### WS Protocol

```json
// Request (client → server)
{"request_id": "uuid", "type": "get_graph"}

// Response (server → client)
{"request_id": "uuid", "status": "ok", "data": { ... }}

// Error
{"request_id": "uuid", "status": "error", "message": "timeout"}
```

## Graph Commands

| type | Parameters | Description |
|------|-----------|-------------|
| `create_node` | `node_type`, `x?`, `y?` | 노드 생성 |
| `remove_node` | `node_id` | 노드 삭제 |
| `connect` | `from_id`, `from_slot`, `to_id`, `to_slot` | 노드 연결 |
| `disconnect` | `node_id`, `slot` | 입력 연결 해제 |
| `set_widget` | `node_id`, `name`, `value` | 위젯 값 변경 |
| `move_node` | `node_id`, `x`, `y` | 노드 위치 이동 |
| `clear_graph` | — | 그래프 전체 초기화 |
| `get_graph` | — | 그래프 직렬화 반환 (WS 응답) |

### Batch Format

```json
{
    "commands": [
        {"type": "create_node", "node_type": "KSampler", "x": 100, "y": 100},
        {"type": "set_widget", "node_id": 1, "name": "steps", "value": 30}
    ]
}
```

## File Structure

```
ComfyUI-GraphControlEndpoint/
├── __init__.py                 # WEB_DIRECTORY, 라우트 임포트
├── nodes/
│   └── graph_control.py        # HTTP 엔드포인트
├── ws/
│   └── graph_ws.py             # WebSocket 엔드포인트
├── web/
│   └── graph_control.js        # 브라우저 확장
├── EditGraphViaEndpoint.md     # 원본 설계 문서
└── docs/
    └── plans/
```

## Error Handling

| Scenario | Response | Handling |
|----------|----------|---------|
| Invalid JSON | 400 `{"error": "invalid JSON"}` | — |
| Missing `type` | 400 `{"error": "missing field: type"}` | — |
| Unknown node type | 200 OK | Browser console.warn |
| WS timeout | `{"status": "error", "message": "timeout"}` | 5s timeout |
| No browser connected | 200 OK, command lost | Documented |
| Batch failure | Partial | Each result in array |

## Key Decisions

1. **Dual channel (HTTP + WS)**: MCP 서버에서 HTTP로 간편하게 명령, WS로 신뢰성 있는 상태 조회
2. **Node types from server**: `/object_info` 활용, 브라우저 불필요
3. **request_id pattern**: WS 요청-응답 매칭에 UUID 사용
4. **Broadcast all**: `sid=None`으로 모든 브라우저 탭에 명령 전달
