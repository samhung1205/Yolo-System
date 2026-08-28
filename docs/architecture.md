# 架構設計文件

> **版本**: v1.0（Agent streaming 與 Web `/agent` 狀態校正）
> **最後更新**: 2026-08-28

---

## 1. 整體架構圖

```text
PySide6 Desktop  ──HTTP──>  FastAPI Backend  ──> MySQL
      │                         │
      │                         ├── Auth / Users Service
      │                         ├── Detection Service
      │                         ├── Chat Service
      │                         ├── YOLO Engine (Ultralytics)
      │                         ├── Chat Providers (OpenAI / DeepSeek)
      │                         └── Static Storage
      │
      ├── image/video detection 走 backend API
      ├── text chat 走 backend API
      └── webcam/RTSP 暫時仍走 legacy local YOLO
```

---

## 2. 目前實際分工

### Desktop
- `Login.py`
  - 呼叫 `/api/auth/*`
- `Register.py`
  - 呼叫 `/api/auth/register`
- `AdminMainUI.py` / `AdminAddUser.py` / `AdminEditUser.py`
  - 呼叫 `/api/users/*`
- `MainUI.py`
  - 單張圖片 detection 呼叫 `POST /api/detections/image`
  - 本地影片 detection 呼叫 `POST /api/detections/video`
  - detection history 呼叫 `GET /api/detections`
  - 單筆詳情呼叫 `GET /api/detections/{id}`
  - 開啟結果圖 / 結果影片使用 backend static URL
- `AICSMain.py`
  - 文字聊天呼叫 `POST /api/chat`
  - streaming 聊天呼叫 `POST /api/chat/stream`
  - 同一視窗內自動沿用 `conversation_id` 做多輪上下文
  - Desktop 只保留 chat bubble UI 與背景 thread 包裝，不再直接呼叫外部模型 API

### Web Frontend
- `LoginPage.jsx`
  - 呼叫 `/api/auth/login`
  - 支援 username 或 email 登入
- `RegisterPage.jsx`
  - 呼叫 `/api/auth/register`
  - 註冊規則：英數 username + email + 英數密碼
- `DashboardPage.jsx`
  - 顯示登入者基本資訊與入口
- `DetectionPage.jsx`
  - 呼叫 `POST /api/detections/image`
- `DetectionHistoryPage.jsx`
  - 呼叫 `GET /api/detections` / `GET /api/detections/{id}`
- `ProfilePage.jsx`
  - 呼叫 `/api/auth/me`
- `ChatPage.jsx`
  - 呼叫 `POST /api/chat` / `GET /api/chat` / `GET/DELETE /api/chat/{conversation_id}`
  - 一般 provider-based chat（OpenAI / DeepSeek），不走 agent layer
  - Conversations 與聊天區共用固定高度；清單獨立捲動並支援 conversation 級刪除
- `AgentPage.jsx` ← Phase 6A-2 新增
  - 路由：`/agent`
  - 呼叫 `POST /api/agent/chat`、`GET /api/agent/modes`
  - 獨立 LangGraph Agent 智慧助理介面，不影響 `/chat`
  - 支援 URL query params：`?mode=explain_detection&detection_id=123`
  - DetectionPage 與 DetectionHistoryPage 均有「Ask Agent to Explain」/「Generate Report」快捷按鈕跳轉此頁
- `admin/UserManagementPage.jsx`
  - 呼叫 `/api/users`
  - MVP 先做 list / create / delete

### Backend
- `app/api/routes/detections.py`
  - detection HTTP routes
- `app/services/detection_service.py`
  - detection 任務建立、序列化、刪除、background video processing
- `app/integrations/yolo_engine.py`
  - 封裝 Ultralytics YOLO 模型載入與 image/video inference
- `app/repositories/detection_repository.py`
  - detection task/object DB 存取
- `app/models/detection_task.py`
- `app/models/detection_object.py`
  - detection ORM
- `app/api/routes/chat.py`
  - `POST /api/chat`
  - `POST /api/chat/stream`
  - `GET /api/chat`
  - `GET /api/chat/{conversation_id}`
  - `DELETE /api/chat/{conversation_id}`
