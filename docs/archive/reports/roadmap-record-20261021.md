> 歷史封存：2026-10-21 自 `docs/roadmap.md` 整理前版本保留。內容描述當時狀態，含已解決限制、舊操作與過期待辦；不得當作目前指令執行。現況見 [文件索引](../../README.md) 與 [開發狀態](../../roadmap.md)。

# 開發路線圖

> 本文件保留原始執行計畫與階段性 checklist，未勾選項目不等同目前功能缺失。
> 當前可執行範圍與限制以 [`README.md`](../../../README.md) 的 Phase 狀態表及
> [`architecture.md`](../../architecture.md) 為準。

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

**狀態**：進行中；2026-10-20 已於實驗室主機完成基礎服務與 React build 驗證，Compose 同網址服務／原有資料／GPU／SSE 已通過，備份隔離還原與關閉自行註冊已通過；公開可信 HTTPS／DB health 與 NNP 相容修復已通過，公開原有資料／媒體／Chat-Agent SSE 亦已通過；使用者已確認校外手機瀏覽器正常，Mac 副本完整 SQL／52 個檔案 SHA-256 核對通過；2026-10-21 維運／完整回歸工具與 CI 已補齊，本機後端 182 項、Vite 8 build／audit 0／瀏覽器及真實 CPU API 回歸通過；Ubuntu 收尾批次待執行。操作與回報證據見 [實驗室同網址服務](../../lab-same-origin.md)。

**使用者決策**：10–50 人實驗室／內部使用，免費優先，使用既有實驗室主機，Ollama 同機運行；須能校外網際網路直連，只有 IP、沒有獨立備份磁碟；帳號由管理員建立，關閉自行註冊（正式 backend 已驗證）。

**前置條件**：Phase 5 完成；取得目標主機規格與既有備份位置。

**詳細依據與平台比較**：[DEPLOY.md](../../../DEPLOY.md)。

### 目前已有的基礎

- [x] 既有 backend pytest 與 API 測試（不是從零補寫測試）。2026-10-20 已在 Agent SSE 假模型測試中固定安裝清單發現結果，正式白名單不變；Mac 後端全套 179 項通過（29.01 秒），不再要求本機存在 qwen2.5。
- [x] Alembic migrations 已至 `0013`；正式升級與還原流程仍需補齊。
- [x] React production build 已在 Ubuntu 產出；MySQL 容器、專用帳號、migration 0013、production backend 與 Ollama Chat／Agent 串接已收到通過結果。
- [x] nginx loopback 入口已在 Ubuntu 啟動；首頁 HTTP 200、經 nginx 的 health 回 DB connected。
- [x] 使用者回報瀏覽器登入／Agent 深連結／Chat／Agent 串流與圖片偵測／歷史目前無問題。
- [x] Compose 批次通過 API／媒體錯誤分流與 Chat／Agent SSE／保存（首片段 1.05／5.42 秒）；關閉自行註冊已套用驗證；公開 HTTPS／舊圖片與對話 SHA-256／媒體保護／兩條 SSE 已於 094649Z 報告整批通過；校外手機瀏覽器由使用者確認正常，跨帳號完整補驗仍待完成。
- [x] Vite 8.3.4／plugin 6.1.2 升級；本機 build、Playwright 暫存 API 登入／路由／關閉註冊回歸通過，npm audit 0；新 gateway 在 Ubuntu 收尾批次建置。
- [x] 部署診斷、媒體容量盤點與每日備份／清理方案已記錄，未建立實際排程。

### 依序實作與驗證

1. **6.1 同網址服務**
   - [ ] 量測目標主機 YOLO／Ollama 記憶體、延遲與排隊；確認同時推論量。
   - [x] 提供 React build，統一代理 `/api/*`、受保護 `/static/*`；HTTPS 與 SSE 驗收通過，上傳大小／timeout 已配置；大檔案邊界仍待回歸。
   - 驗證：前端深連結重新整理、登入／上傳／下載／Agent 串流、Desktop API 連線正常，私人媒體仍須認證。
