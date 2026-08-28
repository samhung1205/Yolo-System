# AGENTS.md — AI 協作規範文件

> 本文件是給 AI 工具（Cursor、Codex、Claude 等）的協作說明，確保每次進入新的 AI 工作階段時，能快速理解專案背景、目標與限制，避免做出破壞性修改。

---

## 專案目標

將現有的 PySide6 + MySQL legacy 桌面系統，漸進式重構為：
- **保留**：PySide6 桌面版（研究展示平台）
- **新增**：FastAPI 後端（桌面版與 Web 版的共用核心）
- **新增**：React + Vite Web 前端（前後端分離展示版）

**核心原則：不一次重寫，逐步驗證，最小破壞。**

---

## 雙軌架構策略（Desktop + Web）

```
[PySide6 Desktop] ──HTTP請求──> [FastAPI Backend] <──HTTP請求── [React Web]
                                       │
                              ┌────────┼────────┐
                         [MySQL DB] [YOLO] [DeepSeek]
```

- 桌面版與 Web 版**共用同一個 FastAPI Backend**
- 桌面版**不直接連 MySQL**（Phase 2 之後）
- YOLO 與 DeepSeek 封裝為 backend service，不直接在 UI 層呼叫

---

## 修改原則

在修改任何檔案前，必須遵守以下原則：

### 絕對禁止
- ❌ 不允許在 UI 層（PySide6 widget / React component）直接寫 SQL
- ❌ 不允許在程式碼中硬編碼密碼、API Key、資料庫連線資訊
- ❌ 不允許一次重寫多個模組（每次只動一個 phase）
- ❌ 不允許在未完成當前 phase 驗證前就進入下一個 phase
- ❌ 不允許刪除 legacy 程式碼（只能並存或逐步替換）

### 必須做到
- ✅ 修改前先讀 README.md、AGENTS.md、相關 docs
- ✅ 新增 .env 管理所有設定，不 commit .env 本體
- ✅ 密碼使用 bcrypt hash
- ✅ 身分驗證使用 JWT
- ✅ 每次改動都要同步更新對應 docs（若 API、資料表、架構有變）
- ✅ 每個 phase 完成後必須說明如何驗證

### Web Frontend Agent UI 規則（Phase 6A-2 起）
- ❌ 不要讓 `/chat` 改用 `/api/agent/chat`；兩條路徑必須維持獨立頁面與獨立 service
- ❌ 不要讓 `/agent` 改用 `/api/chat`
- ❌ 不要讓 Agent UI 重新執行 YOLO detection；Agent 只解釋既有 detection result
- ❌ 不要新增第二個 Axios instance；`agentService.js` 必須沿用既有 `api.js`
- ❌ 不要引入新 UI framework（Tailwind / MUI / Ant Design / Chakra 等）
- ❌ 不要大改 Desktop PySide6 UI（Desktop Agent UI 為下一階段）
- ✅ `agentService.js` 使用 `api.js` 的 axios instance，不重寫 interceptor
- ✅ AgentPage 支援 URL query params `?mode=...&detection_id=...`
- ✅ `admin_help` 模式前端可顯示提示，但以後端權限檢查為準

### Agentic Layer 額外規則（Phase 6A-1 起）
- ❌ 不要 agent 化核心 CRUD（建立、修改、刪除 user / detection / chat log 一律走原本 service）
- ❌ 不要讓 LLM 直接執行 DB 寫入或檔案系統寫入
- ❌ 不要讓 agent 取代 YOLO 推論：YOLO inference 永遠走 `app/services/detection_service.py` + `app/integrations/yolo_engine.py`
- ❌ 不要把 `/api/chat` 與 `/api/agent/chat` 合併；兩條路徑必須維持獨立端點與獨立 service
- ✅ Admin 限定的 agent tool 必須在函式開頭硬檢查 `current_user.is_admin`
- ✅ 任何 agent tool 讀資料時都要以 `current_user` 做 scope，非 admin 只能讀自己的資料
- ✅ LangChain / LangGraph / DeepAgents 一律以 lazy import + try/except 包裝，禁止讓 import 失敗造成 FastAPI 啟動 500
- ✅ DeepAgents 為 optional enhancement，預設 `AGENT_ENABLE_DEEPAGENTS=false`；要啟用前必須在 PR 描述中說明理由
- ✅ 未來若要讓 agent 寫資料，必須加入 human-in-the-loop 確認流程（非本階段範圍）

