# Phase 6A-1 — Backend Agentic Layer with LangChain / LangGraph / DeepAgents

你現在要協助重構一個 YOLO System 專案。這個專案目前包含：

1. FastAPI Backend
2. PySide6 Desktop App
3. React + Vite Web Frontend
4. MySQL database
5. YOLO detection service
6. Provider-based chat service
7. Auth / Users / Upload / Detection History / Chat / Admin Users

本階段任務只做 **Backend Agentic Layer**，不要修改 Web Frontend UI，不要大改 Desktop UI。

---

## 一、核心原則

本次任務不是把整個系統全部改成 LangChain / LangGraph / DeepAgents。

請採用「漸進式 Agentic Layer」重構策略：

1. 保留現有 FastAPI routes、services、repositories、models、schemas。
2. 保留 `detection_service.py` 與 `yolo_engine.py` 作為 deterministic YOLO inference 核心。
3. 不要讓 LLM 直接取代 YOLO inference。
4. 不要破壞既有 Desktop API client。
5. 不要破壞既有 Web ChatPage 與 `/api/chat`。
6. 新增 LangChain / LangGraph / DeepAgents 只負責：
   - AI 任務編排
   - YOLO 結果解釋
   - Detection history 分析
   - 報告產生
   - 管理員輔助查詢
   - 智慧助理對話
7. 新增功能必須可以與原本 `/api/chat`、`/api/detections/*` 共存。
8. 若 `deepagents` 套件或 API 不穩，請先用 LangGraph 完成核心 agent workflow，DeepAgents 作為 optional enhancement。
9. 不要讓 LangGraph / DeepAgents import error 造成 backend 無法啟動。

本階段名稱：

> Phase 6A-1 — Backend Agentic Layer with LangChain / LangGraph / DeepAgents

---

## 二、請先閱讀並理解以下檔案

Backend：

1. `README.md`
2. `AGENTS.md`
3. `docs/architecture.md`
4. `docs/api-spec.md`
5. `docs/database-design.md`
6. `docs/roadmap.md`
7. `backend/main.py`
8. `backend/app/core/config.py`
9. `backend/app/core/deps.py`
10. `backend/app/api/routes/chat.py`
11. `backend/app/api/routes/detections.py`
12. `backend/app/api/routes/users.py`
13. `backend/app/services/chat_service.py`
14. `backend/app/services/detection_service.py`
15. `backend/app/services/user_service.py`
16. `backend/app/repositories/chat_repository.py`
17. `backend/app/repositories/detection_repository.py`
18. `backend/app/integrations/yolo_engine.py`
19. `backend/app/schemas/chat.py`
20. `backend/app/schemas/detection.py`
21. `backend/app/models/chat_log.py`
22. `backend/app/models/detection_task.py`
23. `backend/app/models/detection_object.py`
24. `backend/app/models/user.py`

Desktop 只需檢查，不要大改：

26. `desktop-app/api_client.py`
27. `AICSMain.py`
28. `MainUI.py`

Web Frontend 只需檢查，不要修改：

29. `web-frontend/src/services/api.js`
30. `web-frontend/src/services/chatService.js`
31. `web-frontend/src/pages/ChatPage.jsx`

---

## 三、目標 Backend 架構

請新增以下架構：

```text
backend/app/
├── agents/
│   ├── __init__.py
│   ├── state.py
│   ├── graph.py
│   ├── service.py
│   ├── prompts.py
│   ├── llm.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── detection_tools.py
│   │   ├── history_tools.py
│   │   ├── user_tools.py
│   │   └── report_tools.py
│   └── subagents/
│       ├── __init__.py
│       ├── yolo_result_explainer.py
│       ├── detection_history_analyst.py
│       ├── admin_assistant.py
│       └── report_agent.py
│
├── api/routes/agents.py
├── schemas/agent.py
└── services/agent_service.py 或 agents/service.py
```

---

## 四、Backend 依賴更新

更新 `backend/requirements.txt`，新增必要套件，但不要移除原本套件：

```text
langchain
langgraph
langchain-openai
deepagents
```

注意：

1. `deepagents` 必須是 optional。
2. 如果 `deepagents` import 失敗，不可以讓整個 FastAPI backend 無法啟動。
3. 若 `deepagents` API 不穩，請先以 LangGraph supervisor workflow 完成核心功能。
4. 請在文件中標註 DeepAgents 為 optional enhancement。

