# Phase 6.2 — 實驗室後端 GPU 容器

> 專題／階段紀錄：內含初次建置、修復與當時待辦。現行日常操作以 [維運手冊](lab-operations.md) 為準，最新狀態以 [roadmap](roadmap.md) 為準；不要依舊待辦重跑納管或初次部署包。

本文件接續 [同網址驗證](lab-same-origin.md)。**Ubuntu 修正版 image 已建置成功，未額外傳入身分／cache 環境變數的容器 GPU smoke 通過，兩個既有測試檔共 12 項通過（1.10 秒）。loopback 18000 的 production／DB、登入／YOLO／受保護媒體／Ollama Chat／Agent 與對話讀回均已收到通過回報；正式 8000 已由新容器接手且 healthy，直接／經 nginx 的 health 均 DB connected；使用者已確認新容器可讀回既有圖片／對話且串流正常。Compose 納管與完整 Phase 6 驗收仍待完成。** 現在 backend 為背景容器，nginx／MySQL／Ollama 沿用既有服務。

## 已確認與交付檔案

使用者提供的 Ubuntu 輸出顯示 `nvidia` runtime 位於 `/snap/docker/3613/usr/bin/nvidia-container-runtime`，屬目前 Docker 安裝已有的 runtime；`command -v nvidia-ctk` 沒輸出不代表 Docker 沒有 GPU 支援。執行 `sudo docker run --rm --runtime=nvidia --gpus all ubuntu:22.04 nvidia-smi` 成功看到 RTX 4070 Ti 12 GiB、driver 550.90.07。這只證明裝置可見，不等於 PyTorch CUDA kernel 或自訂 checkpoint 已在容器通過。

本階段檔案在 repo 的 `deploy/`：

- `export_backend_lock.py`：在已驗證 Ubuntu 環境建立 `backend-linux.lock`；確認 Python 3.11、Linux x86_64、已驗證 PyTorch／Ultralytics／LangChain 版本與 `pip check`。產出僅含 `package==version`。conda 內嵌的本機建置來源，只有當套件名稱／版本一致且 conda 安裝紀錄擁有對應 `direct_url.json` 時，才轉為相同版本；來源不明的本機套件、URL／editable 仍拒絕，錯誤僅顯示合法套件名稱與類型，不印路徑／網址。不讀 `.env`，已存在的快照不覆蓋。這是依版本重建，不代表 conda 與 PyPI artifact 完全相同。
- `backend.Dockerfile`：Python 3.11.17 slim bookworm、CUDA 12.6 的 PyTorch wheel，保持 `/opt/yolo/backend` 與三個根目錄相容模組的相對位置；預設非 root 執行。測試 image 另含兩個既有 registry／compatibility 測試。
- `backend.Dockerfile.dockerignore`：Dockerfile 專用 build allowlist。必須與 Dockerfile 同步，使用 repo 根目錄作 context；`.env`、YOLO checkpoint、私人媒體、Git 與 Desktop legacy 不會送入這個 build context。
- `api_smoke.py`：在 Ubuntu 主機互動輸入專案帳密，測試 loopback API 的登入、免費 Ollama 預設、YOLO 模型指紋、偵測存取、Bearer／signed URL 媒體與 Chat／Agent 工具及對話讀回。會留下 1 筆白圖偵測與 2 組對話，供後續重建持久性驗證；不印 token／簽章 URL，不讀 `.env`。
- `backend_smoke.py`：`--health` 需要 API 與 DB connected；`--gpu` 實際跑 CUDA 矩陣、torchvision NMS 及 ASFF／DySample／EfficientViM 模型推論，保存並重新讀取暫存標註 PNG。不連 DB、不修改既有媒體；白圖零物件是正常的，不是準確率評估。

使用者已回報後端 image 建置成功（2026-10-20），tag 為 `sam-yolo-backend:lab-20261020`，image ID 為 `sha256:bdb3d6cba3e3294d47111927cd3549cd7f5b3806c4da4429b791733818eb3654`。快照 COPY、套件安裝／`pip check` 與自訂模組來源 COPY 均通過；快照的實際 SHA／套件數尚待保存。此為初版 image ID；後續以執行時環境變數修正使用者名稱查詢後，CUDA／checkpoint 已通過，仍須重建保存修正版 image ID 並驗證 API。

