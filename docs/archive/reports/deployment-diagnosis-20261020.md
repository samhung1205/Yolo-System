> 歷史封存：2026-10-21 自 `DEPLOY.md` 整理前版本保留。內容描述當時狀態，含已解決限制、舊操作與過期待辦；不得當作目前指令執行。現況見 [文件索引](../../README.md) 與 [開發狀態](../../roadmap.md)。

# Deployment Profile

產生日期：2026-10-20（Asia/Taipei）。平台限制於本日重新查核；正式採用前應再次確認官方文件。這是部署診斷與 Phase 6 計畫，**不是已完成部署的操作手冊**。實驗室主機的已回報驗證結果與 6.1 操作步驟另見 [實驗室同網址服務](../../lab-same-origin.md)；後端映像準備與 GPU 驗證步驟見 [Phase 6.2](../../lab-backend-container.md)；未勾選的完整驗收仍待完成。

## Project profile

- **使用情境與預算**：使用者確認約 10–50 人的實驗室／內部使用，免費優先；最後決定改用既有實驗室主機，Ollama 一起留在主機。已提供 Ubuntu 22.04.4、i7-13700、約 62 GiB RAM、RTX 4070 Ti 12 GiB，為多人共用主機；已確認沒有 NAS／獨立備份磁碟；尚未確認同時推論人數與每日上傳量，不能把 50 個帳號當成已驗證的 50 路並行。
- **部署組成**：React 靜態 build + FastAPI 應用、MySQL、Ollama；前端可由同機 nginx 提供，不需要常駐 Vite dev server。Desktop 是使用者端程式，連至共用 API。依據：[前端設定](../../../web-frontend/package.json)、[後端入口](../../../backend/main.py)、[DB 連線](../../../backend/app/db/session.py)、[Ollama provider](../../../backend/app/integrations/chat_providers/ollama_provider.py)、[Desktop client](../../../desktop-app/api_client.py)。
- **需要伺服器運算**：登入與 JWT、DB 存取、YOLO 圖片／影片推論、Chat／Agent，以及受保護媒體下載均由後端處理。依據：[API routes](../../../backend/app/api/routes)、[YOLO engine](../../../backend/app/integrations/yolo_engine.py)、[媒體存取](../../../backend/app/api/routes/static_files.py)。
- **常駐／長時間工作**：FastAPI、MySQL、Ollama 必須在提供服務期間運行；單張影像同步推論，影片及批次透過 FastAPI `BackgroundTasks` 執行，並非可跨行程重啟保存的工作佇列；Chat／Agent 有 SSE（伺服器逐段傳送回覆）連線。依據：[偵測 routes](../../../backend/app/api/routes/detections.py)、[偵測 service](../../../backend/app/services/detection_service.py)、[Chat routes](../../../backend/app/api/routes/chat.py)、[Agent routes](../../../backend/app/api/routes/agents.py)。
- **執行時間**：先前本機單圖完整請求約 3.69 秒、小模型 Chat／Agent 約 2–3 秒，僅為既有煙霧測試。100 張批次估計數十秒至數分鐘；影片依長度、解析度與硬體而變，可能超過數分鐘。這些不是實驗室部署主機的效能保證；需重測冷載入、長影片及多人排隊。依據：[既有整合驗證](web-integration-validation-20261015.md)、[批次已知限制](../../../AGENTS.md)、[逐幀迴圈](../../../backend/app/integrations/yolo_engine.py)。
- **上傳規模**：單圖 10 MiB、單片 200 MiB；批次預設最多 100 張，同一請求理論檔案總量接近 1000 MiB，另加 multipart 開銷。依據：[大小常數](../../../backend/app/services/detection_service.py)、[批次設定](../../../backend/app/core/config.py)。
- **排程**：使用者詢問每日備份／清理是否能免費；目前未建立排程。建議以主機排程執行，不另外購買雲端排程服務。既有頭像清理工具預設 dry-run；沒有偵測原圖／結果／影片的自動保留政策。依據：[頭像清理](../../../backend/scripts/cleanup_avatars.py)、[偵測 service](../../../backend/app/services/detection_service.py)。
- **儲存盤點**：本次 `backend/static/` 為 219 檔、294,703,144 bytes（約 281 MiB），其中 106 檔超過 400,000 bytes；YOLO checkpoint 合計 75,489,136 bytes，不含 Ollama 模型。前端本次 build 為 19 檔、593,151 bytes，沒有超過 400,000 bytes 的單檔。完整較大媒體清單見 [盤點附表](../../deploy-static-inventory.md)。這些後端媒體不會自動成為前端 CDN 資產；400 KB 是診斷篩選門檻，並非通用平台硬限制。
- **模型交付**：`.pt` 被 Git 忽略，部署時須另行交付並通過 registry 指紋檢查。ASFF／DySample／EfficientViM 還依賴根目錄的相容模組，僅複製 `backend/` 不足。依據：[gitignore](../../../.gitignore)、[registry](../../../backend/app/integrations/model_registry.py)、[相容層](../../../backend/app/integrations/legacy_checkpoint_compat.py)。Agent 原始碼預設模型為 `gemma4`，應記錄實際 tag、manifest 摘要與大小，避免重新下載時取得不同版本。依據：[設定](../../../backend/app/core/config.py)。

