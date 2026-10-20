# 目前狀態與後續工作

最後核對：2026-10-21。本文件是開發／部署完成度的唯一清單；README 說明使用方式，AGENTS 說明協作規範。舊階段編號與完整清單見 [歷史索引](archive/README.md)。

## 已完成的產品與公開部署

| 項目 | 證據與邊界 |
|---|---|
| 共用 FastAPI／MySQL 核心 | Web 與 Desktop 透過 API 存取；migration 最新 `0013` |
| Web 主要流程 | 登入、帳號管理、單圖、100 張批次、歷史、下載、Chat／Agent 與報告已實作 |
| 桌面版 | 共用 API、單圖／影片、Chat／Agent；維護模式，Webcam／RTSP 仍本機推論 |
| Agent 引擎 | 預設 `tool_calling`／gemma4；唯讀工具與權限隔離，DeepAgents 不採用 |
| 部署前安全修正 | JWT 撤銷、登入節流、上傳／頭像歸屬、受保護媒體、LLM 政策、輪次唯一鍵 |
| 實驗室公開部署 | Ubuntu GPU、Compose、HTTPS、關閉註冊、原有資料、Chat／Agent SSE 皆通過；使用者確認手機行動網路正常 |
| 第一份備份 | 隔離 MySQL／檔案還原通過；Mac 副本完整 SQL 與 52 檔 SHA-256 核對通過 |

**平台已確定為實驗室伺服器，網站已部署成功，無須另外部署到 Vercel。** 10–50 個預計帳號不是 50 路同時推論的承諾。

## Phase 6 維運收尾：已實作，待 Ubuntu 驗收

以下本機結果沿用上一輪實作證據，本次文件整理沒有重跑正式 GPU、LLM 或變更服務。

- [x] 維運、備份與中斷工作復原工具完成；本輪部署工具 145 項、後端 190 項本機測試通過（合成圖片／獨立工作目錄）。
- [x] Vite 8.3.4／React plugin 6.1.2，本機 build、audit 0 與瀏覽器流程通過；正式 gateway 待收尾批次套用。
- [x] 獨立 SQLite／測試 HTTPS 的真實 CPU 回歸通過：兩帳號隔離、頭像、100 張批次、ZIP、影片、Desktop client、改密碼與 JWT。
- [x] 手動 CI workflow 已建立；無 checkpoint 的隔離測試 173 通過、9 排除。已隨 `84dcbca` push，尚無 GitHub Actions run 結果。
- [ ] Ubuntu 已同步 `84dcbca`，health／DB 正常；首次 [收尾批次](lab-phase6-finalization.md) 停在容器回歸，未切換 gateway／安裝排程。`5734992` 已在 Ubuntu 跑到完整 pytest（180 過／2 項非法圖片測試失敗）；本輪修正 Ultralytics HEIF 包裝相容性，新增候選 backend 建置／測試 gate／閒置切換與啟動失敗回復，待 Ubuntu 重驗。
- [ ] 首份包含目前來源、SQL、媒體、模型、image、Ollama 與憑證的備份／隔離還原成功，再啟用每日 **23:30 Asia/Taipei**、保留 7 份成功備份。
- [ ] 將新完整備份與引用的 image／Ollama 快取下載到 Mac，執行完整性核對；最初還原基準固定保留。
- [ ] 記錄收尾後來源版本與 image、MySQL 啟停交接；有實際 GitHub run 後另補 CI 結果。

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
