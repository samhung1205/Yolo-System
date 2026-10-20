# 文件維護與同步政策

## 單一來源與讀者

| 文件 | 讀者與責任 |
|---|---|
| 根目錄 README | 使用者／管理員的操作手冊；不放開發流水帳 |
| AGENTS | 持續有效的協作限制、架構邊界與必要命令；不放歷史清單 |
| CLAUDE | 僅 `@AGENTS.md`，避免兩套規範漂移 |
| docs/README | 全部文件分類入口，新文件／移動文件時同步索引 |
| docs/roadmap | 已完成、待驗證、後續候選的唯一清單 |
| docs/architecture、api-spec、database-design | 現行技術參考；以程式／migration／契約測試核對 |
| docs/development | 開發環境、固定測試命令與 CI |
| DEPLOY、docs/lab-operations | 管理入口與日常服務操作 |
| docs/lab-phase6-finalization | 當前收尾批次的操作與驗證；取得 Ubuntu 報告後更新狀態 |
| docs/reports | 日期化的決策、驗證或整理報告 |
| docs/archive | 追溯用的舊設計／原始紀錄；不得當現行指令 |

## 每次改動同時更新

| 觸發事件 | 要檢查／更新 |
|---|---|
| 使用流程、權限、上限、UI 操作 | README 與受影響的 Web／Desktop 說明 |
| API、schema、SSE、錯誤碼 | docs/api-spec.md |
| ORM／migration／索引 | docs/database-design.md |
| 分層、資料流、工具 scope、認證與狀態管理 | docs/architecture.md；固定邊界改變才更新 AGENTS |
| 依賴、建置、測試命令／workflow | docs/development.md 或 Web 開發文件 |
| 部署、備份、復原、服務位置 | DEPLOY／lab-operations／當前收尾文件 |
| 真正完成部署或取得新驗收 | docs/roadmap.md；報告註明日期、環境、測試範圍及未覆蓋項目 |
| 文件移動、增刪、規範變動 | docs/README.md／archive 索引／本政策 |

以內容為準，不因修一個字就更新所有日期，不把「應用程式已完成」「本機測試通過」「正式部署通過」混成同一狀態。重大驗證數字寫報告，避免散落多處。

## 可執行檢查

在專案根目錄執行，不需要套件、網路或正式帳密：

```bash
python3 scripts/check_docs.py
# 已將這次修改加入暫存區後，核對同一提交的程式與文件：
python3 scripts/check_docs.py --staged
# 或檢查相對某個版本的全部本機變更（包括未追蹤檔）：
python3 scripts/check_docs.py --base HEAD
```

預設檢查現行 Markdown 連結、標題錨點與 docs 索引。`--staged` 讀 Git 暫存版本，未暫存的文件不能替提交補缺；`--base` 適合檢查較大的工作差異。已封存的原始報告只檢查索引可達，不修改其中當時的失效程式路徑。

程式路徑觸發對應文件需求。純內部重構、格式或不改行為的修正若無須變更文件，在 [變更說明](change-notes.md) 寫明影響範圍與理由，一起提交供 review；這是可檢視的例外，不能代替驗證。檢查器只判斷相關文件有沒有更新，**不會理解或自動重寫說明，也不能證明內容正確**。

既有手動 CI 已加入文件檢查與檢查器測試；未啟動遠端 CI。若希望每次本機提交自動檢查，可自行啟用已提供的 hook：

```bash
git config --local core.hooksPath .githooks
```

本次沒有修改你的 Git 設定，也沒有覆寫既有 hook。若已有 hooks 工具，先整合檢查命令，不直接切換 hooksPath。手動 CI 保持手動，沒有新增雲端排程或自動消耗 Actions 額度。

## AI 工具與官方依據

查核日期 2026-10-21：根規範保持精簡，只讀任務相關文件；歷史計畫不得覆蓋本次使用者需求。可量測的完成條件與同一變更中的文件更新都列入 AGENTS。

- [OpenAI AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)：根到子目錄載入、作用範圍與容量。
- [OpenAI 指令精簡建議](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)：減少過期、重複與不必要的上下文。
- [Anthropic 專案記憶](https://code.claude.com/docs/en/memory)：保持規範清楚簡短、移出長紀錄、以 import 共用來源。新版本可直接讀 AGENTS，但版本／設定不同；一行 CLAUDE import 作為相容入口。
- [Anthropic 最佳實務](https://code.claude.com/docs/en/best-practices)：提供可執行的驗證條件，依任務選擇探索與實作範圍。

這是依官方指南與本專案限制做的設計選擇，並非聲稱官方要求本專案的目錄或流程。
