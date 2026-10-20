# 開發與部署交接摘要

日期：2026-10-21。此報告從原 README／AGENTS／roadmap 與目前程式整理，協助後續優化快速定位；完成度以 [roadmap](../roadmap.md) 為準，詳細原件見 [歷史索引](../archive/README.md)。本輪以文件與程式交叉檢閱確認邊界，沒有重新部署或完整重跑正式環境。

## 演進與已完成決策

| 階段 | 已完成成果與保留理由 |
|---|---|
| Phase 0–2 | 從 UI 直連 DB 漸進抽離到 FastAPI／SQLAlchemy；Desktop 改用 HTTP，legacy UI 保留 |
| Phase 3–5 | YOLO 單圖／影片、provider-based Chat、React Web、歷史／使用者管理 |
| Phase 6A | 獨立 Agent 端點、Web／Desktop UI、SSE、模型選擇、報告／vision 與批次分析 |
| Agent 重構 A | graph 共用 invoke／stream、runtime context、全模式歷史、取消無聲 mock fallback |
| Agent 重構 B | `create_agent`／`ToolRuntime`、唯讀工具、DB lock、模式工具子集、次數上限與進度事件 |
| Agent 重構 C | 固定案例比較：tool_calling + gemma4 優於其他測試組合，選為預設；DeepAgents 不採用 |
| 安全 P0／P1 | 上傳白名單與 nosniff、LLM 白名單／限流、錯誤清理、PyJWT／撤銷、登入節流與管理員保護 |
| 部署前清理 | React Router 7、頭像上傳者歸屬／孤兒清理、對話輪次唯一鍵與重試 |
| Phase 6 公開部署 | 免費既有實驗室 GPU 主機，Caddy 公開 IP HTTPS、Compose backend／web／gateway、Ollama 同機 |

Agent 比較的完整案例與數據見 [引擎評測](../../tests/evals/results/agent_engine_eval_report.md)。DeepAgents 不採用的原因：任務是短、唯讀查詢，用不到虛擬檔案系統、寫檔與多代理規劃；增加依賴與本機模型負擔。不要因舊設計提到 optional 就重新啟用。

## 模型與資料契約

核准 checkpoint 共 12 個：4 類別 base／ASFF／DySample／EfficientViM、7 類別 base／ASFF／DySample、7 類別 Pre 三個、OBB 與 COCO-80。各自有獨立 SHA-256，`.pt` 不在 Git。

ASFF／DySample／EfficientViM 依歷史 module path 載入，需保留相容層與原模組。換模型先驗證 task／類別，再用指紋更新工具；工具不能新增 registry key 或改 selectable。

各類別信心／IoU 後處理已驗證一般 axis-aligned 模型的等價性，僅 image／batch；OBB 不支援各類別設定，資料庫只存旋轉框外接矩形。完整逐檔／測試說明在 [原 AGENTS 紀錄](../archive/reports/agents-development-record-20261021.md)。

## 避免重複踩坑

- 舊 legacy 分析中的明文密碼、UI SQL、硬編碼 key 描述的是重構前狀態；目前主要流程已後端化，不可依舊行號當成現行漏洞。原本被忽略的本機 raw 分析不發布。
- JWT 撤銷與對話唯一鍵需要 migration `0012`／`0013`；最新 schema 以 migration 與 [資料庫設計](../database-design.md) 為準。
- LLM 不能讀到其他使用者資料；工具可見清單截斷不代表統計總數截斷。一般 Chat 與 Agent 保持分開。
- MySQL 還原後 dump 有冗餘 `CHARACTER SET utf8mb4` 表示差異；只接受已驗證的窄範圍等價正規化，其餘 SQL／資料仍完整比對。
- Docker Snap 的 gateway NNP 例外已做 A/B 驗證，不能用移除全部隔離繞過。重複 nosniff 曾使檢查器誤報，修的是驗收邏輯，不能關安全標頭。
- 停止前端 SSE 不等於取消後端工作；`BackgroundTasks` 不是持久佇列。中斷工作受控標失敗，不重跑已完成結果。

## 驗證與下一步

既有公開 HTTPS／SSE／資料保存、手機行動網路與第一份備份還原已通過。2026-10-21 維運收尾的本機測試與真實 CPU／暫存資料回歸已完成；**尚未取得 Ubuntu 新批次結果**，每日 timer 不視為已啟用，CI 不視為已有遠端 run。

要繼續維運收尾，讀 [收尾批次](../lab-phase6-finalization.md) 與 [目前操作](../lab-operations.md)。要做新功能，從 [後續候選](../roadmap.md#後續優化候選尚未排入本次) 選明確範圍，不需重做平台選擇或重跑原始部署。