- `app/services/chat_service.py`
  - provider 選擇、錯誤映射、chat log 寫入、conversation context 聚合
- `app/integrations/chat_providers/*.py`
  - 雲端 chat provider adapter
- `app/repositories/chat_repository.py`
  - chat log DB 存取
- `app/models/chat_log.py`
  - chat log ORM

---

## 3. Detection 資料流

### 3.1 Image Detection

```text
Desktop MainUI
  └── POST /api/detections/image
        ├── 建立 detection_task
        ├── 儲存原圖
        ├── YOLO predict
        ├── 儲存結果圖
        ├── 寫入 detection_objects
        └── 回傳 task + objects
```

特性：
- 同步執行
- 適合單張圖片
- Desktop 收到回應後直接渲染左右圖與 table

### 3.2 Video Detection

```text
Desktop MainUI
  └── POST /api/detections/video
        ├── 建立 detection_task(status=processing)
        ├── 儲存原始影片
        └── 立即回傳 task id

FastAPI BackgroundTasks
  └── process_video_detection_task()
        ├── YOLO track 逐 frame 推論
        ├── 儲存結果影片
        ├── 產生 preview 圖
        ├── 寫入 detection_objects (preview frame)
        └── 更新 task(status=completed/failed)

Desktop MainUI
  └── 輪詢 GET /api/detections/{id}
        └── 完成後渲染 preview 圖與 table
```

特性：
- API 層非同步
- 目前 Desktop 仍以輪詢等待完成
- 尚未提供取消任務 / 百分比進度

---

## 4. Static Storage

```text
backend/static/
├── avatars/
├── detections/
│   ├── originals/
│   ├── results/
│   ├── previews/
│   └── videos/
│       ├── originals/
│       └── results/
└── results/
```

FastAPI 透過 `/static/...` 掛載這些檔案，Desktop 用完整 URL 讀取或開啟。

---

## 5. Chat 資料流

### 5.1 Text Chat / Conversation MVP

```text
Desktop AICSMain
  └── POST /api/chat
        ├── 驗證 JWT
        ├── ChatService 依 CHAT_PROVIDER 選擇 provider
        ├── 依 conversation_id 載入既有問答作為 context
        ├── 呼叫 OpenAI / DeepSeek cloud API
        ├── 將 question / answer / provider / model_name / conversation_id / turn_index 寫入 chat_logs
        └── 回傳單輪聊天結果
```

特性：
- 同步 API，Desktop 以本地 QThread 包裝避免 UI 卡住
- provider 由 `.env` 決定，不綁死單一供應商
- Desktop 不直接持有外部模型 API key
- 對話上下文先以 `chat_logs` 聚合，不另建 conversation table

### 5.2 Streaming Chat

```text
Desktop AICSMain
  └── POST /api/chat/stream
        ├── 驗證 JWT
        ├── 載入 conversation context
        ├── provider stream_chat()
        ├── 逐段輸出 SSE chunk
        ├── 完整 answer 組裝完成後寫入 chat_logs
        └── 回傳 done event
```

特性：
- backend 對 desktop 提供統一 SSE
- Desktop 不直接解析第三方 provider SSE 協定
- streaming 與非串流共用同一份 chat domain / history/context 設計

---

## 6. 目前仍保留的 Legacy 路徑

### `detect_mainui.py`
- webcam detection
- RTSP / 串流 detection
- local QThread signal-driven 即時推論

### `MainUI.py`
- 對 webcam / RTSP 的按鈕與 Qt thread 控制仍保留 legacy 流程

### `utils/deepseek.py`
- 已退出 desktop 主流程
- 暫時保留作為 legacy 參考，不再是正式 provider 實作

---

## 7. 已知限制

- `POST /api/detections/image` 仍為同步呼叫
- `POST /api/detections/video` 使用 `BackgroundTasks`，不是完整 job queue
- video detection 只保存 preview frame 的物件列表
- Desktop chat history 切換 UI 尚未建立
- Web Chat 頁目前尚未接 `POST /api/chat/stream`

---

## 8. Agentic Layer（Phase 6A-1）

### 8.1 定位