---

## 當前 Phase

> **目前已完成至「批次影像分析 Phase 1」（多圖/資料夾批次上傳 + 類別總數聚合 + Agent `batch_analysis` 模式）。下一步：批次分析 Phase 2（空間關係推論）或 Phase 6（Docker、測試、部署文件完善），視優先順序決定。**

**批次影像分析 Phase 1 — ✅ 完成（2026-07-23 多圖/資料夾批次上傳 + 確定性聚合統計）**

*範圍界定*
- 做：一次上傳最多 `DETECTION_BATCH_MAX_FILES`（預設 100，規劃未來提高到 500）張影像 → 逐張沿用現有單張圖片偵測流程 → 存成一個 `detection_batches` 群組 → Agent `batch_analysis` 模式能回答「這批影像總共偵測到幾艘船/幾架飛機/幾輛車」「有幾張疑似漏檢（估計）」
- 不做（留給後續 Phase）：bbox 空間關係推論（例如「哪些船上有飛機」）、影片逐幀問答、Desktop UI

*Backend*
- [x] migration `0010`：新增 `detection_batches` 表（`status`/`total_files`/`processed_count`/`failed_count`/`skipped_files`/model provenance 欄位）；`detection_tasks` 新增 nullable `batch_id`（`ON DELETE CASCADE`）
- [x] `app/models/detection_batch.py`：`DetectionBatch` ORM，`tasks` relationship 對應回 `DetectionTask.batch`
- [x] `app/repositories/detection_repository.py`：`create_batch` / `update_batch` / `get_batch` / `list_batches` / `count_batches` / `delete_batch` / `get_pending_batch_tasks` / `count_objects_by_class_for_batch`（SQL `GROUP BY`，確定性聚合，不受記憶體內清單上限影響）
- [x] `app/services/detection_service.py`：`create_image_batch()`（驗證張數上限、非圖片檔案略過但不擋整批、逐檔存檔失敗只影響該張）；`process_image_batch_task()`（背景任務逐張推論、每張都即時更新 `processed_count`/`failed_count` 供前端輪詢、模型只載入一次重複使用）；`list_batches` / `get_batch` / `delete_batch`（含靜態檔案清理）
- [x] `app/api/routes/detections.py`：`POST /api/detections/batch`（202）、`GET /api/detections/batches`、`GET /api/detections/batches/{id}`、`DELETE /api/detections/batches/{id}`（註冊於 `/{detection_id}` 之前避免路由歧義）
- [x] `app/schemas/detection.py`：`BatchRead` / `BatchDetailRead`
- [x] `app/agents/tools/batch_tools.py`：`summarize_batch_tool`（read-only，擁有權檢查，`GROUP BY class_name` 聚合 + 零偵測影像疑似漏檢提示 + per-image breakdown 上限 50 筆但總數永遠精確）、`list_batch_images_by_class_tool`
- [x] `app/agents/subagents/batch_analyst.py` + `BATCH_ANALYST_PROMPT`：明確要求「零偵測僅為估計，非確定漏檢」、遇到空間關係問題誠實回覆目前不支援
- [x] `app/agents/state.py` / `graph.py` / `service.py` / `schemas/agent.py` / `api/routes/agents.py`：新增 `batch_id` 全鏈路傳遞（`run_graph`/`stream_graph`/`AgentChatRequest`），新增 `batch_analysis` mode 與 intent 路由（含關鍵字自動判斷）
- [x] `.env.example` / `core/config.py`：`DETECTION_BATCH_MAX_FILES=100`