目前已驗證修正版：`sha256:2fdf4814f7bef3919489586754819b7879059f8108dec8eb5a8ff09c8030a945`。使用者已回報內建設定的 GPU smoke PASS 與 `12 passed in 1.10s`；接下來的 API preflight／切換應使用這個 image（tag 仍為 `sam-yolo-backend:lab-20261020`）。下方初版錯誤保留作為排查說明，不代表仍需重新匯出或重跑已通過的步驟。

## 1. Ubuntu 建立版本快照

若新檔案尚未推送 GitHub，使用 VS Code Remote Explorer 把上述四個檔案從 Mac 的 `deploy/` 拖到 Ubuntu 的同名資料夾。不要用 Mac 的套件環境產生 Linux 快照。

```bash
conda activate yolo-backend
cd ~/apps/Yolo_system
python deploy/export_backend_lock.py
```

成功會顯示套件數量與檔案 SHA-256。若遇到版本差異／本機來源，先查核環境，不跳過驗證或直接輸出含 URL 的 freeze。`backend-linux.lock` 是部署 artifact，之後須同步回版本控制；它不含密碼，但僅為 Python 版本快照，不是 wheel hash lock，也沒有鎖住 apt repository 的所有套件。保留建成 image 的 ID／digest，才有明確的 rollback artifact。

### 匯出本機來源時的排查

第一次 Ubuntu 匯出被來源格式檢查擋下，未產生 `backend-linux.lock`；接著的 Docker `COPY ... not found` 是這個失敗的連帶結果，不是 GPU runtime 測試失敗。更新 `export_backend_lock.py` 後，已知 conda 安裝紀錄所屬的本機來源可轉為版本快照；若仍無法對應，錯誤會顯示套件名稱與來源類型，回報這一行即可，不貼原始 freeze。

在目前尚無快照的狀態，可使用成功條件串接，確保匯出失敗時不建置：

```bash
conda activate yolo-backend
cd ~/apps/Yolo_system
if python deploy/export_backend_lock.py; then
  sudo docker build --platform linux/amd64 \
    -f deploy/backend.Dockerfile \
    -t sam-yolo-backend:lab-20261020 .
fi
```

修正已在 Mac 以暫存 conda metadata 測試：可接受 conda 擁有且版本匹配的來源；拒絕缺少檔案歸屬、版本不符、遠端／來源不明 URL、editable 與重複套件；錯誤與輸出不包含測試來源路徑或憑證。Ubuntu 後續已回報 image build 成功；實際正規化套件名與快照 SHA 尚待保存。後續仍以容器 CUDA／checkpoint 測試確認依版本重建的套件可用。

## 2. 建置測試映像

必須在 repo 根目錄執行，最後的 `.` 是 build context：

```bash
sudo docker build --platform linux/amd64 \
  -f deploy/backend.Dockerfile \
  -t sam-yolo-backend:lab-20261020 .
```

第一次會下載 Python、OpenCV／FFmpeg 系統依賴與 PyTorch CUDA wheels，需數 GB 磁碟與較長下載時間。build 不會啟動或替換目前的 backend。`pip check` 是建置必要步驟；若無可用 wheel 或解依賴失敗，保留 log 查核，不直接放寬已驗證版本。此 image 不內建 GPU driver，沿用主機既有 driver。

### 數字 UID 缺少使用者名稱（第一次容器測試）

使用者首次 GPU smoke 在匯入 torchvision 時失敗：PyTorch 2.11 經 `getpass.getuser()` 查詢 UID 1007，而 image `/etc/passwd` 沒有此主機 UID。尚未進到 CUDA 矩陣與模型推論，不能判定這些測試已通過。Mac Dockerfile 已在套件安裝層之後補 `USER`／`LOGNAME` 與明確的 writable cache 設定；保留 `--user` 的主機 UID／GID。環境變數中的名稱只供套件查詢，不改變程序真正的 Unix 身分。

目前 Ubuntu 的初版 image（`bdb3d6cba3e3...`）仍可先以 `docker run -e ...` 重測。執行時修正已通過；下方命令改為驗證重建後 image 的內建設定，保存新的 image ID，API 切換必須使用修正版。不要重新匯出已存在的版本快照。