## Recommendation

**First choice：既有實驗室主機，建立校外可直接使用的 HTTPS 入口。**

使用者後續確認目前只有主機 IP，沒有網域；必須能從校外網際網路直接使用。公開 IP 的可信 HTTPS／DB health 已通過，公開原有資料／媒體／SSE 已整批通過，校外瀏覽器已由使用者確認正常，維運驗收待完成；SSH forwarding 保留作維護入口。帳號由管理員建立；正式 backend 已關閉自行註冊並通過驗證，HTTPS 已可正常驗證連線，公開 API／媒體／SSE 驗收已通過，校外瀏覽器已由使用者確認，維運待完成。

免費 HTTPS 可評估 Let's Encrypt 的 IP 憑證：已支援 IPv4／IPv6，但效期為 160 小時，必須完成自動續期，不能只手動簽一次。Caddy shortlived IP 憑證已取得，Mac 正常 CA 驗證公開 health 通過；手機行動網路瀏覽器完整流程已由使用者確認，自動續期亦尚未跨過實際週期。[官方公告](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability)。

依使用者最新決定，優先讓同一主機提供 React、FastAPI、MySQL 與 Ollama。使用既有硬體、網路、備份磁碟時，每日排程不會產生雲端呼叫費；仍有電力、磁碟、管理及硬體汰換成本，不能把它稱為沒有資源成本。硬體規格與基本 GPU 推論已確認；容量是否足夠仍需量測同時推論量、峰值 RAM／VRAM、磁碟成長與備份耗時。

Phase 6 目標拓撲（公開 HTTPS／媒體／SSE 已通過；校外瀏覽器已確認；完整維運交接尚待完成）：

```text
校內外瀏覽器 ──> 同一 IP／HTTPS 入口 ──> Caddy
                                      ├─ /、前端路由：React build
                                      └─ /api/*、/static/*：FastAPI
                                                               ├─ MySQL
                                                               ├─ YOLO + 既有 checkpoint
                                                               └─ Ollama
Desktop ───────────────────────────────> 同一網址的 API
主機備份 ──> 一致性的 DB + 媒體／設定 ──> 同機私人目錄 ──> Mac 副本
```

Caddy 為校外入口，直接提供新 React build 並把 API 請求轉給 FastAPI；原 nginx 127.0.0.1:8080 保留作內部診斷入口。`/static/*` 必須繼續經過後端驗證，不能直接公開整個目錄。現有 Vite proxy 僅供開發，FastAPI 不直接提供 React build；本階段新增 [loopback nginx 設定](../../../deploy/nginx.lab.conf)，先經 SSH forwarding 驗證。依據：[Vite 設定](../../../web-frontend/vite.config.js)、[後端入口](../../../backend/main.py)、[受保護 static](../../../backend/app/api/routes/static_files.py)。

**Runner-up：Oracle Cloud Always Free，僅在未來重新考慮免費雲端時試驗。**

