# 目前狀態與後續工作

最後核對：2026-10-21。本文件是開發／部署完成度的唯一清單；README 說明使用方式，AGENTS 說明協作規範。舊階段編號與完整清單見 [歷史索引](archive/README.md)。

## 已完成的產品與公開部署

| 項目 | 證據與邊界 |
|---|---|
| 共用 FastAPI／MySQL 核心 | Web 與 Desktop 透過 API 存取；migration 最新 `0013` |
| Web 主要流程 | 登入、帳號管理、單圖、100 張批次、歷史、下載、Chat／Agent 與報告已實作 |
| 桌面版 | 共用 API、單圖／影片、Chat／Agent；維護模式，Webcam／RTSP 仍本機推論 |
| Agent 引擎 | 預設 `tool_calling`／gemma4；唯讀工具與權限隔離，DeepAgents 不採用；固定案例於 2026-10-22 修正評分後為 [32/32](../tests/evals/results/agent_engine_eval_report.md)（原始回答重新評分，非新模型實測） |
| 部署前安全修正 | JWT 撤銷、登入節流、上傳／頭像歸屬、受保護媒體、LLM 政策、輪次唯一鍵 |
| 實驗室公開部署 | Ubuntu GPU、Compose、HTTPS、關閉註冊、原有資料、Chat／Agent SSE 皆通過；使用者確認手機行動網路正常 |
| 最初基準備份（舊版本） | 隔離 MySQL／檔案還原通過；Mac 副本完整 SQL 與 52 檔 SHA-256 核對通過 |

**平台已確定為實驗室伺服器，網站已部署成功，無須另外部署到 Vercel。** 10–50 個預計帳號不是 50 路同時推論的承諾。

## Phase 6 核心部署與維運收尾：實機批次驗收完成

2026-10-21 使用者回報 `Phase 6 lab finalization: PASS`。本輪使用備份續跑模式：完整功能／GPU／HTTPS 與資料／SSE 驗收引用原報告；首份完整備份、隔離還原、服務恢復與 timer 啟用為本輪實跑。

- [x] 維運、備份與中斷工作復原工具完成；最新部署工具 185 項通過（含模型內部連結、legacy／v2／manifest list、指紋／缺失 blob、API 清單變動與失敗階段診斷）；先前後端 190 項通過。新增四影格真實 CPU 影片追蹤／編碼／解碼驗證通過，使用合成資料與獨立工作目錄。
- [x] Vite 8.3.4／React plugin 6.1.2，本機 build、audit 0 與瀏覽器流程通過；Ubuntu `de65239` 收尾批次已完成 backend／gateway 切換及後續完整 HTTPS 回歸。
- [x] 獨立 SQLite／測試 HTTPS 的真實 CPU 回歸通過：兩帳號隔離、頭像、100 張批次、ZIP、影片、Desktop client、改密碼與 JWT。
- [x] 手動 CI workflow 已建立；無 checkpoint 的隔離測試 173 通過、9 排除。已隨 `84dcbca` push，尚無 GitHub Actions run 結果。
- [x] Ubuntu `de65239` 收尾已通過候選 image／GPU／影片、HTTPS 跨帳號／頭像／單圖／100 張批次／ZIP／影片／Desktop，以及既有資料與 Chat／Agent SSE；日誌已進入首份維運備份，證明前段驗收通過。
- [x] Ubuntu 首份完整維運備份／SQL 與檔案隔離還原／服務恢復通過；每天 **23:30 Asia/Taipei** 的 timer 已啟用，保留最近 **7 份成功備份**，原始基準固定保留。成功報告：`/home/sam/.config/yolo-system/reports/finalize-20261021T033914Z.json`；新快照：`/var/lib/sam-yolo-backups/20261021T033914Z-65040ded`。
- [x] 本次修正版交付來源 `dfa3341`；來源檔案、實際 image ID／模型 digest 與持久掛載記錄於私人快照 manifest／批次報告，啟停交接見維運手冊。MySQL restart policy 與 Ollama enabled／active 已由批次核對。

### 後續交接與觀察（尚未完成）

- [ ] 將新快照 `20261021T033914Z-65040ded` 與引用的 `images/`、`models/` 快取下載到 Mac，執行完整性核對；舊 Mac 副本與最初還原基準固定保留。
- [ ] 觀察首次由 timer 自動觸發的 23:30 備份結果。手動初次備份已驗證，尚無首個定時執行回報。
- [ ] 需要時手動執行 GitHub Actions 並補 run 結果；目前僅有 workflow 與本機 CI 等價驗證，沒有遠端成功 run 證據。

不得把上述未驗證項目勾成完成。共享主機整機重開機、全新硬體災難復原、實際憑證續期週期與大規模併發尚未演練；不因一次批次成功就推論全部通過。現行日常操作見 [維運交接](lab-operations.md)。

## 後續優化候選（尚未排入本次）

| 主題 | 邊界與順序 |
|---|---|
| 批次提高至 1000 張 | 先拆輕量進度／分頁結果，再分片上傳、復原與前端呈現；不要只調大上限 |
| 空間關係推論 | 目前只有確定性類別統計；OBB 僅存外接矩形，旋轉角度未入庫 |
| 認證 | Web JWT 仍存 localStorage；httpOnly cookie 需另評估 CSRF 與 Desktop 相容 |
| 併發／排隊 | 單 worker、程序內限流；多 worker 需共享限流與工作協調，不直接增加 workers |
| Agent 品質 | 依固定評測案例比較，保留資料依據、繁體中文與權限邊界 |
| 桌面版 | 修 bug，新增功能須另有明確需求；Webcam／RTSP 後端化未排程 |

## 本次文件整理

README 已改為使用者／管理員操作手冊，AGENTS 改為持續有效的精簡規範。開發歷程與舊計畫已封存，現行參考文件已校正；文件入口、清理明細與同步檢查見 [文件索引](README.md) 及 [整理報告](reports/documentation-refresh-20261021.md)。
