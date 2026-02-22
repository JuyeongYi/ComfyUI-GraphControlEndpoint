import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "Comfy.GraphControlEndpoint",
    async setup() {
        console.log("[GraphControlEndpoint] 확장 로드 완료");
    },
});
