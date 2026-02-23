# ComfyUI-GraphControlEndpoint API Reference

HTTP/WebSocket을 통해 ComfyUI LiteGraph 노드 에디터를 원격 제어한다.

Base URL: `http://localhost:8188`

---

## HTTP Endpoints

### POST /comfy/graph/command

단일 그래프 명령을 브라우저에 전달한다 (fire-and-forget).

**Request:**
```json
{"type": "<command_type>", ...params}
```

**Response:** `200 {"ok": true}` / `400 {"error": "..."}`

**Command Types:**

| type | params | 설명 |
|------|--------|------|
| `create_node` | `node_type`, `x?`, `y?` | 노드 생성 |
| `remove_node` | `node_id` | 노드 삭제 |
| `connect` | `from_id`, `from_slot`, `to_id`, `to_slot` | 노드 연결 |
| `disconnect` | `node_id`, `slot` | 입력 연결 해제 |
| `set_widget` | `node_id`, `name`, `value` | 위젯 값 변경 |
| `move_node` | `node_id`, `x`, `y` | 노드 위치 이동 |
| `clear_graph` | — | 그래프 전체 초기화 |
| `load_graph` | `graph_data` | 직렬화된 그래프 로드 |

**슬롯 번호:** `output`/`input` 배열의 0-based 인덱스. `GET /comfy/graph/node_types`로 확인 가능.

---

### POST /comfy/graph/batch

여러 명령을 순서대로 실행한다. type 없는 명령은 건너뛰고 errors에 기록.

**Request:**
```json
{
  "commands": [
    {"type": "create_node", "node_type": "KSampler", "x": 100, "y": 100},
    {"type": "set_widget", "node_id": 1, "name": "steps", "value": 30}
  ]
}
```

**Response:**
```json
{"ok": true, "count": 2, "errors": []}
```

부분 실패 시:
```json
{"ok": true, "count": 1, "errors": [{"index": 1, "error": "missing field: type"}]}
```

---

### GET /comfy/graph/node_types

등록된 노드 타입과 입출력 정보를 반환한다 (서버 직접 응답, 브라우저 불필요).

**Query Params:**
- `category` (선택) — 카테고리 필터. 예: `?category=Midjourney`

**Response:**
```json
{
  "KSampler": {
    "input": {
      "required": {
        "model": ["MODEL", {}],
        "steps": ["INT", {"default": 20}]
      }
    },
    "output": ["LATENT"],
    "category": "sampling"
  }
}
```

`output` 배열의 인덱스가 `connect` 명령의 `from_slot`/`to_slot` 번호이다.
`input.required`의 키 순서가 `to_slot` 번호이다.

---

### POST /comfy/graph/queue

prompt를 ComfyUI 실행 큐에 전달한다.

**Request:**
```json
{"prompt": {"1": {"class_type": "KSampler", "inputs": {...}}}}
```

**Response:**
```json
{"ok": true, "prompt_id": "abc-123"}
```

---

### POST /comfy/graph/save

그래프를 JSON 파일로 저장한다. `saved_graphs/` 디렉토리에 저장. 경로 탐색(`../`) 차단.

**Request:**
```json
{"filename": "my_workflow.json", "graph": {...}}
```

**Response:** `200 {"ok": true}` / `400 {"error": "..."}`

---

### POST /comfy/graph/load

저장된 JSON 파일에서 그래프를 로드하고 브라우저에 전달한다.

**Request:**
```json
{"filename": "my_workflow.json"}
```

**Response:**
```json
{"ok": true, "graph": {...}}
```

`404` — 파일 없음

---

### POST /comfy/graph/state (내부용)

브라우저 JS가 WS 요청 결과를 서버에 회신할 때 사용. 외부에서 직접 호출할 일 없음.

**Request:**
```json
{"request_id": "uuid", "data": {...}}
```

---

## WebSocket Endpoint

### WS /comfy/graph/ws

양방향 요청-응답. request_id 기반으로 브라우저 상태를 조회한다.

**연결:** `ws://localhost:8188/comfy/graph/ws`

**Request (client → server):**
```json
{"request_id": "uuid-1", "type": "get_graph"}
```

**Response (server → client):**
```json
{
  "request_id": "uuid-1",
  "status": "ok",
  "data": {"nodes": [...], "links": [...]}
}
```

**Error (timeout 5s):**
```json
{
  "request_id": "uuid-1",
  "status": "error",
  "message": "timeout"
}
```

**WS Request Types:**

| type | 설명 |
|------|------|
| `get_graph` | 현재 그래프 직렬화 데이터 반환 |
| 기타 command type | 해당 명령 실행 후 `{"executed": true}` 반환 |

---

## Error Format

모든 에러는 동일한 형식:
```json
{"error": "설명 메시지"}
```

| HTTP Status | 의미 |
|-------------|------|
| 400 | 잘못된 요청 (JSON 파싱 실패, 필수 필드 누락) |
| 404 | 리소스 없음 (파일 미존재) |
| 200 | 성공 (브라우저 미연결 시에도 200, 명령은 유실) |

---

## Data Flow

```
외부 클라이언트
  │
  ├─ HTTP POST /command, /batch ──→ 서버 ──→ WS broadcast ──→ 브라우저 LiteGraph
  │                                                            (fire-and-forget)
  │
  ├─ HTTP GET /node_types ────────→ 서버 직접 응답
  │
  └─ WS /comfy/graph/ws ─────────→ 서버 ──→ WS broadcast ──→ 브라우저
                                     ↑                          │
                                     └── POST /state ───────────┘
                                         (브라우저가 결과 회신)
```
