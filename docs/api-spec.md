# API 規格文件

> **版本**: v0.7 (Phase 6A-4 LLM Model Selector)  
> **Base URL**: `http://localhost:8000`  
> **最後更新**: 2026-06-09

---

## 通用規範

### 認證方式
需要認證的端點使用 Bearer Token：
```http
Authorization: Bearer <jwt_token>
```

### 錯誤格式
```json
{
  "detail": "錯誤說明"
}
```

### 狀態碼
| 狀態碼 | 說明 |
|--------|------|
| 200 | 成功 |
| 201 | 建立成功 |
| 202 | 任務已接受，背景執行中 |
| 204 | 刪除成功 |
| 400 | 請求錯誤 |
| 401 | 未認證 |
| 403 | 無權限 |
| 404 | 資源不存在 |
| 409 | 資源衝突 |
| 422 | 驗證錯誤 |
| 500 | 伺服器錯誤 |

### 靜態資源（`/static/*`）

偵測結果圖、影片、頭像等靜態檔**不再公開存取**。因為 `<img>` 無法帶 `Authorization` header，API 回傳的 `*_url` / `avatar_url` 會內嵌短期 signed query：

```http
GET /static/detections/results/task_12_a1b2c3d4.jpg?sig=<hmac>&exp=<unix_ts>
```

- `sig`：以 `SECRET_KEY` 對 `v1:{relative_path}:{exp}` 做 HMAC-SHA256
- `exp`：Unix 秒級到期時間；預設由 `.env` 的 `STATIC_URL_EXPIRE_SECONDS` 控制（預設 3600 秒）
- 程式化下載也可改用 `Authorization: Bearer <jwt>` 直接存取 `/static/...`（不需 query），後端會依資源類型檢查擁有權

**Response 欄位**
- `UserRead.avatar`：仍為 DB 內的檔名（供更新用）
- `UserRead.avatar_url`：已簽名的顯示用 URL
- `DetectionTask*.*_url`：皆為已簽名 URL

---

## Auth 端點

### POST /api/auth/register
> 驗證規則：
> - `username`：英數字，長度 `3-32`
> - `email`：合法 Email 格式
> - `password`：至少 `8` 位，且需同時包含英文與數字

```json
{
  "username": "samdemo",
  "email": "sam@example.com",
  "password": "abc12345",
  "nickname": "我的暱稱"
}
```

**Response 201**
```json
{
  "id": 1,
  "username": "samdemo",
  "email": "sam@example.com",
  "nickname": "我的暱稱",
  "avatar": null,
  "register_time": "2026-04-18T10:00:00",
  "is_admin": false,
  "is_active": true
}
```

### POST /api/auth/login
> `username` 欄位可填使用者名稱或 Email

```json
{
  "username": "samdemo",
  "password": "abc12345"
}
```

