# Phase 6.1 — 實驗室同網址服務

> 專題／階段紀錄：內含初次建置、修復與當時待辦。現行日常操作以 [維運手冊](lab-operations.md) 為準，最新狀態以 [roadmap](roadmap.md) 為準；不要依舊待辦重跑納管或初次部署包。

本階段先以 SSH／VS Code port forwarding 驗證 React production build + nginx + 現有 FastAPI。**尚未完成 HTTPS、內網對外開放、完整容器化、備份／還原或 Phase 6 驗收。**

## 已收到的實驗室驗證結果

以下為使用者於 Ubuntu 主機執行後回報，並非在 Mac 本機重現的結果：

- Ubuntu 22.04.4、i7-13700、約 62 GiB RAM、RTX 4070 Ti 12 GiB；多人共用 GPU。磁碟空間是先前快照，正式上線前重查。
- `yolo-backend`：Python 3.11.17、PyTorch 2.11.0+cu126、torchvision 0.26.0+cu126；GPU NMS、自訂 ASFF／DySample／EfficientViM 推論通過，模型檔 12 個。
- MySQL 8.4.11 容器 `sam-yolo-mysql`，專用 DB 帳號連線通過；主機僅發布 `127.0.0.1:13306`，資料存在 named volume `sam-yolo-mysql-data`；migration 為 `0013 (head)`。
- 管理員已改密碼；FastAPI 以 production、單 worker、`127.0.0.1:8000` 啟動，`/api/health` 回 `database=connected`。後續已由 `sam-yolo-backend` 背景容器接手相同 8000，production／Docker healthy、直接與經 nginx 的 DB health 均通過。
- Ollama 0.40.6 service active；設定 loopback、關閉 cloud、同時最多一個模型／一個推論、context 8192、閒置 1m 卸載。模型 `llama3.2`（ID `a80c4f17acd5`、約 2.0 GB）及 `gemma4`（ID `dc35e8d9c606`、約 6.6 GB）皆完成 CLI 回答並回報 100% GPU；完整 manifest digest 尚待保存。
- 真實登入後，Chat 回 HTTP 201、模型 `llama3.2`；Agent 回 HTTP 200、`success=true`，實際呼叫 `summarize_detection_history`，正確讀到新 DB 的零筆任務。這不是 SSE、YOLO API 或完整 Web 驗收；Chat 繁體中文品質另待確認。
- `yolo-web` 以 Node.js 22 建置；實際 Node／npm 版本仍需保存。`npm ci --include=dev` 後，`VITE_API_BASE_URL="" npm run build` 通過；Vite 5.4.21，`dist/` 約 624 KiB，Git 工作目錄乾淨。npm 回報 1 moderate / 1 high；使用者提供 audit，Mac 端另以相同 lockfile 執行唯讀 `npm audit --json` 確認為 esbuild 開發伺服器 CORS、Vite optimized-deps sourcemap 路徑穿越與 Windows 專屬問題。nginx 僅提供 dist，沒有運行開發伺服器，不會直接執行這些路徑；套件弱點仍未修復。Vite 8 及 React plugin 的受控升級／build／瀏覽器回歸保留為 Phase 6 待辦，不執行 `npm audit fix --force`。

- nginx 1.30.6-alpine 容器 `sam-yolo-web` 已依步驟啟動；使用者回報設定檢查完成，經 `127.0.0.1:8080/` 取得 HTTP 200、`Content-Type: text/html`、`Cache-Control: no-store` 與 `nosniff`，經相同入口的 `/api/health` 回 `database=connected`。使用者後續回報前述瀏覽器清單（登入、Agent 深連結重新整理、Chat／Agent 串流顯示與圖片偵測／歷史）目前無問題；API／媒體錯誤分流、跨使用者權限及客觀 SSE 時序仍待補驗。

## 網址條件