---

## 五、Backend 設定更新

更新 `backend/app/core/config.py`，新增 agent 相關設定：

- `AGENT_PROVIDER`，預設沿用 `CHAT_PROVIDER`
- `AGENT_MODEL`，預設沿用 `OPENAI_CHAT_MODEL`
- `AGENT_ENABLE_DEEPAGENTS`，預設 `false`
- `AGENT_MAX_HISTORY_TURNS`，預設 `10`
- `AGENT_SYSTEM_PROMPT`
- `AGENT_RECURSION_LIMIT`，預設 `25`

請確保這些設定不會破壞原本 chat provider 設定。

---

## 六、Agent schemas

新增 `backend/app/schemas/agent.py`，至少包含：

### AgentChatRequest

- `message: str`
- `conversation_id: Optional[str]`
- `mode: Optional[str]`
  - `auto`
  - `general_chat`
  - `explain_detection`
  - `history_analysis`
  - `report`
  - `admin_help`
- `detection_id: Optional[int]`
- `stream: Optional[bool]`

### AgentChatResponse

- `conversation_id: str`
- `answer: str`
- `mode: str`
- `tool_calls: list | None`
- `references: list | None`

### AgentModeRead

- `key: str`
- `label: str`
- `description: str`
- `admin_only: bool`

---

## 七、Agent tools

在 `backend/app/agents/tools/` 中建立工具。

工具必須包裝既有 service / repository，不要重寫業務邏輯。

### 1. detection_tools.py

請提供：

- `get_detection_detail_tool`
- `explain_detection_objects_tool`
- `compare_detection_results_tool`

功能：

- 讀取 detection task
- 讀取 detection objects
- 回傳 `class_name`、`confidence`、`bbox`、`source_type`、`model_name`、`status`、`inference_ms`、image size 等資訊
- 不要直接操作 YOLO model
- 若需要 inference，只能呼叫現有 `detection_service`

### 2. history_tools.py

請提供：

- `list_recent_detections_tool`
- `summarize_detection_history_tool`
- `filter_detections_by_status_or_type_tool`

功能：

- 查詢目前使用者自己的 detection history
- admin 可以查詢全部或指定使用者，但必須檢查權限
- 可統計 success / failed / processing 數量
- 可統計常見 `class_name`
- 可統計最近任務

### 3. user_tools.py

請提供：

- `get_current_user_profile_tool`
- `admin_list_users_tool`

注意：

- 非 admin 不可查所有 users
- 不要讓 agent 修改、刪除使用者
- 本階段只做 read-only admin assistance

### 4. report_tools.py

請提供：

- `generate_detection_report_markdown_tool`
- `summarize_model_performance_tool`

功能：

- 輸出 markdown 報告字串即可
- 不需要先做 PDF
- 報告應包含：
  - task metadata
  - source type
  - file name
  - model name
  - status
  - inference time
  - image size
  - object count
  - detected objects table
  - interpretation
  - limitations

### 工具設計要求

1. 每個 tool 都要有清楚 docstring。
2. 每個 tool 都要處理錯誤，不能讓 exception 直接中斷 agent。
3. 涉及 `user_id` / `current_user` 的工具必須限制資料存取權限。
4. Admin-only tool 必須檢查 `current_user.is_admin`。
5. 不要讓 agent 可以任意讀寫檔案系統。
6. 不要讓 agent 執行任意 SQL。
7. 不要讓 agent 直接刪除 detection、user、chat log。

---

## 八、LangGraph state

新增 `backend/app/agents/state.py`。

請定義 `AgentState`，至少包含：

- `messages`
- `user_id`
- `username`
- `is_admin`
- `conversation_id`
- `mode`
- `intent`
- `detection_id`
- `tool_results`
- `final_answer`
- `errors`

---

## 九、LLM Provider 封裝

新增 `backend/app/agents/llm.py`。

目的：

1. 盡量沿用既有 chat provider 設定。
2. 支援 `openai` / `deepseek` / `mock`。
3. 若 `CHAT_PROVIDER` 或 `AGENT_PROVIDER = mock`，agent 仍可回傳 mock answer，方便本地測試。
4. 不要讓缺少 API key 時整個 backend 掛掉。

