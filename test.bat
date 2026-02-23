@echo off
chcp 65001 >nul

echo [TEST 1] batch: clear + create MJ_Imagine + create MJ_Pan + connect
curl.exe -X POST http://localhost:8188/comfy/graph/batch -H "Content-Type: application/json" -d "{\"commands\":[{\"type\":\"clear_graph\"},{\"type\":\"create_node\",\"node_type\":\"MJ_Imagine\",\"x\":100,\"y\":200},{\"type\":\"create_node\",\"node_type\":\"MJ_Pan\",\"x\":600,\"y\":200},{\"type\":\"connect\",\"from_id\":1,\"from_slot\":4,\"to_id\":2,\"to_slot\":0}]}"
echo.

echo.

pause
