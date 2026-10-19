# Web Frontend

> **狀態**: Phase 5 已完成，Phase 6A 的 Agent Console 與批次分析頁亦已併入。

## 技術選型

- React 18
- Vite
- React Router v7
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
- `AgentPage`（`/agent`，使用 SSE streaming；與一般對話共用 AI 助理入口，維持獨立頁面）
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

## 2026-10-15 Web UX 改善

手機導覽／聊天面板、鍵盤對話框、已保存結果分析選擇、批次錯誤恢復與首頁工作流程已分 A／B／C 改善。
- 設計規範：[DESIGN.md](DESIGN.md)
- 改善內容與回歸方法：[web-ui-improvements.md](../docs/web-ui-improvements.md)
- A／B／C UI 測試使用隔離示範 API；後續真實 MySQL、YOLO 與本機 LLM 驗收另見 [web-real-integration-validation.md](../docs/web-real-integration-validation.md)，含未覆蓋項目。

## AI 助理入口

主選單與工作台只有一個「AI 助理」入口；頁內「一般對話」走 `/chat`，「偵測分析」走 `/agent`，沿用各自 service。既有帶 `mode` / `detection_id` / `batch_id` 的分析捷徑保持有效。

分頁切換保留各自草稿、對話、模型及分析結果選擇；離開 AI 工作區、重新整理或登出會清除記憶體暫存。生成中切換會停止前端接收並保留部分回覆，後端可能仍在執行。
