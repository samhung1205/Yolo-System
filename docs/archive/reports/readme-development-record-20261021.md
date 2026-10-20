> 歷史封存：2026-10-21 自 `README.md` 整理前版本保留。內容描述當時狀態，含已解決限制、舊操作與過期待辦；不得當作目前指令執行。現況見 [文件索引](../../README.md) 與 [開發狀態](../../roadmap.md)。

# YOLO System — 桌面版 + Web 版雙軌架構

> 把一支 UI、業務邏輯與 SQL 全部耦合在同一層的 PySide6 桌面程式，
> 在不中斷既有功能的前提下，逐步重構成桌面版與 React Web 共用同一組
> FastAPI 後端的偵測平台。

**目前狀態**：Phase 6 的公開部署核心已通過：實驗室 Ubuntu Compose／GPU／HTTPS、原有圖片與對話、受保護媒體、Chat／Agent SSE 與保存均正常；備份隔離還原已通過。使用者已確認手機行動網路全流程正常，Mac 備份副本的 SQL 與 52 個檔案 SHA-256 核對通過；2026-10-21 已補齊每日維運／回歸／復原工具、CI 及 Vite 8（audit 0），本機 182 項後端與部署工具測試通過；Ubuntu 收尾批次尚待執行，尚未將整個 Phase 6 標記完成。現行操作見 [部署交接](../../lab-operations.md)，最新一次執行見 [Phase 6 收尾](../../lab-phase6-finalization.md)。

**技術棧**：FastAPI · SQLAlchemy · Alembic · MySQL · React 18 + Vite · PySide6 · Ultralytics YOLO · LangGraph

### 從哪裡開始讀

