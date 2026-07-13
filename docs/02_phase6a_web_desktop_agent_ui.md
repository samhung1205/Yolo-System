# Phase 6A-2 — Web Frontend and Desktop Agent UI Integration

你現在要協助重構一個 YOLO System 專案。這個專案目前包含：

1. FastAPI Backend
2. PySide6 Desktop App
3. React + Vite Web Frontend
4. MySQL database
5. YOLO detection service
6. Provider-based chat service
7. Auth / Users / Upload / Detection History / Chat / Admin Users

本階段任務是 **Web Frontend 與 Desktop 的 Agent UI 整合**。

請注意：本階段應在 Phase 6A-1 Backend Agentic Layer 完成後執行。也就是後端已經提供：

- `POST /api/agent/chat`
- `GET /api/agent/modes`
- `desktop-app/api_client.py` 已有或即將新增 `agent_chat(...)`

---

## 一、核心原則

1. 不要修改 YOLO inference 核心。
2. 不要改壞原本 `/chat` 頁面。
3. 不要改壞原本 `chatService.js`。
4. `/chat` 繼續使用 `/api/chat`。
5. 新增 `/agent` 作為獨立智慧助理頁面。
6. `/agent` 使用 `/api/agent/chat`。
7. Detection 結果頁與 History detail 可以提供一鍵跳轉到 Agent 解釋或報告。
8. Desktop 採最小整合，不要大改 PySide6 UI。
9. 前端 UI 風格沿用現有 `styles.css`，不要引入新的 UI framework。
10. 不要重複建立 Axios instance，必須沿用既有 `api.js`。

本階段名稱：

> Phase 6A-2 — Web Frontend and Desktop Agent UI Integration

---

## 二、請先閱讀並理解以下檔案

Backend 只需確認 API 介面，不要大改：

1. `backend/app/api/routes/agents.py`
2. `backend/app/schemas/agent.py`
3. `docs/api-spec.md`

Desktop：

4. `desktop-app/api_client.py`
5. `AICSMain.py`
6. `MainUI.py`

Web Frontend：

7. `web-frontend/package.json`
8. `web-frontend/src/App.jsx`
9. `web-frontend/src/main.jsx`
10. `web-frontend/src/router/index.jsx`
11. `web-frontend/src/components/Layout.jsx`
12. `web-frontend/src/components/ProtectedRoute.jsx`
13. `web-frontend/src/services/api.js`
14. `web-frontend/src/services/authService.js`
15. `web-frontend/src/services/chatService.js`
16. `web-frontend/src/services/detectionService.js`
17. `web-frontend/src/services/userService.js`
18. `web-frontend/src/pages/ChatPage.jsx`
19. `web-frontend/src/pages/DetectionPage.jsx`
20. `web-frontend/src/pages/DetectionHistoryPage.jsx`
21. `web-frontend/src/pages/DashboardPage.jsx`
22. `web-frontend/src/pages/ProfilePage.jsx`
23. `web-frontend/src/pages/admin/UserManagementPage.jsx`
24. `web-frontend/src/styles.css`

---

## 三、目標 Web Frontend 架構

請新增與更新：

```text
web-frontend/src/
├── services/
│   └── agentService.js
├── pages/
│   └── AgentPage.jsx
├── router/index.jsx
├── components/Layout.jsx
├── pages/DashboardPage.jsx
├── pages/DetectionPage.jsx
├── pages/DetectionHistoryPage.jsx
└── styles.css
```

---

## 四、新增 agentService.js

新增：

`web-frontend/src/services/agentService.js`

內容需求：

### 1. sendAgentMessage

```javascript
sendAgentMessage(message, options)
```

應呼叫：

```text
POST /api/agent/chat
```

payload：

```json
{
  "message": "...",
  "conversation_id": "...",
  "mode": "auto",
  "detection_id": 123
}
```

`options` 可以包含：

- `conversationId`
- `mode`
- `detectionId`
- `stream`

### 2. listAgentModes

```javascript
listAgentModes()
```

應呼叫：

```text
GET /api/agent/modes
```

要求：

1. 沿用既有 `api.js` 的 axios instance。
2. 不要重寫 token interceptor。
3. 不要修改 `chatService.js`。
4. 不要讓 `/chat` 改用 `agentService.js`。

---

## 五、新增 AgentPage.jsx

新增：

`web-frontend/src/pages/AgentPage.jsx`

這是一個獨立 Agent 智慧助理頁，不要直接取代原本 `ChatPage.jsx`。

頁面功能：

1. mode 下拉選單：
   - `auto`
   - `general_chat`
   - `explain_detection`
   - `history_analysis`
   - `report`
   - `admin_help`