Mac 已以缺少 passwd entry 的 mock 重現查詢失敗，確認提供 `USER`／`LOGNAME` 後不再呼叫該查詢。Ubuntu 後續以執行時設定 `USER`／`LOGNAME` 及 cache 路徑重測通過：PyTorch 2.11.0+cu126、torchvision 0.26.0+cu126、CUDA runtime 12.6，矩陣／NMS PASS，ASFF／DySample／EfficientViM 皆在 cuda:0 完成推論與 PNG 保存／重新讀取，總結為 `Container custom YOLO GPU smoke test: PASS`。

### Ultralytics 設定目錄與修正版 image

上述通過的測試仍出現設定目錄警告：`YOLO_CONFIG_DIR=/tmp/ultralytics` 的父目錄不存在，Ultralytics 改用 `/tmp/Ultralytics`。這沒有讓推論失敗。Dockerfile 已在套件安裝層之後建立 `/tmp/ultralytics`，以 1777 權限允許指定數字 UID 在此建立自己的設定子目錄；只修改 image 的容器暫存目錄，不修改主機目錄權限。

將 Mac 更新後的 `deploy/backend.Dockerfile` 同步到 Ubuntu，直接重新執行第 2 節 build；既有 `backend-linux.lock` 保留，不重新匯出、不使用 `--no-cache`。若依賴與 base image 未變，套件安裝層可使用快取。建置成功後，以下兩個一次性測試不再傳入額外 `-e`，以驗證名稱與 cache 設定已寫入 image；先 GPU smoke，再既有 pytest。保存新的 image ID（`sudo docker image inspect sam-yolo-backend:lab-20261020 --format '{{.Id}}'`），API 切換使用這個修正版。

## 3. 容器 GPU／checkpoint 驗證（建置成功後）

在 Ubuntu 先查看 `nvidia-smi` 的共用 GPU 使用情況，選擇合適的測試時間。執行以下暫存容器，僅將既有 checkpoint 唯讀掛入；不掛 `.env`，不掛既有 `static`，不接網路。

```bash
sudo docker run --rm --no-healthcheck \
  --runtime=nvidia --gpus all \
  --network none \
  --user "$(id -u):$(id -g)" \
  --cpus 2 --memory 4g \
  --mount type=bind,source="$HOME/apps/Yolo_system/backend/pt",target=/opt/yolo/backend/pt,readonly \
  sam-yolo-backend:lab-20261020 \
  python /opt/yolo/deploy/backend_smoke.py --gpu
```

預期有 CUDA matrix／NMS PASS、三個自訂模型 PASS 與 `Container custom YOLO GPU smoke test: PASS`。GPU 記憶體仍為共享資源；CPU／RAM 限制不代表有獨立 GPU 配額。實際模型測試失敗時先診斷，不繞過 checkpoint 指紋或更新 GPU driver。

再跑與主機相同的兩個既有測試（預期目前為 12 項；以實際版本為準）：

```bash
sudo docker run --rm --no-healthcheck \
  --network none \
  --user "$(id -u):$(id -g)" \
  --cpus 2 --memory 4g \
  --mount type=bind,source="$HOME/apps/Yolo_system/backend/pt",target=/opt/yolo/backend/pt,readonly \
  sam-yolo-backend:lab-20261020 \
  python -m pytest -q -p no:cacheprovider \
    tests/test_yolo_model_registry.py \
    tests/test_legacy_checkpoint_compat.py
```

## 4. 容器 API preflight（GPU 與既有測試通過後）

本節保留切換前已完成的預檢步驟，現在不需重跑。當時 nginx 轉送至前景 backend 的 8000，另啟動僅限 loopback 的 18000，先驗證 production 設定讀取與 MySQL；接著再驗證登入／YOLO／Ollama／媒體，全部通過後才切換。`--network host` 讓容器沿用主機 localhost 的 MySQL 13306 與 Ollama 11434。暫用程序不設 restart policy。

先在 Ubuntu 確認候選埠未被使用：

```bash
ss -ltn '( sport = :18000 )'
```

只有表頭才繼續。依序掛入私人設定（唯讀）、checkpoint（唯讀）、現有媒體（讀寫）；不顯示設定內容。請保留先前前景 backend，受控測試期間避免同時操作真實影片／批次。