*Web*
- [x] 新頁面 `web-frontend/src/pages/BatchDetectionPage.jsx`（路由 `/detections/batch`）：多檔/整個資料夾選擇（`webkitdirectory`）、上傳後輪詢進度條、逐張縮圖 + 狀態、刪除批次、「用 Agent 分析這批」捷徑
- [x] `detectionService.js`：`detectImageBatch` / `listBatches` / `getBatch` / `deleteBatch`
- [x] `agentService.js` / `AgentPage.jsx`：新增 `batch_id` 支援（沿用既有 `detection_id` 的智慧預填 prompt / query params 同步邏輯），`batch_analysis` 模式預設 prompt
- [x] `router/index.jsx`、`Layout.jsx`、`DashboardPage.jsx`：新增 Batch Analysis 入口
- [x] `styles.css`：新增 `.batch-progress-bar` / `.batch-task-grid` / `.batch-task-card` / `.status-completed_with_errors`

*已知限制（記錄為後續待辦）*
- [ ] 背景處理為單一 worker 依序執行（非併發），100 張視硬體效能可能需數十秒到數分鐘；擴到 500 張或跨批次併發需 Phase 6 job queue
- [ ] 僅支援影像批次；影片批次與逐幀問答為後續 Phase
- [ ] `summarize_batch_tool` 僅做每類別總數聚合，不做 bbox 空間關係判斷（例如「船上有沒有飛機」）

**Phase 6A-6 — ✅ 完成（2026-07-23 IME 修復 + 對話滾動 + Agent Vision）**

*Web 輸入體驗修復*
- [x] `ChatPage.jsx` / `AgentPage.jsx`：textarea 加上 `onCompositionStart` / `onCompositionEnd` + `isComposing`/`keyCode 229` 判斷，修復中文輸入法選字確認時被誤判為送出的問題
- [x] `.chat-thread` / `.agent-thread`：修復 grid `1fr` + `overflow` 未生效的「grid blowout」問題（缺少 `min-height:0` 與明確上限），對話越長也不會撐開整個頁面版面，改為容器內滾動
- [x] `ChatPage.jsx`：補上訊息滾動到底部的 `threadRef` + `useEffect`（`AgentPage.jsx` 已有，維持一致行為）

*Agent 視覺能力（bounding box 以外的影像理解）*
- [x] `detection_tools.load_detection_image_tool()`：唯讀讀取偵測結果圖（annotated，優先 `result_image_path` > `preview_image_path` > `source_image_path`）並 base64 編碼，不觸發任何新推論
- [x] `AGENT_ENABLE_VISION`（預設 `false`）：開啟後 `explain_detection` / `report` 模式會把偵測影像以 multimodal `image_url` content block 附加給 LLM，需搭配支援圖片輸入的 provider/model（OpenAI gpt-4o / gpt-4.1、Ollama llava / qwen2-vl 等）；非視覺模型會導致該次請求以「AI 模型目前無法完成回覆」收尾，不會造成後端錯誤
- [x] `YOLO_RESULT_EXPLAINER_PROMPT` / `REPORT_AGENT_PROMPT`：新增「圖片有附上時可描述實際觀察到的內容，但需與 YOLO 結構化偵測結果明確區分」的規則
- [x] `GENERAL_CHAT_PROMPT`：一般聊天模式被問到特定偵測內容時，改為引導使用者切換至 Explain Detection / Report 並填入 Detection ID，而非模糊地說「需要提供圖片或 JSON」
- [x] `AgentPage.jsx`：Detection ID 欄位新增即時提示（Explain Detection / Report 模式未填會顯示必填警示；Auto 模式未填會提示可能被當一般聊天處理）
- [x] `tests/test_agent_vision_tool.py`：新增擁有權檢查、路徑穿越防護、檔案大小上限、優先順序的單元測試

**Phase 6A-5 — ✅ 完成（2026-07-12 全面品質修復 + Agent 強化 + Web 下載功能）**

*Agent 功能強化*
- [x] `AgentPage.jsx`：mode / detection_id 切換時智慧替換自動填入的 prompt（使用者自打的文字不會被覆蓋）
- [x] `AgentPage.jsx`：`?mode=&detection_id=` query params 支援 in-app 導航（已在 /agent 頁時點捷徑也會生效）
- [x] `AgentPage.jsx`：新增 `history_analysis` / `admin_help` 模式的預設 prompt

*Web 下載功能*
- [x] `detectionService.downloadAsset()`：blob 下載 helper（沿用共用 axios instance）
- [x] `DetectionPage`：偵測完成後可下載結果圖
- [x] `DetectionHistoryPage`：detail 面板可下載結果圖 / 結果影片

