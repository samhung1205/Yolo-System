# 開發路線圖

> 本文件保留原始執行計畫與階段性 checklist，未勾選項目不等同目前功能缺失。
> 當前可執行範圍與限制以 [`README.md`](../README.md) 的 Phase 狀態表及
> [`architecture.md`](architecture.md) 為準。

> **最後更新**: 2026-04-18  
> **目標**: 漸進式重構 legacy PySide6 專案為桌面版 + Web 版雙軌架構

---

## 里程碑總覽

```
Phase 0 ✅  →  Phase 1 🔜  →  Phase 2  →  Phase 3  →  Phase 4  →  Phase 5  →  Phase 6
  盤點          Backend         Desktop       YOLO         Chat        Web        完善
  文件          MVP Auth        改接API       Service      Service    Frontend    部署
```

---

## Phase 0 — 盤點現有專案 ✅ 已完成

**目標**: 深入理解 legacy 專案，建立文件基礎  
**完成時間**: 2026-04-18

### 完成項目
- [x] 分析所有 legacy 主要模組（Login, Register, MainUI, AdminMainUI, detect, deepseek 等）
- [x] 識別所有關鍵問題（SQL injection, 明文密碼, 硬編碼設定）
- [x] 建立 `README.md`
- [x] 建立 `AGENTS.md`
- [x] 建立 legacy 現況分析（後併入 `README.md`，獨立檔案已移除）
- [x] 建立 `docs/architecture.md`
- [x] 建立 `docs/api-spec.md`
- [x] 建立 `docs/database-design.md`
- [x] 建立 `docs/roadmap.md`
- [x] 建立新目錄骨架（`backend/`, `desktop-app/`, `web-frontend/`）

### 驗證方式
- 文件可讀、結構清晰
- 目錄骨架建立完成

---

## Phase 1 — FastAPI Backend MVP ✅ 已完成（2026-04-18）

**目標**: 建立可獨立運行的 FastAPI backend，包含 Auth 功能  
**預估工時**: 2-4 小時  
**前置條件**: Phase 0 完成

### 任務清單

#### 1.1 環境與基礎設定
- [ ] 建立 `backend/requirements.txt`
- [ ] 建立 `backend/.env.example`
- [ ] 建立 `backend/main.py`（FastAPI app entry point）
- [ ] 設定 Alembic（`alembic.ini`, `migrations/env.py`）

#### 1.2 資料庫層
- [ ] `backend/app/db/session.py`（SQLAlchemy engine + SessionLocal）
- [ ] `backend/app/core/config.py`（Pydantic Settings 讀取 .env）
- [ ] `backend/app/models/user.py`（User ORM model）
- [ ] Alembic migration：建立 `users` 表

#### 1.3 Auth 功能
- [ ] `backend/app/core/security.py`（bcrypt hash/verify + JWT create/decode）
- [ ] `backend/app/core/deps.py`（get_db, get_current_user dependencies）
- [ ] `backend/app/schemas/auth.py`（LoginRequest, TokenResponse）
- [ ] `backend/app/schemas/user.py`（UserCreate, UserRead）
- [ ] `backend/app/services/auth_service.py`（register, login 業務邏輯）
- [ ] `backend/app/api/routes/auth.py`（POST /register, POST /login, GET /me）

#### 1.4 Health Check
- [ ] `backend/app/api/routes/health.py`（GET /health）

### 完成項目
- [x] `backend/` 目錄完整結構
- [x] SQLAlchemy + MySQL 連線（config via .env）
- [x] Alembic migration：建立 `users` 表 + seed admin
- [x] POST /api/auth/register（bcrypt hash）
- [x] POST /api/auth/login（JWT）
- [x] GET /api/auth/me（JWT 驗證）
- [x] GET /api/health（database: connected）
- [x] GET/POST /api/users（分頁、搜尋）
- [x] PUT/DELETE /api/users/{id}（管理員）
- [x] POST /api/upload/avatar
- [x] Swagger UI：http://localhost:8000/docs
- [x] 權限控制（一般用戶 403，管理員正常）

### 環境
- conda 環境 `yolo-backend`（Python 3.11）
- MySQL 9.0.1 / database: `yolo`
- 預設 admin 帳號：`admin` / `Admin@2026`（**請登入後立即更改密碼**）

---

## Phase 2 — 桌面版改接 Backend API

**目標**: PySide6 桌面版的登入/註冊/管理員功能改呼叫 API  
**預估工時**: 3-5 小時  
**前置條件**: Phase 1 完成且驗證通過

### 任務清單

#### 2.1 Backend 補充
- [ ] `backend/app/api/routes/users.py`（GET/POST /users, PUT/DELETE /users/{id}）
- [ ] `backend/app/services/user_service.py`
- [ ] Alembic migration（若資料表有變動）

