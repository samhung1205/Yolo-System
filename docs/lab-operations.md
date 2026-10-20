# 實驗室部署：目前操作與交接

2026-10-20 公開入口核心驗收通過：[https://140.113.135.113](https://140.113.135.113)。報告 `public-verify-20261020T094649Z-2578684/report.json`：原有圖片／對話 SHA-256 一致、Bearer／signed URL／未登入保護、Chat SSE／保存（首片段 1.05 秒）及 Agent 工具／SSE／保存（5.13 秒）皆通過。未重建／重啟服務。使用者另已確認手機行動網路瀏覽器全流程正常；Mac 備份副本亦已實際核對通過。2026-10-21 維運／完整回歸工具已完成本機實作與測試，Ubuntu 首次執行停在容器回歸、尚未進入服務變更；修正與續跑見 [Phase 6 收尾批次](lab-phase6-finalization.md)，Phase 6 持續進行。

## 服務位置與管理界線

| 服務 | 入口／資料 | 管理方式 |
|---|---|---|
| Caddy／新 React build | 公網 IP 的 TCP 443；憑證在 `sam-yolo-caddy-data` | Compose 的 gateway；不公開管理 API |
| FastAPI | 127.0.0.1:8000；`.env`／模型唯讀，static 持久掛載 | Compose 的 backend，單 worker |
| 舊 nginx／React dist | 127.0.0.1:8080，僅維護診斷 | Compose 的 web |
| MySQL | 127.0.0.1:13306；`sam-yolo-mysql-data` | 原 Docker 容器，尚未納管 Compose |
| Ollama | 127.0.0.1:11434；llama3.2／gemma4 | 原生 systemd；active／enabled 已查核，未做主機重開機演練 |

Python 程式保留 sam 身分，需要 Docker 時先 `sudo -v`。不重啟共享 Docker daemon、GPU 驅動、主機或其他人的容器。

Docker Snap 的 gateway 設定使用私人 `YOLO_GATEWAY_NNP=false` 相容例外；AppArmor enforce、seccomp、唯讀與唯一 NET_BIND_SERVICE 的 A/B 已通過。一般 Compose 預設仍為 NNP=true。不要直接刪除這個參數或改成 privileged／unconfined；背景見 [HTTPS 部署](lab-public-https.md)。

## 狀態與啟停

目前正式管理前綴始終使用兩個 Compose 檔及私人 image 參數：

```bash
cd ~/apps/Yolo_system
sudo docker compose --env-file "$HOME/.config/yolo-system/compose.env" \
  -f deploy/compose.lab.yaml -f deploy/compose.public.yaml ps
curl -fsS --max-time 15 https://140.113.135.113/api/health
```

health 除 HTTP 200，還要核對 JSON `database=connected`。

若本專案容器已停止，依既存 image／資料掛載啟動：

```bash
sudo docker compose --env-file "$HOME/.config/yolo-system/compose.env" \
  -f deploy/compose.lab.yaml -f deploy/compose.public.yaml \
  up -d --no-build --pull never backend web gateway
```

只有確認沒有進行中的偵測／批次／對話並進入維護時段後，才停止本專案網站：

```bash
sudo docker compose --env-file "$HOME/.config/yolo-system/compose.env" \
  -f deploy/compose.lab.yaml -f deploy/compose.public.yaml \
  stop -t 120 gateway backend
```

上述命令不停止 MySQL／Ollama，也不刪資料。MySQL 的 restart policy 將由收尾批次核對／補齊；整機開機仍未演練，獨立主機還原步驟見收尾文件，不使用 `down -v`／prune 或未核對名稱的 rm。

## 已完成的校外驗收與 Mac 副本

2026-10-20 使用者已確認以下兩項完成且正常；下載後亦已執行本機完整性核對。以下保留操作供日後參考：

1. 手機關閉 Wi-Fi，以行動網路開啟網站，確認登入、上傳一張測試圖片、查看結果與歷史、Chat 及 Agent；特別注意圖片顯示與逐段回覆。若失敗，記錄操作與錯誤，不把密碼／token 貼回。
2. VS Code Remote 開啟 `/home/sam/.local/share/yolo-system/backups/`，分別 Download 以下兩個完整目錄到 Mac 的 `/Users/SAM/Desktop/Yolo-system-backups/`：
   - `20261020T075232Z-2550504`：原始 SQL／檔案壓縮產物與 manifest。
   - `20261020T081258Z-2556729`：成功隔離還原的 manifest／報告。

Mac 目的地已建立為本人專用 0700 目錄，不放在 Git 專案內；備份含私人設定。不要只下載成功報告而漏掉原始產物。下載後的 Mac 核對指令：

```bash
cd /Users/SAM/Desktop/Agents/Yolo_system
python3 deploy/verify_downloaded_backup.py \
  /Users/SAM/Desktop/Yolo-system-backups/20261020T075232Z-2550504 \
  /Users/SAM/Desktop/Yolo-system-backups/20261020T081258Z-2556729
```

檢查器只讀／串流核對壓縮產物、解壓 SQL 與 tar 內每一檔案 SHA-256，以及成功報告所指向的基準；不解出私人設定、不印內容、不連線伺服器、不重新執行 MySQL 還原。本機六項工具測試通過；實際下載副本亦 PASS：52 個檔案、76,200,654 bytes，壓縮產物／完整 SQL／檔案 SHA-256 與成功還原報告一致。這是下載完整性核對，沒有在 Mac 再執行 MySQL 還原。

已從此驗證通過的備份取回 `deploy/backend-linux.lock` 至 Mac 專案，118 個固定版本及關鍵 GPU／Agent 版本驗證通過；SHA-256 為 `76a616b975843fe2327e59ce2d11e418b4a76c9c9aa77d749ddb1bbb5a02cc77`。它記錄已驗證的 Ubuntu 建置環境，未鎖定 wheel／OS 產物雜湊，也不代表之後的環境變更已納入。

## 備份與升級邊界

現有 [備份／隔離還原工具](lab-backup.md) 可在維護時段人工執行。為確保 SQL／媒體一致，擷取期間會短暫停止本專案 backend；恢復服務後再用無網路 MySQL 隔離還原。不要直接放入需要互動 sudo 密碼的無人排程；新收尾批次另安裝 root 保護的 stdlib worker，首份驗證成功後才啟用 23:30 timer。

原始已驗證備份早於 HTTPS 更新，是該時間點的資料與設定；它不包含後續新增對話、Caddy 憑證 volume、Docker image 本體或完整 Git 原始碼。下一批維運需要建立目前部署的可重建交接資訊與新備份，再設計每日排程／容量與保留輪替。原始成功還原基準先固定保留，不能先刪掉。

升級前先備份；記錄目前 image ID／來源版本與 Linux lock，於暫用服務完成 schema／GPU／API 驗證，再切換 backend 或 gateway，並讀回舊資料。失敗時只回復本專案 image／Compose 參數；不可把正式 DB 直接還原覆蓋成舊版本。涉及 migration 的回退須另做相容驗證。不要重跑初期 Compose 納管或舊更新包，它們針對舊基準，並非日常重啟指令。

## Phase 6 尚未完成的部分

- [Phase 6 收尾批次](lab-phase6-finalization.md) 已補齊上述實作：每日 23:30 備份、7 份成功版本輪替、空間／失敗紀錄、來源／憑證／image／Ollama 交接、隔離還原與服務恢復；Ubuntu 首次容器回歸失敗，尚未進入安裝；不能把準備完成記成已啟用。
- 來源版本交付；Ubuntu Linux lock 已從驗證備份同步回 Mac，程式與文件已隨 `84dcbca` commit／push，Ubuntu 已同步，health／DB 正常。
- Mac 後端全套 182 通過（29.14 秒），假模型 SSE 測試隔離本機 Ollama 清單；跨帳號／頭像／批次／影片／Desktop 的真實 CPU／暫存 SQLite／測試 HTTPS 回歸已通過，Ubuntu GPU／正式 HTTPS 版本由同一批次實測。手動 CI workflow 已建立，已 push／尚未取得 GitHub run 結果。
- 同時推論量／峰值資源、背景影片與批次重啟時的受控復原。單 worker 保留，未承諾 50 路並行。

httpOnly cookie、1000 張批次與空間關係推論維持另行安排。Caddy 的實際自動續期週期尚未觀察；shared host 不做未協調的整機重開機。