| 想知道 | 看這裡 |
|---|---|
| 架構怎麼演進、資料流長怎樣 | [docs/architecture.md](../../architecture.md) |
| 有哪些 API 端點 | [docs/api-spec.md](../../api-spec.md) |
| 資料表設計與 legacy 對照 | [docs/database-design.md](../../database-design.md) |
| 怎麼跑起來 | 本文件的[啟動方式](#啟動方式) |
| 實驗室部署進度與同網址服務 | [docs/lab-same-origin.md](../../lab-same-origin.md) |
| 後端 GPU 容器建置與驗證 | [docs/lab-backend-container.md](../../lab-backend-container.md) |
| Compose 設定驗證與分服務納管 | [docs/lab-compose.md](../../lab-compose.md) |
| 備份與隔離還原批次驗證 | [docs/lab-backup.md](../../lab-backup.md) |
| 關閉自行註冊與校外 IP HTTPS 更新包 | [docs/lab-public-https.md](../../lab-public-https.md) |
| 現行啟停、驗收證據與備份下載 | [docs/lab-operations.md](../../lab-operations.md) |
| 各階段做了什麼 | 本文件的[開發歷程](#開發歷程) |

---

## 專案簡介

本系統整合 YOLO 影像偵測、AI 對話與 agent 助理、使用者與管理員後台。原始版本為純 PySide6 桌面應用程式，UI、業務邏輯與資料庫操作高度耦合；重構的核心是把「誰可以直接存取資料庫、模型與外部 API」從 UI 移到後端，使桌面版與 Web 版能共用同一份業務邏輯。

---

## Legacy 專案現況與重構目標

### Legacy 現況

> 以下描述的是重構「之前」的狀態，作為對照保留。`mysql/dataDB.py` 與
> `utils/deepseek.py` 已退出正式流程且不納入版本控制；開發機可能仍保留 legacy 參考檔。

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
├── DEPLOY.md                   # 部署診斷、實驗室主機方案與 Phase 6 驗收計畫
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

### Legacy 桌面版（維護模式，詳見 [desktop-app/README.md](../../../desktop-app/README.md)）
```bash
# 建議直接用 yolo-backend conda 環境（已含 PySide6 / ultralytics）；不再限制 Python 3.9-3.11
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

# 執行 migration 建立 users / detection_* 資料表（需先確認 MySQL 連線；請在 backend/ 目錄執行）
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
| Phase 2 | 桌面版改接 Backend API | ✅ **已完成**（2026-10-19 起維護模式：註冊頭像上傳、個資/改密碼改走 `/api/auth/profile`） |
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
| 各類別閾值 Phase 1 | 各類別獨立 conf / IOU 閾值（image + batch） | ✅ **已完成**（migration `0011`、`class_thresholds` Form 欄位、Web `ClassThresholdEditor`；影片與 Desktop 未支援） |
| 部署前清理 | react-router 7、頭像歸屬與清理、對話輪次唯一鍵 | ✅ **已完成**（migration `0013`；`scripts/cleanup_avatars.py`） |
| 安全強化 P1 | 認證強化（部署前） | ✅ **已完成**（PyJWT + token 撤銷 migration `0012`、登入節流、密碼可含符號、管理員自我保護、啟動檢查、production 關閉 `/docs`） |
| Agent 重構 C | Agent 評測 + 預設引擎/模型 + Deep Agents 評估 | ✅ **已完成**（`tests/evals/evaluate_agent_engines.py`；預設 `tool_calling` + gemma4；Deep Agents 評估後不採用） |
| Agent 重構 B | tool-calling 引擎（LangChain `create_agent`） | ✅ **已完成**（`AGENT_ENGINE=tool_calling` 開啟，預設仍為 `pipeline`；Web 顯示工具進度） |
| Agent 重構 A | 單一 graph 執行路徑 + 全模式對話歷史 + 明確錯誤 | ✅ **已完成**（graph compile 一次、runtime context、`invoke`/`stream` 同一 graph；B 用 `create_agent`、Deep Agents 延到 C） |
| 安全強化 P0 | 上傳白名單 + static nosniff、LLM 白名單與限流、隱藏內部錯誤 | ✅ **已完成**（`app/core/uploads.py`、`app/services/llm_policy.py`；其餘審查發現見 AGENTS.md） |
| 批次上限 1000 張 | 分片上傳 + 輪詢瘦身 + 中斷復原 | ⏳ 待辦（已完成瓶頸分析，見 AGENTS.md） |
| Phase 6 | 實驗室主機同網址部署、Docker、備份與驗收 | ⏳ 進行中（Compose／GPU／持久資料／SSE 通過；備份隔離還原與公開 HTTPS／媒體／SSE 通過；校外瀏覽器與 Mac 副本已確認；維運與完整回歸待完成，見 [DEPLOY.md](../../../DEPLOY.md)） |

---

## 文件索引

| 文件 | 說明 |
|------|------|
| [architecture.md](../../architecture.md) | 架構設計、資料流與 agent 層邊界 |
| [api-spec.md](../../api-spec.md) | API 端點規格 |
| [database-design.md](../../database-design.md) | 資料表設計與 legacy 對照 |
| [roadmap.md](../../roadmap.md) | 開發路線圖與里程碑 |
| [DEPLOY.md](../../../DEPLOY.md) | 部署診斷、平台比較、實驗室免費部署與 Phase 6 驗收計畫 |
| [01_phase6a_backend_agentic_layer.md](../design/phase6a-backend-original-plan.md) | Agentic layer 設計說明 |
| [02_phase6a_web_desktop_agent_ui.md](../design/phase6a-ui-original-plan.md) | Web / Desktop Agent UI 整合 |
| [evals/explain_detection_eval_framework.md](../../evals/explain_detection_eval_framework.md) | explain_detection component eval 框架 |
| [AGENTS.md](../../../AGENTS.md) | AI 協作規範 |

> Legacy 系統的現況分析請見上方「Legacy 專案現況與重構目標」；原本獨立的
> `docs/current-system-analysis.md` 已不再維護。

---

## 後續工作

Phase 0–5 與 6A 系列已完成（見上方 Phase 狀態表）。目前仍待辦：

1. **Phase 6** — 執行 [Ubuntu 收尾批次](../../lab-phase6-finalization.md)：本機維運／回歸／CI 與 Vite 8 已備妥（Mac 副本與校外瀏覽器已通過）（公開 HTTPS／媒體／SSE 已通過；見 [部署交接](../../lab-operations.md)）
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
- 桌面端 [MainUI.py](../../../MainUI.py) 已改為：
  - 單張圖片走 backend image detection
  - 本地影片檔走 backend video detection
  - detection history 可讀 backend
  - 結果圖/結果影片可由 UI 開啟

### Phase 3 已知限制

- webcam 偵測仍走 legacy [detect_mainui.py](../../../detect_mainui.py)
- RTSP / 串流仍走 legacy [detect_mainui.py](../../../detect_mainui.py)
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
- Desktop [AICSMain.py](../../../AICSMain.py) 已改為：
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
- Detection 影像預覽已共用 `ZoomableImage`：Object Detection、Detection Records 與 Batch Analysis 的結果圖可點擊開啟 modal，支援按鈕/滾輪縮放、放大後拖曳、重設與 `Esc` 關閉
- Batch Analysis 的 Recent Batches / Batch Detail、Object Detection 的 Original / Result，以及 Detection Analyst 的 Settings / Chat panel 已統一高度與內容起點；結果圖下載按鈕統一顯示 `Download`
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
- desktop 的 [Register.py](../../../Register.py)、[AdminAddUser.py](../../../AdminAddUser.py)、[AdminEditUser.py](../../../AdminEditUser.py) 已同步改為相同帳號規則：
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
  - [backend/requirements.txt](../../../backend/requirements.txt) 補上 `opencv-python-headless`
  - [PersonFormMain.py](../../../PersonFormMain.py) 改用 [ui_state.py](../../../desktop-app/ui_state.py)，移除對 legacy `mysql.dataDB.SI` 的依賴
  - [MainUI.py](../../../MainUI.py) 修正動態按鈕建立順序，避免 `pushButton_history` / `pushButton_open_result` 尚未建立就先綁定事件

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
4. 登入後開啟 [AICSMain.py](../../../AICSMain.py) 對話視窗
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
- LangChain / LangGraph / DeepAgents 一律 lazy import；缺套件時 backend 仍能啟動。缺 API key 時回傳明確的「模型供應商尚未設定」錯誤（2026-10-19 起不再偷偷回 mock 回覆）。
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

### 各類別閾值（per-class conf / IOU，2026-09-04）

同一個模型的不同類別可以各自設定信心閾值與 NMS IOU，例如「ship 放寬到 conf 0.20 / IOU 0.40，
airplane 收緊到 conf 0.50 / IOU 0.35」。適用於單張影像偵測與批次偵測。

**為什麼可行**
Ultralytics 的 `predict()` 只接受純量 `conf`/`iou`，所以後端改為「單次推論 + 分類別後處理」：
以所有門檻的最小 `conf` 搭配 `iou=1.0`（等於關閉抑制）取得原始候選框，再依各類別自己的門檻
過濾並重跑 class-aware NMS。這在數學上與「各類別分別用自己門檻推論」**等價而非近似**，兩個
理由都有回歸測試（`backend/tests/test_per_class_thresholds.py`，21 項）：
- 貪婪 NMS 依信心遞減處理，低於門檻的候選框不可能改變門檻以上框的存留結果
- Ultralytics 預設的 NMS 本來就是分類別進行的，不同類別的框不會互相抑制

**Backend**
- migration `0011`：`detection_tasks` / `detection_batches` 新增 `class_thresholds_json`；原本的純量
  `confidence_threshold` / `iou_threshold` 保留為未列出類別的預設值，既有紀錄與單一閾值請求不受影響
- `class_thresholds` 以 multipart Form 欄位（JSON 字串）傳入，key 為 class id：
  `{"0": {"conf": 0.20, "iou": 0.40}, "4": {"conf": 0.50, "iou": 0.35}}`
- class id 會對照所選模型的 `canonical_class_names` 驗證，不符即回 400
- 批次的背景任務從批次紀錄讀取設定，因此重啟續跑仍沿用同一組閾值
- `DETECTION_PERCLASS_MAX_DET`（預設 3000）：關閉抑制後候選框變多，而 `max_det` 是在 NMS 之後
  才套用，維持預設 300 會讓密集影像在自行抑制前就被截斷

**Web**
- 新元件 `ClassThresholdEditor`：類別清單直接取自 `/api/yolo-models` 既有的 `canonical_class_names`，
  切換模型時自動重建並清掉失效的覆寫
- `DetectionPage` / `BatchDetectionPage`：保留原本兩支全域滑桿當預設，新增「各類別自訂閾值」開關
  與表格；結果區會顯示實際採用的 per-class 閾值

**實測結果**（7 類模型、同一張密集影像）
| 設定 | airplane | small-vehicle |
|------|----------|---------------|
| 全域 conf 0.20 | 20 | 113 |
| 全域 conf 0.50 | 18 | 9 |
| per-class（airplane 0.20 / small-vehicle 0.50） | **20** | **9** |

per-class 同時保住了全域 0.50 會漏掉的 2 架 airplane，又把 small-vehicle 收到與全域 0.50 相同的
9 個，這正是這個功能的用途。

**已知限制**
- 僅支援 image 與 batch；影片偵測仍只吃純量 conf/iou
- Desktop PySide6 尚未提供對應 UI
- 只改變後處理、不改變模型，因此無法找回信心低於所有門檻最小值的物件

**驗證**：`alembic upgrade head`（含 downgrade 往返）通過、backend 47 項測試全數通過、
`npm run build` 通過、並以真實模型與影像完成端到端實測（含權限與 400 錯誤路徑）。

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

*最後更新: Web detection / analyst UI 對齊與可縮放影像檢視器 — 2026-09-04*
