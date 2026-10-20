# 系統架構與維護邊界

最後核對：2026-10-21。本文描述目前原始碼與已確認的部署拓撲；驗證完成度集中於 [roadmap](roadmap.md)，早期設計保留於 [歷史索引](archive/README.md)。

## 主要元件

```text
React Web ─────────┐
                  ├─ HTTP / JWT / SSE → FastAPI
PySide6 Desktop ──┘                     ├─ routes → services → repositories → MySQL
                                       ├─ detection_service → YoloEngine → GPU
                                       ├─ chat_service → LLM provider
                                       ├─ agent service → 唯讀工具 / LLM
                                       └─ static_files → 權限 / 簽章 → 媒體
Desktop Webcam / RTSP → 本機 YOLO（既有例外，不入網站偵測紀錄）
```

UI 不直接連 MySQL，也不持有外部 provider key。桌面版保留 legacy UI 以維護既有功能；主力介面是 Web。

## 實驗室部署

```text
瀏覽器 → https://140.113.135.113 → Caddy gateway / React build
                                 └─ /api、/static → FastAPI 127.0.0.1:8000
                                                   ├─ MySQL 127.0.0.1:13306
                                                   ├─ YOLO checkpoint / GPU
                                                   └─ Ollama 127.0.0.1:11434
維護入口 → nginx 127.0.0.1:8080 → 同一 FastAPI
```

Caddy／backend／nginx 由 Compose 管理，MySQL 是既有獨立容器，Ollama 為原生 systemd。backend 使用單 worker、主機 UID／GID、唯讀設定與模型、持久讀寫媒體；MySQL named volume 與 Caddy 憑證 volume 持久保存。公開入口已通過可信 IP HTTPS 與校外手機驗收。

Snap 的 gateway 需要私人 NNP=false 相容例外，保留其他隔離與資源限制；原因見 [HTTPS 專題](lab-public-https.md)。目前操作見 [維運交接](lab-operations.md)，每日排程啟用／新完整備份仍待 [收尾驗證](lab-phase6-finalization.md)。

## 偵測與媒體

- 單張：route 驗證參數／上傳 → service 保存原圖 → `YoloEngine` 載入核准 checkpoint 並推論 → 保存標註圖／物件與模型來源 → 回傳紀錄。
- 批次：建立 `detection_batches` 與各圖 `detection_tasks`，`BackgroundTasks` 逐圖執行、更新處理數；類別統計由 DB `GROUP BY` 完整聚合。
- 影片：背景逐幀推論，保存結果影片與 preview，資料庫物件清單來自 preview frame，不是全影片每幀物件。
- 模型：registry 限定 key、預期 SHA-256、類別對照與相容模組。OBB 的 DB bbox 是旋轉框外接矩形，不保存角度；各類別閾值只支援一般 image／batch。
- 媒體：DB 存相對路徑，檔案位於 `backend/static/`；`/static` 不是公開目錄。Bearer 請求檢查擁有權，瀏覽器顯示採短期簽章 URL；安全標頭與格式白名單保留。
- 頭像：檔名帶上傳者 id，指定時檢查歸屬、存在與是否被他人使用；換圖／刪人清理無人使用檔案，孤兒清理工具預設 dry-run。

## Chat 與 Agent

一般對話走 `/api/chat*`，依 conversation 載入上下文，再呼叫 provider；串流與非串流都保存問答。Agent 走獨立 `/api/agent/chat*`，只讀已有偵測／批次／歷史資料；兩者共用 `chat_logs`，Agent 以 `provider=langgraph-agent` 區別。

| 引擎 | 用途與執行方式 |
|---|---|
| `tool_calling`（預設） | LangChain `create_agent`，模式決定工具子集；工具／模型次數有上限，compiled agent 快取 |
| `pipeline` | LangGraph 的意圖 → 工具／輔助模組 → 回答；mock、確定性報告與 vision 路徑保留對應處理 |

使用者、DB、資料選取與鎖由 runtime context 注入，模型不能指定任意使用者身分。並行工具透過 DB lock 序列化 session 使用；非管理員查自己的資料，管理員工具函式內再次檢查。工具截斷清單不影響 DB 的完整聚合數字。

兩個引擎對 service 提供相同階段／文字事件，service 產生 SSE；Web 與 Desktop 不解析 provider 原始串流。tool-calling 可附 `tool` 事件，Web 顯示進度，Desktop 可忽略。LangChain／LangGraph lazy import；錯誤回傳固定訊息，provider 未設定不偷偷改 mock。

目前免費預設為 Chat Ollama `llama3.2`、Agent Ollama `gemma4`；模型清單依用途標註後端預設。DeepAgents 已決定不採用，flag 保持 false。Agent 不提供 CRUD 工具、不觸發 YOLO，也不直接寫檔；service 保存問答屬既有應用流程。

## Web 工作區與 Desktop

Web 的單一「AI 助理」入口用路由連結切換 `/chat`／`/agent`，頁面與 service 獨立，共用一個 Axios instance。路由父層在記憶體分開保存草稿、模型、當前對話與資料選擇；重新整理、離開或登出即清除，已保存資料仍在 DB。Agent 保留 `mode`／`detection_id`／`batch_id` URL 帶入。

前端中止請求只代表停止接收，無法保證後端生成已取消。一般對話可切換歷史；Agent 尚無完整跨工作階段歷史清單。Web Profile 目前編輯暱稱／密碼、顯示頭像，沒有頭像上傳 UI；Web 單張偵測頁不提供影片上傳。

Desktop 透過 `desktop-app/api_client.py` 使用共用 API。Webcam／RTSP 仍本機推論；模型選擇、批次、各類別閾值與報告下載尚未完整移植。細節見 [桌面版說明](../desktop-app/README.md)。

## 認證、資料庫與限制

JWT 使用 PyJWT、bcrypt 密碼與 `users.token_version` 撤銷；Web token 仍存 localStorage，Desktop 存 QSettings，httpOnly cookie 未採用。登入節流與 LLM 額度目前是單程序記憶體，因此正式後端保留單 worker。管理員不可自我刪除／停用／降級，不可移除最後一位啟用管理員。

資料庫最新 migration `0013` 包含對話輪次唯一鍵，service 撞鍵重試；schema 見 [資料庫設計](database-design.md)，API 契約見 [規格](api-spec.md)。正式關閉自行註冊與 API 文件；開發環境設定不可推論為正式政策。

影片／批次使用 `BackgroundTasks`，不是持久工作佇列；意外重啟後可依受控工具標記中斷工作失敗，不自動重跑推論。1000 張批次、跨批次排隊、多 worker、空間關係、完整硬體災難復原與大規模併發均未宣稱完成。