#### 2.2 Desktop 修改（最小必要）
- [ ] 建立 `desktop-app/api_client.py`（httpx-based API client）
- [ ] 修改 `Login.py::onSignIn()` → 呼叫 `POST /api/auth/login`
- [ ] 修改 `Register.py::onRegisterIn()` → 呼叫 `POST /api/auth/register`
- [ ] 修改 `utils/UserInfo.py` → 儲存 JWT token（保留 QSettings 介面）
- [ ] 修改 `AdminMainUI.py` → 呼叫 `/api/users/*`
- [ ] 修改 `AdminAddUser.py` → 呼叫 `POST /api/users`
- [ ] 修改 `AdminEditUser.py` → 呼叫 `PUT /api/users/{id}`

### 驗證方式
- 桌面版登入/登出正常
- 管理員可新增/編輯/刪除使用者（透過 API）
- `mysql/dataDB.py` 的 selectDB/insertDB 不再被呼叫

---

## Phase 3 — YOLO Detection Service

**目標**: 封裝 YOLO 辨識為後端 service，提供 API  
**預估工時**: 3-5 小時  
**前置條件**: Phase 2 完成

### 任務清單
- [ ] `backend/app/services/detection_service.py`（純 Python，不依賴 Qt）
- [ ] `backend/app/api/routes/detections.py`（POST /detections/image 等）
- [ ] Alembic migration：建立 `detection_tasks`, `detection_objects` 表
- [ ] 修改 `detect_mainui.py`（保留 Qt Signals，但 core logic 呼叫 service）
- [ ] 靜態檔案服務（辨識結果圖片）

### 驗證方式
- `POST /api/detections/image` 可上傳圖片並回傳辨識結果
- 桌面版 YOLO 功能仍可正常使用

---

## Phase 4 — AI Chat Service

**目標**: 封裝 DeepSeek 對話為後端 service，移除硬編碼 API key  
**預估工時**: 2-3 小時  
**前置條件**: Phase 3 完成

### 任務清單
- [ ] `backend/app/services/chat_service.py`（純 Python，不依賴 Qt）
- [ ] `backend/app/api/routes/chat.py`（POST /chat，支援 streaming）
- [ ] Alembic migration：建立 `chat_logs` 表
- [ ] 修改 `utils/deepseek.py` → 呼叫後端 `/api/chat`（移除硬編碼 API key）
- [ ] 將 DEEPSEEK_API_KEY 移至 `.env`

### 驗證方式
- `POST /api/chat` 可正常回應
- 聊天記錄儲存至資料庫
- `utils/deepseek.py` 中無硬編碼 API key

---

## Phase 5 — React Web 前端 MVP

**目標**: 建立 React Web 前端，實現登入、detection 展示、聊天介面  
**預估工時**: 8-15 小時  
**前置條件**: Phase 4 完成

### 任務清單
- [ ] 初始化 Vite + React 專案（`web-frontend/`）
- [ ] 設定 React Router、axios/fetch 封裝
- [ ] 登入頁面（呼叫 `/api/auth/login`）
- [ ] 主頁（Dashboard）
- [ ] 影像辨識上傳頁面
- [ ] 辨識歷史列表
- [ ] AI 聊天介面
- [ ] 管理員使用者管理頁面（若是管理員）

### 驗證方式
- Web 版可完整執行登入→辨識→聊天流程
- 不依賴任何 PySide6 或桌面端資源

---

## Phase 6 — 完善與部署

**目標**: 完整部署文件、測試、Docker、CI/CD  
**預估工時**: 5-10 小時  
**前置條件**: Phase 5 完成

### 任務清單
- [ ] 建立 `docker-compose.yml`（backend + MySQL + web-frontend）
- [ ] 建立 `Dockerfile`（backend）
- [ ] 建立 `Dockerfile`（web-frontend）
- [ ] 撰寫 backend 單元測試（pytest）
- [ ] 撰寫 API 整合測試
- [ ] 建立 Alembic migration 說明
- [ ] 補充 README.md 部署說明
- [ ] 建立 `audit_logs` 完整實作
- [ ] 效能調整與錯誤處理完善

---

## 風險與注意事項

| 風險 | 說明 | 緩解方式 |
|------|------|---------|
| Legacy 資料遷移 | `user` 表明文密碼無法直接遷移 | Phase 2 提供遷移腳本，需要使用者 reset 密碼 |
| YOLO 模型檔案 | `.pt` 檔案不在 repo 中 | 文件說明模型放置位置 |
| QSettings 跨平台 | Windows/macOS QSettings 路徑不同 | Phase 2 用 JWT token 取代 |
| DeepSeek API 費用 | 串流 API 有費用 | 開發時限制使用，加入速率限制 |
| LangChain/LangGraph 依賴龐大 | 安裝失敗可能拖垮 FastAPI 啟動 | Lazy import + mock LLM fallback；缺套件時 `/api/agent/*` 回 mock 回覆而不是 500 |
| DeepAgents API 不穩 | 不同版本介面差異大 | 預設關閉、`AGENT_ENABLE_DEEPAGENTS` flag 才開啟，requirements 中註解；核心 workflow 由 LangGraph 提供 |