*Backend 修復*
- [x] migration `0008`：`chat_logs.user_id` FK 改為 `ON DELETE CASCADE`（修復刪除有聊天紀錄的 user 時 FK 錯誤）
- [x] `user_service.delete_user()`：同步清理該 user 的 detection 靜態檔案與 avatar
- [x] `history_tools` / `report_tools`：統計工具改用 `count_tasks` + `HISTORY_SCAN_LIMIT=1000`（修復 100 筆上限造成統計錯誤），payload 回報 `truncated`
- [x] `detection_history_analyst` / `report_agent` / `admin_assistant`：`role:"tool"` 改為 user-turn 嵌入（修復 OpenAI 嚴格模式 400）
- [x] `main.py`：SECRET_KEY 為預設值時啟動警告；`APP_ENV=production` 直接拒絕啟動

*Web 修復*
- [x] `DetectionHistoryPage`：AbortController 正式接上 axios（修復篩選競態）；刪除後分頁 clamp
- [x] `ChatPage`：init 自動開啟 vs「New」、送出 vs 切換對話兩個競態修復
- [x] `ChatPage` / `AgentPage`：預設 model 改選第一個 `available` 的 provider
- [x] `agentService` SSE 401：清除 session 並導回 /login（對齊 axios interceptor）
- [x] `DetectionPage`：object URL 洩漏修復

*Desktop 修復*
- [x] `Login.py`：登入時清除另一角色的 token（修復 admin/user session 錯亂）；登入 / restore 時自動下載 avatar 到本地快取
- [x] `AdminMainUI.to_close()`：登出時清除 admin session
- [x] `AgentWindow` / `AICSMain`：closeEvent（含 QDialog reject）斷開串流執行緒 signal + 中斷請求 + orphan thread 保活（修復關窗 crash 風險）
- [x] `api_client.py`：分操作 timeout（推論 180s / 影片上傳 600s / SSE 300s / binary 120s）；`list_detections(with_meta=True)` 回傳 `X-Total-Count` / `X-Total-Pages`
- [x] `MainUI.py`：detection history 分頁改用後端 total（含刪除後 clamp）；影片輪詢在關窗時取消

*已知未處理（記錄為後續待辦）*
- [x] `/static` 認證（signed URL + JWT fallback；`<img>` 使用 API 回傳的 `*_url` / `avatar_url`）
- [ ] migration `0002` seed admin 預設密碼：部署後必須立即改密
- [ ] YOLO 推論 / LLM 串流阻塞 worker：正式部署需 job queue（Phase 6）
- [ ] `turn_index` 併發重複（低風險，待補 unique constraint）
- [ ] webcam / RTSP legacy QThread 重啟問題（legacy 範圍）

**Phase 0 — 已完成**
- [x] 盤點 legacy 專案
- [x] 建立 README.md
- [x] 建立 AGENTS.md
- [x] 建立 legacy 現況分析（後併入 README.md「Legacy 專案現況與重構目標」，獨立檔案已移除）
- [x] 建立新目錄骨架

**Phase 1 — ✅ 完成（待 MySQL 密碼確認後執行 migration）**
- [x] 建立 `backend/` 目錄完整結構
- [x] 設定 SQLAlchemy + MySQL 連線（config via .env）
- [x] 建立 `users` 資料表 migration 腳本
- [x] 實作 POST /api/auth/register（bcrypt hash）
- [x] 實作 POST /api/auth/login（JWT）
- [x] 實作 GET /api/auth/me（JWT 驗證）
- [x] 實作 GET /api/health
- [x] 實作 GET/POST/PUT/DELETE /api/users（管理員）
- [x] 實作 POST /api/upload/avatar
- [x] FastAPI server 可啟動，端點驗證通過
- [x] 確認 MySQL root 密碼 → 執行 `alembic upgrade head`
- [x] 建立 admin 帳號（migration seed 或手動）

**環境需求**：建議使用 `conda` 環境（macOS Sonoma Gatekeeper 問題）
```bash
conda activate yolo-backend
cd backend && uvicorn main:app --reload
```

