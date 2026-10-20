# 文件索引

一般使用者從 [使用手冊](../README.md) 開始；管理員從 [維運操作](lab-operations.md) 開始；後續開發先看 [目前狀態](roadmap.md) 與 [協作規範](../AGENTS.md)。

## 使用與維運

| 文件 | 用途 |
|---|---|
| [README：使用者與管理員手冊](../README.md) | 登入、單圖／批次、紀錄、AI、管理帳號與故障處理 |
| [DEPLOY：部署入口](../DEPLOY.md) | 已採用的實驗室部署方案、拓撲與管理界線 |
| [維運操作與交接](lab-operations.md) | 日常健康檢查、啟停、備份、更新與回復 |
| [Phase 6 收尾批次](lab-phase6-finalization.md) | 尚待 Ubuntu 執行的完整回歸與 23:30 備份啟用 |
| [目前狀態與後續工作](roadmap.md) | 已上線、待實機驗證與尚未排程的項目 |
| [桌面版說明](../desktop-app/README.md) | PySide6 啟動、功能對照與本機推論例外 |

## 開發參考

| 文件 | 用途 |
|---|---|
| [開發環境與驗證](development.md) | Python／Node、開發資料庫、測試與 CI |
| [系統架構](architecture.md) | 分層、資料流、Chat／Agent、媒體與部署拓撲 |
| [API 規格](api-spec.md) | 端點、認證、請求／回應、SSE 與權限 |
| [資料庫設計](database-design.md) | 資料表、關聯與 migration 0013 |
| [Web 開發說明](../web-frontend/README.md) | 前端啟動與共用元件／service 規則 |
| [Web 設計規範](../web-frontend/DESIGN.md) | 版面、元件、操作與可及性 |
| [AI 協作規範](../AGENTS.md) | 持續有效的開發限制與文件同步責任 |
| [Claude 相容入口](../CLAUDE.md) | 匯入同一份 AGENTS 規則 |
| [文件維護政策](documentation-policy.md) | 變更對應、檢查命令與選用 pre-commit |
| [純內部修改說明](change-notes.md) | 沒有行為改變時的可 review 例外紀錄 |

## 部署專題與階段紀錄

以下保留原路徑供既有部署工具／交接引用；內含初次建置及當時待辦，**日常操作請回到維運手冊**。

| 文件 | 保留原因 |
|---|---|
| [同網址初期驗證](lab-same-origin.md) | loopback nginx／代理與最初瀏覽器驗證 |
| [後端 GPU 容器](lab-backend-container.md) | CUDA、checkpoint、容器 UID／cache 修復 |
| [Compose 納管](lab-compose.md) | 既有容器接手與持久資料驗證依據 |
| [第一份備份與隔離還原](lab-backup.md) | MySQL utf8mb4 等價差異、初始還原基準與保密界線 |
| [公開 HTTPS 與註冊政策](lab-public-https.md) | IP 憑證、Snap NNP 例外、nosniff 修正與公開驗收 |

## 評測與品質

- [偵測解釋評估框架](evals/explain_detection_eval_framework.md)：評分設計參考，含原英文 rubric；不是執行結果。
- [Agent 引擎評測結果](../tests/evals/results/agent_engine_eval_report.md)：pipeline／tool-calling 與模型比較，支援預設決策。
- [偵測解釋評測結果](../tests/evals/results/explain_detection_eval_report.md)：固定案例下的模型回覆與限制。

## 報告與歷史

- [本次整理報告](reports/documentation-refresh-20261021.md)：保留、移動、刪除與同步檢查的明細。
- [重構與部署交接摘要](reports/development-handoff-20261021.md)：階段決策、模型、認證與後續優化入口。
- [歷史文件索引](archive/README.md)：原 README／AGENTS／roadmap／部署診斷、初始 Agent 設計、UI 與整合報告。

新增或移動文件時維護本索引或歷史索引，再執行 `python3 scripts/check_docs.py`。歷史模板中的命令與指示是紀錄，不能視為新的使用者要求。