2. optional `detection_id` 輸入欄
3. message textarea
4. send button
5. 顯示對話 thread
6. 顯示 agent answer
7. 顯示目前 response mode
8. 顯示 references / tool_calls，如果後端有回傳
9. 若 mode = `admin_help`，但目前 user 不是 admin，前端可以提示此模式僅管理員可用
10. 仍要以後端權限檢查為準
11. 初版不需要 streaming

AgentPage 必須支援 URL query params：

- `mode`
- `detection_id`

例如：

```text
/agent?mode=explain_detection&detection_id=123
```

要求：

1. 若 URL 帶入 `mode`，頁面自動選擇該 mode。
2. 若 URL 帶入 `detection_id`，頁面自動填入欄位。
3. 如果 mode 是 `explain_detection` 或 `report` 且有 detection_id，可以提供預設 message，例如：
   - `請解釋這筆 detection 結果`
   - `請幫我產生這筆 detection 的 markdown 報告`
4. 初版送出後只需要 append 到本地 messages state，不一定要先做完整 conversation list。
5. 後端仍需儲存到 chat_logs。

---

## 六、更新 router/index.jsx

更新：

`web-frontend/src/router/index.jsx`

新增 route：

```text
/agent -> AgentPage
```

要求：

1. 記得 import `AgentPage`。
2. `/agent` 需要登入後才能使用，請套用既有 ProtectedRoute 機制。
3. 不要動壞現有：
   - `/login`
   - `/register`
   - `/`
   - `/detections`
   - `/detections/history`
   - `/chat`
   - `/profile`
   - `/admin/users`

---

## 七、更新 Layout.jsx

更新：

`web-frontend/src/components/Layout.jsx`

在 NAV_ITEMS 或現有側邊欄/導覽列加入：

```javascript
{ to: "/agent", label: "AI Agent" }
```

要求：

1. `/agent` 對一般使用者也可見。
2. admin_help 是 mode 權限，不是 route 權限。
3. 不要把 `/chat` 改名成 `/agent`。
4. 保留原本 Chat 導覽項目。

---

## 八、更新 DashboardPage.jsx

更新：

`web-frontend/src/pages/DashboardPage.jsx`

新增一張 card：

標題：

```text
AI Agent
```

說明：

```text
使用 LangGraph Agent 分析 detection results、history，並產生報告。
```

按鈕：

```text
Open Agent
```

導向：

```text
/agent
```

要求：

1. 沿用現有 dashboard card 風格。
2. 不要大改 dashboard layout。
3. 不要引入新 UI framework。

---

## 九、更新 DetectionPage.jsx

更新：

`web-frontend/src/pages/DetectionPage.jsx`

當圖片偵測完成並得到 `result.id` 後，在結果區新增按鈕：

1. `Ask Agent to Explain`
2. `Generate Report`

點擊後導向：

```text
/agent?mode=explain_detection&detection_id={result.id}
```

以及：

```text
/agent?mode=report&detection_id={result.id}
```

要求：

1. 只有在 `result.id` 存在時才顯示。
2. 不要影響原本 detection upload / result render。
3. 不要改變原本 detection API 呼叫流程。
4. 不要讓 Agent 按鈕自動重新執行 YOLO detection。
5. Agent 只解釋既有 detection result。

---

## 十、更新 DetectionHistoryPage.jsx

更新：

`web-frontend/src/pages/DetectionHistoryPage.jsx`

當 selected detection 存在時，在 Selected Detail 區塊新增兩個按鈕：

1. `Explain with Agent`
2. `Generate Report`

導向：

```text
/agent?mode=explain_detection&detection_id={selected.id}
```

以及：

```text
/agent?mode=report&detection_id={selected.id}
```

要求：

1. 只有在 selected detection 存在時顯示。
2. 不要破壞原本 history list / selected detail。
3. 不要改變原本 detection history API 呼叫流程。
4. Agent 只解釋既有 detection result。

---

## 十一、更新 styles.css

更新：

`web-frontend/src/styles.css`

新增 AgentPage 所需最小 CSS。

請沿用現有風格，例如：

- `page-stack`
- `page-header`
- `panel`
- `chat-layout`
- `chat-sidebar`
- `chat-main`
- `chat-thread`
- `chat-bubble`
- `button`
- `field`
- `alert`

可以新增：

- `agent-layout`
- `agent-controls`
- `agent-thread`
- `agent-message`
- `agent-message-user`
- `agent-message-assistant`
- `agent-meta`
- `agent-tool-calls`
- `agent-reference-list`

要求：

1. 不要引入 Tailwind。
2. 不要引入 MUI / Ant Design / Chakra。
3. 不要大改全域樣式。
4. 不要讓現有頁面版面跑掉。

---

## 十二、Desktop 整合

若 Phase 6A-1 尚未完成，請先更新：

`desktop-app/api_client.py`

新增：

```python
agent_chat(
    access_token,
    message,
    conversation_id=None,
    mode="auto",
    detection_id=None,
)
```

