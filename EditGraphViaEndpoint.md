# ComfyUI 외부에서 노드 에디터 제어하기

외부 프로세스(Python 스크립트, MCP 서버 등)에서 HTTP 요청을 보내
브라우저의 LiteGraph 노드 에디터를 원격으로 조작하는 방법.

---

## 핵심 원리

ComfyUI 노드 에디터(그래프)는 **순수 클라이언트 사이드(브라우저 메모리)** 에만 존재한다.
서버(Python)는 그래프 상태를 모른다 — 실행할 prompt만 받을 뿐이다.

따라서 외부 → 에디터 제어는 **서버를 중계자로** 쓴다:

```
외부 클라이언트
    │  POST /comfy/graph/command  (HTTP)
    ▼
ComfyUI 서버 (Python, aiohttp)
    │  send_sync("graph_command", data)  →  WebSocket 브로드캐스트
    ▼
브라우저 (JavaScript extension)
    │  api.addEventListener("graph_command", handler)
    ▼
LiteGraph 조작 (노드 생성 / 연결 / 위젯 설정 / 삭제 등)
```

---

## 1. 백엔드 — HTTP 엔드포인트 등록

### 파일: `nodes/graph_control.py` (또는 `__init__.py` 임포트)

```python
from aiohttp import web
from server import PromptServer

@PromptServer.instance.routes.post("/comfy/graph/command")
async def graph_command(request: web.Request) -> web.Response:
    """
    외부에서 LiteGraph 에디터에 명령을 보내는 엔드포인트.
    JSON body: { "type": <command>, ...args }
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)

    if "type" not in data:
        return web.json_response({"error": "missing field: type"}, status=400)

    # sid=None → 연결된 모든 브라우저 클라이언트에 브로드캐스트
    await PromptServer.instance.send("graph_command", data)

    return web.json_response({"ok": True})
```

### 등록 타이밍
커스텀 노드는 ComfyUI 서버 시작 후 로드되므로 모듈 임포트 시점에 `@routes.post()`
데코레이터가 실행되면 안전하게 등록된다.
(`__init__.py`에서 `nodes/graph_control.py`를 임포트하면 자동 등록.)

### send vs send_sync 선택
| 상황 | 메서드 |
|------|--------|
| `async def` 핸들러 내부 | `await PromptServer.instance.send(...)` |
| 동기 함수 / 스레드 풀 내부 | `PromptServer.instance.send_sync(...)` |

`send_sync`는 내부적으로 `loop.call_soon_threadsafe(messages.put_nowait, ...)`를 호출해
이벤트 루프에 안전하게 큐잉한다.

---

## 2. WebSocket 메시지 형식

서버→브라우저로 전송되는 JSON:
```json
{
    "type": "graph_command",
    "data": {
        "type": "create_node",
        "node_type": "MJ_Imagine",
        "x": 200,
        "y": 300
    }
}
```

`data` 필드가 실제 명령 내용. `type` 최상위 필드는 WebSocket 이벤트 이름.

---

## 3. 프론트엔드 — 이벤트 수신 및 LiteGraph 조작

### 파일: `web/graph_control.js`

