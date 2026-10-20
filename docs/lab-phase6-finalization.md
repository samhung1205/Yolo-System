# Phase 6 收尾批次

2026-10-21：Ubuntu 已同步 `84dcbca`，公開 health／DB 正常；首次收尾停在 `container-regression`，尚未切換 gateway 或安裝每日排程。修正版已移除主機 `/tmp` 掛載並補上子程序錯誤紀錄，**仍待 Ubuntu 重驗，不能先標記 Phase 6 全部完成**。既有網站、校外手機驗收與第一份備份維持先前通過結果。

## 已完成的本機驗證

- 後端全套 182 passed（29.14 秒），新增中斷工作盤點／套用／批次計數測試。
- 部署工具涵蓋備份失敗恢復、輪替範圍、root／使用者權限界線、暫存還原歸屬、來源更新與 gateway 回退。最終全套 130 項通過（含真實本機假 Docker Unix API）。
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

1. 正式 backend image 的完整 pytest、合成圖片、自訂模型 CUDA／NMS；測試圖片直接建立在測試容器的 16 MiB tmpfs，容器移除即丟棄，不掛主機 `/tmp`、正式 `.env` 或私人媒體、不連正式 DB。測試／腳本／checkpoint 維持唯讀掛載，沿用原 UID／GPU／CPU／RAM 限制。
2. 建置新的 Vite 8／Caddy image，先驗證 Caddy 設定，只切換 gateway；保留 Snap NNP 相容旗標與原憑證 volume。啟動失敗自動回復原 gateway 設定；不重啟共享 Docker／MySQL／Ollama。
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

本批實際演練的是同主機**隔離 DB／檔案還原、backend 暫停／恢復、gateway 切換／回退**；不會未經協調重開共享主機，也不宣稱已演練全新硬體／網路的完整災難復原。CI 原始檔已隨 `84dcbca` push，Ubuntu 已同步該版本；GitHub Run workflow 尚無成功結果。容量以本輪小型測試為基準；1000 張、大檔壓測、50 路併發、httpOnly cookie 與空間推論另排。