使用者確認只有主機 IP，沒有網域，且需要實驗室成員從校外網際網路直接使用。仍採免費既有主機；HTTPS 對外入口待網路盤點與選定，目前維持 SSH forwarding 測試，不將付費網域／雲端資源視為已授權。使用者亦確認沒有 NAS／獨立備份磁碟，後續先完成同主機一致性備份與隔離還原，再規劃下載到 Mac 保存另一份副本；同主機備份不能視為已具異機備援。

## 尚待完成

- Docker 的 `nvidia` runtime 已在 Ubuntu 實測可見 RTX 4070 Ti；目前 backend 已由背景容器接手 8000。後端修正版映像已在 Ubuntu 通過 CUDA／NMS、自訂 checkpoint 與 12 項既有測試，步驟與 image ID 見 [Phase 6.2 後端 GPU 容器](lab-backend-container.md)；暫用 18000 已回報 production 啟動與 health DB connected；登入／YOLO／受保護媒體／Ollama Chat／Agent 及對話讀回亦已通過；正式 8000 已接手且 healthy、經 nginx health DB connected；使用者亦確認新容器可讀回原有圖片與對話、串流正常。Compose v2.29.2 與固定 image digest 已確認；[Compose 設定](lab-compose.md) 已備妥，Ubuntu 設定驗證已通過；納管及合併驗證改用 [批次腳本](lab-compose.md)，實際結果待回報。
- HTTPS／內網存取、正式依賴升級驗證、備份位置與還原、重啟與跨帳號驗收尚未完成。

## 本階段拓撲

```text
Mac 瀏覽器 → VS Code SSH forwarding → Ubuntu 127.0.0.1:8080 nginx
                                              ├─ React dist（唯讀）
                                              └─ /api、/static → 127.0.0.1:8000 FastAPI
```

nginx 使用獨立容器與 Linux host network，因此 `127.0.0.1:8000` 指向主機上現有 backend；不能直接把本設定搬到 bridge network 的 backend 容器。設定來源為 [nginx.lab.conf](../deploy/nginx.lab.conf)。它是完整的 nginx 主設定檔，須掛到 `/etc/nginx/nginx.conf`，不是 `conf.d/default.conf`。

- 僅 listen `127.0.0.1:8080`，不使用 `-p`。若要正式讓其他電腦直接存取，需另行配置 HTTPS／內網名稱及存取範圍。
- `/api`、`/static`、production 關閉的 docs 路徑都交由 backend；保留 HTTP 錯誤與媒體權限。**不把 `backend/static` 掛成公開檔案目錄。**
- SPA 深連結回 `index.html`；不存在的 `/assets/` 回 404；HTML 不儲存快取，帶 hash 的 build assets 可長期快取。
- 上傳總量上限 1024 MiB，涵蓋目前 100 張、每張 10 MiB 加 multipart 開銷；應用程式仍檢查各檔大小。此值不是將批次提高到 1000 張。
- 關閉 proxy buffering／request buffering，read／send timeout 為 600 秒的兩次讀寫間隔，不是整體任務必然完成期限。SSE 是否即時送達仍須實測。
- access log 不記錄 query string，以免將簽章媒體 URL 的憑證寫進請求紀錄。

## Ubuntu 操作

FastAPI 先保持運行，另開遠端終端機。將 repo 的設定複製到既有私人設定目錄；若檔案尚未同步到 Ubuntu，可先依對話提供的相同內容建立私人副本，之後再和版本控制來源比對。

```bash
cd ~/apps/Yolo_system
install -m 600 deploy/nginx.lab.conf "$HOME/.config/yolo-system/nginx.lab.conf"
sudo docker pull nginx:1.30.6-alpine
```

先確認 `web-frontend/dist/index.html` 存在。驗證語法：

```bash
sudo docker run --rm \
  --mount type=bind,source="$HOME/.config/yolo-system/nginx.lab.conf",target=/etc/nginx/nginx.conf,readonly \
  --mount type=bind,source="$HOME/apps/Yolo_system/web-frontend/dist",target=/usr/share/nginx/html,readonly \
  nginx:1.30.6-alpine nginx -t
```