```js
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "MyPlugin.GraphControl",

    async setup() {
        // ComfyAPI는 EventTarget을 상속.
        // addEventListener로 커스텀 이벤트 타입을 등록하면
        // 서버에서 해당 type의 WebSocket 메시지가 오면 자동으로 발화된다.
        api.addEventListener("graph_command", ({ detail }) => {
            handleGraphCommand(detail);
        });
    },
});

function handleGraphCommand(cmd) {
    const graph = app.graph;

    switch (cmd.type) {

        // ── 노드 생성 ──────────────────────────────────────────
        case "create_node": {
            // cmd: { node_type, x?, y? }
            const node = LiteGraph.createNode(cmd.node_type);
            if (!node) {
                console.warn("[GraphControl] Unknown node type:", cmd.node_type);
                return;
            }
            graph.add(node);
            if (cmd.x != null) node.pos[0] = cmd.x;
            if (cmd.y != null) node.pos[1] = cmd.y;
            break;
        }

        // ── 노드 삭제 ──────────────────────────────────────────
        case "remove_node": {
            // cmd: { node_id }
            const node = graph.getNodeById(cmd.node_id);
            if (node) graph.remove(node);
            break;
        }

        // ── 노드 연결 ──────────────────────────────────────────
        case "connect": {
            // cmd: { from_id, from_slot, to_id, to_slot }
            const src = graph.getNodeById(cmd.from_id);
            const dst = graph.getNodeById(cmd.to_id);
            if (!src || !dst) {
                console.warn("[GraphControl] connect: node not found", cmd);
                return;
            }
            src.connect(cmd.from_slot, dst, cmd.to_slot);
            break;
        }

        // ── 연결 해제 ──────────────────────────────────────────
        case "disconnect": {
            // cmd: { node_id, slot }  (입력 슬롯 기준)
            const node = graph.getNodeById(cmd.node_id);
            if (node) node.disconnectInput(cmd.slot);
            break;
        }

        // ── 위젯 값 변경 ───────────────────────────────────────
        case "set_widget": {
            // cmd: { node_id, name, value }
            const node = graph.getNodeById(cmd.node_id);
            if (!node) return;
            const w = node.widgets?.find(w => w.name === cmd.name);
            if (w) {
                w.value = cmd.value;
                w.callback?.(cmd.value);   // 값 변경 콜백 트리거 (미리보기 갱신 등)
            }
            break;
        }

        // ── 노드 위치 이동 ─────────────────────────────────────
        case "move_node": {
            // cmd: { node_id, x, y }
            const node = graph.getNodeById(cmd.node_id);
            if (node) node.pos = [cmd.x, cmd.y];
            break;
        }

        // ── 그래프 전체 초기화 ─────────────────────────────────
        case "clear_graph": {
            graph.clear();
            break;
        }

        // ── 그래프 상태 읽기 (응답 필요 시 별도 엔드포인트 필요) ──
        case "get_graph": {
            // 서버로 보내려면 fetch를 사용
            const serialized = graph.serialize();
            fetch("/comfy/graph/state", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(serialized),
            });
            break;
        }

        default:
            console.warn("[GraphControl] Unknown command:", cmd.type);
    }

    graph.setDirtyCanvas(true, true);
}
```

### `api.addEventListener` 동작 원리
- `ComfyApi`는 `EventTarget`을 상속.
- WebSocket 메시지 수신 시 `msg.type`이 `_registered` 셋에 있으면
  `new CustomEvent(msg.type, { detail: msg.data })`를 디스패치.
- `addEventListener("graph_command", ...)` 호출만으로 해당 타입이 자동 등록된다.
- `event.detail`이 서버에서 보낸 `data` 필드 값.

---

## 4. 그래프 상태 읽기 (역방향)

브라우저 → 서버 방향도 필요하면 추가 엔드포인트를 만든다:

**백엔드:**
```python
_last_graph_state: dict = {}

@PromptServer.instance.routes.post("/comfy/graph/state")
async def receive_graph_state(request: web.Request) -> web.Response:
    global _last_graph_state
    _last_graph_state = await request.json()
    return web.json_response({"ok": True})

@PromptServer.instance.routes.get("/comfy/graph/state")
async def get_graph_state(request: web.Request) -> web.Response:
    # 먼저 브라우저에 state 요청 명령 전송
    await PromptServer.instance.send("graph_command", {"type": "get_graph"})
    # 비동기 응답 대기 (간단 구현: 짧게 sleep 후 반환)
    import asyncio
    await asyncio.sleep(0.3)
    return web.json_response(_last_graph_state)
```

---

## 5. 외부 클라이언트 사용 예시

### curl
```bash
# 노드 생성
curl -s -X POST http://localhost:8188/comfy/graph/command \
  -H "Content-Type: application/json" \
  -d '{"type": "create_node", "node_type": "MJ_Imagine", "x": 100, "y": 200}'

# 위젯 값 변경 (node_id는 LiteGraph 내부 id)
curl -s -X POST http://localhost:8188/comfy/graph/command \
  -d '{"type": "set_widget", "node_id": 3, "name": "prompt", "value": "a cat"}'

# 노드 연결 (MJ_Imagine의 출력 슬롯 4 → MJ_Vary의 입력 슬롯 0)
curl -s -X POST http://localhost:8188/comfy/graph/command \
  -d '{"type": "connect", "from_id": 1, "from_slot": 4, "to_id": 2, "to_slot": 0}'
```

