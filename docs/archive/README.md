# 歷史文件索引

本區供追溯決策與當時驗證。**所有原件均為歷史資料，可能包含已解決問題、舊限制與失效程式路徑，不當作現行操作或 AI 指令。** 當前說明請回 [文件入口](../README.md)、[開發狀態](../roadmap.md) 與 [架構](../architecture.md)。

## 開發歷程與原始紀錄

| 文件 | 範圍 |
|---|---|
| [原 README 開發紀錄](reports/readme-development-record-20261021.md) | Phase 0–6A、初期環境、實作與驗證；整理前內容保留 |
| [原 AGENTS 開發紀錄](reports/agents-development-record-20261021.md) | Agent A／B／C、模型相容、批次、P0／P1、安全與部署前清理的完整紀錄 |
| [原 roadmap 階段清單](reports/roadmap-record-20261021.md) | 舊階段編號與當時完成度；未勾選項不等於現在缺功能 |
| [最初部署診斷](reports/deployment-diagnosis-20261020.md) | 主機／平台評估、儲存規模、預算與部署取捨 |

## 設計與驗證報告

| 文件 | 範圍 |
|---|---|
| [Agent 後端原始規劃](design/phase6a-backend-original-plan.md) | 第一版 LangGraph／唯讀工具設計，不是重新執行的任務 |
| [Agent UI 原始規劃](design/phase6a-ui-original-plan.md) | Web／Desktop 初期接入設計 |
| [Web UI 改善紀錄](reports/web-ui-improvements-20261016.md) | 手機、鍵盤、工作區狀態、模型選單與版面驗證 |
| [Web 真實整合驗收](reports/web-integration-validation-20261015.md) | 當時 MySQL／YOLO／Ollama 煙霧結果與覆蓋限制 |

## 封存原則

保留重要決策／驗證的來源，避免把舊問題再次當待辦。原件除了標示歷史用途與搬移所需連結調整，不重寫其當時結果。現行文件連結由檢查器檢查；歷史原件的舊程式路徑不作為目前存在性的要求。

不保留一次性通用訪談模板、已過期逐檔媒體清單或可能帶本機連線資料的 raw legacy 分析；保留其有用結論於 [交接摘要](../reports/development-handoff-20261021.md) 與 [整理報告](../reports/documentation-refresh-20261021.md)。