**Response 200**
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "samdemo",
    "email": "sam@example.com",
    "nickname": "我的暱稱",
    "avatar": null,
    "register_time": "2026-04-18T10:00:00",
    "is_admin": false,
    "is_active": true
  }
}
```

### GET /api/auth/me
**Response 200**
```json
{
  "id": 1,
  "username": "samdemo",
  "email": "sam@example.com",
  "nickname": "我的暱稱",
  "avatar": "20260418_example.jpg",
  "register_time": "2026-04-18T10:00:00",
  "is_admin": false,
  "is_active": true
}
```

---

## Users 端點

### GET /api/users
**Query Params**
- `page` (int, default `1`)
- `limit` (int, default `20`)
- `search` (str, optional)

**Response 200**
```json
{
  "items": [
    {
      "id": 1,
      "username": "samdemo",
      "email": "sam@example.com",
      "nickname": "我的暱稱",
      "avatar": "20260418_example.jpg",
      "register_time": "2026-04-18T10:00:00",
      "is_admin": false,
      "is_active": true
    }
  ],
  "total": 1,
  "page": 1,
  "limit": 20
}
```

### POST /api/users
```json
{
  "username": "demouser2",
  "email": "demo2@example.com",
  "password": "abc12345",
  "nickname": "新使用者",
  "avatar": "20260418_example.jpg"
}
```

### PUT /api/users/{id}
```json
{
  "nickname": "新暱稱",
  "username": "demoedit3",
  "email": "demo3@example.com",
  "password": "newpass123",
  "is_admin": false,
  "avatar": "20260418_example.jpg"
}
```

### DELETE /api/users/{id}
**Response 200**
```json
{
  "message": "User deleted successfully"
}
```

---

## Upload 端點

### POST /api/upload/avatar
**Request Body**
- `file`: JPEG / PNG / GIF / WEBP，大小限制 5 MB

**Response 200**
```json
{
  "filename": "20260418120000_ab12cd34.jpg",
  "url": "/static/avatars/20260418120000_ab12cd34.jpg"
}
```

---

## Chat 端點

### POST /api/chat
> 單輪/多輪文字聊天，需登入後使用。若帶入 `conversation_id`，backend 會把同一對話的既有問答當作 context。
> `provider` 與 `model` 為 per-request override，可由前端模型選單傳入；省略時沿用 `.env` 設定。

```json
{
  "question": "請用三句話說明 YOLO detection service 的用途",
  "conversation_id": "0f4f24d3a5f84d6ea4ce3cae4a0b1e9f",
  "provider": "openai",
  "model": "gpt-4o"
}
```

欄位說明：

| 欄位 | 必填 | 說明 |
|------|------|------|
| `question` | ✅ | 使用者訊息，1-8000 字 |
| `conversation_id` | ❌ | 同對話 id 才能延續 context；省略則自動產生 |
| `provider` | ❌ | 覆蓋 `CHAT_PROVIDER`：`openai` / `deepseek` / `ollama` |
| `model` | ❌ | 覆蓋預設模型名稱，例如 `gpt-4o`、`deepseek-coder` |

**Response 201**
```json
{
  "id": 5,
  "user_id": 1,
  "conversation_id": "0f4f24d3a5f84d6ea4ce3cae4a0b1e9f",
  "turn_index": 2,
  "provider": "openai",
  "model_name": "gpt-4.1-mini",
  "question": "請用三句話說明 YOLO detection service 的用途",
  "answer": "YOLO detection service 會接收圖片或影片並執行物件偵測。它會保存原始檔、結果檔與偵測物件資料。桌面版與未來的 Web 前端都可以共用這條 backend API。",
  "created_at": "2026-04-19T10:00:00"
}
```

**可能錯誤**
- `503 Service Unavailable`
  - `CHAT_PROVIDER` 未設定正確
  - 對應 provider API key 未設定
- `502 Bad Gateway`
  - provider 上游 API 呼叫失敗

**本地驗證補充**
- `CHAT_PROVIDER=mock` 時，`POST /api/chat` 與 `POST /api/chat/stream` 會回傳本地生成的假資料，用於 UI 串接驗證；正式環境應使用 `openai` 或 `deepseek`

### GET /api/chat
> 取得目前使用者的對話列表摘要

**Query Params**
- `limit` (int, default `20`, max `100`)

**Response 200**
```json
[
  {
    "conversation_id": "0f4f24d3a5f84d6ea4ce3cae4a0b1e9f",
    "title": "請用三句話說明 YOLO detection service...",
    "provider": "openai",
    "model_name": "gpt-4.1-mini",
    "turn_count": 2,
    "last_question": "那這樣桌面端要改哪些地方？",
    "last_answer_preview": "桌面端主要要改 MainUI 與 AICSMain 的 API 呼叫鏈路...",
    "created_at": "2026-04-19T10:00:00",
    "updated_at": "2026-04-19T10:02:00"
  }
]
```

### GET /api/chat/{conversation_id}
> 取得單一對話的完整問答歷史

**Response 200**
```json
{
  "conversation_id": "0f4f24d3a5f84d6ea4ce3cae4a0b1e9f",
  "title": "請用三句話說明 YOLO detection service...",
  "turn_count": 2,
  "created_at": "2026-04-19T10:00:00",
  "updated_at": "2026-04-19T10:02:00",
  "messages": [
    {
      "id": 4,
      "user_id": 1,
      "conversation_id": "0f4f24d3a5f84d6ea4ce3cae4a0b1e9f",
      "turn_index": 1,
      "provider": "openai",
      "model_name": "gpt-4.1-mini",
      "question": "請用三句話說明 YOLO detection service 的用途",
      "answer": "YOLO detection service 會接收圖片或影片並執行物件偵測...",
      "created_at": "2026-04-19T10:00:00"
    }
  ]
}
```

### POST /api/chat/stream
> SSE 串流聊天版本。Desktop 目前主要使用這條 API 逐段更新 assistant bubble。
> 接受與 `POST /api/chat` 相同的 `provider` / `model` per-request override 欄位。

```json
{
  "question": "請用三句話介紹本系統",
  "conversation_id": "0f4f24d3a5f84d6ea4ce3cae4a0b1e9f",
  "provider": "ollama",
  "model": "llama3.2"
}
```

**Response 200**
`Content-Type: text/event-stream`

事件格式：
```text
data: {"type":"start","conversation_id":"0f4f24d3a5f84d6ea4ce3cae4a0b1e9f","turn_index":3,"provider":"openai","model_name":"gpt-4.1-mini"}