**Phase 2 — ✅ 完成（Desktop 主要資料流已改接 API）**
- [x] 建立 `desktop-app/api_client.py`（desktop 共用 API client）
- [x] 建立 `desktop-app/ui_state.py`（取代 `mysql.dataDB.SI` 的視窗共享狀態）
- [x] 建立 `desktop-app/avatar_cache.py`（backend avatar 本地快取）
- [x] 修改 `Login.py` 改呼叫 POST /api/auth/login
- [x] 修改 `Register.py` 改呼叫 POST /api/auth/register
- [x] 修改 `AdminMainUI.py` 查詢/刪除/個資/密碼改呼叫 backend API
- [x] 修改 `AdminAddUser.py` / `AdminEditUser.py` 改呼叫 /api/users/*
- [x] 修改 `MainUI.py` 個資/密碼改呼叫 backend API
- [x] 修改 `utils/UserInfo.py` 儲存 user/admin JWT token
- [x] Desktop 啟動時改用 `/api/auth/me` 驗證 token 並恢復 session
- [ ] **已知限制**：註冊前頭像仍沿用本地暫存流程

**Phase 3 — ✅ 完成（Detection image/video MVP；webcam/RTSP 為 Phase 3+ 待辦）**
- [x] 設計 `/api/detections/*` 實際資料流與檔案上傳格式
- [x] 建立 `detection_tasks` / `detection_objects` 資料模型與 migration
- [x] 建立 `YoloEngine` / `DetectionService`
- [x] 實作 `POST /api/detections/image`
- [x] 實作 `POST /api/detections/video`
- [x] 實作 `GET /api/detections`（含 status / source_type 篩選 + limit / page 分頁 + X-Total-Count header）
- [x] 實作 `GET /api/detections/{id}`
- [x] 實作 `DELETE /api/detections/{id}`
- [x] 修改 `MainUI.py` 單張圖片改由 backend 觸發 detection
- [x] 修改 `MainUI.py` 本地影片檔改由 backend 觸發 detection
- [x] 規劃 detection 任務結果與靜態檔案保存策略
- [x] Web `DetectionHistoryPage`：篩選欄（status / type）、刪除按鈕、分頁控制
- [x] Desktop `show_detection_history`：篩選 combobox + 刪除確認 + 分頁上下頁
- [x] `desktop-app/api_client.py`：`list_detections()` 支援 filter params；新增 `delete_detection()`
- [ ] webcam detection 後端化（Phase 3+，需 WebSocket/MJPEG 串流，獨立大功能）
- [ ] RTSP / 串流 detection 後端化（同上）
- [ ] video detection 任務取消 / 更完整進度回報（Phase 3+）

**Phase 4 — ✅ 完成（provider-based chat + history/context + streaming）**
- [x] 建立 `chat_logs` 資料模型與 migration
- [x] 建立 `POST /api/chat`
- [x] 建立 `POST /api/chat/stream`
- [x] 建立 `GET /api/chat`
- [x] 建立 `GET /api/chat/{conversation_id}`
- [x] 建立 provider-based chat integration 抽象層
- [x] 實作 `OpenAIChatProvider`
- [x] 實作 `DeepSeekChatProvider` 相容層
- [x] 修改 `AICSMain.py` 改呼叫 backend `/api/chat`
- [x] Desktop 不再直接持有外部模型 API key
- [x] chat history 查詢 API
- [x] 多輪上下文管理
- [x] backend streaming chat（SSE / WebSocket）

**Phase 6A-3b — ✅ 完成（Desktop AgentWindow 獨立對話視窗）**
- [x] 新增 `AgentWindow.py`（PySide6 QDialog，含 Mode 下拉、Detection ID 欄位、AIChatMessageWindow 泡泡、Enter 送出、resizeEvent 重繪）
- [x] 自帶 `AgentStreamThread`（呼叫 `/api/agent/chat/stream`），不依賴 `AICSMain.py`
- [x] `MainUI.py` 新增「AI Agent」按鈕（`add_detection_controls` column 6）
- [x] `open_agent_window()` 方法：有 `current_detection` 時自動帶入 `detection_id`，mode 預設切換為 `explain_detection`
- [x] `AgentWindow.py` 支援 stand-alone 啟動（`python AgentWindow.py`）

**Phase 6A-4 — ✅ 完成（LLM 模型選單：前端 per-request provider/model 切換）**
- [x] 新增 `backend/app/api/routes/models.py` — `GET /api/models`，依 `.env` 動態回傳可用 provider 清單；Ollama 呼叫 `/api/tags` 取得本地已安裝模型
- [x] `backend/main.py` 註冊 `models.router`（`/api/models`）
- [x] `backend/app/schemas/chat.py` — `ChatRequest` 新增 optional `provider` / `model` 欄位（含 validator）
- [x] `backend/app/schemas/agent.py` — `AgentChatRequest` 新增 optional `provider` / `model` 欄位（含 validator）
- [x] `backend/app/services/chat_service.py` — `_get_provider()` 支援 per-request override；`create_chat_reply()` / `stream_chat_reply()` 接受並傳遞
- [x] `backend/app/api/routes/chat.py` — 將 `payload.provider` / `payload.model` 傳入 service
- [x] `backend/app/api/routes/agents.py` — 將 `payload.provider` / `payload.model` 傳入 service
- [x] `backend/app/agents/service.py` — `create_agent_reply()` / `stream_agent_reply()` 接受 `provider_name` / `model_name_override` 並傳遞到 graph
- [x] `backend/app/agents/graph.py` — `run_graph()` / `stream_graph()` / `_compose_answer_node()` 使用 state 中的 override 呼叫 `get_chat_model(provider, model_name)`
- [x] `backend/app/agents/state.py` — `AgentState` 新增 `provider_name` / `model_name_override`
- [x] `web-frontend/src/services/modelService.js` — `listModels()` 呼叫 `GET /api/models`，沿用 `api.js` axios instance
- [x] `web-frontend/src/services/chatService.js` — `sendMessage()` 新增 `provider` / `model` 參數
- [x] `web-frontend/src/services/agentService.js` — `sendAgentMessage()` / `streamAgentMessage()` 支援 `provider` / `model`
- [x] `web-frontend/src/pages/ChatPage.jsx` — mount 時載入模型清單；textarea 上方新增 provider/model 雙 select
- [x] `web-frontend/src/pages/AgentPage.jsx` — mount 時載入模型清單；controls 區 Detection ID 下方新增 provider/model select
- [x] `web-frontend/src/styles.css` — 新增 `.model-selector-row` / `.model-selector` / `.model-selector-provider` / `.model-selector-model` 樣式

**Phase 6A-3 — ✅ 完成（Agent Streaming + Desktop AgentApiThread）**
- [x] `backend/app/agents/llm.py` 新增 `stream()` 方法（MockChatModel word-by-word + _LangChainChatModel LangChain native stream）
- [x] `backend/app/agents/graph.py` 新增 `stream_graph()` — 產生 `(phase, data)` tuple，讓 service 層轉為 SSE
- [x] `backend/app/agents/service.py` 新增 `stream_agent_reply()` — SSE generator，格式與 `/api/chat/stream` 一致
- [x] `backend/app/api/routes/agents.py` 新增 `POST /api/agent/chat/stream`
- [x] `desktop-app/api_client.py` 新增 `stream_agent_chat()` generator
- [x] `web-frontend/src/services/agentService.js` 新增 `streamAgentMessage()` async generator（native fetch + ReadableStream）
- [x] `web-frontend/src/pages/AgentPage.jsx` 預設 streaming，可切換 Streaming toggle；串流中顯示 ▍ 閃爍游標
- [x] `AICSMain.py` 新增 `AgentApiThread`（`/api/agent/chat/stream`）及 `enable_agent_mode()` / `disable_agent_mode()` helper

**Phase 6A-2 — ✅ 完成（Web Frontend & Desktop Agent UI）**
- [x] 新增 `web-frontend/src/services/agentService.js`（`sendAgentMessage` / `listAgentModes`，沿用既有 `api.js` axios instance）
- [x] 新增 `web-frontend/src/pages/AgentPage.jsx`（獨立 `/agent` 頁，不取代 `/chat`）
- [x] 更新 `router/index.jsx` — 新增 `/agent` protected route
- [x] 更新 `Layout.jsx` — 新增「AI Agent」導覽項目
- [x] 更新 `DashboardPage.jsx` — 新增 AI Agent card
- [x] 更新 `DetectionPage.jsx` — detection 完成後顯示「Ask Agent to Explain」/「Generate Report」按鈕
- [x] 更新 `DetectionHistoryPage.jsx` — selected detail 顯示「Explain with Agent」/「Generate Report」按鈕
- [x] 更新 `styles.css` — 新增 `agent-layout`、`agent-controls`、`agent-thread`、`agent-message-*`、`agent-tool-calls`、`agent-reference-list`、`agent-shortcut-row`
- [x] Desktop：`api_client.py` 已包含 `agent_chat()` / `list_agent_modes()`（Phase 6A-1 完成）
- [ ] **已知限制**：Desktop PySide6 Agent 對話 UI 為下一階段；Agent streaming 為下一階段

**Phase 6A-1 — ✅ 完成（Backend Agentic Layer with LangGraph）**
- [x] 新增 `backend/app/agents/` 完整骨架（state / llm / prompts / graph / service / tools / subagents）
- [x] 新增 `backend/app/schemas/agent.py`（AgentChatRequest / AgentChatResponse / AgentModeRead）
- [x] 新增 `backend/app/api/routes/agents.py`（`POST /api/agent/chat`、`GET /api/agent/modes`）
- [x] 在 `backend/main.py` 註冊 `/api/agent` 前綴
- [x] `backend/app/core/config.py` 新增 `AGENT_*` 設定（AGENT_PROVIDER / AGENT_MODEL / AGENT_ENABLE_DEEPAGENTS / AGENT_MAX_HISTORY_TURNS / AGENT_RECURSION_LIMIT / AGENT_SYSTEM_PROMPT）
- [x] `backend/requirements.txt` 新增 langchain / langchain-openai / langgraph（deepagents 為註解 optional）
- [x] `desktop-app/api_client.py` 新增 `agent_chat()` / `list_agent_modes()`，不動 `chat()` / `stream_chat()`
- [x] LangChain / LangGraph / DeepAgents 一律 lazy import；缺套件或缺 API key 時 backend 仍可啟動（agent 回 mock 回覆）
- [x] Agent tool layer **read-only**：不曝露 delete / update / create 類工具，不直接呼叫 YOLO
- [x] `chat_logs` 共用、agent 寫入時 `provider="langgraph-agent"`，無需 migration
- [ ] Phase 6A-2 待辦：Web `/agent` 頁面、Desktop AICSMain agent UI、agent streaming

**Phase 5 — ✅ 完成（Web 所有主流程可用，API/runtime 驗證通過）**
- [x] 建立 `web-frontend/` Vite + React 骨架
- [x] 建立 `ProtectedRoute` / `Layout`
- [x] 建立 `LoginPage` / `RegisterPage`
- [x] 建立 `DashboardPage`
- [x] 建立 `DetectionPage`
- [x] 建立 `DetectionHistoryPage`（含篩選 / 分頁 / 刪除）
- [x] `DetectionHistoryPage` 大量紀錄 UX：固定高度雙欄、Task List / Detail 獨立捲動、固定分頁列、900px 以下單面板切換
- [x] 建立 `ProfilePage`（含 nickname / password 自我更新）
- [x] 建立 `ChatPage`
- [x] `ChatPage` 大量對話 UX：左右面板同高、Conversations 獨立捲動、最近 100 組紀錄、conversation 級二次確認刪除
- [x] 建立 `admin/UserManagementPage`（含 Edit 彈窗 + is_active 切換）
- [x] 建立 `authService` / `detectionService` / `userService` / `chatService`
- [x] `npm run build` 通過
- [x] API 層串接 backend 驗證（auth / detection / users / chat history）
- [x] 新增 `mock` chat provider 供本地 UI 驗證
- [x] 逐步驗證主流程 API / runtime：
 - register/login（username 與 email 均可登入）
 - admin users list/create/edit/delete
 - image detection / detection history（篩選 + 刪除）
 - profile 自我更新（nickname / password）
 - mock chat
 - desktop register/admin 表單新規則 runtime 檢查
- [x] Backend：新增 `PUT /api/auth/profile`（自助更新 nickname/password）
- [x] Backend：`UserUpdate` 新增 `is_active` 欄位
- [ ] Chat streaming Web UI（視需求，非阻塞）

---

## 文件同步規則

| 觸發事件 | 需要更新的文件 |
|---------|--------------|
| API 端點新增 / 修改 | `docs/api-spec.md` |
| 資料表結構變動 | `docs/database-design.md` |
| 架構設計變動 | `docs/architecture.md` |
| 目錄結構變動 | `README.md`（目錄結構區塊） |
| 啟動方式變動 | `README.md`（啟動方式區塊） |
| Phase 推進 | `README.md`（Phase 狀態表）+ `AGENTS.md`（當前 Phase） |
| 新增重要模組 | `docs/architecture.md` 或相關 docs |

---

## AI 工作流程

### 每次進入新工作階段時，請先：
1. 閱讀 `README.md`（了解目前 phase 與架構）
2. 閱讀 `AGENTS.md`（了解限制與規則）
3. 閱讀 `docs/architecture.md`（了解架構與資料流；legacy 現況見 README.md）
4. 閱讀本次任務相關的原始碼檔案

### 輸出報告格式
在開始實作前，先輸出：
- **現況理解**：你對目前專案狀況的理解
- **本次範圍**：這次要改哪些檔案、做哪些事
- **預計影響**：哪些功能可能受到影響
- **驗證方式**：如何確認修改後功能正確

### 完成後必須回報
- 修改 / 新增了哪些檔案
- 做了哪些事情
- 如何啟動與驗證
- 還有哪些未完成項目
- 建議下一步

---

## 下一步待辦（Phase 1 任務清單）

```
backend/
├── main.py                     # FastAPI app entry point
├── requirements.txt            # 依賴套件
├── .env.example                # 環境變數範例
├── alembic.ini                 # Alembic 設定
├── migrations/                 # Alembic migration 腳本
└── app/
    ├── __init__.py
    ├── api/
    │   ├── __init__.py
    │   └── routes/
    │       ├── __init__.py
    │       ├── auth.py         # /api/auth/*
    │       ├── users.py        # /api/users/*
    │       └── health.py      # /api/health
    ├── core/
    │   ├── __init__.py
    │   ├── config.py           # 讀取 .env
    │   ├── security.py         # JWT、bcrypt
    │   └── deps.py             # FastAPI dependencies
    ├── db/
    │   ├── __init__.py
    │   └── session.py          # SQLAlchemy engine & session
    ├── models/
    │   ├── __init__.py
    │   └── user.py             # User ORM model
    └── schemas/
        ├── __init__.py
        └── user.py             # Pydantic schemas
```

---

## Legacy 主要問題摘要（給 AI 快速參考）

| 問題 | 位置 | Phase 修復 |
|------|------|-----------|
| 硬編碼 DB 連線資訊 | `mysql/dataDB.py` L6-11 | Phase 1 |
| SQL 注入風險（字串格式化） | `Login.py` L82, `Register.py` L124,137 | Phase 1 |
| 明文密碼儲存 | `Register.py` L137, `yolo.sql` | Phase 1 |
| 硬編碼 DeepSeek API Key | `utils/deepseek.py` L14 | Phase 4 |
| UI 直接執行 SQL | 所有 `*UI.py` 檔案 | Phase 2 |
| PySide6 依賴注入到 service 層 | `utils/deepseek.py`, `utils/UserInfo.py` | Phase 4 |
| 全域共享連線（非 thread-safe） | `mysql/dataDB.py` L23 | Phase 1 |

---

## macOS Sonoma 啟動注意事項

因 Gatekeeper 掃描 native extension，使用 pip venv 冷啟動約 1-2 分鐘。
建議使用 conda 環境（冷啟動約 20 秒）：
```bash
conda activate yolo-backend
cd backend && uvicorn main:app --reload --port 8000
```

---

*最後更新: AI Chat Conversations UX 與刪除功能 — 2026-07-24*
