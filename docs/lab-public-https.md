# Phase 6 — 管理員建立帳號與校外 IP HTTPS 批次

> 專題／階段紀錄：內含初次建置、修復與當時待辦。現行日常操作以 [維運手冊](lab-operations.md) 為準，最新狀態以 [roadmap](roadmap.md) 為準；不要依舊待辦重跑納管或初次部署包。

2026-10-20：**公開 HTTPS 核心驗收整批通過**。最新報告 `/home/sam/.config/yolo-system/releases/public-verify-20261020T094649Z-2578684/report.json`：舊圖片／對話 SHA-256 一致、Bearer／signed URL／未登入媒體保護、Chat SSE／保存（首片段 1.05 秒／25 chunks）、Agent 工具／SSE／保存（5.13 秒／11 chunks）皆 PASS。本輪未重建／重啟／替換服務，只新增兩組測試對話。先前 nosniff 是舊檢查的重複值誤判，已由續驗實際通過。**使用者已確認手機行動網路瀏覽器全流程正常；Mac 副本的完整 SQL 與 52 個檔案 SHA-256 核對通過。每日維運與完整回歸仍待完成，整個 Phase 6 尚未結束**；下一步及現行啟停見 [部署交接](lab-operations.md)。

## 一個更新包與一次執行

Mac 上的 `deploy/out/yolo-public-update-20261020.tar.gz` 是產生的原始碼更新包（被 Git 忽略），不含 `.env`、帳密、媒體、模型或 node_modules。產生器為 [package_public_update.py](../deploy/package_public_update.py)，內容受 `lab_public_apply.py` 的明確檔案白名單限制。

先用 VS Code Remote 的上傳／拖放功能，把該壓縮檔放到 Ubuntu **`/home/sam/apps/`**。網站暫停操作，避免偵測／批次／對話執行中切換；一次執行：

```bash
conda activate yolo-backend
cd ~/apps
tar -xzf yolo-public-update-20261020.tar.gz
sudo -v
python yolo-public-update-20261020/apply.py --ip 140.113.135.113
```

解壓的 `~/apps/yolo-public-update-20261020/` 是更新包交付物，保留在專案外即可，不需移進 `deploy/`；正式來源已由腳本套用到專案。後續診斷／維護腳本統一放在專案 `deploy/`。目前不用重跑舊包或修復腳本；日常管理使用文末的 Compose 指令。

Python 保持 sam 身分。沿用先前測試的專案管理員帳密，只互動輸入一次；不在命令列、檔案或報告保存密碼／token。Ubuntu 需保留目前的 `deploy/lab_compose_apply.py`、`lab_backup_verify.py` 及私人 `compose.env`；它們已在前一批使用。

腳本依序合併：

1. 核對已通過的備份報告與原始壓縮產物、Compose 服務身分、介面上的公網 IP、443 空閒、可用磁碟、管理員登入及無進行中偵測。擷取原有圖片／對話指紋。
2. 在覆寫前檢查**全部**來源檔案的 preimage SHA-256（容許單純 CRLF／LF 差異），若有額外程式修改就停止；原碼先保存在私人 releases 目錄，再套用指定檔案。已套用相同版本可重跑，沒有 git reset／commit／push。
3. 以既有 Ubuntu Python lock 建置新 backend。拉取官方 Node 22 與 Caddy 2.11.7 映像，記錄 registry digest，使用 digest 建置 React＋Caddy 的前端入口 image。專用 ignore 排除祕密、媒體與模型；最終前端 image 不含 Node／Vite dev server。
4. 新 backend 在 loopback 18000、同一 UID／GID 與唯讀資料掛載下先驗證 health、註冊確實 403、自訂 YOLO CUDA／PNG 與既有 12 項測試。暫存容器只按本次 ID 清除，之後才更換正式 backend。
5. 更新私人 `compose.env` 中的 image／IP 參數，Compose 環境強制 `ALLOW_REGISTRATION=false`，讀回原有資料與媒體。基礎 compose 也使用該參數與政策，避免舊的基礎啟動指令降回原本會開放註冊的 image。
6. 新增 `sam-yolo-gateway`，只在指定 IPv4 的 **TCP 443** 提供 HTTPS；公開 CA 的 TLS-ALPN 驗證與正常瀏覽使用同一個 port。明確使用 Let's Encrypt shortlived profile，Caddy 自動續期；不使用本機自簽 CA、不關閉憑證驗證。憑證／ACME 帳號存於外部 named volume `sam-yolo-caddy-data`。
7. 真實 HTTPS 客戶端驗證 CA 與 IP、DB health、關閉註冊、原有圖片／對話、SPA／API／媒體錯誤分流、GPU，以及 Chat／Agent SSE 與新對話保存。新增兩組測試對話。