data: {"type":"chunk","delta":"本系統"}

data: {"type":"chunk","delta":"整合了 YOLO 偵測、使用者管理與 AI 對話。"}

data: {"type":"done","id":8,"user_id":1,"conversation_id":"0f4f24d3a5f84d6ea4ce3cae4a0b1e9f","turn_index":3,"provider":"openai","model_name":"gpt-4.1-mini","question":"請用三句話介紹本系統","answer":"本系統整合了 YOLO 偵測、使用者管理與 AI 對話。","created_at":"2026-04-19T12:00:00"}
```

若失敗，會回傳：
```text
data: {"type":"error","message":"錯誤訊息"}
```

---

## Detections 端點

### Detection Task Summary
```json
{
  "id": 12,
  "user_id": 3,
  "source_type": "image",
  "source_filename": "test.jpg",
  "source_image_path": "detections/originals/task_12_a1b2c3d4.jpg",
  "source_image_url": "/static/detections/originals/task_12_a1b2c3d4.jpg",
  "result_image_path": "detections/results/task_12_a1b2c3d4.jpg",
  "result_image_url": "/static/detections/results/task_12_a1b2c3d4.jpg",
  "source_video_path": null,
  "source_video_url": null,
  "result_video_path": null,
  "result_video_url": null,
  "preview_image_path": null,
  "preview_image_url": null,
  "model_name": "yolo11n.pt",
  "status": "completed",
  "inference_ms": 123.45,
  "image_width": 1280,
  "image_height": 720,
  "frame_count": null,
  "object_count": 2,
  "created_at": "2026-04-18T12:00:00",
  "updated_at": "2026-04-18T12:00:01"
}
```

### Detection Object
```json
{
  "id": 31,
  "object_index": 1,
  "class_id": 0,
  "class_name": "person",
  "confidence": 0.92,
  "bbox": [120.0, 45.0, 420.0, 600.0]
}
```

### POST /api/detections/image
> 單張圖片 YOLO 偵測，立即完成後回傳結果

**Query Params**
- `conf` (float, default `0.25`)
- `iou` (float, default `0.45`)

**Request Body**
- `file`: 圖片檔案

**Response 201**
```json
{
  "id": 12,
  "user_id": 3,
  "source_type": "image",
  "source_filename": "test.jpg",
  "source_image_path": "detections/originals/task_12_a1b2c3d4.jpg",
  "source_image_url": "/static/detections/originals/task_12_a1b2c3d4.jpg",
  "result_image_path": "detections/results/task_12_a1b2c3d4.jpg",
  "result_image_url": "/static/detections/results/task_12_a1b2c3d4.jpg",
  "source_video_path": null,
  "source_video_url": null,
  "result_video_path": null,
  "result_video_url": null,
  "preview_image_path": null,
  "preview_image_url": null,
  "model_name": "yolo11n.pt",
  "status": "completed",
  "inference_ms": 123.45,
  "image_width": 1280,
  "image_height": 720,
  "frame_count": null,
  "object_count": 2,
  "created_at": "2026-04-18T12:00:00",
  "updated_at": "2026-04-18T12:00:01",
  "error_message": null,
  "objects": [
    {
      "id": 31,
      "object_index": 1,
      "class_id": 0,
      "class_name": "person",
      "confidence": 0.92,
      "bbox": [120.0, 45.0, 420.0, 600.0]
    }
  ]
}
```

### POST /api/detections/video
> 單支影片 YOLO 偵測，建立 task 後以背景任務執行

**Query Params**
- `conf` (float, default `0.25`)
- `iou` (float, default `0.45`)

**Request Body**
- `file`: MP4 / MOV / AVI / MKV / FLV

**Response 202**
```json
{
  "id": 18,
  "user_id": 3,
  "source_type": "video",
  "source_filename": "demo.mp4",
  "source_image_path": null,
  "source_image_url": null,
  "result_image_path": null,
  "result_image_url": null,
  "source_video_path": "detections/videos/originals/task_18_a1b2c3d4.mp4",
  "source_video_url": "/static/detections/videos/originals/task_18_a1b2c3d4.mp4",
  "result_video_path": null,
  "result_video_url": null,
  "preview_image_path": null,
  "preview_image_url": null,
  "model_name": "yolo11n.pt",
  "status": "processing",
  "inference_ms": null,
  "image_width": null,
  "image_height": null,
  "frame_count": null,
  "object_count": 0,
  "created_at": "2026-04-18T12:10:00",
  "updated_at": "2026-04-18T12:10:00",
  "error_message": null,
  "objects": []
}
```

### GET /api/detections
> 一般使用者看自己的 tasks，admin 可看全部

**Response 200**
```json
[
  {
    "id": 18,
    "user_id": 3,
    "source_type": "video",
    "source_filename": "demo.mp4",
    "source_image_path": null,
    "source_image_url": null,
    "result_image_path": null,
    "result_image_url": null,
    "source_video_path": "detections/videos/originals/task_18_a1b2c3d4.mp4",
    "source_video_url": "/static/detections/videos/originals/task_18_a1b2c3d4.mp4",
    "result_video_path": "detections/videos/results/task_18_e5f6g7h8.mp4",
    "result_video_url": "/static/detections/videos/results/task_18_e5f6g7h8.mp4",
    "preview_image_path": "detections/previews/task_18_i9j0k1l2.jpg",
    "preview_image_url": "/static/detections/previews/task_18_i9j0k1l2.jpg",
    "model_name": "yolo11n.pt",
    "status": "completed",
    "inference_ms": 6042.21,
    "image_width": 1280,
    "image_height": 720,
    "frame_count": 300,
    "object_count": 4,
    "created_at": "2026-04-18T12:10:00",
    "updated_at": "2026-04-18T12:10:07"
  }
]
```

### GET /api/detections/{id}
> 取得單筆 detection 詳情

**Response 200**
- 回傳格式與 `POST /api/detections/image` 相同，但依實際 task type 帶入 image 或 video 欄位

### DELETE /api/detections/{id}
> 刪除 detection task 與相關靜態檔案

**Response 204**
- 無回應 body

---

## Agent 端點（Phase 6A-1）

> 這是 LangGraph supervisor 提供的進階智慧助理入口，與 `/api/chat` 完全獨立。寫入的 chat log `provider="langgraph-agent"`，與 provider-based chat 不衝突。

### POST /api/agent/chat
> 需要 JWT 驗證

```json
{
  "message": "請解釋這筆 detection 結果",
  "conversation_id": null,
  "mode": "explain_detection",
  "detection_id": 1,
  "provider": "openai",
  "model": "gpt-4o"
}
```

欄位說明：

| 欄位 | 必填 | 說明 |
|------|------|------|
| `message` | ✅ | 使用者訊息，1-8000 字 |
| `conversation_id` | ❌ | 缺省會自動產生 |
| `mode` | ❌ | `auto` / `general_chat` / `explain_detection` / `history_analysis` / `report` / `admin_help`，缺省為 `auto` |
| `detection_id` | ❌ | `explain_detection` / `report` 模式必填；指向 `detection_tasks.id` |
| `stream` | ❌ | 保留欄位（已改用 `/api/agent/chat/stream` 獨立端點） |
| `provider` | ❌ | 覆蓋 `AGENT_PROVIDER`：`openai` / `deepseek` / `ollama` |
| `model` | ❌ | 覆蓋預設 agent 模型名稱 |

**Response 200**

```json
{
  "conversation_id": "8b1c8b2bf7c84d2bbb6ee0f1ab4e8d2f",
  "answer": "...",
  "mode": "explain_detection",
  "tool_calls": [
    {"tool": "yolo_explainer", "ok": true}
  ],
  "references": [
    {"type": "detection", "detection_id": 1}
  ]
}
```

錯誤對應：

- 一般使用者呼叫 `mode=admin_help` → `answer` 會回傳「此操作需要管理員權限」訊息，HTTP 200（agent friendly error）。
- `mode=explain_detection` / `report` 缺 `detection_id` → `answer` 會說明需要提供 detection_id，HTTP 200。
- 指定的 `detection_id` 不屬於使用者（非 admin）→ `answer` 會說明「無權存取指定的偵測任務」，HTTP 200。
- LangChain / LangGraph 未安裝或 LLM provider 失敗 → 自動切換 mock LLM，回傳 mock 回覆，HTTP 200。

### POST /api/agent/chat/stream  ← Phase 6A-3 新增
> 需要 JWT 驗證 · Content-Type: application/json · Accept: text/event-stream

Request body 與 `POST /api/agent/chat` 完全相同（含 `provider` / `model` override 欄位）。

SSE 事件格式：

```text
data: {"type": "start", "conversation_id": "...", "mode": "...", "tool_calls": [...], "references": [...]}