---

## 十、LangGraph graph

新增 `backend/app/agents/graph.py`。

請使用 LangGraph 建立 supervisor workflow。

建議節點：

### 1. classify_intent

判斷使用者要做：

- `general_chat`
- `explain_detection`
- `detection_history_analysis`
- `generate_report`
- `admin_help`

規則：

- 如果 request.mode 有指定，優先使用 mode。
- 如果 mode = `auto`，才讓規則或 LLM 判斷 intent。
- 如果 `detection_id` 存在，優先允許 `explain_detection` / `report`。
- 如果需要 admin 權限但 `current_user.is_admin = false`，直接回覆權限不足。

### 2. call_tools_or_subagent

根據 intent 呼叫相應 subagent 或 tools。

### 3. compose_answer

整理工具結果與 LLM 回覆。

### 4. handle_error

統一錯誤訊息。

---

## 十一、Subagents

在 `backend/app/agents/subagents/` 中建立以下 subagent prompt 或 helper。

### 1. yolo_result_explainer.py

負責把 detection objects 轉成自然語言解釋。

必須包含：

- 偵測到哪些類別
- 各類別數量
- 信心分數範圍
- bbox 大致位置描述
- 模型名稱
- 推論時間
- 限制說明

重要提醒：

> YOLO 結果是模型預測，不等於人工標註真值。

### 2. detection_history_analyst.py

負責分析使用者過去 detection history。

可統計：

- 任務總數
- 成功 / 失敗 / 處理中數量
- 最近任務
- 常見類別
- 平均 inference time
- 最近一次任務狀態

### 3. report_agent.py

負責產生 markdown 報告。

報告格式建議：

```markdown
# YOLO Detection Report

## 1. Task Summary
## 2. Input Source
## 3. Model and Inference
## 4. Detected Objects
## 5. Interpretation
## 6. Limitations
## 7. Suggested Next Steps
```

### 4. admin_assistant.py

僅限 admin。

可以協助摘要：

- 使用者數量
- 最近 detection 任務情況
- 最近 chat / agent activity
- 系統使用概況

不要直接修改或刪除資料。

---

## 十二、Agent service

新增 `backend/app/agents/service.py` 或 `backend/app/services/agent_service.py`。

提供：

```python
create_agent_reply(
    db,
    current_user,
    message,
    conversation_id=None,
    mode="auto",
    detection_id=None,
)
```

功能：

1. 建立或沿用 `conversation_id`。
2. 呼叫 LangGraph graph。
3. 將 user message 與 agent answer 寫入現有 `chat_logs`。
4. `provider` 可填 `"langgraph-agent"`。
5. `model_name` 填實際模型，例如 `settings.AGENT_MODEL`。
6. 回傳 `AgentChatResponse`。
7. 如果 agent 執行失敗，回傳友善錯誤訊息，但不要洩漏敏感 traceback。

可選：

```python
stream_agent_reply(...)
```

本階段可以先不做 streaming，但請保留架構註解。

---

## 十三、Backend API route

新增 `backend/app/api/routes/agents.py`。

提供：

1. `POST /api/agent/chat`
2. `GET /api/agent/modes`

### POST /api/agent/chat

要求：

- 需要 JWT 驗證
- 呼叫 agent service
- 回傳 `AgentChatResponse`

### GET /api/agent/modes

回傳可用 modes：

- `auto`
- `general_chat`
- `explain_detection`
- `history_analysis`
- `report`
- `admin_help`

其中 `admin_help` 的 `admin_only = true`。

更新 `backend/main.py`：

```python
from app.api.routes import agents

app.include_router(agents.router, prefix="/api/agent", tags=["Agent"])
```

---

## 十四、保留既有 Chat API

不要刪除或破壞：

- `POST /api/chat`
- `POST /api/chat/stream`
- `GET /api/chat`
- `GET /api/chat/{conversation_id}`

新增 `/api/agent/chat` 作為進階智慧助理入口。

---

## 十五、Desktop 最小整合

本階段只更新 `desktop-app/api_client.py`，新增：

```python
agent_chat(
    access_token,
    message,
    conversation_id=None,
    mode="auto",
    detection_id=None,
)
```

要求：

