# Phase 6.2 — Compose 管理（第一步：Backend／nginx）

> 專題／階段紀錄：內含初次建置、修復與當時待辦。現行日常操作以 [維運手冊](lab-operations.md) 為準，最新狀態以 [roadmap](roadmap.md) 為準；不要依舊待辦重跑納管或初次部署包。

## 已確認狀態

2026-10-20，使用者回報正式 `sam-yolo-backend` 已在 8000 healthy，直接及經 nginx 8080 的 health 都 DB connected；瀏覽器重新登入後，偵測 ID 1 的原圖／結果圖、既有 Chat／Agent 對話及串流皆正常。這已驗證從暫用 API 容器更換成正式後端容器後，DB 與媒體仍可讀回。

Ubuntu Docker Compose 為 **v2.29.2**。使用者提供的現有 image：

| 服務 | 本機 image ID | Registry digest |
|---|---|---|
| backend | `2fdf4814f7bef3919489586754819b7879059f8108dec8eb5a8ff09c8030a945` | 尚未推送 registry；Compose 直接使用已驗證的本機 ID |
| nginx | `0d831f5435ede3eeaba5768270c9e6f542d58306f69bb61f148e5c2374b57c56` | `nginx@sha256:970364228b1e4f932abc22d321932816782cca8a20b85a77552a7cfe9acfb3b5` |
| MySQL | `4aae07a2c195abb9b3e92449443b39b51212f555a35ff8f93da0e82683f45de8` | `mysql@sha256:0f51e63e537a1f176423fa03ef559aabe6fa4372a53160a44bc7e75da7d15364` |

這次只把 backend／nginx 寫入 Compose。MySQL 仍使用現有 `sam-yolo-mysql` 及 `sam-yolo-mysql-data`；Ollama 仍為主機 systemd service。MySQL 的 Compose 納管在備份與還原驗證後進行，本檔沒有 DB service、DB 密碼或 volume 宣告；不會自動建立另一個 MySQL。

## 交付與相容性

- [compose.lab.yaml](../deploy/compose.lab.yaml)：固定 project `sam-yolo`、既有 container names、Linux host network、GPU runtime、目前 CPU／RAM 上限與有限日誌輪替。backend 使用原 image 的 CMD 與 DB-aware healthcheck；web 等候 backend healthy。僅提供現有 React dist，frontend build image 仍待完成。
- [configure_lab_compose.py](../deploy/configure_lab_compose.py)：在 Ubuntu 以 sam 帳號執行，建立 mode 0600 的 `~/.config/yolo-system/compose.env`，只含 repo／私人設定路徑與目前 UID／GID。它只檢查設定檔的存在與權限，不讀帳密、不呼叫 Docker、不覆蓋既有 compose.env。
- GPU 使用 `deploy.resources.reservations.devices`（driver nvidia／count all／capabilities gpu），避開要求 Compose 2.30+ 的 service-level `gpus` 屬性。沿用既有 `runtime: nvidia`，不安裝 toolkit 或更換 driver。這不是 GPU 記憶體或時間配額。
- bind mounts 設定 `create_host_path: false`；路徑不對時須修正，不自動建立空目錄來掩蓋漏掛設定。`.env`、checkpoint、nginx 設定及 dist 唯讀；static 讀寫。
- image `pull_policy: never`；這次沿用主機已存在的 artifact，不下載不同版本或重建。之後移到新主機需明確交付 image，只有 Git／Compose 不足以重建 Linux 環境。

## 1. 只驗證設定，不切換服務

用 VS Code 將兩個新檔複製到 Ubuntu 專案的 `deploy/`，然後在 Ubuntu 執行：

```bash
conda activate yolo-backend
cd ~/apps/Yolo_system
python deploy/configure_lab_compose.py
```

不用 sudo 執行 Python；否則會使用錯誤的家目錄與 UID。腳本要求既有私人設定目錄不允許群組／其他人存取，backend/.env 同樣必須為自己擁有的私人檔案。若失敗或 compose.env 已存在，回報訊息，不反覆覆蓋設定。

建立成功後，用明確 env-file 載入 sam 的路徑／UID，避免 sudo 的 HOME 改變掛載：

```bash
sudo docker compose \
  --env-file "$HOME/.config/yolo-system/compose.env" \
  -f deploy/compose.lab.yaml config --quiet
```

成功不輸出文字，接著列服務：

```bash
sudo docker compose \
  --env-file "$HOME/.config/yolo-system/compose.env" \
  -f deploy/compose.lab.yaml config --services
```

預期只有 `backend`、`web`（順序不限）。這些命令只解析設定，不會接管或重啟現有容器。使用者已回報 Ubuntu v2.29.2 的 config --quiet 成功、config --services 列出 backend／web，設定驗證通過。接續使用下方批次腳本納管；手動建立的同名容器不會因名字一致就被 Compose 接管。

## 2. 加速執行：一次完成納管與驗證（目前建議）