原文件六平台以外的候選：本次官方資料列 A1 共 2 OCPU／12 GB RAM，另有免費儲存額度；有容量不足、閒置主機被回收及 ARM64 相容性／效能需驗證等限制。此選項不是已部署或已驗證的替代品，也不是使用者目前選擇。[Oracle 官方說明](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)、[Ollama ARM64 支援](https://docs.ollama.com/linux)。

**What would change this**：若實驗室主機不能持續開機、無可用備份位置，或需要校外穩定服務，需重新比較可用硬體與雲端預算。若需要大量使用者同時推論，須先量測 GPU／記憶體、排隊與延遲，不能直接用免費 CPU 主機承諾服務量。

### 每日備份／清理是否會超過免費額度？

在所選的實驗室方案中，**每天執行一次不會觸發雲端付費門檻**，前提是工作及儲存都使用既有資源。會先遇到的是磁碟滿、備份太久或推論競爭。只備份到同一顆磁碟，不能防止該磁碟損壞。

- 以目前媒體量不成長、未壓縮計算，7 份全量約 **2.06 GB**、30 份約 **8.84 GB**；均不含 DB、Ollama 模型、其他備份與後續新增資料。這是容量示例，不是每月傳輸或帳單預測。
- 初步建議：每日 DB 一致性備份 + 媒體增量備份，保留 7 個日版本，備份成功與可還原後才輪替；先取得實際 DB 大小與每日新增量，再確認保留策略。固定模型另保存可重建資訊或一份副本，避免每天重複全量複製。
- 頭像清理先執行 `python scripts/cleanup_avatars.py` 預覽（於 `backend/`），確認規則後才安排 `--apply`。不能把依檔案日期任意刪除偵測媒體當成安全清理，因為 DB 與歷史紀錄仍可能引用它們。依據：[清理工具](../../../backend/scripts/cleanup_avatars.py)、[偵測刪除與檔案清理](../../../backend/app/services/detection_service.py)。本次未刪檔或建立排程。
- 若未來選雲端備份，費用由容量、版本、操作數與傳輸決定。例如 R2 Standard 有 10 GB-month 儲存及操作免費額度，但超額可計費；不是自帶零元硬上限。本方案沒有啟用 R2。[官方價格](https://developers.cloudflare.com/r2/pricing/)。

### 為什麼沒有直接部署到一般網站平台？

專案可以改用外部平台，公網 IP 不是程式架構的硬性要求。前面的選擇是同時保留免費、實驗室 RTX 4070 Ti 與本機 Ollama，再讓校外成員使用；因此採用自架主機，需要自行建立安全可達的入口。HTTPS 對校外傳輸帳密／JWT 很重要，外部託管平台通常只是代為管理網址及憑證，並未免除 HTTPS。

| 方式 | 網站入口 | 推論與資料 |
|---|---|---|
| 整套放實驗室 | 自行設定 HTTPS 與校外可達性 | 使用既有 GPU／Ollama／MySQL 與磁碟，需自管服務及備份 |
| 整套移到雲端 | 選代管平台可減少入口設定 | 另選足夠的 GPU 或 CPU、常駐模型與持久儲存方案，不能預設一般免費網站額度足夠 |
| 前端放平台、後端留實驗室 | 前端可用平台網址／HTTPS | 實驗室 API 仍需安全可達，平台不會自動取得這台 GPU；還需設定前後端連線 |

例如 Vercel Functions 的 4.5 MB 請求限制會擋目前較大上傳；Render 免費 web service 無持久磁碟，無法按現在的本機目錄方式可靠保存媒體。這些是具體方案限制，不代表所有外部平台都不能部署。[Vercel 官方限制](https://vercel.com/docs/functions/limitations)、[Render 免費限制](https://render.com/docs/free)。

備份與還原驗證在自架和雲端都需要；它不是使用公網 IP 才額外出現的需求。若未來願意為雲端推論／儲存付費，或接受調整模型與效能，再依新條件重選平台；目前沒有購買任何雲端資源。

## Collision forecast

以下比較的是**保留目前完整功能及自架 Ollama**的情況；前端單獨可靜態託管，不代表完整系統可免費託管。付費能力不視為使用者已同意付費。

| 平台 | Verdict | 第一個實際限制與可能現象 |
| --- | --- | --- |
| Vercel Hobby | **BLOCKED**（完整系統） | 函式請求 4.5 MB 上限先擋住較大圖片／影片／批次，回 `413 FUNCTION_PAYLOAD_TOO_LARGE`；300 秒上限也限制長任務，超時為 `504 FUNCTION_INVOCATION_TIMEOUT`。2 GB 函式記憶體亦非目前 Ollama 的部署規格。[官方限制](https://vercel.com/docs/functions/limitations) |
| Cloudflare Workers／Pages | **BLOCKED**（完整系統） | Worker 128 MB、Free CPU 10 ms，不能直接承載目前原生 YOLO／Ollama。即使只做代理，Free zone 100 MB 請求上限也會擋大影片／批次，回 413。Containers 屬另一個需付費的產品。[Workers 限制](https://developers.cloudflare.com/workers/platform/limits/)、[Containers 價格](https://developers.cloudflare.com/containers/platform/pricing/) |
| Netlify Functions | **BLOCKED**（完整系統） | 同步函式 60 秒、二進位有效 payload 約 4.5 MB；背景函式 payload 僅 256 KB，不能直接用來接收目前批次／影片上傳。可能在上傳被拒或長任務逾時，需另外建置後端。[官方限制](https://docs.netlify.com/build/functions/configuration/) |
| Render Free | **BLOCKED**（可靠保存完整系統） | 無 persistent disk；休眠、重啟、重新部署會失去上傳檔案與執行時下載的模型。閒置 15 分鐘休眠、每月共用 750 instance-hours，不適合依目前方式持久保存與運行整套服務。[官方限制](https://render.com/docs/free) |
| Railway Free | **BLOCKED**（目前模型） | 每服務 0.5 GB RAM、0.5 GB volume。Gemma 模型檔本身已超出磁碟額度；載入則可能記憶體不足。免費每月 $1 credit 不是常駐整套服務的保證。[Railway 方案](https://railway.com/pricing)、[Gemma tags](https://ollama.com/library/gemma4/tags) |
| AWS Lightsail | **FITS WITH CAVEATS**（付費技術候選）；零預算排除 | 一般 VM 可承載此架構，但最小 0.5 GB 機型不足；所需機型必須量測後決定。主機有固定費用，另須注意快照與流量超額。CPU 長時間推論還會受 burst capacity 影響；不是長期免費方案。[價格](https://aws.amazon.com/lightsail/pricing/)、[CPU baseline](https://docs.aws.amazon.com/lightsail/latest/userguide/baseline-cpu-performance.html) |

**First wall you will hit**：若誤將完整 FastAPI 放上 Vercel／Netlify，通常尚未進入 YOLO 就在上傳時碰到約 4.5 MB 平台上限；程式允許的單圖 10 MiB、影片 200 MiB 都更大。依據：[上傳 route](../../../backend/app/api/routes/detections.py)、[大小常數](../../../backend/app/services/detection_service.py)。若走 Railway Free，模型磁碟／RAM 會先擋住 Ollama。

在選定的實驗室主機，已完成基本 GPU 與模型驗證，但仍不足以宣稱已達或接近哪個併發上限。優先驗證 Ollama + YOLO 同時載入的峰值記憶體、批次排隊、原圖／結果／影片及備份成長。Ollama 並行會增加記憶體需求，過載可能回 503；10–50 位使用者不等於同時服務相同數量的推論。[Ollama 官方 FAQ](https://docs.ollama.com/faq)。

另一個現有瓶頸是批次每 2 秒輪詢完整詳情，repository 連每張 task 的 objects 一起載入；ZIP 下載也先在記憶體組好整包。擴到 1000 張前需先處理，但不把這次部署自動擴成 1000 張改造。依據：[輪詢](../../../web-frontend/src/pages/BatchDetectionPage.jsx)、[repository](../../../backend/app/repositories/detection_repository.py)、[ZIP 建立](../../../backend/app/services/detection_service.py)。

### 額度用完後的行為

- **所選實驗室主機**：沒有雲端額度或按次帳單；磁碟滿、RAM 不足或停電會影響可用性。基本硬體與推論已驗證；併發、資料成長與備份容量仍待量測。
- **Vercel Hobby**：超額通常須等待額度恢復，不自動轉成付費擴容。[Hobby 說明](https://vercel.com/docs/plans/hobby)。
- **Workers Free**：每日 100,000 請求額度是執行限制，不是自動購買付費方案；靜態資產與 R2／Containers 應分開看待。[Workers 限制](https://developers.cloudflare.com/workers/platform/limits/)。
- **Netlify Free**：現行官方已明載每月 300 credits 硬上限，耗盡會暫停，不能加購 Free 額度；更新原診斷範本「未載明」的敘述。[方案](https://www.netlify.com/pricing/)、[暫停說明](https://docs.netlify.com/manage/accounts-and-billing/billing/resume-paused-projects/)。
- **Render**：Free hours 用完暫停；流量超額有付款方式時可能加收，沒付款方式則暫停。獨立 Cron service 最低每月 $1。[Free 說明](https://render.com/docs/free)、[Cron 價格](https://render.com/docs/cronjobs)。
- **Railway**：付費方案按資源收費；目前官方已提供 Compute hard limit，達到時下線 workloads，更新原範本對支出上限不明的描述。沒有設定 hard limit 不能視為自動封頂。[成本控制](https://docs.railway.com/pricing/cost-control)。
- **Lightsail**：固定主機費以外仍可能有用量費；AWS 預算通知有延遲，不能視為零元硬上限。[價格](https://aws.amazon.com/lightsail/pricing/)、[AWS Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)。

**免費 headroom**：所選方案取決於實驗室資源，不能由人數單獨換算可用天數。原六平台對這個完整工作負載先遇到架構／單服務限制，不能用帳號數乘免費請求額度假裝能上線。待量測硬體、同時工作數、每日新增量及備份耗時後，再給容量與延遲估算。

## 最新部署條件（2026-10-20）

使用對象仍為實驗室成員約 10–50 人，但必須能從校外網際網路直接連線。只有 IP、沒有網域；已由管理員建立帳號、正式 backend 關閉自行註冊並驗證；公開 HTTPS／原有資料／受保護媒體與 Chat-Agent SSE 已通過，SSH forwarding 保留作維護。沒有 NAS 或獨立備份磁碟；已做同主機備份／隔離還原，並下載至 Mac 核對另一份副本，不能宣稱同主機備份已能抵抗主機／磁碟故障。使用者要求加速，常規部署與驗證改為批次執行、自動彙總，重要登入／存取與資料保護決策才停下確認。Compose 納管／原有圖片與對話／GPU／路由／Chat-Agent SSE 已通過，報告 compose-20261020T055006Z-2532143.json；Ollama active／enabled、可用磁碟 486.5 GiB。[備份與隔離還原](../../lab-backup.md) 已實際通過：原始備份 20261020T075232Z-2550504、成功報告 20261020T081258Z-2556729；30 行全為 MySQL 已知等價 utf8mb4 表示，其他 SQL 與所有檔案完整，正式服務正常。Mac 副本已核對完整 SQL 與 52 個檔案 SHA-256 通過；每日排程尚待完成。[關閉自行註冊與校外 HTTPS 更新包](../../lab-public-https.md) 已於 Ubuntu 套用與建置，新 backend 政策／DB／自訂 GPU／12 項測試／原有圖片與對話通過；HTTPS PENDING、ACME error types 空（releases/20261020T084747Z-2562377/report.json），後續 Snap NNP 相容修復與可信 HTTPS 已通過（093549Z 報告）；Mac 公開 health／DB 正常，媒體重複 nosniff 被舊比較方式誤判，public_verify 已整批通過（094649Z 報告）：舊圖片與對話 SHA-256 一致、媒體權限、HTTPS Chat／Agent SSE 與保存 PASS（首片段 1.05／5.13 秒）。使用者已確認 Mac 下載完成與手機行動網路瀏覽器全流程正常；本機亦已實際核對備份完整性；現行操作見 docs/lab-operations.md，尚未宣稱整個 Phase 6 完成。批次證據見 [Compose 管理](../../lab-compose.md)。

## Pre-launch checklist

Phase 6 尚未實作完成，以下依序進行；每一步驗證通過再往下，不改寫 legacy，也不合併 `/api/chat` 與 `/api/agent/chat`。

2026-10-21 收尾工具與本機驗證已補齊；Ubuntu 一次執行、23:30 備份、回復與 CI 交付見 [Phase 6 收尾](../../lab-phase6-finalization.md)。目前仍待 Ubuntu 報告，不先標記全 Phase 完成。

### 6.1 主機與同網址服務

- [ ] 記錄實驗室主機 OS／CPU／GPU／RAM／可用磁碟、10–50 人中預期同時推論數，以及既有 NAS／獨立磁碟與網路存取方式。
- [ ] 先在該主機跑現有 YOLO + Ollama，量測同時載入、冷啟動、單圖／影片／100 張批次、Chat／Agent 的時間與峰值 RAM／VRAM；再定容器資源與併發上限。
- [x] 建立 React production build 與同網址服務，前端使用相對 `/api`；SPA 深連結重新整理可用，`/api/*` 與 `/static/*` 不落入前端 fallback。不是用 Vite dev／preview 充當正式服務。
- [x] 公開 IP 可信 HTTPS、關閉自行註冊、受保護媒體與兩條 SSE 已通過，手機行動網路完整流程由使用者確認；Caddy／nginx 上傳與 timeout 已配置。Caddy 自動續期已配置，實際續期週期與大檔案邊界回歸仍待觀察。
- [x] 初期單 FastAPI worker；目前登入／LLM 限流在行程記憶體，多 worker 前需共享狀態。YOLO CPU 工作仍需控制併發；單 worker 不等於所有同步工作自動序列執行。依據：[登入限流](../../../backend/app/core/rate_limit.py)、[LLM 限流](../../../backend/app/services/llm_policy.py)、[routes](../../../backend/app/api/routes/detections.py)。

### 6.2 Docker 與持久保存

- [x] 建立 Compose、backend 與前端 build／nginx Dockerfile、`.dockerignore`；避免把本機設定、私人媒體與不需要的 legacy 執行環境打包進 image。
- [ ] MySQL 資料、`backend/static`、Ollama 模型都使用持久 volume；YOLO checkpoint 與自訂相容原始碼另有明確交付路徑。容器網路中的 DB／Ollama 位址需按部署設定，不直接沿用開發機 localhost。
- [ ] 鎖定可重建的 Python／Node／推論套件版本與模型資訊；容器內實際載入至少一個自訂 checkpoint 並完成標註圖保存，不能只驗證 import。
- [ ] 重建容器後，帳號、聊天、偵測結果、頭像與模型都仍可使用。現有簽章／JWT 權限與 `/static` 安全 headers 保留。

### 6.3 設定、migration、備份與復原

- [x] 部署設定只透過未追蹤的環境檔或既有祕密管理方式提供；下列只列名稱，不記錄值。
  - 主要：`APP_ENV`, `APP_HOST`, `APP_PORT`, `SECRET_KEY`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_ECHO`, `CORS_ORIGINS`。
  - 本地推論：`CHAT_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `AGENT_PROVIDER`, `AGENT_MODEL`, `AGENT_OLLAMA_MODEL`, `AGENT_ENGINE`, `AGENT_ENABLE_DEEPAGENTS`, `YOLO_DEFAULT_MODEL_KEY`。
  - 容量／限制：`CHAT_REQUEST_TIMEOUT`, `DETECTION_BATCH_MAX_FILES`, `DETECTION_PERCLASS_MAX_DET`, `LLM_RATE_LIMIT_PER_MINUTE`, `LLM_PAID_DAILY_LIMIT`, `STATIC_URL_EXPIRE_SECONDS`。
  - 前端／Desktop：`VITE_API_BASE_URL`（build-time）, `YOLO_API_BASE_URL`（Desktop）；`VITE_PROXY_TARGET` 僅開發使用，不是正式代理設定。
  - 其餘可選名稱與讀取位置見下方清單；不用外部 API 時不需要新增付費 provider 的金鑰。
- [x] 使用專用 MySQL 應用帳號；migration 使用足夠但受限的權限；先備份，再於 `backend/` 執行 `alembic upgrade head`，核對 revision `0013`（含 `0012` token_version）。正式環境啟動前確認 seed admin 已改密與 SECRET_KEY 符合啟動檢查。依據：[migrations](../../../backend/migrations/versions)、[啟動檢查](../../../backend/app/core/startup_checks.py)。
- [ ] 每日一致性 DB 備份 + 媒體增量備份，存至獨立既有資源，定義保留天數、容量警戒及失敗紀錄；不啟用雲端自動加值。資料庫不能直接靠複製正在寫入的資料目錄當成可還原備份。
- [ ] 先人工確認頭像清理 dry-run；偵測媒體清理政策另行設計。備份與清理時間避開推論尖峰，排程採明確時區（Asia/Taipei）。
- [x] 於隔離資料庫與目錄實際還原，SQL／檔案驗證已通過（20261020T081258Z-2556729）。
- [x] 原始備份與成功驗證報告已下載 Mac；壓縮產物、完整 SQL 與 52 個檔案 SHA-256 全部通過。此副本為公開更新前的時間點。
- [x] 從已驗證備份取回 Ubuntu `deploy/backend-linux.lock` 至 Mac；118 個固定版本及關鍵 GPU／Agent 版本核對通過，雜湊記錄於部署交接。
- [x] 中斷工作受控處理已定義與測試：預設唯讀，明確套用時停 backend、將未完成紀錄標 failed、重算批次計數並恢復；保留完成結果與媒體，使用者重新上傳。Ubuntu 尚待實測，不自動恢復或新增 queue。

### 6.4 驗收與文件

- [x] 假模型 SSE 測試已隔離本機 Ollama 安裝清單；Mac 後端全套 179 通過（29.01 秒），正式白名單不變。
- [ ] Ubuntu 收尾批次：容器完整回歸／跨帳號／頭像／批次／影片／Desktop／gateway 回退／每日備份首次實跑；工具與本機回歸已備妥。
- [x] 手動 CI workflow 已建立（官方 action 固定 commit、唯讀、15 分鐘）；未 push、未取得 GitHub run 結果。
- [x] Vite 8.3.4／plugin 6.1.2：build、瀏覽器登入／深連結／路由保護／關閉註冊通過，npm audit 0。
- [ ] 測試登入、權限、個資／頭像、偵測／批次／影片、歷史下載、Chat、Agent SSE、Desktop 連線；一般使用者仍不能讀別人的媒體，無簽章／JWT 不能取得私人檔案。
- [ ] 健康檢查不只看 HTTP 200：現有 `/api/health` 可能在 DB 異常仍回 200，要檢查 JSON 的 `database`。依據：[health route](../../../backend/app/api/routes/health.py)。
- [ ] 補充正式啟動／停止、migration、備份還原、升級與 rollback 文件及 CI；token 是否改 httpOnly cookie 仍是獨立待決定事項，不是本次診斷已實作的變更。
- [ ] 1000 張批次、空間推論、完整 `audit_logs` 與大型併發另排；不因原 roadmap 列在 Phase 6 就默認一起重寫。

本次基線驗證（2026-10-20）：`npm run build` 通過；`conda run --no-capture-output -n yolo-backend python -m pytest -q` 為 **173 passed / 1 failed**。失敗為 [Agent stream test](../../../backend/tests/test_agent_stream_route.py) 的 `test_tool_engine_streams_tool_events`：測試指定 qwen2.5，但當次受限環境無法連線本機 Ollama，動態模型白名單未包含它而回 400，未進 SSE；僅在該次 Python 行程模擬模型清單後，單項通過。沒有修改測試或放寬正式白名單，也沒有執行正式 DB migration／清理。這不是已完成的部署驗收。 後續已在該假模型測試固定 fetch_ollama_models 的回傳並要求 HTTP 200；Mac 全套已重跑 179 passed（29.01 秒），不修改正式 allowed_models。公開 HTTPS／媒體／SSE 另已在 Ubuntu 通過；兩種證據不混稱為完整部署／CI 驗收。

### 環境變數讀取位置（僅名稱）

主設定由 [Settings](../../../backend/app/core/config.py) 集中讀取：

```text
ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY
APP_ENV, APP_HOST, APP_PORT, CORS_ORIGINS, ALLOW_REGISTRATION
DB_ECHO, DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER
CHAT_CONTEXT_MAX_TURNS, CHAT_PROVIDER, CHAT_REQUEST_TIMEOUT, CHAT_SYSTEM_PROMPT
OPENAI_ALLOWED_MODELS, OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_CHAT_MODEL
DEEPSEEK_ALLOWED_MODELS, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_CHAT_MODEL
OLLAMA_BASE_URL, OLLAMA_MODEL
AGENT_ENABLE_DEEPAGENTS, AGENT_ENABLE_VISION, AGENT_ENGINE
AGENT_MAX_HISTORY_TURNS, AGENT_MAX_TOOL_CALLS, AGENT_MODEL, AGENT_OLLAMA_MODEL
AGENT_PROVIDER, AGENT_RECURSION_LIMIT, AGENT_SYSTEM_PROMPT, AGENT_VISION_MAX_IMAGE_BYTES
DETECTION_BATCH_MAX_FILES, DETECTION_PERCLASS_MAX_DET
DETECTION_PREVIEW_DIR, DETECTION_RESULT_DIR, DETECTION_SOURCE_DIR
DETECTION_VIDEO_RESULT_DIR, DETECTION_VIDEO_SOURCE_DIR
YOLO_DEFAULT_MODEL, YOLO_DEFAULT_MODEL_KEY, YOLO_RESULTS_DIR
LLM_PAID_DAILY_LIMIT, LLM_RATE_LIMIT_PER_MINUTE
LOGIN_FAILURE_WINDOW_SECONDS, LOGIN_MAX_FAILURES_PER_ACCOUNT, LOGIN_MAX_FAILURES_PER_IP
STATIC_URL_EXPIRE_SECONDS
```

其他直接讀取位置：

| 檔案 | 名稱 |
| --- | --- |
| [api.js](../../../web-frontend/src/services/api.js)、[agentService.js](../../../web-frontend/src/services/agentService.js) | `VITE_API_BASE_URL` |
| [vite.config.js](../../../web-frontend/vite.config.js) | `VITE_API_BASE_URL`, `VITE_PROXY_TARGET` |
| [desktop api_client](../../../desktop-app/api_client.py) | `YOLO_API_BASE_URL` |
| [MainUI.py](../../../MainUI.py) | `YOLO_DESKTOP_MODEL` |
| [AgentWindow.py](../../../AgentWindow.py)、[AICSMain.py](../../../AICSMain.py)、[AdminMainUI.py](../../../AdminMainUI.py)、[AdminAddUser.py](../../../AdminAddUser.py)、[Register.py](../../../Register.py) | `QT_FONT_DPI` |

本報告只列設定名稱，不包含部署金鑰或連線密碼。

## Sources

上文平台判斷以官方資料為準；原診斷文件的 2026-10-05 數字並非永久保證。此處更新了 Railway 支出硬上限、Netlify Free 額度耗盡行為，也區分 Workers 與付費 Containers。

- [Vercel Functions limits](https://vercel.com/docs/functions/limitations)、[Hobby](https://vercel.com/docs/plans/hobby)、[Cron](https://vercel.com/docs/cron-jobs/usage-and-pricing)
- [Cloudflare Workers limits](https://developers.cloudflare.com/workers/platform/limits/)、[Containers pricing](https://developers.cloudflare.com/containers/platform/pricing/)、[R2 pricing](https://developers.cloudflare.com/r2/pricing/)
- [Netlify Function configuration](https://docs.netlify.com/build/functions/configuration/)、[pricing](https://www.netlify.com/pricing/)、[paused projects](https://docs.netlify.com/manage/accounts-and-billing/billing/resume-paused-projects/)
- [Render Free](https://render.com/docs/free)、[pricing](https://render.com/pricing)、[Cron](https://render.com/docs/cronjobs)
- [Railway pricing](https://railway.com/pricing)、[resource prices](https://docs.railway.com/pricing)、[cost control](https://docs.railway.com/pricing/cost-control)
- [Lightsail pricing](https://aws.amazon.com/lightsail/pricing/)、[CPU baseline](https://docs.aws.amazon.com/lightsail/latest/userguide/baseline-cpu-performance.html)、[AWS Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)
- [Oracle Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [Ollama Linux](https://docs.ollama.com/linux)、[FAQ](https://docs.ollama.com/faq)、[Gemma tags](https://ollama.com/library/gemma4/tags)
