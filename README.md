# YOLO System — 桌面版 + Web 版雙軌架構

> 把一支 UI、業務邏輯與 SQL 全部耦合在同一層的 PySide6 桌面程式，
> 在不中斷既有功能的前提下，逐步重構成桌面版與 React Web 共用同一組
> FastAPI 後端的偵測平台。

**目前狀態**：後端、Web 前端與桌面版主流程皆可執行；容器化與部署（Phase 6）尚未開始，目前僅支援本機執行。

**技術棧**：FastAPI · SQLAlchemy · Alembic · MySQL · React 18 + Vite · PySide6 · Ultralytics YOLO · LangGraph

### 從哪裡開始讀

| 想知道 | 看這裡 |
|---|---|
| 架構怎麼演進、資料流長怎樣 | [docs/architecture.md](docs/architecture.md) |
| 有哪些 API 端點 | [docs/api-spec.md](docs/api-spec.md) |
| 資料表設計與 legacy 對照 | [docs/database-design.md](docs/database-design.md) |
| 怎麼跑起來 | 本文件的[啟動方式](#啟動方式) |
| 各階段做了什麼 | 本文件的[開發歷程](#開發歷程) |

---

## 專案簡介

本系統整合 YOLO 影像偵測、AI 對話與 agent 助理、使用者與管理員後台。原始版本為純 PySide6 桌面應用程式，UI、業務邏輯與資料庫操作高度耦合；重構的核心是把「誰可以直接存取資料庫、模型與外部 API」從 UI 移到後端，使桌面版與 Web 版能共用同一份業務邏輯。

---

## Legacy 專案現況與重構目標

### Legacy 現況

> 以下描述的是重構「之前」的狀態，作為對照保留。`mysql/dataDB.py` 與
> `utils/deepseek.py` 已在重構過程中移除，現行程式碼中不再存在。

- **框架**: PySide6 桌面應用
- **資料庫**: MySQL（直接在 UI handler 中執行 SQL）
- **密碼**: 明文儲存於資料庫
- **API Key**: 硬編碼於 `utils/deepseek.py`
- **DB 連線**: 硬編碼於 `mysql/dataDB.py`
- **SQL 注入風險**: 使用字串格式化拼接 SQL
- **狀態管理**: `mysql/dataDB.py` 中的全域 `SI` class 管理視窗引用

### 重構目標
1. UI / 業務邏輯 / 資料庫操作分層
2. 引入 FastAPI 後端作為共用核心服務
3. 引入 React Web 前端作為展示版本
4. 桌面版與 Web 版共用後端 API
5. 密碼改用 bcrypt hash，身分驗證使用 JWT
6. 敏感設定移至 `.env`
7. Web auth 帳號格式已調整為英數 `username`，並可搭配 `email`；登入支援 username 或 email

---

## 架構摘要

### 舊架構
```
PySide6 UI ──直接調用──> mysql/dataDB.py ──> MySQL
PySide6 UI ──直接調用──> utils/deepseek.py ──> DeepSeek API
PySide6 UI ──直接調用──> detect_mainui.py ──> YOLO
```

### 現行架構
```
PySide6 Desktop App ──HTTP──> FastAPI Backend ──> MySQL (SQLAlchemy)
React Web Frontend  ──HTTP──> FastAPI Backend ──> MySQL (SQLAlchemy)
                                    │
                              ┌─────┴─────┐
                         YOLO Service  Chat Service (provider-based)
```

---

## 專案目錄結構

```
Yolo_system/
│
├── README.md                   # 本文件
├── AGENTS.md                   # AI 協作規範文件
│
├── docs/                       # 專案文件
│   ├── architecture.md         # 架構設計
│   ├── api-spec.md             # API 規格
│   ├── database-design.md      # 資料庫設計
│   ├── roadmap.md              # 開發路線圖
│   ├── 01_phase6a_backend_agentic_layer.md
│   ├── 02_phase6a_web_desktop_agent_ui.md
│   ├── evals/                  # explain_detection eval 框架說明
│   └── prompts/                # agent / 稽核用 prompt
│
├── backend/                    # FastAPI 後端
│   ├── app/
│   │   ├── api/routes/         # API 路由
│   │   ├── core/               # 設定、安全、JWT、簽章靜態 URL
│   │   ├── db/                 # SQLAlchemy 設定
│   │   ├── models/             # ORM 模型
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── repositories/       # 資料存取層
│   │   ├── services/           # 業務邏輯服務
│   │   ├── integrations/       # YOLO engine、模型註冊表、chat providers
│   │   └── agents/             # LangGraph supervisor、subagents、tools
│   ├── migrations/versions/    # Alembic migrations
│   ├── tests/                  # 後端單元測試
│   ├── .env.example            # 環境變數範例
│   ├── requirements.txt
│   └── main.py
│
├── desktop-app/                # PySide6 桌面版（Phase 2 起重構）
│   ├── api_client.py           # Desktop 端共用 API client
│   ├── avatar_cache.py         # backend avatar 本地快取工具
│   └── ui_state.py             # Desktop 視窗共享狀態
│
├── AgentWindow.py              # Phase 6A-3b：Desktop 獨立 Agent QDialog
│
├── web-frontend/               # React + Vite 前端（Phase 5 MVP）
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── pages/              # Login / Register / Dashboard / Detection / History / Profile / Chat / Agent / Admin
│   │   ├── components/         # Layout / ProtectedRoute
│   │   ├── services/           # authService / chatService / agentService / detectionService / modelService / userService
│   │   ├── router/             # React Router 設定
│   │   ├── App.jsx
│   │   └── styles.css
│   └── README.md
│
├── tests/evals/                # explain_detection component eval 與結果
│
│── [桌面版進入點與 legacy UI - 根目錄]
│   ├── Login.py
│   ├── Register.py
│   ├── MainUI.py
│   ├── AdminMainUI.py
│   ├── AdminAddUser.py
│   ├── AdminEditUser.py
│   ├── AICSMain.py
│   ├── detect_mainui.py        # webcam / RTSP，尚未後端化
│   ├── PersonFormMain.py
│   ├── utils/
│   └── ui/
```

---

## 啟動方式

### 桌面版
```bash
# 需要 Python 3.9-3.11, PySide6, pymysql, ultralytics
# 於 repo 根目錄執行
# 可選：若 backend 不在 http://127.0.0.1:8000，先設定 API base URL
# export YOLO_API_BASE_URL=http://127.0.0.1:8000
python Login.py
```

### Backend
```bash
cd backend
cp .env.example .env   # 填入實際 MySQL 密碼與其他設定

# 推薦用 conda（macOS Sonoma 避免 Gatekeeper 慢啟動問題）
conda create -n yolo-backend python=3.11 -y
conda run -n yolo-backend pip install -r requirements.txt

# 若使用 repo 內模型，可設定：
# YOLO_DEFAULT_MODEL=../yolo11n.pt
# 若要啟用 chat provider，可設定：
# CHAT_PROVIDER=openai
# OPENAI_API_KEY=sk-...
# 若只想做本地 UI 驗證，可暫時改用：
# CHAT_PROVIDER=mock
# CORS_ORIGINS 可用逗號分隔，或 JSON array 字串

# 執行 migration 建立 users / detection_* 資料表（需先確認 MySQL 連線）
conda run -n yolo-backend alembic upgrade head

# 啟動伺服器（約 20 秒冷啟動）
conda run -n yolo-backend uvicorn main:app --reload --port 8000
# 開啟 http://localhost:8000/docs 驗證
```

> **macOS Sonoma 注意事項**：pip venv 安裝的 native extension (.so) 會觸發 Gatekeeper 掃描（每次約 60-100 秒）。建議使用 conda 環境（約 20 秒）。

### Web Frontend
```bash
cd web-frontend
npm install
npm run dev
```

本地驗證若沿用目前專案的 mock chat / detection 測試組合，建議直接用：
```bash
# backend
cd backend
conda run -n yolo-backend uvicorn main:app --reload --host 127.0.0.1 --port 8000

# frontend
cd web-frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

### 自訂 YOLO checkpoint 相容層

Web 平台只載入 registry 核准的已訓練 checkpoint，不使用根目錄的舊版
`tasks.py` 建構模型。ASFF、DySample 與 EfficientViM checkpoint 所保存的歷史
Python module path，由
`backend/app/integrations/legacy_checkpoint_compat.py` 映射到版本庫內的原始碼：

- `models/custom_modules/ASFFHead.py`
- `SCAM_DySample.py`
- `AddModules/EfficientViMBlock.py`

因此不需要、也不應再把這些檔案複製到 conda 環境的 Ultralytics
`site-packages`。根目錄 `tasks.py` 與 `AddModules/Dysample.py` 僅保留為舊訓練
架構參考，不是 FastAPI 推論 runtime dependency。

---

## 目前 Phase 狀態

| Phase | 名稱 | 狀態 |
|-------|------|------|
| Phase 0 | 盤點現有專案、建立文件 | ✅ 已完成 |
| Phase 1 | 建立 Backend 骨架與 Auth | ✅ **已完成** |
| Phase 2 | 桌面版改接 Backend API | ✅ **已完成**（註冊前頭像仍沿用本地暫存流程） |
| Phase 3 | 重構 YOLO Detection Service | ✅ **已完成**（image/video MVP；webcam/RTSP 為 Phase 3+ 待辦） |
| Phase 4 | 重構 AI Chat Service | ✅ **已完成**（provider-based chat + history/context + streaming） |
| Phase 5 | 建立 React Web 前端 MVP | ✅ **已完成**（所有主流程頁面可用，API/runtime 驗證通過） |
| Phase 6A-1 | Backend Agentic Layer (LangGraph) | ✅ **已完成**（`/api/agent/chat` + `/api/agent/modes`，DeepAgents 為 optional flag） |
| Phase 6A-2 | Web / Desktop Agent UI 整合 | ✅ **已完成**（`/agent` 頁面、Dashboard/Detection shortcuts、Desktop api_client 就緒） |
| Phase 6A-3 | Agent Streaming + Desktop AgentApiThread | ✅ **已完成**（SSE `/api/agent/chat/stream`，AgentPage 預設 streaming，AICSMain AgentApiThread） |
| Phase 6A-3b | Desktop AgentWindow 獨立視窗 | ✅ **已完成**（`AgentWindow.py` QDialog，MainUI 新增「AI Agent」按鈕） |
| Phase 6A-4 | LLM 模型選單 | ✅ **已完成**（`GET /api/models`；Chat/Agent 頁面 per-request provider/model 切換） |
| Phase 6A-5 | 品質修復與 Agent / 下載強化 | ✅ **已完成**（Agent prompt 捷徑修正、Web 下載結果圖/影片、chat_logs FK cascade、desktop session/執行緒修復） |
| Phase 6A-6 | IME 輸入修復 + 對話滾動 + Agent Vision | ✅ **已完成**（中文輸入法送出誤判修復、對話 thread 滾動修復、`AGENT_ENABLE_VISION` 唯讀圖片附加） |
| 批次影像分析 Phase 1 | 多圖 / 資料夾批次上傳 + 類別總數聚合 + Agent `batch_analysis` | ✅ **已完成**（`POST /api/detections/batch`、`detection_batches` 表、Web `/detections/batch` 頁面、Agent 新模式） |
| Phase 6 | Docker、測試、部署文件完善 | ⏳ 待辦 |

---

## 文件索引

| 文件 | 說明 |
|------|------|
| [architecture.md](docs/architecture.md) | 架構設計、資料流與 agent 層邊界 |
| [api-spec.md](docs/api-spec.md) | API 端點規格 |
| [database-design.md](docs/database-design.md) | 資料表設計與 legacy 對照 |
| [roadmap.md](docs/roadmap.md) | 開發路線圖與里程碑 |
| [01_phase6a_backend_agentic_layer.md](docs/01_phase6a_backend_agentic_layer.md) | Agentic layer 設計說明 |
| [02_phase6a_web_desktop_agent_ui.md](docs/02_phase6a_web_desktop_agent_ui.md) | Web / Desktop Agent UI 整合 |
| [evals/explain_detection_eval_framework.md](docs/evals/explain_detection_eval_framework.md) | explain_detection component eval 框架 |
| [AGENTS.md](AGENTS.md) | AI 協作規範 |

> Legacy 系統的現況分析請見上方「Legacy 專案現況與重構目標」；原本獨立的
> `docs/current-system-analysis.md` 已不再維護。

---

## 後續工作

Phase 0–5 與 6A 系列已完成（見上方 Phase 狀態表）。目前仍待辦：

1. **Phase 6** — Docker compose、部署文件、CI/CD（尚未開始，目前僅支援本機執行）
2. webcam / RTSP 改為後端任務或獨立 streaming service
3. image detection 由同步呼叫改為非同步任務；影片改用真正的 job queue（含進度與取消）
4. Web 一般對話頁接上 `POST /api/chat/stream`（Agent 頁已使用 SSE）

---

## 開發歷程

> 以下為各階段的完成範圍與當時的已知限制，保留作為決策紀錄。
> 只想了解目前狀態的話，看上方的「Phase 狀態表」與「後續工作」即可。

#### Phase 2 完成範圍

- `Login.py` / `Register.py` 已改呼叫 backend auth API，不再直接查 MySQL。
- `AdminMainUI.py` / `AdminAddUser.py` / `AdminEditUser.py` 已改呼叫 `/api/users/*`。
- `MainUI.py` 與 `AdminMainUI.py` 的個資修改、改密碼已改走 backend。
- Desktop 端透過 `QSettings` 保存 JWT，啟動時會用 `/api/auth/me` 驗證 token 再自動登入。
- 已登入後的頭像更新改走 `/api/upload/avatar`，並同步快取到本地 `user_avatars/`。

### Phase 2 完成當時已知限制

- 註冊前頭像仍沿用本地暫存，尚未改成匿名上傳或註冊後補傳。
- YOLO、DeepSeek 主流程仍是 legacy local call，尚未進入 backend service phase。

### Phase 3 已完成範圍

- backend 已新增 detection domain：
  - `DetectionTask`
  - `DetectionObject`
  - `YoloEngine`
  - `DetectionService`
  - `/api/detections/*`
- 已完成 `POST /api/detections/image`
- 已完成 `POST /api/detections/video`
  - video 目前為 background task + desktop 輪詢 `GET /api/detections/{id}`
- 已完成 `GET /api/detections`
- 已完成 `GET /api/detections/{id}`
- 已完成 `DELETE /api/detections/{id}`
- backend 會統一保存：
  - 原始圖片：`static/detections/originals`
  - 結果圖片：`static/detections/results`
  - 原始影片：`static/detections/videos/originals`
  - 結果影片：`static/detections/videos/results`
  - preview 圖：`static/detections/previews`
- 桌面端 [MainUI.py](MainUI.py) 已改為：
  - 單張圖片走 backend image detection
  - 本地影片檔走 backend video detection
  - detection history 可讀 backend
  - 結果圖/結果影片可由 UI 開啟

### Phase 3 已知限制

- webcam 偵測仍走 legacy [detect_mainui.py](detect_mainui.py)
- RTSP / 串流仍走 legacy [detect_mainui.py](detect_mainui.py)
- video detection 目前只保存 preview frame 的 detection objects，不是每一幀都入庫
- 桌面端影片 detection 目前仍以輪詢等待完成，尚未做真正非阻塞 UI 任務管理
- history UI 目前是動態 dialog，尚未做完整篩選/分頁/刪除

### Phase 4 已完成範圍

- backend 已新增 chat domain：
  - `ChatLog`
  - `ChatService`
  - `POST /api/chat`
  - `POST /api/chat/stream`
  - `GET /api/chat`
  - `GET /api/chat/{conversation_id}`
- 已新增 provider-based integration：
  - `OpenAIChatProvider`
  - `DeepSeekChatProvider`
  - `BaseChatProvider`
- `chat_logs` 已新增：
  - `conversation_id`
  - `turn_index`
- backend 已支援多輪上下文：
  - 同一 `conversation_id` 下的歷史問答會作為 provider context 傳入
- backend 已支援 streaming chat：
  - `text/event-stream`
  - 串流完成後仍會寫入 `chat_logs`
- provider 選擇改由 `.env` 控制：
  - `CHAT_PROVIDER=openai`
  - `CHAT_PROVIDER=deepseek`
- Desktop [AICSMain.py](AICSMain.py) 已改為：
  - 使用 backend `/api/chat`
  - 使用 backend `/api/chat/stream` 逐段更新 assistant bubble
  - 同一視窗內自動沿用 `conversation_id`
  - 不再直接 import `utils.deepseek.ApiThread`
  - 保留原本 chat bubble UI 與非阻塞互動流程
- backend 會將單輪聊天結果寫入 `chat_logs`

### Phase 4 已知限制

- Desktop 目前僅支援同一視窗內的多輪上下文，尚未加入 history 切換 UI
- `utils/deepseek.py` 仍保留在 repo 中作為 legacy 參考，但已退出 desktop 主流程
- 真正的 provider 執行層驗證仍需要本機有效 API key

### Phase 5 已完成範圍

- 已建立 React + Vite 前端骨架：
  - React Router
  - Axios service layer
  - `ProtectedRoute`
  - `Layout`
- 已建立頁面：
  - `LoginPage`
  - `RegisterPage`
  - `DashboardPage`
  - `DetectionPage`
  - `DetectionHistoryPage`
  - `ProfilePage`
  - `ChatPage`
  - `admin/UserManagementPage`
- `DetectionHistoryPage` 已針對大量紀錄優化：Web 寬螢幕使用固定高度雙欄與獨立捲動，分頁固定於列表底部；900px 以下改為 Task List / Detail 單面板切換
- `ChatPage` 已統一 Conversations / Chat 面板高度；歷史對話清單獨立捲動、最多載入最近 100 組，並可透過 `DELETE /api/chat/{conversation_id}` 二次確認後刪除
- 已串接 backend API：
  - `/api/auth/login`
  - `/api/auth/register`
  - `/api/auth/me`
  - `/api/detections/image`
  - `/api/detections`
  - `/api/detections/{id}`
  - `/api/chat`
  - `/api/chat`
  - `/api/chat/{conversation_id}`
  - `/api/users`
  - `/api/users/{id}`（create/delete 已接；edit service 已備好但 UI 未做）
- 已完成 localStorage token 管理與 admin route guard
- `npm run build` 已通過
- 已完成 API / runtime 驗證：
  - register / login（`username` 與 `email` 都可登入）
  - admin users list / create / delete
  - image detection / detection history
  - profile
  - chat（`CHAT_PROVIDER=mock`）
- desktop 的 [Register.py](Register.py)、[AdminAddUser.py](AdminAddUser.py)、[AdminEditUser.py](AdminEditUser.py) 已同步改為相同帳號規則：
  - `username`：英數字 `3-32` 位
  - `email`：合法 Email
  - `password`：至少 `8` 位，且需同時包含英文與數字

### Phase 5 已知限制

- ChatPage 走非串流 `/api/chat`，尚未接 SSE `/api/chat/stream`（Web streaming 待辦）
- Web 端尚未做 detection video streaming / avatar upload
- webcam / RTSP detection 尚未 backend 化（Phase 3+ 待辦）

### Phase 3 已驗證結果

- backend 實測通過：
  - `alembic upgrade head`
  - `POST /api/auth/login`
  - `POST /api/detections/image`
  - `POST /api/detections/video`
  - `GET /api/detections`
  - `GET /api/detections/{id}`
  - `DELETE /api/detections/{id}`
  - `/static/...` 結果圖、preview 圖、結果影片可直接存取
- 桌面端 offscreen smoke test 實測通過：
  - `Login.py` 一般使用者登入
  - `MainUI.py` 進入 detection 頁
  - `img_predict()`
  - `video_predict()`
  - detection history 讀取
- 本輪執行層驗證額外修正：
  - [backend/requirements.txt](backend/requirements.txt) 補上 `opencv-python-headless`
  - [PersonFormMain.py](PersonFormMain.py) 改用 [ui_state.py](desktop-app/ui_state.py)，移除對 legacy `mysql.dataDB.SI` 的依賴
  - [MainUI.py](MainUI.py) 修正動態按鈕建立順序，避免 `pushButton_history` / `pushButton_open_result` 尚未建立就先綁定事件

### Phase 4 手動驗證方式

1. 在 `backend/.env` 設定（可由 `backend/.env.example` 複製）：
```bash
CHAT_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_CHAT_MODEL=gpt-4.1-mini
CHAT_CONTEXT_MAX_TURNS=10
```
2. 啟 backend：
```bash
cd backend
conda run -n yolo-backend alembic upgrade head
conda run -n yolo-backend uvicorn main:app --reload --port 8000
```
3. 啟 desktop：
```bash
# 於 repo 根目錄執行
python Login.py
```
4. 登入後開啟 [AICSMain.py](AICSMain.py) 對話視窗
5. 送出一則問題，確認：
   - user bubble 正常顯示
   - assistant bubble 會逐段顯示 backend 串流回覆
   - 同一視窗送第二則問題時會延續上一輪上下文
   - provider 錯誤時 UI 顯示合理錯誤訊息
6. 確認資料庫 `chat_logs` 有新增紀錄
7. 驗證 history API：
```bash
curl -H "Authorization: Bearer <TOKEN>" http://127.0.0.1:8000/api/chat
curl -H "Authorization: Bearer <TOKEN>" http://127.0.0.1:8000/api/chat/<conversation_id>
```
8. 驗證 streaming API：
```bash
curl -N -X POST "http://127.0.0.1:8000/api/chat/stream" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"question":"請用三句話介紹本系統"}'
```

### Phase 6A-1 — Backend Agentic Layer（LangGraph）

新增了 `/api/agent/*` 智慧助理入口，與既有 `/api/chat` 完全獨立。設計重點：

- YOLO 推論仍由 `detection_service` 觸發；agent **只讀**現有 `DetectionTask` / `DetectionObject`。
- `chat_logs` 表共用，agent 寫入時 `provider="langgraph-agent"`，與 chat provider 不衝突，無需 migration。
- LangChain / LangGraph / DeepAgents 一律 lazy import；任一缺套件或缺 API key 時 backend 仍能啟動，並回傳 mock 回覆。
- DeepAgents 為 **optional enhancement**，預設關閉。`requirements.txt` 中保留註解，需手動啟用。

#### 新增端點

```text
POST /api/agent/chat   # JWT 必填；mode = auto | general_chat | explain_detection | history_analysis | report | admin_help
GET  /api/agent/modes  # JWT 必填；回傳可用 mode 與 admin_only flag
```

#### 啟動方式

依現有指引啟動 backend：

```bash
conda activate yolo-backend
cd backend
# 第一次或要切換到真實 LLM 才需要安裝 langchain
conda run -n yolo-backend pip install -r requirements.txt
conda run -n yolo-backend uvicorn main:app --reload --port 8000
```

`.env` 範例新增：

```env
# 留空會繼承 CHAT_PROVIDER / OPENAI_CHAT_MODEL
AGENT_PROVIDER=
AGENT_MODEL=
AGENT_ENABLE_DEEPAGENTS=false
AGENT_MAX_HISTORY_TURNS=10
AGENT_RECURSION_LIMIT=25
```

本地驗證可設 `AGENT_PROVIDER=mock` 不需要 API key。

#### 測試方式

```bash
TOKEN=...  # 從 /api/auth/login 取得

curl -X GET "http://127.0.0.1:8000/api/agent/modes" \
  -H "Authorization: Bearer $TOKEN"

curl -X POST "http://127.0.0.1:8000/api/agent/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"請摘要我最近的偵測歷史","mode":"history_analysis"}'

curl -X POST "http://127.0.0.1:8000/api/agent/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"請解釋這筆偵測","mode":"explain_detection","detection_id":1}'

curl -X POST "http://127.0.0.1:8000/api/agent/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"請產出 detection 報告","mode":"report","detection_id":1}'
```

#### DeepAgents（optional enhancement）

預設關閉。若要啟用：

1. 解除 `backend/requirements.txt` 中 `deepagents>=0.0.5` 的註解並重新安裝。
2. `.env` 設定 `AGENT_ENABLE_DEEPAGENTS=true`。
3. 後端啟動後會在 `agents.llm.deepagents_available()` 中顯示 `True`，本階段尚未把 DeepAgents 直接接入 supervisor，僅保留 flag 與 readiness check。

#### Phase 6A-1 已知限制

- 此階段當時尚未提供 agent streaming；`/api/agent/chat/stream` 已於 Phase 6A-3 完成。
- DeepAgents flag 目前僅做 import readiness，沒有實際使用 deepagents.subagents。

---

### Phase 6A-2 — Web Agent Console（Web Frontend & Desktop Agent UI）

#### Web Agent Console（`/agent`）

新增了獨立的 AI Agent 智慧助理頁面，與 `/chat` 完全分開：

| 路由 | 說明 |
|------|------|
| `/chat` | 一般 provider-based chat（`POST /api/chat`） |
| `/agent` | LangGraph Agent Console（`POST /api/agent/chat`） |

**AgentPage 功能：**

- mode 下拉選單（auto / general_chat / explain_detection / history_analysis / report / admin_help）
- 可選填 `detection_id`，搭配 explain_detection / report mode 自動填入預設訊息
- 對話 thread 顯示 tool_calls / references（若後端有回傳）
- `admin_help` 模式：非管理員前端顯示提示，後端仍進行權限驗證

**Agent Shortcuts：**

完成一次圖片偵測或在 Detection History 選取一筆紀錄後，可一鍵跳轉：

```text
/agent?mode=explain_detection&detection_id=123   ← Ask Agent to Explain
/agent?mode=report&detection_id=123              ← Generate Report
```

#### Web Frontend 啟動方式

```bash
cd web-frontend
npm install
npm run dev      # http://localhost:5173
npm run build    # 生產版本 build 檢查
```

#### Desktop 整合狀態

`desktop-app/api_client.py` 已包含 `agent_chat()` / `list_agent_modes()`（Phase 6A-1 完成）。
Desktop PySide6 的獨立 `AgentWindow.py` 已於 Phase 6A-3b 完成。

#### Phase 6A-3 — Agent Streaming（SSE）

新增 `POST /api/agent/chat/stream`，SSE 事件格式與 `/api/chat/stream` 一致：

```
start → chunk (×N) → done   或   error
```

Web `AgentPage` 預設使用 streaming，右上角 **Streaming** checkbox 可切換為 batch 模式。
串流中顯示 ▍ 閃爍游標，`done` 後才渲染 tool_calls / references。

Desktop `AICSMain.py` 新增 `AgentApiThread` + `enable_agent_mode()` / `disable_agent_mode()` helper，
可由 MainUI 或其他呼叫者切換至 LangGraph agent backend，不影響原本 `/api/chat/stream` 流程。

#### Phase 6A-3b — Desktop AgentWindow 獨立視窗

`AgentWindow.py` — 獨立 PySide6 QDialog，從 `MainUI.py` 的「AI Agent」按鈕開啟：

- **Mode 下拉選單**：auto / general_chat / explain_detection / history_analysis / report / admin_help
- **Detection ID 欄位**：有 `current_detection` 時自動帶入，mode 自動切換為 `explain_detection`
- **泡泡對話顯示**：使用 `AIChatMessageWindow`，與 AICSMain.py 風格一致
- **Streaming**：自帶 `AgentStreamThread`，呼叫 `/api/agent/chat/stream`，逐字顯示
- **Stand-alone 啟動**（開發測試用）：`python AgentWindow.py`

---

### Phase 6A-4 — LLM 模型選單

新增 `GET /api/models` 端點與前端 provider/model 選單，讓使用者可在 Chat 與 Agent 頁面即時切換 LLM。

#### 後端（`GET /api/models`）

| Provider | 出現條件 | 模型來源 |
|----------|---------|---------|
| OpenAI GPT | `.env` 中 `OPENAI_API_KEY` 有設定 | 固定列表（`gpt-4.1-mini`、`gpt-4o` 等）+ 設定值優先 |
| DeepSeek | `.env` 中 `DEEPSEEK_API_KEY` 有設定 | 固定列表（`deepseek-chat`、`deepseek-coder` 等）|
| Ollama（本地） | 一律出現 | 即時呼叫 `OLLAMA_BASE_URL/api/tags`；Ollama 未啟動時 fallback 至 `OLLAMA_MODEL` |
| mock | 不出現（僅內部測試用）| — |

#### 前端

- `web-frontend/src/services/modelService.js` — `listModels()` 呼叫 `GET /api/models`
- `ChatPage.jsx` — textarea 上方顯示 provider / model 雙 select
- `AgentPage.jsx` — controls 側邊欄 Detection ID 下方顯示 provider / model select

#### Per-request model override

`POST /api/chat`、`POST /api/chat/stream`、`POST /api/agent/chat`、`POST /api/agent/chat/stream` 均已接受 optional `provider` 與 `model` 欄位，優先於 `.env` 設定。

---

### Phase 6A-5 — 品質修復與 Agent / 下載強化（2026-07-12）

一次性收斂前期審查發現的問題，並新增兩項功能（完整清單見 `AGENTS.md` Phase 6A-5 區塊）：

**新功能**
- Web `DetectionPage` / `DetectionHistoryPage` 新增「下載結果圖 / 下載結果影片」按鈕（blob 下載，沿用共用 axios instance）。
- Agent 頁 mode / Detection ID 切換時會智慧更新預設 prompt（自打文字不會被覆蓋）；`history_analysis` / `admin_help` 補上預設 prompt；`/agent?mode=...&detection_id=...` 捷徑在頁內導航也會生效。

**重要修復**
- migration `0008`：`chat_logs.user_id` FK 改 `ON DELETE CASCADE` — 修復刪除有聊天紀錄的使用者時整個 API 失敗的 bug；刪 user 時同步清理 detection / avatar 靜態檔案。
- Agent 統計工具移除 100 筆掃描上限（`HISTORY_SCAN_LIMIT=1000` + 真實 `total_tasks`）；history / report / admin 三個 subagent 的 `role:"tool"` 訊息改為 user-turn 嵌入，修復 OpenAI 嚴格模式 400。
- Desktop：登入時清除另一角色 token（修復 admin/user session 錯亂）、admin 登出清 session、串流視窗關閉時安全斷開 QThread、`api_client` 分操作 timeout、detection history 分頁改用後端 total、影片輪詢關窗即停、登入自動快取頭像。
- Web：DetectionHistory 篩選競態（abort 未接 axios）、刪除後分頁 clamp、ChatPage 兩個競態、SSE 401 導回登入、object URL 洩漏、預設 model 改選可用 provider。

**驗證**：`alembic upgrade head` 通過（FK 已確認 `ondelete: CASCADE`）、backend import + `/api/health` 200、subagent 訊息 roles 確認無 `tool`、`npm run build` 通過、desktop 全部修改檔案 `py_compile` 通過。

---

### 批次影像分析 Phase 1（2026-07-23）

一次上傳多張影像（或整個資料夾），逐張沿用現有單張圖片偵測流程，並用確定性 SQL 聚合回答「這批影像總共偵測到幾艘船/幾架飛機/幾輛車」「有幾張疑似漏檢（估計）」之類的問題。空間關係推論（例如「哪些船上有飛機」）與影片逐幀問答為後續 Phase。

**Backend**
- migration `0010`：新增 `detection_batches` 表 + `detection_tasks.batch_id`（nullable FK，`ON DELETE CASCADE`）
- `POST /api/detections/batch`：上傳多張圖片（欄位 `files`），單次上限 `DETECTION_BATCH_MAX_FILES`（預設 100，`.env` 可調，規劃未來提高到 500）；非圖片檔案自動略過（記錄於 `skipped_files`），不中斷整批請求；儲存完成後立即回傳 202，推論在背景任務中依序執行
- `GET /api/detections/batches`、`GET /api/detections/batches/{id}`、`DELETE /api/detections/batches/{id}`：清單（分頁/篩選同既有慣例）、詳情（含每張圖 task 摘要，供前端輪詢進度）、刪除（含靜態檔案清理）
- Agent 新模式 `batch_analysis`：`summarize_batch_tool` 對整批 `detection_objects` 做 `GROUP BY class_name` 聚合；`batch_analyst` subagent + `BATCH_ANALYST_PROMPT` 明確要求「零偵測影像數僅為估計提示，非確定漏檢結論」，且對空間關係問題誠實回覆目前不支援
- `AgentState` / `run_graph` / `stream_graph` / `/api/agent/chat(/stream)` 新增 optional `batch_id`（與既有 `detection_id` 相同模式）

**Web**
- 新頁面 `/detections/batch`（`BatchDetectionPage.jsx`）：多檔/整個資料夾選擇、上傳進度條（輪詢 `GET /api/detections/batches/{id}`）、逐張縮圖結果、「用 Agent 分析這批」捷徑（`/agent?mode=batch_analysis&batch_id={id}`）
- `detectionService.js` 新增 `detectImageBatch` / `listBatches` / `getBatch` / `deleteBatch`
- `AgentPage.jsx` 新增 Batch ID 欄位與 `batch_analysis` 模式（沿用既有 Detection ID 欄位的智慧預填 / query params 同步邏輯）
- Dashboard / 側邊選單新增「Batch Analysis」入口

**已知限制**
- 背景處理為單一 worker 依序執行（非併發），100 張視硬體效能可能需數十秒到數分鐘；未來擴到 500 張或多批次併發需 Phase 6 job queue
- 僅支援影像批次；影片批次與逐幀問答為後續 Phase
- 僅做每類別總數聚合，不做 bbox 空間關係判斷

**驗證**：`alembic upgrade head` 通過（`detection_batches` 表 + `detection_tasks.batch_id` 已建立）、backend 全部新模組 import 成功、`npm run build` 通過。

---

### Phase 3 手動驗證方式

1. 啟 backend：
```bash
conda run -n yolo-backend bash -lc 'cd backend && YOLO_DEFAULT_MODEL=../yolo11n.pt uvicorn main:app --host 127.0.0.1 --port 8001'
```
2. 另開 terminal 啟桌面端：
```bash
# 於 repo 根目錄執行
export YOLO_API_BASE_URL=http://127.0.0.1:8001
conda run -n yolo-backend python Login.py
```
3. 使用一般使用者登入後驗證：
   - 圖片 detection
   - 本地影片 detection
   - 歷史紀錄
   - 打開结果

---

*最後更新: 批次影像分析 Phase 1 完成 — 2026-07-23*
