import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

/**
 * 그래프 명령을 처리한다 (단방향, fire-and-forget).
 * @param {object} cmd - {type, ...params}
 */
function handleGraphCommand(cmd) {
    const graph = app.graph;
    if (!graph) {
        console.warn("[GraphControlEndpoint] graph가 아직 초기화되지 않음");
        return;
    }

    switch (cmd.type) {
        case "create_node": {
            const node = LiteGraph.createNode(cmd.node_type);
            if (!node) {
                console.warn(`[GraphControlEndpoint] 알 수 없는 노드 타입: ${cmd.node_type}`);
                return;
            }
            node.pos = [cmd.x || 0, cmd.y || 0];
            graph.add(node);
            break;
        }
        case "remove_node": {
            const node = graph.getNodeById(cmd.node_id);
            if (node) graph.remove(node);
            break;
        }
        case "connect": {
            const fromNode = graph.getNodeById(cmd.from_id);
            const toNode = graph.getNodeById(cmd.to_id);
            if (fromNode && toNode) {
                fromNode.connect(cmd.from_slot, toNode, cmd.to_slot);
            }
            break;
        }
        case "disconnect": {
            const node = graph.getNodeById(cmd.node_id);
            if (node) node.disconnectInput(cmd.slot);
            break;
        }
        case "set_widget": {
            const node = graph.getNodeById(cmd.node_id);
            if (!node) break;
            const widget = node.widgets?.find(w => w.name === cmd.name);
            if (widget) {
                widget.value = cmd.value;
                widget.callback?.(widget.value);
            }
            break;
        }
        case "move_node": {
            const node = graph.getNodeById(cmd.node_id);
            if (node) node.pos = [cmd.x, cmd.y];
            break;
        }
        case "clear_graph": {
            graph.clear();
            break;
        }
        case "load_graph": {
            if (cmd.graph_data) {
                graph.configure(cmd.graph_data);
            }
            break;
        }
        default:
            console.warn(`[GraphControlEndpoint] 알 수 없는 명령: ${cmd.type}`);
            return;
    }

    graph.setDirtyCanvas(true, true);
}

/**
 * WS 양방향 요청을 처리하고 결과를 서버에 회신한다.
 * @param {object} req - {request_id, type, ...params}
 */
async function handleWsRequest(req) {
    const graph = app.graph;
    let result = {};

    try {
        switch (req.type) {
            case "get_graph": {
                result = graph ? graph.serialize() : {};
                break;
            }
            default:
                // 일반 명령도 WS를 통해 올 수 있음
                handleGraphCommand(req);
                result = { executed: true };
        }
    } catch (e) {
        result = { error: e.message };
    }

    // 서버에 결과 회신
    try {
        await fetch("/comfy/graph/state", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                request_id: req.request_id,
                data: result,
            }),
        });
    } catch (e) {
        console.error("[GraphControlEndpoint] 상태 회신 실패:", e);
    }
}

app.registerExtension({
    name: "Comfy.GraphControlEndpoint",
    async setup() {
        // 단방향 명령 수신
        api.addEventListener("graph_command", (event) => {
            handleGraphCommand(event.detail);
        });

        // WS 양방향 요청 수신
        api.addEventListener("graph_ws_request", (event) => {
            handleWsRequest(event.detail);
        });

        console.log("[GraphControlEndpoint] 확장 로드 완료");
    },
});