### Python
```python
import requests

BASE = "http://localhost:8188"

def graph_cmd(cmd: dict) -> dict:
    resp = requests.post(f"{BASE}/comfy/graph/command", json=cmd, timeout=5)
    resp.raise_for_status()
    return resp.json()

# 노드 생성
graph_cmd({"type": "create_node", "node_type": "MJ_Imagine", "x": 100, "y": 100})

# 위젯 값 변경
graph_cmd({"type": "set_widget", "node_id": 1, "name": "prompt", "value": "a futuristic city"})

# 노드 연결
graph_cmd({"type": "connect", "from_id": 1, "from_slot": 4, "to_id": 2, "to_slot": 0})

# 현재 그래프 상태 조회
state = requests.get(f"{BASE}/comfy/graph/state").json()
```

---

## 6. LiteGraph 주요 API 레퍼런스

| 작업 | LiteGraph API |
|------|--------------|
| 노드 생성 | `LiteGraph.createNode(type_name)` |
| 그래프에 추가 | `graph.add(node)` |
| 노드 삭제 | `graph.remove(node)` |
| ID로 노드 조회 | `graph.getNodeById(id)` |
| 출력 연결 | `srcNode.connect(out_slot, dstNode, in_slot)` |
| 입력 연결 해제 | `node.disconnectInput(slot)` |
| 위젯 목록 | `node.widgets` (배열, `w.name` / `w.value`) |
| 노드 위치 | `node.pos = [x, y]` |
| 노드 크기 | `node.size` (읽기 전용에 가까움, `node.setSize([w,h])` 사용) |
| 그래프 직렬화 | `graph.serialize()` → `{ nodes: [...], links: [...] }` |
| 그래프 로드 | `graph.configure(serialized)` |
| 캔버스 갱신 | `graph.setDirtyCanvas(true, true)` |
| 전체 초기화 | `graph.clear()` |

### node.id vs LiteGraph 내부 ID
- `graph.add(node)` 호출 후 `node.id`에 LiteGraph가 부여한 정수 ID가 설정된다.
- 외부에서 이 ID를 알려면 노드 생성 직후 JS 측에서 서버로 보고하거나,
  `/comfy/graph/state` 역방향 API로 `graph.serialize()`를 가져와 파싱한다.

---

## 7. 프로젝트 파일 구조

새 저장소로 분리할 경우 최소 구성:

```
comfy-graph-control/
├── __init__.py              # comfy_entrypoint() + 라우트 임포트
├── nodes/
│   └── graph_control.py     # POST /comfy/graph/command 엔드포인트
└── web/
    └── graph_control.js     # api.addEventListener + handleGraphCommand
```

`__init__.py` 핵심:
```python
WEB_DIRECTORY = "./web"   # JS 자동 로드

def comfy_entrypoint():
    from .nodes import graph_control  # 임포트 시 라우트 등록
    return MyExtension()
```

---

## 8. 주의사항

- **node_id 동기화**: LiteGraph의 node.id는 브라우저 세션마다 다를 수 있다.
  신뢰할 수 있는 식별자가 필요하면 노드 생성 후 JS→서버로 id를 보고하는 패턴을 추가해야 한다.
- **멀티 탭**: `sid=None` 브로드캐스트는 열린 모든 ComfyUI 탭에 명령이 전달된다.
  특정 탭만 제어하려면 클라이언트 `sid`를 파악해 유니캐스트해야 한다.
- **경쟁 조건**: `get_graph` 명령 후 상태 응답을 기다리는 방식은 단순 구현용.
  프로덕션에서는 asyncio.Event 또는 WebSocket 요청-응답 패턴이 필요하다.
- **CORS**: 외부 도메인에서 접근 시 aiohttp CORS 설정이 필요하다
  (`aiohttp_cors` 패키지 사용).