使用者要求後續以批次方式執行，只有資料保護、必要登入或關鍵部署條件才停下。將 [lab_compose_apply.py](../deploy/lab_compose_apply.py) 複製到 Ubuntu deploy/，網站暫停操作並確認沒有其他人正在使用後，一次執行：

```bash
conda activate yolo-backend
cd ~/apps/Yolo_system
sudo -v
python deploy/lab_compose_apply.py
```

sudo -v 先取得 Docker 使用權限，Python 本身保持 sam 身分。腳本只呼叫 sudo -n docker，不在子程序要求或保存 sudo 密碼；再互動輸入與先前相同的專案管理員帳密，登入失敗會在停止容器之前結束。請勿以 sudo python 執行。

批次合併以下檢查與操作：

- 驗證實際 Compose 設定、既有 image／掛載／UID／restart policy、MySQL 原容器與 volume、兩個 health。用管理員 scope 確認沒有 pending／processing 的偵測；LLM 使用中的請求仍須由操作者先暫停。
- 切換前擷取最近最多 3 筆已完成影像與 5 組本帳號對話的指紋；要求至少一筆影像及兩組對話，避免錯用另一個空帳號。原圖／結果圖內容、Bearer／signed URL／未登入拒絕都會驗證，不把 token／URL／原始對話寫入報告。
- 依序納管 backend、nginx。舊容器改為帶 UTC 時間與 PID 的唯一備用名稱並保持停止；每個服務 health／原有資料讀回自動通過後才繼續。若已是同一 Compose project 的服務，保留不重建。
- 檢查 Compose project/service 標籤、MySQL ID／掛載維持一致、首頁／SPA／API 與媒體錯誤分流、production docs 關閉，以及新 Compose 容器內 CUDA 實際矩陣運算。
- 經 nginx 執行一次真實 Ollama Chat SSE、一次 Agent 歷史工具 SSE，檢查 error／chunk／done 與對話保存。會新增兩組測試對話。報告記錄首片段秒數、總耗時與片段數，這是觀測數值，不據此宣稱所有負載下都沒有 buffering。
- 合併唯讀 IPv4 介面、可用磁碟空間、Ollama active／enabled 盤點，以供下一批 HTTPS／備份工作使用。

一般例外或 Ctrl+C 會嘗試自動回復本批更換的服務：只有 project/service/image 身分吻合的新容器才會被停止與改名保存，恢復原容器後再驗證 health／原有資料。沒有刪容器、volume、image 或媒體的指令，也不重啟 MySQL、Ollama、Docker daemon 或共享主機。無法自動回復時會列出失敗服務；Docker 無法連線或腳本被強制終止時，仍可能需人工處理，不宣稱一定能自動回復。

報告為 `~/.config/yolo-system/reports/compose-<UTC時間>-<PID>.json`，mode 0600，含既有資料指紋、原容器 ID、實際備用名稱與通過／失敗狀態。批次備用名稱與下方舊手動範例不同，人工處理時使用報告中的名稱。檔案鎖避免重複啟動同一批次。成功時最後顯示：

```text
Compose adoption / persistence / routing / GPU / Chat-Agent SSE: PASS
```

修正版批次腳本已在 Mac 完成 20 項測試，其中 4 項使用真實 Docker CLI 連接暫存 Unix socket 的假 API，不連真實 Docker daemon，驗證空／缺少 Labels、缺少 Health、正常 Compose metadata；其餘涵蓋安全錯誤分類與中途 stop／rename／partial create／GPU／SSE 失敗回復、原容器保留、已納管不重建、拒絕操作外來容器、拒絕未驗證映像、HTTP 200 但 SSE error／未保存答案、signed URL 圖片不一致。

**Ubuntu 已通過（2026-10-20）**：使用者提供完整 PASS，報告 `~/.config/yolo-system/reports/compose-20261020T055006Z-2532143.json`。backend／web 納管、各次 health／原有資料內容一致、SPA／API／媒體錯誤分流與 Compose 容器內 CUDA kernel 均通過。Chat 經 nginx SSE 首片段 1.05 秒、25 片段；Agent 首片段 5.42 秒、12 片段，兩者對話均保存。這些是當次觀測值，不是併發或延遲保證。

盤點結果：可用磁碟 486.5 GiB；介面 IPv4 包含 `140.113.135.113`、`172.18.65.223`、`172.17.0.1`；Ollama active／enabled。這不證明公網 port 可達或實體重開機已驗證。先前 inspect 失敗與登入密碼誤輸的兩次批次均未切換服務；最後一次正確登入後整批通過，不需重建 DB 或重設帳號。

### 第一次 inspect 失敗的修正

使用者只收到舊版泛用訊息 `Docker 指令失敗（inspect）`，不足以判定是樣板、容器缺少、sudo 或 daemon 問題，不因此重啟 Docker／主機或重建 DB。修正版改用簡單欄位選取，Labels 用可處理缺少 key 的頂層 index，project/service 與 optional Health 在 Python 正規化；立即丟棄原始 labels／health log，不選取 Config.Env，不輸出帳密。