```bash
sudo docker run -d \
  --name sam-yolo-backend-check \
  --network host \
  --runtime=nvidia --gpus all \
  --user "$(id -u):$(id -g)" \
  --cpus 4 --memory 8g \
  --shm-size 256m \
  -e APP_PORT=18000 \
  --mount type=bind,source="$HOME/apps/Yolo_system/backend/.env",target=/opt/yolo/backend/.env,readonly \
  --mount type=bind,source="$HOME/apps/Yolo_system/backend/pt",target=/opt/yolo/backend/pt,readonly \
  --mount type=bind,source="$HOME/apps/Yolo_system/backend/static",target=/opt/yolo/backend/static \
  sam-yolo-backend:lab-20261020 \
  python -m uvicorn main:app --host 127.0.0.1 --port 18000 --workers 1
```

`APP_PORT=18000` 覆蓋 `.env` 的 8000，讓容器 healthcheck 檢查暫用程序。uvicorn 命令亦指定相同埠；不能只改其中一個。CPU／RAM 上限是初步測試設定，不代表多人負載或 GPU 配額已驗收。

查看啟動與健康：

```bash
sudo docker logs --tail 30 sam-yolo-backend-check
curl -sS --max-time 15 http://127.0.0.1:18000/api/health
```

預期 log 為 production、startup complete、listen 127.0.0.1:18000，JSON `database=connected`。若剛啟動時連不上，先確認 log 是否已 startup complete，再重試 curl。Docker health 狀態可能起初為 starting，會按 image 的 30 秒週期檢查；不可僅以 running 宣稱 DB 通過。

如需確認容器所用 artifact，執行 `sudo docker inspect --format '{{.Image}}' sam-yolo-backend-check`，應與上述修正版 ID 相同；此指令僅輸出 image ID，不印完整 inspect／設定內容。若名稱已存在，先查看既有 `sam-yolo-backend-check` 狀態及 log，不刪除其他容器或停止其他人程序。preflight 失敗時原有 nginx／8000 仍可用；停止這個測試程序使用 `sudo docker stop sam-yolo-backend-check`。

2026-10-20 使用者回報 `sam-yolo-backend-check` 已以 production 模式啟動於 127.0.0.1:18000；health HTTP 200，`status=ok`、`database=connected`（timestamp `2026-10-20T05:07:27.535579+00:00`）。這只通過設定／啟動／DB，登入、YOLO、Ollama、媒體與正式切換／持久性仍待驗證。

### API 整合測試

把 Mac 的 `deploy/api_smoke.py` 複製到 Ubuntu 同名路徑，於 Ubuntu 主機執行（不需重建 image）：

```bash
conda activate yolo-backend
cd ~/apps/Yolo_system
python deploy/api_smoke.py
```

輸入專案登入帳號與密碼；密碼不回顯。只向 127.0.0.1:18000 發送請求，不使用代理或跟隨 redirect。模型清單須符合 Ollama 免費預設，付費 provider 若仍啟用會在發送 LLM 請求前停止。測試依序建立 ASFF 白圖偵測、Chat 與 Agent 歷史查詢，檢查實際 `summarize_detection_history` 工具成功與對話讀回，最後預期 `Container API integration smoke test: PASS`。白圖 0 個物件是正常結果；這不是準確率或 API 使用 GPU 的獨立證明，GPU 以先前容器內 smoke 為據。

腳本不刪除測試資料，保留輸出的 detection／conversation ID，供切換與重建後再查驗；中途失敗也可能已留下部分資料，勿無限重跑。媒體檢查包含原圖／標註圖、未授權 401、Bearer 下載、signed URL 下載與 PNG 解碼／nosniff；不等同於跨帳號權限或 SSE 驗收。2026-10-20 使用者後續回報 `Container API integration smoke test: PASS`：登入成功、免費 Ollama 預設正確、12 個 checkpoint 可用、ASFF 偵測／DB 讀回／受保護媒體通過，Chat 使用 llama3.2，Agent 實際成功呼叫 `summarize_detection_history`，兩組對話皆讀回成功。

保留供切換／重建後確認的資料：

- detection ID：`1`
- Chat conversation：`ba336b9d42ea436c8e87da1395379728`
- Agent conversation：`fb38c53b9f8f4281a24d94cf87302411`

使用者後續已確認正式 8000 的新容器能讀回上述原有圖片與對話，切換後串流正常；這次容器更換的持久掛載驗證通過，不等同於資料庫／媒體備份還原已驗證。

### 登入階段 401 排查（已解決）

