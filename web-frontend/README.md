# Web 前端開發說明

使用者操作見 [使用手冊](../README.md)，本文件提供 React 前端開發資訊。

## 技術與啟動

React 18、React Router 7、Axios、原生 CSS；Vite 8.3.4／React plugin 6.1.2。Node.js 最低 20.19 或 22.12，建議使用相容的 Node 22。

```bash
cd web-frontend
npm ci --include=dev
npm run dev -- --host 127.0.0.1 --port 5173
```

後端預設 `http://127.0.0.1:8000`。如需覆寫，在未入版控的開發設定中使用：

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8001
VITE_PROXY_TARGET=http://127.0.0.1:8001
```

正式 build 使用相對 API，不把後端私人連線資料放進前端：

```bash
VITE_API_BASE_URL='' npm run build
```

網站由正式 Caddy image 提供；build 通過不等於已更新伺服器。現行部署見 [維運操作](../docs/lab-operations.md)。

## 頁面與共用規則

路由定義於 `src/router/index.jsx`：登入／註冊、工作台、單圖／批次／歷史、Profile、Chat、Agent 與管理員使用者頁。`/register` 是否可用由後端政策決定，正式環境關閉。

「AI 助理」是共用導覽入口，`/chat` 與 `/agent` 維持獨立頁面、端點與 service。`AssistantWorkspace` 保留工作區記憶體中的分開草稿、模型與資料選擇；離開、重新整理或登出清除。停止接收不保證後端停止。

沿用 `services/api.js` 共用 Axios，設計依 [DESIGN.md](DESIGN.md)；不要新增第二套 API instance 或 UI framework。改 UI 後 build 並驗證操作、手機版與鍵盤。

- [架構](../docs/architecture.md)
- [API 規格](../docs/api-spec.md)
- [歷史 UI 改善](../docs/archive/reports/web-ui-improvements-20261016.md)
- [歷史真實整合驗證](../docs/archive/reports/web-integration-validation-20261015.md)
- [文件同步政策](../docs/documentation-policy.md)
