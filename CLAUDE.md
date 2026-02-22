# ComfyUI-GraphControlEndpoint

HTTP/WebSocket을 통해 외부에서 ComfyUI LiteGraph 노드 에디터를 원격 제어하는 커스텀 익스텐션.

## Project Structure

```
├── __init__.py              # WEB_DIRECTORY 설정, 라우트 임포트
├── nodes/
│   └── graph_control.py     # HTTP 엔드포인트 (command, batch, node_types, queue, save, load)
├── ws/
│   └── graph_ws.py          # WebSocket 엔드포인트 (/comfy/graph/ws)
├── web/
│   └── graph_control.js     # 브라우저 JS 확장 (이벤트 수신 + LiteGraph 조작)
└── docs/plans/              # 설계 문서
```

## Architecture

- **명령 전송**: HTTP POST → 서버 → WebSocket 브로드캐스트 → 브라우저 LiteGraph
- **상태 조회**: 별도 WS `/comfy/graph/ws` (request_id 기반 요청-응답)
- **노드 타입 조회**: 서버에서 직접 응답 (ComfyUI의 NODE_CLASS_MAPPINGS 활용)

## Key APIs

- `PromptServer.instance.send(event_type, data)` — async WebSocket 브로드캐스트
- `PromptServer.instance.send_sync(event_type, data)` — 동기 컨텍스트용
- `api.addEventListener(event_type, handler)` — 브라우저 JS에서 WS 이벤트 수신

## Conventions

- 언어: 한국어 (코드 주석, 커밋 메시지)
- 주 사용처: MCP 서버 연동 (AI 에이전트가 그래프를 원격 조작)
- 엔드포인트 prefix: `/comfy/graph/`
- 에러 응답: `{"error": "message"}` with appropriate HTTP status