---

## Phase 6A-1 — Backend Agentic Layer ✅ 完成（2026-05-14）

**目標**: 在不破壞 `/api/chat`、`/api/detections/*`、Desktop 與 Web 既有流程的前提下，新增 LangGraph supervisor 為核心的 agentic layer，提供 `/api/agent/chat` 與 `/api/agent/modes`。

### 任務清單
- [x] 新增 backend agent schemas（`AgentChatRequest` / `AgentChatResponse` / `AgentModeRead`）
- [x] 新增 read-only agent tools（detection / history / user / report）並做權限隔離
- [x] 新增 subagent helpers（yolo_result_explainer / detection_history_analyst / report_agent / admin_assistant）
- [x] 新增 LangGraph supervisor workflow（classify_intent / call_tools_or_subagent / compose_answer / handle_error）
- [x] 新增 agent service `create_agent_reply()`，寫入 `chat_logs` 並回傳 `AgentChatResponse`
- [x] 新增 API routes `POST /api/agent/chat`、`GET /api/agent/modes` 並於 `main.py` 註冊
- [x] 在 `desktop-app/api_client.py` 新增 `agent_chat()` / `list_agent_modes()`
- [x] LangChain / LangGraph / DeepAgents 全部 lazy import，缺套件時 backend 仍可啟動
- [x] Mock LLM fallback（缺 `OPENAI_API_KEY` 時自動降級）
- [x] 同步 README / AGENTS.md / docs/architecture.md / docs/api-spec.md
- [x] Agent streaming（於 Phase 6A-3 完成）

---

## Phase 6A-3 — Agent Streaming + Desktop AgentApiThread ✅ 完成（2026-05-14）

**目標**: 為 `/api/agent/chat/stream` 加入 SSE streaming 後端，Web AgentPage 預設使用 streaming，Desktop AICSMain.py 加入最小整合。

### 任務清單
- [x] `llm.py` 新增 `stream()` — MockChatModel word-by-word + _LangChainChatModel LangChain native stream
- [x] `graph.py` 新增 `stream_graph()` — 產生 `(phase, data)` tuple
- [x] `service.py` 新增 `stream_agent_reply()` — SSE generator，格式與 `/api/chat/stream` 一致
- [x] `routes/agents.py` 新增 `POST /api/agent/chat/stream`
- [x] `api_client.py` 新增 `stream_agent_chat()` generator
- [x] `agentService.js` 新增 `streamAgentMessage()` async generator
- [x] `AgentPage.jsx` 預設 streaming（Streaming toggle 可關閉）
- [x] `AICSMain.py` 新增 `AgentApiThread` + `enable_agent_mode()` / `disable_agent_mode()`
- [x] Desktop 獨立 `AgentWindow.py`（Phase 6A-3b）

---

## Phase 6A-2 — Web Frontend & Desktop Agent UI ✅ 完成（2026-05-14）

**目標**: 在 Web Frontend 新增獨立 `/agent` 頁面，整合 `POST /api/agent/chat`；在 DetectionPage / DetectionHistoryPage 加入快捷跳轉按鈕；Desktop 採最小整合（`api_client.py` 已具備 `agent_chat()`）。

### 任務清單
- [x] 新增 `web-frontend/src/services/agentService.js`（`sendAgentMessage` / `listAgentModes`）
- [x] 新增 `web-frontend/src/pages/AgentPage.jsx`（mode 選擇、detection_id 輸入、對話 thread、tool_calls / references 顯示）
- [x] 更新 `web-frontend/src/router/index.jsx` — 新增 `/agent` protected route
- [x] 更新 `web-frontend/src/components/Layout.jsx` — 新增「AI Agent」導覽項目
- [x] 更新 `web-frontend/src/pages/DashboardPage.jsx` — 新增 AI Agent card
- [x] 更新 `web-frontend/src/pages/DetectionPage.jsx` — detection 完成後顯示 Agent shortcuts
- [x] 更新 `web-frontend/src/pages/DetectionHistoryPage.jsx` — selected detail 顯示 Agent shortcuts
- [x] 更新 `web-frontend/src/styles.css` — 新增 agent-* CSS classes
- [x] Desktop：`desktop-app/api_client.py` 已包含 `agent_chat()` / `list_agent_modes()`（Phase 6A-1 完成）
- [x] Desktop：`AgentApiThread` + `enable_agent_mode()` / `disable_agent_mode()` helper（Phase 6A-3）
- [x] Agent SSE streaming（Phase 6A-3）
- [x] Desktop PySide6 完整 Agent 對話視窗（獨立 AgentWindow；於 Phase 6A-3b 完成）

---

*下次更新: Phase 1 完成後更新狀態*
