# 實驗室部署：目前操作與交接

2026-10-21 使用者回報 **Phase 6 lab finalization: PASS**。網站已部署在 [https://140.113.135.113](https://140.113.135.113)，完整功能／GPU／HTTPS／資料與 Chat-Agent SSE 已驗收；本輪備份續跑完成完整 SQL／檔案隔離還原、服務恢復，並啟用每天 **23:30 Asia/Taipei** 的備份 timer，保留最近 **7 份成功備份**。原始還原基準固定保留。

本輪成功報告：`/home/sam/.config/yolo-system/reports/finalize-20261021T033914Z.json`。新完整快照：`/var/lib/sam-yolo-backups/20261021T033914Z-65040ded`。前段功能驗收引用原始報告，本輪沒有重新執行全部 API／LLM 測試；詳細證據與排查歷程見 [Phase 6 收尾批次](lab-phase6-finalization.md)。

使用者先前已確認校外手機全流程及舊 Mac 備份副本正常；**新版快照連同 image／Ollama 快取的 Mac 副本仍待下載核對**。首個由 23:30 timer 自動觸發的備份結果尚待觀察。擷取資料時 backend 會短暫暫停，請避免在該時段開始重要工作。

## 服務位置與管理界線

| 服務 | 入口／資料 | 管理方式 |
|---|---|---|
| Caddy／新 React build | 公網 IP 的 TCP 443；憑證在 `sam-yolo-caddy-data` | Compose 的 gateway；不公開管理 API |
| FastAPI | 127.0.0.1:8000；`.env`／模型唯讀，static 持久掛載 | Compose 的 backend，單 worker |
| 舊 nginx／React dist | 127.0.0.1:8080，僅維護診斷 | Compose 的 web |
| MySQL | 127.0.0.1:13306；`sam-yolo-mysql-data` | 獨立 Docker 容器，restart=unless-stopped；未納管 Compose |
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

上述命令不停止 MySQL／Ollama，也不刪資料。MySQL 的 restart policy 已由成功收尾批次核對為 unless-stopped；整機開機仍未演練，獨立主機還原步驟見收尾文件，不使用 `down -v`／prune 或未核對名稱的 rm。

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

## 每日備份的日常檢查

```bash
systemctl list-timers sam-yolo-backup.timer --all
sudo journalctl -u sam-yolo-backup.service -n 30 --no-pager
```

timer 已啟用；備份 service 是 oneshot，完成後顯示 inactive 不代表失敗，應讀取最近 journal／快照 manifest 的 success 與 restore_verified。失敗快照不計入成功版本輪替。需要手動備份時，在維護時段執行 `sudo systemctl start sam-yolo-backup.service`；這會擷取新資料並短暫停止 backend，無須重跑完整部署／回歸批次。

## 備份與升級邊界

現有 [備份／隔離還原工具](lab-backup.md) 可在維護時段人工執行。為確保 SQL／媒體一致，擷取期間會短暫停止本專案 backend；恢復服務後再用無網路 MySQL 隔離還原。模型快取以 Ollama 身分匯出，安全內部連結會存成一般內容，避免還原依賴舊路徑；越界或壞連結不接受。不要直接放入需要互動 sudo 密碼的無人排程；新收尾批次另安裝 root 保護的 stdlib worker，首份驗證成功後才啟用 23:30 timer。

舊 Mac 副本與最初還原基準早於 HTTPS／本次維運收尾，不包含後續新增資料；固定保留，不以它宣稱目前版本已有離機副本。本次新完整快照已驗證來源、SQL、媒體、模型、設定、憑證與 image／Ollama 快取，接著須下載新快照與兩個快取目錄；具體結構與驗證指令見收尾文件。

升級前先備份；記錄目前 image ID／來源版本與 Linux lock，於隔離候選 image 完成必要測試／GPU 驗證，再受控切換 backend 或 gateway，確認啟動／DB／API 與舊資料。當前收尾包含上傳解碼及影片追蹤依賴修正，候選 backend 必須先通過真實影片測試；僅在沒有進行中偵測／批次時切換，失敗回復原設定／image，不在運行容器內臨時 pip 安裝。失敗時只回復本專案 image／Compose 參數；不可把正式 DB 直接還原覆蓋成舊版本。涉及 migration 的回退須另做相容驗證。不要重跑初期 Compose 納管或舊更新包，它們針對舊基準，並非日常重啟指令。

## 已完成的收尾與後續交接

- 完整回歸、GPU、HTTPS、資料保存、備份／隔離還原、服務恢復與每日 23:30 排程已通過；版本／image 與模型 digest 以成功私人報告／manifest 為準，來源與操作說明已隨 Git 交付。
- 仍待新版完整備份的 Mac 副本驗證、首次由 timer 自動執行的觀察；最新清單統一見 [roadmap](roadmap.md)，不把舊 Mac 副本當成新版本交接。
- 手動 GitHub Actions workflow 已交付，尚無 GitHub run 成功證據；不因 Ubuntu 通過就聲稱 CI 已跑過。
- 共享主機重開機、新主機完整災難復原、實際憑證續期週期與大規模併發尚未演練；單 worker 與共享 GPU 邊界保留。

httpOnly cookie、1000 張批次與空間關係推論維持另行安排。Caddy 的實際自動續期週期尚未觀察；shared host 不做未協調的整機重開機。
