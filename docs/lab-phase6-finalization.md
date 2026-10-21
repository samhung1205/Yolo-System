# Phase 6 收尾批次

2026-10-21：前段完整功能與 GPU 驗收已通過。Ubuntu `d4ab0fa` 的 `finalize-20261021T031358Z.json` 進入備份後，連結匯出成功，停在 `Ollama manifest inventory changed`；此文字是舊驗證器的失配訊息，不能據此認定模型真的變動。原驗證漏掉 Ollama 0.40.6 的 manifests-v2／manifest list，已補本機測試與修正，仍待實機續跑。此次尚未停止 backend 擷取資料；每日排程尚未啟用。2026-10-21 11:28 台灣時間，Mac 實際存取公開 HTTPS health 得到 status=ok／database=connected。

## 已完成的本機驗證

- 上一輪後端全套 **190 passed（29.91 秒）**：獨立工作目錄／隨機測試 key／合成圖片，不讀正式 `.env` 或私人媒體；使用本機核准 checkpoint，非 Ubuntu GPU 重驗。新增 Ultralytics HEIF 包裝下的格式白名單、壞檔拒絕與暫存清理測試。
- 部署工具涵蓋備份失敗恢復、輪替範圍、root／使用者權限界線、暫存還原歸屬、來源更新與 gateway 回退。最新全套 **185 項通過**（含本機假 Docker Unix API、候選 backend 不動正式服務、忙碌拒絕切換、啟動失敗回復、私人設定競爭保護、影片依賴失敗／輸出截斷拒絕與 CI 補充依賴）。
- Vite 8.3.4／React plugin 6.1.2，production build 通過，npm audit 為 0；Node 最低 20.19 或 22.12，部署使用 Node 22 image。依 [Vite 8 遷移文件](https://vite.dev/guide/migration) 更新，沒有執行 audit fix --force。
- Playwright 實際瀏覽器：production build 登入／工作台、Agent query／重新整理、登出、未登入路由保護與關閉註冊頁通過。API 使用獨立 SQLite，沒有使用正式帳密／資料庫。favicon 404 與選取不存在的測試偵測 404 為預期診斷，沒有 JS 執行例外。
- `lab_regression.py` 已在獨立 SQLite、測試 HTTPS 與真實 CPU 模型跑通：兩個臨時帳號、管理員權限、頭像歸屬／清理、單圖／100 張批次／ZIP、四影格影片、媒體權限、Desktop client、改密碼撤銷 JWT；臨時帳號清理成功。100 張合成圖片批次在本次 CPU 環境共 9.276 秒（含上傳／進度等待），只作測試紀錄，不當作真實資料的效能承諾。這不冒稱 Ubuntu GPU 驗收。
- GitHub Actions workflow 已建立，採手動 Run workflow、唯讀權限、固定官方 action commit、15 分鐘上限，不配置付費 runner／儲存／排程；無權重／無媒體／無 .env 的獨立來源樹已實跑 173 passed、9 個 checkpoint 測試明確 deselected（26.77 秒），非 GPU 測試不依賴私人模型。workflow 已隨 `84dcbca` push；尚未取得 GitHub run 結果。私有庫執行前檢查帳號免費額度。遵循 [GitHub Actions 安全指引](https://docs.github.com/en/actions/reference/security/secure-use)。

## Ubuntu 一次執行

現在以 GitHub 來源更新，不再套用舊的 tar 更新包。Ubuntu 已同步過 `84dcbca`，在工作目錄乾淨時直接拉取修正版；有本機修改時先依維運手冊保存，不使用 reset／clean 強制清除。

在 VS Code Remote 終端執行整段（pull 失敗就停止）：

```bash
(
set -eu
conda activate yolo-backend
cd "$HOME/apps/Yolo_system"
git pull --ff-only origin main
sudo -v
python deploy/lab_finalize.py
)
```

舊 `deploy/out/` 套用包是建立當時的來源快照，不會隨 Git 更新，現在不要重跑它來覆蓋較新的檔案。

只需輸入一次本次回歸用的**專案管理員**帳密；不寫入報告。該帳號須是先前公開驗收使用的管理員，才能比對原有圖片與對話。若 Git 拒絕覆寫本機檔案，先保存與比對修改，不能強制覆蓋。

整批完成：

1. 依目前來源與 Linux lock 建置候選 backend image，正式網站在建置期間持續運行；候選 image 必須通過完整 pytest、合成圖片、自訂模型 CUDA／NMS，以及四影格真實影片追蹤／預覽／輸出解碼。測試圖片直接建立在測試容器的 16 MiB tmpfs，容器移除即丟棄，不掛主機 `/tmp`、正式 `.env` 或私人媒體、不連正式 DB。測試／腳本／checkpoint 維持唯讀掛載，沿用原 UID／GPU／CPU／RAM 限制。
2. 確認正式 backend 身分／掛載未改變，並只讀查核沒有 pending／processing 偵測或批次，才將私人 image 參數指向已測試候選；只重建本專案 backend，等待 DB health 與關閉註冊政策通過。失敗時回復原設定與舊 backend image，保留媒體／模型／DB 掛載；不執行 migration。接著建置新的 Vite 8／Caddy image、先驗證設定再切 gateway，保留 Snap NNP 旗標與原憑證 volume，gateway 啟動失敗亦回復。全程不重啟共享 Docker／MySQL／Ollama。
3. 真實 HTTPS 的兩帳號、頭像、圖片／批次／影片、Desktop client 與 JWT 撤銷回歸；只刪本輪建立且已無進行中工作的臨時帳號。
4. 原有圖片／對話基準、Chat／Agent SSE 與保存；各新增一組管理員測試對話。記錄共享 GPU 的觀測峰值，不推論成 50 人同時使用的能力。
5. 僅將本專案 MySQL 的 restart policy 補為 unless-stopped，確認 Ollama active／enabled。
6. 安裝 root 保護的獨立標準庫程式。初次成功備份／隔離還原後，才啟用每天 **23:30 Asia/Taipei** 的 timer，保留最近 7 份成功備份；原始 `20261020T075232Z-2550504` 與成功報告在另一個目錄，固定不動。

首次另保存目前 image 與 Ollama 模型快取，可能需要數分鐘及十多 GB 空間，期間網站仍可用；擷取 SQL／媒體期間 backend 會短暫暫停，恢復後才做隔離還原。下次依相同 image ID／模型 digest 重用快取。若服務忙、有未處理中斷工作或空間不足，拒絕備份並留下失敗報告，不能把失敗當成功輪替。

成功摘要為 `Phase 6 lab finalization: PASS`，並列出新備份路徑及 `~/.config/yolo-system/reports/finalize-*.json`。失敗只需回報最後摘要；勿貼私人配置、完整 manifest、SQL 或 token。排程採 [systemd timer](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html)，含明確時區與停機後補跑；補跑仍受忙碌／空間檢查約束。

## 2026-10-21 容器回歸失敗與續跑

首次報告為 `~/.config/yolo-system/reports/finalize-20261020T182237Z.json`。舊版只顯示 `執行失敗：sudo`，這只是最外層指令名稱，不能據此認定密碼錯誤。當時 stdout／stderr 未被保存，確切退出原因仍無法由該報告還原。

已確認舊實作把主機 `TemporaryDirectory` 的 `/tmp` 掛進 Docker Snap，而 Snap 看的是自己的 `/tmp`；這是有官方依據的可能原因，不冒稱已收到 Ubuntu 原始 stderr。改用容器內合成圖片／有界 tmpfs，避免該路徑依賴，也不放寬主機隔離。[Canonical 說明](https://github.com/canonical/docker-snap/discussions/248)、[Docker tmpfs](https://docs.docker.com/engine/storage/tmpfs/)。

失敗時修正版保存 exit code、stdout、stderr 到該輪私人 releases 的 `container-regression.json`（0600），摘要報告另有 `command_failure` 的 exit code／固定提示／紀錄路徑。不把原始輸出或完整指令參數放到終端機；其他子程序失敗也會保存私人紀錄。請只回報終端機摘要，勿公開整份私人紀錄。容器測試未通過就停止，不切 gateway、不建立測試帳號、不安裝備份。

本機部署工具全套 **137 項通過**，含實際執行合成圖片 seed、子程序 stderr／權限保存、Docker mount 與 sudo 驗證錯誤區分，以及回歸失敗必須阻止後續服務變更；未在 Mac 冒稱通過 Linux Docker Snap／GPU。重新執行上述 Git 更新與單次收尾指令即可，不需重新 stash 未改動的來源或重建 backend。

## 2026-10-21 非圖片拒絕測試的 HEIF 相容修正

Ubuntu `5734992` 的容器已執行完整 pytest，結果為 **180 passed／2 failed**，兩項均是 `test_upload_hardening.py` 的非圖片拒絕／暫存清理；紀錄另有 `pi-heif` 缺少且離線 AutoUpdate skipped。HMAC 短 key 警告來自未掛正式設定的隔離測試，不是這兩項失敗，也不代表正式 SECRET_KEY 被更改。

[Ultralytics 8.4.38 原始碼](https://github.com/ultralytics/ultralytics/blob/v8.4.38/ultralytics/utils/patches.py) 會將 `PIL.Image.open` 包裝為「任何開檔例外就檢查／載入 pi-heif」。非法圖片原本該得到 `UnidentifiedImageError`，卻可能先變成缺少 optional module 的錯誤。上傳驗證現在辨識此已知包裝並使用其保存的 Pillow 原生函式，再明確限定 JPEG／PNG／WEBP／GIF／BMP；不改寫全域 Image.open、不新增 HEIF 支援、不全面吞掉 import 錯誤。未知包裝版本拒絕繼續，升級依賴時須重驗。[Pillow formats 參數](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.open)。

新 backend image 設 `YOLO_AUTOINSTALL=false`，維持固定依賴；不連網臨時補套件、不修改 Linux lock。因既有正式 image 不會隨 git pull 更新，本輪把建置候選、完整 pytest／GPU gate、閒置檢查與受控 backend 切換納入同一批次，而非只在測試容器覆蓋檔案。請在沒有其他成員提交工作時執行上述一段命令；建置通常可重用既有 dependency layer，切換 backend 時會短暫無法服務。

本機新增測試已重現 upstream 包裝導致缺 pi-heif，再驗證修正版壞檔回 400／清理、所有白名單格式通過與 TIFF 拒絕，且沒有安裝嘗試。完整 190 後端／145 部署工具通過；當時正式 Linux image／GPU／HTTPS 尚待 Ubuntu；後續已跑至 HTTPS 影片失敗，見下節。

## 2026-10-21 影片追蹤缺少 lap

Ubuntu 報告 `finalize-20261020T184510Z.json` 已通過候選回歸及服務切換，HTTPS 回歸完成到 100 張批次／ZIP。影片失敗後，篩選出的正式日誌為 `Video detection failed for task 103` 與 `ModuleNotFoundError: No module named 'lap'`，直接原因已確認。

`YoloEngine.detect_video()` 使用 Ultralytics `model.track()`；追蹤的 [matching 模組](https://docs.ultralytics.com/reference/trackers/utils/matching/) 會延遲載入 lap，單圖 smoke 不會驗出它。原始 Ubuntu 118 筆 freeze 未包含此選用依賴。本機環境已有 lap，因此先前 CPU 影片通過不能證明容器完整。

修正使用 [lap 0.5.13](https://pypi.org/project/lap/0.5.13/)：`backend/requirements.txt` 明確列入；Docker 由 `deploy/backend-runtime.lock` 的獨立層安裝固定 binary wheel、`--no-deps` 並執行 pip check／import。原始 `backend-linux.lock` 與 CUDA 版本不動，可重用既有大型依賴層。CI 合併兩份 lock 後只轉 CPU Torch；維持 `YOLO_AUTOINSTALL=false`，不在運行容器或 Ubuntu conda 臨時補裝。

候選 image 現在必須先通過 `backend_smoke.py --video`：合成四影格 64×64 MP4、核准的 ASFF 模型真實 CUDA 追蹤、預覽／metadata、輸出影片實際解碼四影格。測試使用容器內暫存資料且無網路；任何失敗會在 backend／gateway 切換之前停止。完整 HTTPS 影片／Desktop／資料權限驗收依然保留。

本機以 lap 0.5.13 跑過相同影片流程的真實 CPU 推論／追蹤／輸出解碼，另有 153 項部署工具測試全部通過；本輪尚未在 Ubuntu 重跑 GPU／HTTPS，也尚未啟用每日備份。續跑使用上方同一段 Git 更新與收尾指令，不重跑舊套用包。

## 2026-10-21 首次模型快取失敗與受控續跑

Ubuntu 備份 `20261020T214632Z-1f089380`：managed preflight／image 快取成功，隨後 `error=Unsafe native model archive`，沒有 recovery_error，公開 health／DB 正常。依 worker 的順序，此次尚未暫停 backend、擷取 SQL／媒體或進入隔離還原。快速目錄診斷確認 12 個目錄、21 個一般檔案與 2 個符號連結，與舊版拒絕所有連結項目的規則相符。尚未由這份統計確認兩個連結的目標；修正版僅處理可解析且位於模型目錄內的連結，越界／損壞連結仍拒絕。

`lab_finalize.py --resume-backup` 可引用同一帳號私人 reports 內的原始報告，只有原報告確實完成候選 GPU／影片、HTTPS／Desktop 與資料／SSE 驗收，且 backend／gateway image 未變、三個 Compose 服務歸屬正確、HTTPS／DB 與關閉註冊政策正常，才直接重試備份階段。報告缺失／權限不符／驗收不完整或 image 改變時拒絕續跑，須改走完整流程。不建置或切換 backend／gateway、不建立新測試帳號／對話。備份 worker 的 busy／空間、SQL／檔案一致性與完整隔離還原檢查照常執行；首份成功且 worker 版本吻合後才 enable timer。

修正封存原因並更新 Git 後，Ubuntu 可使用：

```bash
(
set -eu
conda activate yolo-backend
cd "$HOME/apps/Yolo_system"
git pull --ff-only origin main
sudo -v
python deploy/lab_finalize.py --resume-backup \
  "$HOME/.config/yolo-system/reports/finalize-20261020T214321Z.json"
)
```

續跑報告記錄 `mode=resume-backup`、`resumed_from` 及原驗收證據，備份與還原是本輪實跑；不把引用的舊 HTTPS／SSE 結果標為新測試。image 快取可重用，不刪原始基準或已有快取；有錯誤時保留私人報告。新增 6 項續跑測試，部署工具全套 159 項本機通過；其中實跑假服務驗證只啟動備份與 enable、不建置 gateway／backend 或執行 Regression。以下連結匯出修正已完成本機驗證，Ubuntu 首份成功備份／還原與 timer 啟用仍待續跑，不能因工具完成就宣稱備份成功。

### 模型符號連結的可攜式匯出修正

原始 `/usr/bin/tar` 會保留連結，但後續驗證只接受一般檔案／目錄，因此正常的模型內部 alias 也會被拒絕。現在由 root worker fork 子程序，先清除附加群組並永久降為 Ollama 的 GID／UID，再用標準庫匯出；不以 root 身分讀取 Ollama 可寫入的模型內容，也不改原始模型目錄。

匯出先掃描小型目錄資訊，解析每個來源，要求解析後仍在模型根目錄內；拒絕根目錄被替換為連結、越界／損壞／循環連結、特殊檔案與擷取途中檔案變更，再讀取／壓縮大型資料。以 [Python tarfile 的 dereference 行為](https://docs.python.org/3.11/library/tarfile.html#tarfile.TarFile) 將安全內部 alias 的內容存成一般檔案／目錄，封存不包含符號或硬連結；還原不依賴舊主機的絕對路徑。保留原本逐 blob SHA-256、manifest inventory 與整份快取 SHA-256 驗證；匯出逾 20 分鐘會回收該讀取子程序。

本機重現相對／絕對內部 manifest 連結及內部目錄 alias，驗證匯出後實際內容一致、只有一般檔案／目錄；也驗證越界、循環、壞連結、FIFO、來源替換拒絕，以及降權順序與逾時回收；blob 本身為內部連結時仍核對內容指紋，壞內容依然拒絕。部署工具全套 **170 項通過**，未操作 Ubuntu 正式模型或服務。續跑使用上方 `--resume-backup` 同一段命令；安裝器會更新 root 保護的 worker，既有 image 快取重用，失敗的 root-owned 模型 partial 依既有規則重建。首次模型匯出與完整 SHA-256／隔離還原仍需數分鐘；首份成功後才啟用 23:30 timer。

### 2026-10-21 Ollama 0.40.6 索引／子模型 digest 修正

實機快照 `20261021T031358Z-efb05f44` 的錯誤為 `Ollama manifest inventory changed`，`restore_verified`／`recovery_error`／`operational_warning` 均未設定。這發生在模型快取驗證，先於 `capture()` 停止 backend。先前只補安全符號連結，未同時核對目前版本的索引格式，是前置調查不足；本機合成測試通過不能替代實機完整驗證。

已查核官方 v0.40.6：[paths.go](https://github.com/ollama/ollama/blob/v0.40.6/manifest/paths.go) 同時讀 legacy／v2，優先 v2 並正規化公開 registry；[model_list.go](https://github.com/ollama/ollama/blob/v0.40.6/server/model_list.go) 的 API 可回傳所選 child digest；[manifest.go](https://github.com/ollama/ollama/blob/v0.40.6/manifest/manifest.go) 定義 child reference／inline JSON 指紋。原驗證只收集路徑元件恰為 `manifests` 的檔案原始 SHA，因此會把合法 v2 或所選子模型誤判成清單變動。

新驗證逐一核對 blob 完整位元組 SHA-256、模型名稱與 registry／tag 對應、v2 優先序、child reference 或 inline canonical digest、config／layer 是否存在與大小；API 指向的 child 必須可由對應的 named manifest 到達且資料完整。不接受僅在其他 blob 出現的同一 digest；未安裝的其他平台 child 不會被當成已備份的本機模型。快取前後另讀取 API 比對 name／digest，將真正的清單變動分開報錯。保留所有越界／連結／檔案類型檢查，不以停用指紋驗證解決。

本輪完整部署工具 **185 項通過**，含真實檔案系統 v2 連結匯出後驗證、舊格式、新 list、inline 欄位順序、缺少所選 child／權重、錯誤名稱、壞 blob 與 API 前後變動。沒有重新建置或修改 Ubuntu 網站 image。Ubuntu 請沿用上方同一段 `--resume-backup` 指令；原始前段驗收報告仍為 `finalize-20261020T214321Z.json`。

為減少後續人工來回，worker 的私人 manifest／journal 現在記錄 `preflight`、`image-cache`、`model-cache`、`capture`、`isolated-restore`、`service-verification`；主批次在失敗時只讀本輪新 manifest 的選定錯誤／恢復旗標並顯示，拒絕拿舊備份錯誤當作本輪原因。不輸出設定、SQL、媒體清單或 pause marker 內的容器 ID。systemctl 啟動失敗改標示「systemd 備份服務」，不再誤導成 sudo 密碼問題。

網站影響：模型／image 快取讀取會消耗 CPU／磁碟；只有一致性擷取階段會短暫停止 backend，登入／偵測／Chat／Agent 請求或串流可能中斷。worker 在擷取 finally 與失敗清理中恢復 backend，另有 systemd ExecStopPost，但不能只由程式存在就宣稱恢復成功，仍須 health／容器狀態。備份不覆寫正式 DB、不更換網站 image；此次是在停機前失敗，公開 health／DB 已另外實測正常。首次成功還原前不啟用每日 timer。

## 備份、狀態與停用

```bash
systemctl list-timers sam-yolo-backup.timer --all
sudo journalctl -u sam-yolo-backup.service -n 30 --no-pager
sudo systemctl start sam-yolo-backup.service
```

第三行是手動要求一次備份，不需重裝。只有初次安裝成功才有每日排程；舊 `lab_backup_verify.py` 仍可人工使用，不能另放 cron 重複跑。

備份在 `/var/lib/sam-yolo-backups/`，root 擁有、sam 的 primary group 可讀、其他人無權讀。VS Code Remote 可直接開此路徑下載。時間戳目錄包含 SQL、所有檔案清單與 SHA-256、完整未提交來源快照、媒體／checkpoint／私人設定與 Caddy data；`images/` 與 `models/` 保存每個版本一次，manifest 指向對應快取及 SHA-256。版本快取不隨每日快照自動刪除；先核對仍被哪些快照引用，再由管理員另行清理。**下載時間戳目錄時，也要下載其引用的 image／model 快取，才是完整的離機交接**；舊 Mac 副本仍只代表原時間點，不會自動同步。

下載整個備份根目錄到 Mac 專案外私人資料夾後，可讀驗證（SNAPSHOT_NAME 換成批次實際列出的目錄名）：

```bash
python3 /Users/SAM/Desktop/Agents/Yolo_system/deploy/verify_managed_backup.py \
  /Users/SAM/Desktop/Yolo-system-managed-backups SNAPSHOT_NAME
```

這個檢查器另有 6 項測試；不解出設定、不印 SQL、不重新啟動 MySQL，會拒絕漏下載或不符 SHA-256 的 image／模型快取。

每份新備份均啟動無網路、CPU／RAM 受限的暫存 MySQL，匯入並重新完整 dump 比對；僅接受已查核的 MySQL #110825 冗餘字元集表示差異。檔案實際解到隔離目錄並核對 SHA-256，完成後清理有本輪歸屬標籤的暫存資源。Ollama 快取核對 manifest digest 與 blob SHA-256。Caddy 憑證狀態每日檢查，距到期少於 24 小時或 Ollama 失聯會讓維運服務報錯；可用的 DB 備份仍先完成。

root worker 不 import 專案／conda 套件；使用者可修改的檔案會在永久降為 sam 身分的子程序讀取。模型快取由 ollama 身分讀取。沒有加入 Docker group、設定 passwordless sudo 或放寬 AppArmor。更新 worker 要重新執行安裝器；編輯專案副本不會悄悄修改 root 排程內容。

需要停用每日排程時：

```bash
sudo systemctl disable --now sam-yolo-backup.timer
```

這不刪備份、不停止網站，也不停止正在執行的備份 service。服務中斷時，ExecStopPost 只依 root 保護的暫停記錄恢復同一個 backend ID，拒絕碰身分不同的容器。

## 工作中斷的受控處理

不是自動重跑，也不新增 job queue。先唯讀查看：

```bash
cd ~/apps/Yolo_system
sudo -v
python deploy/lab_recover.py
```

若確定這些是 backend 重啟留下的工作，在維護時段執行：

```bash
python deploy/lab_recover.py --apply
```

它與備份／部署共用鎖，只停止本專案 backend、等待最多 120 秒，將仍 pending／processing 的紀錄標為 failed、重算批次計數，保留 completed 結果及所有媒體；最後恢復 backend。使用者可重新上傳原檔。若目前真有正在執行的長工作，先等它完成，不以這個指令當作取消按鈕。

## 新主機復原與版本交接

1. 先在獨立目錄核對全部檔案與快取 SHA-256。禁止直接覆蓋現行 DB／volume；原始備份基準與現有服務都保留。
2. 從 `images/<id>.tar.gz` 解壓後 `docker image load` 載入，核對 image ID；從檔案快照的 `source/` 還原程式／模型／媒體，將 `private/` 設定放回私人目錄與 backend `.env`，權限 0600。新主機 UID／路徑、DB 密碼及公網 IP 必須重新配置，不能原封不動沿用原主機 bind 路徑。
3. 建立**新的** MySQL volume／容器，以備份記錄的字元集／collation 匯入 SQL。核對 Alembic revision，再連測試 backend；既有 `0013` SQL 已含 schema，不再 seed 覆寫帳號。後續 schema 升級另先備份、跑 `alembic upgrade head`，不自動 downgrade 正式 DB。
4. 以專用 ollama 帳號還原模型快取至該帳號的 `.ollama/models/`，檢查 `ollama list` 的名稱／digest。Caddy data 還原到新命名 volume；不同 IP 須調整設定並重新取得憑證，保持私鑰私有。
5. 更新 Compose 私人設定並只啟動新環境，跑 GPU smoke、API 回歸與資料雜湊比對，再安排切換。失敗回到原環境；不能直接拿舊 SQL 覆寫正在服務的資料庫。

本批在 Ubuntu 要驗證的是同主機**隔離 DB／檔案還原、backend 更新／回復與備份暫停／恢復、gateway 切換／回退**；不會未經協調重開共享主機，也不宣稱已演練全新硬體／網路的完整災難復原。CI 原始檔已隨 `84dcbca` push，Ubuntu 已同步該版本；GitHub Run workflow 尚無成功結果。容量以本輪小型測試為基準；1000 張、大檔壓測、50 路併發、httpOnly cookie 與空間推論另排。