若 Phase 6A-1 已經完成，請檢查此 method 是否存在。

本階段 Desktop UI 採最小整合：

1. 不強制新增完整 PySide6 Agent 對話 UI。
2. 若要新增，請只做簡單入口或內部開關。
3. 預設仍保留原本 `/api/chat`。
4. 不要破壞既有 login / detection / chat / history 功能。
5. 若沒有 UI 整合，請在文件標註 Desktop Agent UI 為下一階段。

---

## 十三、文件更新

更新以下文件：

### 1. README.md

新增：

- Phase 6A-2 狀態
- Web Agent Console 說明
- `/agent` 頁面說明
- Web frontend 啟動方式
- Agent shortcuts 說明

### 2. docs/architecture.md

補上 Web frontend 入口：

- `/chat`：一般 provider-based chat
- `/agent`：LangGraph agent assistant
- DetectionPage 可以跳轉 Agent explanation
- DetectionHistoryPage 可以跳轉 Agent report

### 3. docs/api-spec.md

確認已有：

- `POST /api/agent/chat`
- `GET /api/agent/modes`

若已存在，不要重複新增，只需補上 Web frontend 使用說明。

### 4. docs/roadmap.md

新增 Phase 6A-2 checklist：

- `agentService.js`
- `AgentPage.jsx`
- `/agent` route
- Layout navigation
- Dashboard Agent card
- Detection result shortcuts
- History detail shortcuts
- Desktop minimal integration
- Web build verification

### 5. AGENTS.md

補充 AI coding agent 注意事項：

- Web frontend 的 `/chat` 與 `/agent` 要分開，不可互相覆蓋
- 不要讓 Agent UI 重新執行 YOLO detection
- Agent 只解釋既有 detection result
- 不要引入新 UI framework
- 不要重寫 axios interceptor

---

## 十四、驗證方式

完成後請提供以下驗證步驟。

### Backend API 確認

確認 Phase 6A-1 後端仍可啟動：

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Swagger 確認：

```text
http://127.0.0.1:8000/docs
```

確認存在：

- `POST /api/agent/chat`
- `GET /api/agent/modes`

### Web Frontend

#### 1. 安裝與啟動

```bash
cd web-frontend
npm install
npm run dev
```

#### 2. Build 檢查

```bash
npm run build
```

#### 3. 瀏覽器驗證

確認以下頁面正常：

- `/login`
- `/`
- `/detections`
- `/detections/history`
- `/chat`
- `/agent`
- `/admin/users`

#### 4. Agent UI 驗證

確認：

1. `/agent` 可載入。
2. 可選 mode。
3. 可輸入 message。
4. 可輸入 detection_id。
5. 可呼叫 `/api/agent/chat`。
6. 可顯示 answer。
7. 可顯示 tool_calls / references，如果後端有回傳。
8. `/chat` 仍然使用原本 chat 功能。

#### 5. DetectionPage shortcuts

完成一筆圖片 detection 後，確認：

1. `Ask Agent to Explain` 按鈕出現。
2. 點擊後跳轉：

```text
/agent?mode=explain_detection&detection_id=...
```

3. `Generate Report` 按鈕出現。
4. 點擊後跳轉：

```text
/agent?mode=report&detection_id=...
```

#### 6. DetectionHistoryPage shortcuts

選擇一筆 detection history 後，確認：

1. `Explain with Agent` 按鈕出現。
2. `Generate Report` 按鈕出現。
3. 點擊後正確跳轉到 `/agent` 並帶入 mode / detection_id。

### Desktop

1. 確認 `desktop-app/api_client.py` 中 `agent_chat` method 存在。
2. 確認既有 Desktop login/chat/detection 未受影響。
3. 若沒有 Agent UI，文件標註為下一階段。

---

## 十五、完成後回報格式

請按照以下格式回報：

1. 現況理解
2. 本次修改範圍
3. 新增/修改檔案列表
4. Web Frontend 架構變更摘要
5. Desktop 變更摘要
6. API 串接摘要
7. 如何啟動與驗證
8. 目前限制
9. 下一步建議

---

## 十六、重要限制

請務必遵守：

1. 不要刪掉原本 `/chat`。
2. 不要讓 `/chat` 改用 `/api/agent/chat`。
3. 不要讓 `/agent` 改用 `/api/chat`。
4. 不要重寫 `api.js` interceptor。
5. 不要新增第二個 Axios instance。
6. 不要引入新 UI framework。
7. 不要讓 Agent UI 重新執行 YOLO detection。
8. 不要大改 Desktop UI。
9. 不要破壞現有登入、偵測、歷史紀錄、使用者管理功能。
10. 如果後端 `/api/agent/chat` 尚未完成，請先停止並回報需要先完成 Phase 6A-1。