使用者第一次執行整合腳本，health／未登入拒絕存取通過，輸入 `samtest` 帳密後得到 HTTP 401；尚未出現 `Login / current user: PASS`。舊版錯誤未包含端點，可能是 `POST /api/auth/login` 或其後的 `GET /api/auth/me`，不能據此判定容器或 JWT 故障。新版 helper 的失敗訊息顯示方法／端點（媒體路徑遮罩且不含 query），並在登入成功後立即印 `Login: PASS`，便於區分。

先查看測試容器最近的 auth access log 狀態碼，區分 login 401（帳號不存在／停用／密碼不符）與 login 200 後 me 401（token 驗證，需再診斷）。實驗室是另建 MySQL；只複製 Git 與模型不會帶入 Mac 上的帳號。不要因這次 401 自動重設密碼、建立管理員、關閉驗證或重建資料庫。確認使用曾登入實驗室網頁的帳號後只重試一次；避免反覆猜密碼觸發登入節流。首次 401 當下尚未建立白圖或 Chat／Agent 測試資料。使用者後續確認改用專案帳號即成功，整合測試全數通過；沒有修改認證、密碼或 DB。

## 5. 接手正式 8000（整合測試通過後）

2026-10-20 使用者已執行以下切換程序並回報：新容器 `sam-yolo-backend`（短 ID `c3fe2954c948`、image `2fdf4814f7be`）以 production 監聽 127.0.0.1:8000，Docker 狀態 `healthy`；直接 8000 與經 nginx 8080 的 health 均回 `status=ok`、`database=connected`（UTC `2026-10-20T05:16:43`）。使用者後續已確認網站三項檢查正常：偵測 ID 1 原圖／結果圖、既有 Chat／Agent 對話、切換後串流。此為瀏覽器功能確認，客觀 SSE 時序量測另待驗收。以下保留已執行的操作供重建參考，**目前不要重複 docker run 或停止新容器**。暫停網站操作，確認沒有影片／批次／對話正在執行。保持 nginx、MySQL 與 Ollama 運行；只停止自己的測試容器與原前景 uvicorn，不重啟共享 Docker 或主機。切換期間 nginx 可能短暫回 502。

### 檢查名稱、停止舊程序

```bash
sudo docker ps -a --filter 'name=^/sam-yolo-backend$'
```

只有表頭才繼續；若已有同名容器，先查明，不自動刪除。停止已驗證的暫用容器，保留供排查：

```bash
sudo docker stop --time 120 sam-yolo-backend-check
```

回到原本執行 `uvicorn ... --port 8000` 的終端機按 Ctrl+C，等候 `Application shutdown complete`。這時網站入口會短暫無法連 API。

```bash
ss -ltn '( sport = :8000 )'
```

只有表頭才繼續；若仍 LISTEN，先回報，不使用廣泛的 pkill／killall 或停止他人程序。

### 啟動已驗證 image

固定使用上一步已驗證的 image ID，避免 tag 被意外覆寫。沿用相同掛載與資源限制，改為正式 8000、加入 restart policy 及有限日誌輪替，不重建 image、不重跑 migration、不刪 volume。`.env` 與 checkpoint 唯讀、static 讀寫，sam UID／GID 與預檢相同。

```bash
sudo docker run -d \
  --name sam-yolo-backend \
  --restart unless-stopped \
  --stop-timeout 120 \
  --log-driver json-file \
  --log-opt max-size=10m --log-opt max-file=3 \
  --network host \
  --runtime=nvidia --gpus all \
  --user "$(id -u):$(id -g)" \
  --cpus 4 --memory 8g \
  --shm-size 256m \
  -e APP_PORT=8000 \
  --mount type=bind,source="$HOME/apps/Yolo_system/backend/.env",target=/opt/yolo/backend/.env,readonly \
  --mount type=bind,source="$HOME/apps/Yolo_system/backend/pt",target=/opt/yolo/backend/pt,readonly \
  --mount type=bind,source="$HOME/apps/Yolo_system/backend/static",target=/opt/yolo/backend/static \
  sha256:2fdf4814f7bef3919489586754819b7879059f8108dec8eb5a8ff09c8030a945
```

啟動命令沿用 image 內建的單 worker uvicorn 127.0.0.1:8000；APP_PORT 與 healthcheck 一致。

```bash
sudo docker logs --tail 30 sam-yolo-backend
```