Docker 失敗會分類為樣板、sudo、權限、daemon 或容器不存在，並顯示失敗階段；optional inspect 只有確定容器不存在才回 None，不再把權限／daemon 故障視為名稱可用。報告新增 changed_services；若本批未進入容器切換，終端機明確印「本次未停止或更換任何容器」。原始 inspect 根因未取得完整 stderr，不能追認為特定原因；修正版的實際 Ubuntu 整批結果已通過。

只需同步新的 `deploy/lab_compose_apply.py` 到 Ubuntu，執行相同 sudo -v／Python 批次。不要重跑設定產生器或重建映像；腳本會核對現況，已納管的服務會保留不重建。

## 3. 舊手動切換與回復參考



下方保留人工排查時的分服務流程；正常操作改用上述批次腳本，不再每個步驟停下等待回覆。MySQL、Ollama 與其他使用者的容器持續運行。保留原容器供回復，不刪 image／volume／媒體，不執行整組 down 或 prune。

### Backend 先切換

1. 確認網站無進行中的偵測、批次或對話，備用名稱 `sam-yolo-backend-before-compose-20261020` 尚未使用；若已存在先查明。
2. 停止原 backend，等待停止成功後改名保留。改名不改變掛載；手動停止的 unless-stopped 容器保持停止，不能與新 backend 並行占用 8000。

```bash
sudo docker stop --time 120 sam-yolo-backend
sudo docker rename sam-yolo-backend sam-yolo-backend-before-compose-20261020
```

3. 只啟動 Compose backend：

```bash
sudo docker compose \
  --env-file "$HOME/.config/yolo-system/compose.env" \
  -f deploy/compose.lab.yaml up -d --no-deps --no-build --pull never backend
```

4. 等 startup complete／healthy，檢查 8000 與既有 nginx 8080 的 DB health、原圖／結果圖與對話讀回。原 nginx 尚未替換，這一步只驗證 backend 管理方式改變。亦檢查容器的 Compose project/service 標籤，不以名字相同當成納管成功。

### nginx 再切換

確認 backend 通過後，檢查 `sam-yolo-web-before-compose-20261020` 未使用；停止原 nginx，改名保留，再只啟動 Compose web：

```bash
sudo docker stop --time 30 sam-yolo-web
sudo docker rename sam-yolo-web sam-yolo-web-before-compose-20261020
sudo docker compose \
  --env-file "$HOME/.config/yolo-system/compose.env" \
  -f deploy/compose.lab.yaml up -d --no-deps --no-build --pull never web
```

此時 8080 入口短暫中斷。完成後重驗首頁／SPA 深連結／API 與媒體錯誤分流，以及登入、既有偵測與對話、Chat／Agent 串流；確認 MySQL 原容器與原 volume 未變。

### 單服務回復

如任一新服務啟動失敗，先保存該容器 log，停止後才移除**該 Compose 服務容器**，以釋放原名。以 backend 為例：

```bash
sudo docker compose \
  --env-file "$HOME/.config/yolo-system/compose.env" \
  -f deploy/compose.lab.yaml stop backend
sudo docker compose \
  --env-file "$HOME/.config/yolo-system/compose.env" \
  -f deploy/compose.lab.yaml rm -f backend
sudo docker rename sam-yolo-backend-before-compose-20261020 sam-yolo-backend
sudo docker start sam-yolo-backend
```

先確認每步成功再執行下一步；不加 `-v`，不以 `docker rm -f` 強制中斷正在工作的容器。web 回復使用對應的 `web` 服務與原 nginx 備用名稱。backend 回復後暫停後續 Compose 操作，因為恢復的舊容器不屬於 Compose。這是容器管理切換的回復，不是資料庫時間點還原；共用 DB／媒體中的新寫入仍保留。

## 驗證界線與下一步

Mac 已以本機 Compose 5.1.4、不連 Docker daemon，完成生成設定、mode 0600／拒絕覆蓋、缺少參數拒絕，以及實際 Compose config 解析與 GPU／UID／掛載／固定 image 的檢查。未在 Mac 執行容器；Ubuntu 2.29.2 的 config、實際服務納管與整批驗證已收到通過結果。

Compose backend／nginx 納管階段已通過。下一步執行 [備份與隔離還原批次](lab-backup.md)。仍待 frontend build image、MySQL 備份／隔離還原與納管、Docker 開機啟動及受控復原驗證、校外 HTTPS、關閉自行註冊、Vite 工具鏈與完整 Phase 6 驗收；Ollama enabled 已確認，尚未進行實體重開機。

## 官方參考

- [Compose GPU device reservations](https://docs.docker.com/compose/how-tos/gpu-support/)
- [Compose services、GPU 與 bind mount 屬性](https://docs.docker.com/reference/compose-file/services/)
- [明確 env-file 與變數展開](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)