```text
PySide6 Desktop  ──HTTP──>  /api/agent/chat          ──>  AgentService
React Web        ──HTTP──>  /api/agent/chat/stream        │
                                                 ├── LangGraph Supervisor
                                                 │     ├── classify_intent
                                                 │     ├── call_tools_or_subagent
                                                 │     ├── compose_answer
                                                 │     └── handle_error
                                                 ├── Subagents
                                                 │     ├── yolo_result_explainer
                                                 │     ├── detection_history_analyst
                                                 │     ├── report_agent
                                                 │     └── admin_assistant
                                                 ├── Tools (read-only)
                                                 │     ├── detection_tools
                                                 │     ├── history_tools
                                                 │     ├── user_tools
                                                 │     └── report_tools
                                                 └── chat_logs (provider="langgraph-agent")
```

關鍵原則：

- YOLO 推論仍然由 `app/integrations/yolo_engine.py` 透過 `detection_service` 觸發，agent **只讀** 既有 `DetectionTask` / `DetectionObject`。
- `/api/chat` 與 `/api/agent/chat` 完全分開；兩者寫入同一張 `chat_logs`，但 agent 路徑使用 `provider="langgraph-agent"` 作為區隔，不需要 migration。
- LangChain / LangGraph / DeepAgents 一律以 lazy import + 友善 fallback 包裝；缺套件或缺 API key 時 agent 仍可回 mock 回覆，FastAPI 不會啟動失敗。
- DeepAgents 為 optional enhancement，預設 `AGENT_ENABLE_DEEPAGENTS=false`。

### 8.2 LangGraph workflow

```text
classify_intent ──> call_tools_or_subagent ──┬──> compose_answer ──> END
                                             └──> handle_error  ──> END
```

- `classify_intent`：若 request.mode != `auto` 直接套用該 mode；否則依使用者訊息與 `detection_id` 做關鍵字啟發式判斷。
- `call_tools_or_subagent`：依 intent 呼叫對應 subagent helper 取得 deterministic payload，並組出要餵給 LLM 的 message list。
- `compose_answer`：呼叫 `agents/llm.get_chat_model()` 產生最終回覆；若是 `generate_report`，保證 deterministic markdown 不會被 LLM 改寫，會放在 LLM 解讀文字之前。
- `handle_error`：把 `permission_denied` / `detection not found` / `requires detection_id` 等錯誤映射為使用者可見訊息。

### 8.3 Agent 工具邊界

| 工具 | 權限 | 行為 |
|------|------|------|
| `get_detection_detail_tool` / `explain_detection_objects_tool` / `compare_detection_results_tool` | 擁有者或 admin | read-only |
| `list_recent_detections_tool` / `summarize_detection_history_tool` / `filter_detections_by_status_or_type_tool` | 非 admin 強制 `user_id=current_user.id` | read-only |
| `get_current_user_profile_tool` | 自己 | read-only |
| `admin_list_users_tool` | admin only（函式開頭硬檢查） | read-only |
| `generate_detection_report_markdown_tool` / `summarize_model_performance_tool` | 擁有者或 admin | read-only |

本階段 **不曝露** delete / update / create 類工具。Agent 不可直接觸發 detection、不可呼叫 YOLO。

### 8.4 已知限制

- DeepAgents 整合僅保留 flag，沒有真實 subagent registry。
- Agent 工具僅唯讀；不提供 create / update / delete，也不能觸發 YOLO 推論。

> 更正（2026-08-28）：本節先前記載「agent streaming 尚未實作」與「Web
> Frontend 尚未提供 `/agent` 入口」，兩者皆已於 Phase 6A-2／6A-3 完成：
> `POST /api/agent/chat/stream` 由 `agents/service.stream_agent_reply()`
> 實作為 SSE，Web 端入口為 `web-frontend/src/pages/AgentPage.jsx`
> （路由 `/agent`）。

---

## 9. 下一步建議

1. 補 Web 一般對話頁的 streaming UI（`/chat` 尚未接 SSE；`/agent` 已接）
2. 將 image detection 也統一為 async task
3. 將 webcam / RTSP 改為 backend 任務或專門 streaming service
4. Phase 6：Docker、部署文件與 CI/CD