Compose 會替換 backend 容器，保留舊 image；DB 與媒體沿用原持久掛載。原有 nginx 127.0.0.1:8080 留作內部排查入口，仍提供舊 React dist；**正式入口改用輸出的 HTTPS 網址**，新版前端直接由 Caddy image 提供。MySQL、Ollama、其他人的容器、Docker daemon、主機與防火牆規則不重啟／不修改。原先停止保留的 before-compose 容器不更動。

## 結果與失敗處理

成功最後顯示：

```text
Admin-only signup / public HTTPS / persistence / GPU / SSE: PASS
網站：https://140.113.135.113
批次報告：/home/sam/.config/yolo-system/releases/<時間戳>/report.json
```

成功後由手機行動網路或其他校外網路開啟網址，完成登入／圖片／Chat／Agent 的瀏覽器確認，才補記校外使用者端驗收。自動續期已配置不等於已跨過一次真實續期週期；容器與主機也尚未做全面重開機演練。

若約四分鐘後仍無公開可信憑證，會列 `ACME error types` 與 **PENDING**、exit 2；保留已通過測試且關閉註冊的 backend 與 Caddy 自動重試，8080 內部入口仍可用。這表示公網入口尚未通過，可能涉及校方 443 可達性或 ACME 問題；不直接認定為防火牆，也不自動開防火牆或反覆強制申請。只貼最後約 10 行摘要，詳細 Caddy 日誌保存在私人 release 目錄，不需貼整份日誌。

其他切換／資料／SSE 驗證失敗會停止**身分符合本專案**的 gateway，回復先前的 backend image／Compose 參數，再驗證原有資料。這是應用容器回復，不把正式 DB 還原至過去。回復後公網入口停止，原本 loopback 服務可用；回復失敗會明確回報，請保留私人 report、rollback.env 與 source-backup，不執行 prune 或刪除 volume。

## HTTPS PENDING 時的一輪只讀診斷

不要重跑更新包、建置或 GPU 測試。將 [lab_https_diagnose.py](../deploy/lab_https_diagnose.py) 用 VS Code 上傳到 `/home/sam/apps/Yolo_system/deploy/`，以 sam 執行（先前放在 `~/apps/` 只是傳送便利，沒有專案外執行的必要）：

```bash
sudo -v
python ~/apps/Yolo_system/deploy/lab_https_diagnose.py --ip 140.113.135.113
```

不需專案登入；只讀取本專案 gateway 的 Docker 狀態／重啟次數／OOM／憑證 volume、443 監聽、loopback health／註冊政策、系統及 requests 正常 CA 驗證結果，以及 Caddy 啟動／TLS 錯誤摘要。不停服務、不改防火牆、不建立 ACME order、不讀 `.env`／私鑰或輸出 request headers／token；只將遮蔽後摘要另存私人 `reports/https-diagnose-*.json`。貼終端機摘要即可。主機自行連到公網 IP 通過仍不代表校外來源可達，最後須另外從校外驗收。

若 gateway 已在重啟但錯誤摘要仍空，摘要不代表沒有日誌。診斷器已補支援非 JSON、ANSI 及其他啟動 logger；目前不必再次上傳，先讀本專案容器的最後 40 行啟動日誌：