2. **6.2 Docker 與持久保存**
   - [x] Ubuntu 現有 NVIDIA Docker runtime 通過 GPU 裝置可見性測試（RTX 4070 Ti）；不代表容器內 PyTorch 推論已驗證。
   - [x] backend Dockerfile、專用 ignore、Linux 版本快照匯出與測試工具已備妥；Ubuntu image `sam-yolo-backend:lab-20261020` 建置通過，ID 與步驟見 [後端容器步驟](../../lab-backend-container.md)。
   - [x] 初版 image 加使用者名稱／cache 環境變數後，容器內 CUDA matrix／NMS、ASFF／DySample／EfficientViM 推論與 PNG 驗證通過。
   - [x] 修正版 image 內建 UID 名稱／可寫設定目錄，無額外環境變數的 GPU smoke 與既有 12 項測試通過（1.10 秒）；ID `2fdf4814f7be...`。
   - [x] loopback 18000 容器 production 啟動與 health DB connected（使用者回報）。
   - [x] loopback 18000 登入／YOLO／受保護媒體／Ollama Chat／Agent 真實工具與對話讀回通過（`api_smoke.py`，偵測 ID 1／兩組對話）。
   - [x] 已驗證 image 接手 8000，容器 healthy、直接／經 nginx 的 health 均 DB connected。
   - [x] 使用者確認新容器可讀回偵測 ID 1 原圖／結果圖與兩組既有對話，切換後串流正常。
   - [x] Compose backend／nginx 設定與 UID／路徑產生器已備妥，Ubuntu v2.29.2 config --quiet／--services 驗證通過。
   - [x] Ubuntu Compose backend／web 納管、health／舊資料／GPU／路由／Chat-Agent SSE 整批通過（報告 compose-20261020T055006Z-2532143.json，見 [Compose 管理](../../lab-compose.md)）；Ollama active／enabled、磁碟可用 486.5 GiB。
   - [x] React-Caddy production image、shortlived IP HTTPS 與關閉註冊的 [單檔更新包](../../lab-public-https.md) 已於 Ubuntu 套用／建置，新 backend 關閉註冊／DB／自訂 GPU／12 項測試與原有圖片／對話一致通過；HTTPS PENDING、ACME error types 空，報告 20261020T084747Z-2562377；只讀診斷確認 gateway 重啟／exec operation not permitted，前版修復連 shell 也被拒絕、未切換服務；依 Canonical 已知 Snap NNP 限制改為 A/B 驗證後的 gateway 專用 NNP 例外，同 image／唯讀／AA／cap 上限及原 backend 不變；Ubuntu NNP 修復／公開可信 HTTPS 通過（093549Z 報告）；媒體驗收遭重複 nosniff 誤判，已備不改服務的 public_verify 續驗工具；不重跑整包建置。公開 API／媒體／兩條 SSE 與保存已整批通過（public-verify-20261020T094649Z-2578684）；校外瀏覽器由使用者確認正常。
   - [ ] MySQL 交接及完整啟停／重建配置。
   - [ ] MySQL／上傳媒體／Ollama 模型持久 volume；交付未納入 Git 的 YOLO checkpoint 及根目錄相容模組。
   - 驗證：容器內實際載入自訂模型；容器重建後資料與模型可用。
3. **6.3 維運與復原**
   - [ ] 正式設定、專用 DB 帳號、migration／seed admin 改密與升級流程。
   - [x] 沒有 NAS／獨立備份磁碟：[備份／隔離還原批次](../../lab-backup.md) 首次 Ubuntu 備份完成、隔離匯入後 SQL 雜湊不符（20261020T075232Z-2550504）；修正版重驗既有備份，不停止服務，重驗已確認全部檔案完整；SQL 首差異高度吻合 MySQL #110825 冗餘字元集表示，修正版在 Ubuntu 已通過（20261020T081258Z-2556729），30 行全部為此等價差異，其餘 SQL／所有檔案完整；原始備份與成功報告已下載 Mac，實際核對完整 SQL／52 個檔案 SHA-256 通過。
   - [x] 從已驗證備份同步 Ubuntu Linux lock 至 Mac：118 個固定版本及關鍵 GPU／Agent 版本核對通過，SHA-256 記錄於部署交接。
   - [ ] 每日 23:30 Asia/Taipei／保留 7 份成功備份工具已備妥；Ubuntu 首份完整來源／SQL／檔案／image／模型／憑證備份與隔離還原成功後才啟用。清理先 dry-run。
   - [x] 中斷工作的離線盤點／受控標失敗與重算批次計數工具及測試已完成，保留完成結果與媒體；Ubuntu 待驗。多 worker 仍未採用。
   - 驗證：隔離還原 DB 與媒體；檢查排程結果、磁碟容量與重啟後任務狀態。
4. **6.4 部署驗收與文件**
   - [ ] Mac 後端全套 182 通過；兩帳號／頭像／單圖／批次 ZIP／影片／Desktop／JWT 的真實 CPU／暫存 SQLite／測試 HTTPS 回歸已通過，Ubuntu 正式 image 全套與正式 HTTPS 回歸由 [單次收尾批次](../../lab-phase6-finalization.md) 執行。
   - [x] 手動 CI workflow 已完成，固定官方 action commit／唯讀／15 分鐘；未 push 或執行 GitHub run。
   - [ ] 現行正式啟停／驗收／備份下載與升級回復界線已整併至 [部署交接](../../lab-operations.md)；每日排程、完整重建／還原與 CI 仍待完成，不能先標記 Phase 6 完成。
   - 驗證：登入→偵測→歷史→Chat／Agent 全流程、權限隔離、持久保存與復原。

**另行安排**：1000 張批次、空間推論、完整 `audit_logs`、大規模併發；httpOnly cookie 仍待討論，不隨本次文件更新自動變更認證。

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
