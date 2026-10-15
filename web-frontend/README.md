# Web Frontend

> **狀態**: Phase 5 Web MVP 已建立，API / runtime 驗證完成，待人工瀏覽器最終驗收。

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
- `DetectionHistoryPage`
- `ProfilePage`
- `ChatPage`
- `admin/UserManagementPage`

## 啟動方式

```bash
cd /Users/SAM/Desktop/Agents/Yolo_system/web-frontend
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
- 本次 UI 測試使用隔離示範 API；真實 YOLO、LLM 與 DB 整合仍需在正式開發環境驗證。
