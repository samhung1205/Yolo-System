# Web Frontend

> **狀態**: Phase 5 已完成，Phase 6A 的 Agent Console 與批次分析頁亦已併入。

## 技術選型

- React 18
- Vite
- React Router v6
- Axios
- 簡單 CSS

## 目前已建立頁面

- `LoginPage`
- `RegisterPage`
- `DashboardPage`
- `DetectionPage`
- `BatchDetectionPage`
- `DetectionHistoryPage`
- `ProfilePage`
- `ChatPage`
- `AgentPage`（`/agent`，使用 SSE streaming）
- `admin/UserManagementPage`

## 啟動方式

```bash
cd web-frontend
npm install
npm run dev
```

若 backend 不在 `http://127.0.0.1:8000`，可用 `.env` 設定：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8001
VITE_PROXY_TARGET=http://127.0.0.1:8001
```

標準本地驗證組合：
```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_PROXY_TARGET=http://127.0.0.1:8000
npm run dev -- --host 127.0.0.1 --port 5173
```