只在語法成功後啟動：

```bash
sudo docker run -d \
  --name sam-yolo-web \
  --restart unless-stopped \
  --network host \
  --cpus 1 \
  --memory 256m \
  --mount type=bind,source="$HOME/.config/yolo-system/nginx.lab.conf",target=/etc/nginx/nginx.conf,readonly \
  --mount type=bind,source="$HOME/apps/Yolo_system/web-frontend/dist",target=/usr/share/nginx/html,readonly \
  nginx:1.30.6-alpine
```

若容器名稱已存在，先 `sudo docker ps -a --filter name=sam-yolo-web` 及讀取 log，不直接刪除其他容器。nginx restart policy 只涵蓋 nginx；不代表前景 backend 已可在登出／重開機後持續運行。

## 驗證與停止

先在 Ubuntu 執行下列檢查，不登入也能驗證分流：

```bash
curl -sS --max-time 15 -o /dev/null -w 'Homepage HTTP %{http_code}\n' http://127.0.0.1:8080/
curl -sS --max-time 15 -o /dev/null -w 'SPA HTTP %{http_code}\n' http://127.0.0.1:8080/agent
curl -sS --max-time 15 http://127.0.0.1:8080/api/health
curl -sS --max-time 15 -o /dev/null -w 'Unknown API HTTP %{http_code}\n' http://127.0.0.1:8080/api/not-a-route
curl -sS --max-time 15 -o /dev/null -w 'Private media HTTP %{http_code}\n' http://127.0.0.1:8080/static/avatars/not-a-file.png
curl -sS --max-time 15 -o /dev/null -w 'Missing asset HTTP %{http_code}\n' http://127.0.0.1:8080/assets/not-a-file.js
```

預期依序 200、200、JSON `database=connected`、404、401、404；200 狀態仍需確認實際 HTML／JS 能載入。若 502，檢查前景 backend 是否仍在 `127.0.0.1:8000` 運行；若 nginx 沒啟動，執行 `sudo docker logs --tail 50 sam-yolo-web`。

在 VS Code 遠端視窗的 Ports／連接埠新增 8080，使用該列實際顯示的本機網址開啟瀏覽器；若 Mac 的 8080 已被占用，VS Code 可能選其他本機埠。只需轉送 nginx 的 8080，前端 build 使用相對 API 位址。瀏覽器依序驗證：登入、重新整理 `/agent` 深連結、Chat、Agent SSE、影像偵測與受保護媒體、登出。完整 HTTPS／其他使用者權限、100 張／影片、Desktop 與重啟持久性驗收仍待完成。

停止本階段入口：`sudo docker stop sam-yolo-web`；再啟動：`sudo docker start sam-yolo-web`。修改私人設定檔後先以相同 `nginx -t` 指令驗證，再 `sudo docker exec sam-yolo-web nginx -s reload`。重新 build 前先停止入口，完成成功 build 後再啟動，避免提供一半更新的 `dist`；之後以版本化 artifact／image 完善升級與 rollback。

## Sources

- [esbuild 開發伺服器公告](https://github.com/advisories/GHSA-67mh-4wv8-2f99)
- [Vite optimized-deps sourcemap 公告](https://github.com/advisories/GHSA-4w7w-66w2-5vf9)
- [Vite Windows 路徑公告](https://github.com/advisories/GHSA-fx2h-pf6j-xcff)
- [launch-editor Windows 公告](https://github.com/advisories/GHSA-v6wh-96g9-6wx3)
- [nginx 官方映像](https://hub.docker.com/_/nginx)
- [Docker host network](https://docs.docker.com/engine/network/drivers/host/)
- [nginx proxy directives](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
- [nginx core directives](https://nginx.org/en/docs/http/ngx_http_core_module.html)