1. 不要破壞原本 `chat()` / `stream_chat()`。
2. 不要大改 PySide6 UI。
3. 可以先只提供 API client method，不一定要立即做完整 UI。
4. 若要改 `AICSMain.py`，請採取最小修改：
   - 新增 Agent 模式入口或內部開關
   - 預設仍可用原本 `/api/chat`

---

## 十六、文件更新

更新以下文件：

### 1. README.md

新增：

- Phase 6A-1 狀態
- Agentic AI Layer 說明
- Backend 啟動方式
- `/api/agent/chat` 測試方式
- DeepAgents optional enhancement 說明

### 2. docs/architecture.md

加入 LangGraph / DeepAgents agentic layer 架構圖。

請明確寫出：

- YOLO inference 是 deterministic service
- Agentic layer 只負責 orchestration / explanation / analysis / reporting
- `/api/chat` 是一般 provider-based chat
- `/api/agent/chat` 是 LangGraph agent assistant

### 3. docs/api-spec.md

補上：

#### POST /api/agent/chat

Request example：

```json
{
  "message": "請解釋這筆 detection 結果",
  "conversation_id": null,
  "mode": "explain_detection",
  "detection_id": 1
}
```

Response example：

```json
{
  "conversation_id": "...",
  "answer": "...",
  "mode": "explain_detection",
  "tool_calls": [],
  "references": []
}
```

#### GET /api/agent/modes

### 4. docs/roadmap.md

新增 Phase 6A-1 checklist：

- Backend agent schemas
- Agent tools
- LangGraph supervisor
- Agent API routes
- Desktop API client method
- Documentation

### 5. AGENTS.md

補充 AI coding agent 注意事項：

- 不要 agent 化核心 CRUD
- 不要讓 LLM 直接執行危險 DB 寫入
- 不要讓 LLM 取代 YOLO inference
- Admin 操作需權限檢查
- 未來若要資料修改，需加入 human-in-the-loop
- `/api/chat` 與 `/api/agent/chat` 要分開，不可互相覆蓋

---

## 十七、驗證方式

完成後請提供以下驗證步驟。

### Backend

#### 1. 編譯檢查

```bash
python -m compileall backend/app
```

#### 2. 啟動 FastAPI

```bash
cd backend
uvicorn main:app --reload --port 8000
```

#### 3. Swagger 確認

打開：

```text
http://127.0.0.1:8000/docs
```

確認存在：

- `POST /api/agent/chat`
- `GET /api/agent/modes`

#### 4. API 測試

登入取得 token 後測試：

- `GET /api/agent/modes`
- `POST /api/agent/chat` with `mode=general_chat`
- `POST /api/agent/chat` with `mode=history_analysis`
- `POST /api/agent/chat` with `mode=explain_detection` and `detection_id`
- `POST /api/agent/chat` with `mode=report` and `detection_id`

#### 5. 權限測試

- 一般使用者不可使用 `admin_help` 查詢所有 users
- 管理員可以使用 `admin_help`

### Desktop

1. 確認 `desktop-app/api_client.py` 新增 `agent_chat` 不影響既有 login/chat/detection。
2. 若沒有 UI 整合，文件中標註 Desktop Agent UI 為下一階段。

---

## 十八、完成後回報格式

請按照以下格式回報：

1. 現況理解
2. 本次修改範圍
3. 新增/修改檔案列表
4. Backend 架構變更摘要
5. Desktop 變更摘要
6. API 變更摘要
7. 如何啟動與驗證
8. 目前限制
9. 下一步建議

---

## 十九、重要限制

請務必遵守：

1. 不要一次大爆改整個專案。
2. 不要刪掉 legacy desktop。
3. 不要刪掉既有 `/api/chat`。
4. 不要讓 `/api/chat` 與 `/api/agent/chat` 混在一起。
5. 不要讓 LangGraph / DeepAgents import error 造成 backend 無法啟動。
6. 不要讓 agent 任意操作資料庫。
7. 不要讓 agent 刪除使用者、刪除 detection、刪除 chat log。
8. 不要讓 agent 直接呼叫 YOLO model。
9. 不要把 deterministic detection pipeline 改成 LLM-driven pipeline。
10. 如果 DeepAgents 不穩，先以 LangGraph 完成核心 agent workflow，DeepAgents 留作 optional enhancement。