等到 startup complete 後：

```bash
curl -sS --max-time 15 http://127.0.0.1:8000/api/health
curl -sS --max-time 15 http://127.0.0.1:8080/api/health
sudo docker ps --filter 'name=^/sam-yolo-backend$'
```

兩個 health 都須 `database=connected`，Docker health 起初 starting 屬正常、稍後應 healthy。restart policy 會在程序退出時依規則重啟，但不會只因 unhealthy 自動重啟，也不代表共享主機開機啟動已實測。

在既有 VS Code forwarding 的 8080 網站重新整理並登入，確認偵測紀錄 ID 1 原圖／結果圖可開、Chat 與 Agent 各自的測試對話仍在，再測一次 Chat／Agent 串流。只有實際回報後才記錄切換與重建讀回通過；不重跑完整 api_smoke 來取代舊 ID 存續驗證。MySQL／nginx 設定與資料皆保留。

### 如新容器啟動失敗，回復前景程序

先保存 `sudo docker logs --tail 50 sam-yolo-backend`（不要貼完整 inspect 或 .env）。只停止新容器，等待停止與 8000 釋放，再以原環境啟動既有前景後端：

```bash
sudo docker stop --time 120 sam-yolo-backend
conda activate yolo-backend
cd ~/apps/Yolo_system/backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
```

原 nginx 仍代理 8000，因此不需重建 nginx 或 DB。手動停止的 unless-stopped 容器保持停止，不應在回復前景程序時並行爭用 8000。

## 6. Phase 6 仍待完成

- 正式 8000／nginx health 與新容器既有資料讀回／串流已通過；接續 [Compose 管理](lab-compose.md)，目前只準備設定與驗證步驟，未實際納管。
- Compose、frontend build image、完整啟停／重建配置、runtime 設定／媒體／模型持久保存與 Docker／Ollama 開機啟動驗證；共享主機不直接重開機測試。
- CPU／RAM／VRAM 量測與排隊／併發上限；目前 4 CPU／8 GiB RAM 是初步配置，不代表 10–50 人負載已驗收，亦無 GPU 配額隔離。
- HTTPS／內網存取、備份與隔離還原、Vite 工具鏈升級、跨帳號權限／客觀 SSE 時序與完整端到端驗收。不得僅因 API smoke 通過就標記 Phase 6 完成。

### Compose 準備前的唯讀查詢

等待既有資料讀回結果時，於 Ubuntu 查詢 Compose 版本及目前 image 的 registry digest；不修改或重啟服務，不輸出容器 Env 或私人設定：

```bash
sudo docker compose version
sudo docker image inspect nginx:1.30.6-alpine mysql:8.4 --format '{{.Id}} {{json .RepoDigests}}'
```

使用者已回報 Compose v2.29.2 與 nginx／MySQL registry digest，完整值及新設定見 [Compose 管理](lab-compose.md)。既有 named volume 不改名、不刪除。Compose 不會僅因 container_name 相同就接管手動 docker run 的容器，後續需要規劃受控替換與保留回復途徑，目前未執行 Compose up／down。

## 本機可完成的檢查

Mac 上已檢查兩支新 Python 程式語法、版本快照對 URL／本機來源／不固定與重複套件的拒絕，以及 health probe 對 DB error／缺少 DB 狀態／API 無法連線的失敗判定。Mac Docker daemon 尚未啟動，且本機沒有 NVIDIA GPU，因此 Mac 沒有執行 image build 或容器 CUDA 驗收。Ubuntu 已回報修正版 image、容器 CUDA／自訂 checkpoint、12 項既有測試及 18000 production／DB health 通過；API 整合腳本在 Mac 完成語法與模擬契約檢查，Ubuntu 後續已回報實際 API 整合全數通過。正式 8000 已切換並 healthy，直接／經 nginx health 均 DB connected；新容器既有圖片／對話讀回與串流已回報正常；Compose 設定已在 Ubuntu 通過驗證；接續批次納管與合併驗證，實際結果待回報。

## Sources

- [NVIDIA 容器 GPU 測試](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/sample-workload.html)
- [Python 官方映像](https://hub.docker.com/_/python)
- [Dockerfile 專用 ignore 與 build context](https://docs.docker.com/build/concepts/context/)
- [PyTorch 官方 CUDA wheel 版本](https://pytorch.org/get-started/previous-versions/)