data: {"type": "chunk", "delta": "..."}        (一或多次)

data: {"type": "done",  "conversation_id": "...", "answer": "...", "mode": "...", "tool_calls": [...], "references": [...]}

data: {"type": "error", "message": "..."}      (僅在失敗時)
```

工具呼叫（tool calls）在 `start` 事件完成後即回傳，LLM 答案以 `chunk` 漸進串流。
`done` 事件同時觸發 `chat_logs` 寫入（`provider="langgraph-agent"`）。

Web 端使用 native `fetch` + `ReadableStream`（`agentService.js → streamAgentMessage()`）。
Desktop 端使用 `DesktopApiClient.stream_agent_chat()`（`AICSMain.py → AgentApiThread`）。

---

### GET /api/agent/modes
> 需要 JWT 驗證

**Response 200**

```json
[
  {"key": "auto",              "label": "自動偵測",       "description": "...", "admin_only": false},
  {"key": "general_chat",      "label": "一般對話",       "description": "...", "admin_only": false},
  {"key": "explain_detection", "label": "解釋偵測結果",   "description": "...", "admin_only": false},
  {"key": "history_analysis",  "label": "偵測歷史分析",   "description": "...", "admin_only": false},
  {"key": "report",            "label": "產出報告",       "description": "...", "admin_only": false},
  {"key": "admin_help",        "label": "管理員輔助",     "description": "...", "admin_only": true}
]
```

---

## Web Frontend 使用說明（Phase 6A-2）

| 頁面 | 呼叫端點 | 說明 |
|------|---------|------|
| `/chat` | `POST /api/chat` | 一般 provider-based chat（ChatPage.jsx → chatService.js） |
| `/agent` | `POST /api/agent/chat`、`GET /api/agent/modes` | LangGraph agent（AgentPage.jsx → agentService.js） |
| `/detections` 結果區 | 跳轉 `/agent?mode=explain_detection&detection_id={id}` | DetectionPage 快捷按鈕 |
| `/detections/history` 詳情區 | 跳轉 `/agent?mode=report&detection_id={id}` | DetectionHistoryPage 快捷按鈕 |

`agentService.js` 使用與 `chatService.js` 相同的 `api.js` axios instance（共用 token interceptor）。

---

## Models 端點（Phase 6A-4）

### GET /api/models
> 需要 JWT 驗證。回傳目前環境中可用的 LLM providers 與其模型清單，由前端模型選單用於動態渲染選項。

**決策邏輯：**
- `openai`：`.env` 中 `OPENAI_API_KEY` 有設定才回傳
- `deepseek`：`.env` 中 `DEEPSEEK_API_KEY` 有設定才回傳
- `ollama`：一律回傳；模型清單從 `OLLAMA_BASE_URL/api/tags` 即時查詢，若 Ollama 未啟動則 fallback 到 `OLLAMA_MODEL` 設定值
- `mock`：不出現在回傳清單（僅內部測試用）

**Response 200**
```json
[
  {
    "provider": "openai",
    "label": "OpenAI GPT",
    "models": ["gpt-4.1-mini", "gpt-4o", "gpt-4-turbo", "gpt-4"]
  },
  {
    "provider": "deepseek",
    "label": "DeepSeek",
    "models": ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"]
  },
  {
    "provider": "ollama",
    "label": "Ollama (本地)",
    "models": ["llama3.2", "gemma2:9b"]
  }
]
```

**前端整合：**
- `ChatPage`：mount 時呼叫，在 textarea 上方渲染 provider / model 雙下拉選單（`modelService.listModels()`）
- `AgentPage`：mount 時呼叫，在左側 controls 的 Detection ID 下方渲染相同選單
- 選單渲染所需的 `modelService.js` 沿用既有 `api.js` axios instance

---

## 目前限制

- `POST /api/detections/image` 為同步執行
- `POST /api/detections/video` 為 background task，需輪詢 `GET /api/detections/{id}`
- video detection 目前只保存 preview frame 的 detection objects，不保存每一幀結果
- webcam / RTSP / 串流尚未 backend 化
- Chat `/api/chat` streaming（`/api/chat/stream`）Web 前端尚未接入 SSE
