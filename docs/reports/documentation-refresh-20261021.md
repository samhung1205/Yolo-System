# 文件盤點與整理報告

日期：2026-10-21。範圍包含根目錄文件、`docs/`、Web／Desktop 說明、Web 設計規範與兩份 Agent 評測結果；依現有程式、migration、部署回報與官方指南核對。未修改正式服務、認證策略或業務程式。

## 問題與整理結果

原 README 776 行、AGENTS 637 行，混有歷史、Phase 1 待辦、過期限制與當前操作。部分架構／API 文件仍說 Web 沒串流、HTTPS 尚未部署；roadmap 日期與待辦落後實作。這些敘述已從現行入口移除或修正。

| 原資料 | 處置與原因 |
|---|---|
| README | 改為繁體中文使用手冊：一般使用、管理帳號、限制與排錯 |
| AGENTS | 改為精簡持續規則，保留權限／分層／共享主機保護與驗證責任 |
| 原 README／AGENTS／roadmap／DEPLOY | 完整開發／診斷紀錄保留於 [歷史索引](../archive/README.md)，不再每次注入 AI 上下文 |
| 兩份 Phase 6A 原始任務規格 | 移至 archive/design，標示不是目前執行指令 |
| Web UI 改善／2026-10-15 整合結果 | 移至 archive/reports，保留環境與未覆蓋範圍 |
| `docs/prompts/` 四份模板 | 刪除 stack_audit、eval_design、multi-agent、ai_detection_analyst_context；一次性通用訪談指示／舊產品快照，不是程式依賴或驗證證據，核心產品／評估結論已保留 |
| `docs/deploy-static-inventory.md` | 刪除過期逐檔清單，避免私人媒體檔名持續留在現行文件；當時 aggregate 規模保留於歷史部署診斷 |
| 被 Git 忽略的 `docs/current-system-analysis.md` | 移除本機 raw legacy 分析，避免把舊連線資料或過期行號發布；重構背景與已解決問題保留於乾淨交接摘要 |
| architecture／API／database | 保留為現行參考，修正串流、provider、正式拓撲、密碼與最新 migration 說明 |
| lab-same-origin／backend-container／compose／backup／public-https | 保留穩定路徑與重要排錯依據，新增階段紀錄標示，日常操作導向 lab-operations |
| 評測框架與兩份評測報告 | 保留重現依據；框架移除對話式開場，標示設計並非實測結果 |
| Web DESIGN | 保留現有產品設計規範，不混入開發流水帳 |

## 新的維護機制

- [文件索引](../README.md) 按使用／維運、開發、部署專題、評測與報告分類。
- [開發文件](../development.md)、[交接摘要](development-handoff-20261021.md) 分開啟動命令與歷史理由。
- [同步政策](../documentation-policy.md) 規定程式與對應文件同一變更交付；AGENTS 為單一規則來源，CLAUDE 只匯入。
- `scripts/check_docs.py` 檢查現行連結、錨點與索引；`--staged`／`--base` 提醒程式變動對應文件。提供選用 pre-commit，沒有修改本機 Git 設定。
- 既有手動 CI 加入文件檢查及其測試；保持手動，沒有觸發遠端 run。

本機檢查器只驗證機械條件；不自動生成正確文件、不保證每項功能都有解說。純內部修改須留下可檢閱理由。舊 bundle 是建立時的來源快照，不會因本次文件更新而自動變成新版本；本輪未重包或部署舊批次。

## 官方來源與設計取捨

查閱 [OpenAI AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)、[指令精簡建議](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)、[Anthropic 記憶機制](https://code.claude.com/docs/en/memory) 與 [開發最佳實務](https://code.claude.com/docs/en/best-practices)。採精簡根規範、任務相關上下文、同一規則來源與可執行驗證；沒有照搬平台範例中的核准流程或引入新代理架構。

## 驗證與範圍

本輪檢查通過：34 份文件的索引／現行連結／錨點、相對 HEAD 的變更同步、12 項檢查器測試（含真實暫存 Git repository 的 staged／unstaged 分離）、30 段 API JSON 範例語法與 Git 空白檢查；對照 Web 實際路由／表單、後端設定與 migration，校正使用手冊。具體檢查結果於交付時回報。

這是文件整理與同步工具驗證；沒有把先前的 182 項後端、130 項部署測試當成這輪重跑結果，也沒有宣稱每日 23:30 備份已啟用。正式完成度見 [roadmap](../roadmap.md)。