```bash
sudo docker logs --tail 40 sam-yolo-gateway
```

不需重跑更新包、不先放寬容器權限或開防火牆；取得退出原因後才做對應修正。

本次 pytest 的 12 項測試皆通過；`.pytest_cache` 權限警告僅影響測試快取，不需為此重建 image。日後測試可加 `-p no:cacheprovider`。

## Docker Snap 的 NNP 相容修復（Ubuntu 已通過）

先前 `gateway-capfix-20261020T092737Z-2573863/report.json` 停在前置檢查：連 `/bin/sh` 都回 `operation not permitted`，未建置映像、未切換服務，因此不能把問題只歸因於 Caddy file capability。Canonical 明確記錄：Docker Snap 使用 `no-new-privileges=true` 會因 AppArmor 限制而無法啟動容器。[Docker Snap 官方說明](https://github.com/canonical/docker-snap#usage)。

重新上傳修正版 [lab_gateway_repair.py](../deploy/lab_gateway_repair.py) 覆蓋 `/home/sam/apps/Yolo_system/deploy/lab_gateway_repair.py`；旁邊保留前批的 `lab_compose_apply.py`、`lab_backup_verify.py`、`lab_https_diagnose.py`。一次執行：

```bash
conda activate yolo-backend
cd ~/apps/Yolo_system
sudo -v
python deploy/lab_gateway_repair.py --ip 140.113.135.113
```

腳本先確認 Docker Snap、gateway image／Compose 身分、原 backend／web／MySQL 與關閉註冊政策；用相同 image、唯讀根目錄、cap_drop ALL／唯一 NET_BIND_SERVICE、無網路／無掛載的短暫容器比對 NNP=true／false。只有 true 重現 exec EPERM、false 可執行 Caddy 2.11.7，且程序顯示 AppArmor enforce、seccomp=2、有效／bounding capabilities 僅 NET_BIND_SERVICE，才允許正式切換。不能重現或其他限制不符就停下，不自動猜測或放寬其他設定。

切換只更新本專案 gateway：在私人 compose.env 加 `YOLO_GATEWAY_NNP=false`；Compose 使用 `no-new-privileges:${YOLO_GATEWAY_NNP:-true}`，其他主機／預設仍是 true。保持原 gateway image、唯讀、capability 上限、憑證 volume、原 AppArmor profile 及 Docker 預設 seccomp；不使用 privileged／unconfined，不改主機 AppArmor、Docker daemon、防火牆或 GPU，不更換／重啟 backend／web／MySQL／Ollama，不建置／下載映像、不跑 GPU。這是此台 Docker Snap 的 NNP 保護例外，不能宣稱 NNP 仍啟用；未來遷移至支援的 runtime 後再重驗開啟。原 env／Compose 原碼與報告存私人 `releases/gateway-snap-nnp-*/`。

gateway 無法啟動時只回復原 env／Compose 與 gateway；若已監聽但可信 HTTPS 尚未就緒，保留修復入口及憑證自動重試並回報 PENDING。HTTPS 就緒後繼續正常 CA／IP SAN／health、路由與註冊政策驗證，這時才登入原先的專案管理員，依上一批基準驗證原有圖片／對話及 Chat／Agent SSE／保存（新增兩組測試對話）；不保存帳密／token。登入或驗收失敗不把可用的 gateway 降回已知不能執行的 NNP 設定，最後仍需校外瀏覽器確認。

本機修正版 15 項工具測試、實際 Compose 預設 NNP=true／相容設定 false 的合併與限制檢查通過；Mac 未執行 Linux image，Ubuntu 已通過 A/B 與 Caddy 啟動並取得公開憑證；公開驗收結果見下節。舊更新包不重跑、不搬進 deploy/，也不需要重新上傳整包。

## 重複 nosniff 的驗收續跑（已通過，不需重跑）

Caddy 與 backend 各設定一次 nosniff，requests 讀到合併字串 `nosniff, nosniff`；舊檢查要求整串恰等於 `nosniff`，因此誤報「媒體缺少 nosniff」。Fetch 的瀏覽器演算法按分隔後第一個值判斷；這次修正版更嚴格要求每個值皆為 nosniff（大小寫不敏感），缺少、空值或混入其他值仍失敗，不取消保護檢查。[Fetch Standard](https://fetch.spec.whatwg.org/#x-content-type-options-header)。

只需上傳 [lab_public_verify.py](../deploy/lab_public_verify.py) 至 `/home/sam/apps/Yolo_system/deploy/`；沿用同目錄已在 Ubuntu 使用的 repair／compose／backup helpers，不重傳整包。執行：

```bash
conda activate yolo-backend
cd ~/apps/Yolo_system
sudo -v
python deploy/lab_public_verify.py --ip 140.113.135.113
```

先核對 HTTPS／DB health／標頭與原服務身分，再登入原測試的專案管理員，依第一次公開更新的原基準逐一核對圖片 SHA-256／物件／對話、Bearer 與 signed URL／未登入保護，以及 Chat／Agent 的 SSE／保存；新增兩組測試對話。Docker 操作被限制為 inspect，不能 build／exec／start／stop／Compose；不跑 GPU、不換映像、不重新申請憑證，報告保存私人 `releases/public-verify-*/report.json`。

本機續驗工具 7 項測試及原 Compose 工具 13 項通過。另已從 Mac 以正常 HTTPS 實測 `/`、`/agent`、auth config 均 200，未知 API／docs／不存在 asset 404、未登入 static 401，均有有效 nosniff；未將此 HTTP 檢查宣稱為校外瀏覽器登入驗收。下一次 gateway image 建置的 Caddyfile 已改為 deferred set，確保下游 nosniff 不被上游追加成重複值；Referrer-Policy 只在上游未提供時設定，並刪除冗餘的 X-Forwarded-For 指令。官方 Caddy 2.11.7 adapt 已確認此設定；**此設定清理尚未更新現有 gateway image，本輪續驗不必為它重建服務**。[Caddy header 指令](https://caddyserver.com/docs/caddyfile/directives/header)。

## 正式服務管理（這批成功後）

完整入口使用兩個 Compose 檔；私人 env 檔同時固定目前後端及 gateway image：

```bash
cd ~/apps/Yolo_system
sudo docker compose --env-file "$HOME/.config/yolo-system/compose.env" \
  -f deploy/compose.lab.yaml -f deploy/compose.public.yaml ps
```

相同前綴加 `up -d --no-build --pull never backend gateway` 可依保存的映像啟動服務；不要重跑最初的 `lab_compose_apply.py` 納管腳本，因為它驗證的是舊部署基準。不要刪除憑證 volume；gateway 仍需持續運行、能連線 CA，外部 443 需持續可達，才能自動續期。

MySQL 尚未納入 Compose；每日備份／輪替、Mac 副本、Vite 工具鏈升級與完整 Phase 6 驗收仍待完成，不能把本批當成整個 Phase 6 已結束。

## 驗證與官方依據

- Mac：帳號政策／既有認證測試、React production build、登入與直開 `/register`／設定失敗的實際瀏覽器檢查；沿用既有樣式及 Axios。部署工具測試涵蓋來源衝突／竄改／symlink、公開 CA 設定、HTTPS request／SSE 路徑、登入失敗不變更、切換失敗回復與憑證未就緒保留服務。
- 已下載官方 Caddy 2.11.7 並驗證發行檔 SHA-512，實際解析 Caddyfile；實際 Compose 合併解析通過。Mac 沒有執行 Linux Docker image 或申請憑證。
- [Let's Encrypt IP 憑證及 160 小時效期](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability)、[Caddy ACME profile／challenge 設定](https://caddyserver.com/docs/caddyfile/directives/tls)、[Caddy 2.11.7 修正 SSE 連線問題](https://github.com/caddyserver/caddy/releases/tag/v2.11.7)。
