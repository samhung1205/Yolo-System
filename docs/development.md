# 開發環境與驗證

這份文件給需要修改程式的人；一般使用者請看 [使用手冊](../README.md)，伺服器管理請看 [維運操作](lab-operations.md)。正式網站已在實驗室主機，不要為本機開發重新部署正式服務。

## 程式入口

| 位置 | 用途 |
|---|---|
| `backend/main.py` | FastAPI、lifespan 與路由入口 |
| `backend/app/api/routes/` | HTTP／SSE／媒體端點 |
| `backend/app/services/`／`repositories/` | 業務規則與 DB 操作 |
| `backend/app/integrations/` | YOLO、模型 registry、LLM providers |
| `backend/app/agents/` | 唯讀工具、pipeline／tool-calling 引擎 |
| `backend/migrations/versions/` | schema 演進，最新 `0013` |
| `web-frontend/src/` | React 頁面、元件、共用 API 與狀態 |
| `desktop-app/`／根目錄 `Login.py` | 桌面共用 client 與舊 UI 入口 |
| `deploy/` | Compose、Dockerfile、維運與驗證工具 |
| `tests/evals/` | Agent 評測案例與結果 |

模型的 ASFF、DySample、EfficientViM 歷史 module path 由 `legacy_checkpoint_compat.py` 對應至 `models/custom_modules/ASFFHead.py`、`SCAM_DySample.py`、`AddModules/EfficientViMBlock.py`。只複製 backend 可能不夠。維護模型指紋可使用 `backend/scripts/update_model_hash.py` 的 `--list`／`--dry-run`，實際更新前仍要驗證架構與類別。

## 本機後端

建議 Python 3.11／conda。下列步驟使用**獨立開發資料庫與設定**，不能複製正式 `.env` 到 Git 或拿正式 DB 做測試。

```bash
conda create -n yolo-backend python=3.11
conda activate yolo-backend
cd backend
cp .env.example .env
python -m pip install -r requirements.txt
```

編輯未入版控的 `.env`：填入自己的 DB 連線與足夠長的隨機 `SECRET_KEY`，保持 `APP_ENV=development`。依啟動檢查設定管理員資訊；密碼勿使用預設值。需要純文字對話測試時可明確設 `CHAT_PROVIDER=mock`，不要混淆為 Ollama 實測。

在 `backend/` 執行：

```bash
python -m alembic upgrade head
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

開發 API 文件為 `http://127.0.0.1:8000/docs`；`/api/health` 可確認 DB。production 會關閉 API 文件，根路徑 404 不是健康檢查失敗。

`.pt` 不在版本庫，需要使用已授權的模型檔並通過 registry 指紋；無私人模型的 CI 可排除 checkpoint 測試。Ollama／GPU 驗證與純 mock 測試分開記錄。

## 本機 Web

目前使用 React 18、React Router 7、Vite 8。Node.js 最低 20.19 或 22.12，建議 Node 22 的相容版本。另一個終端機：

```bash
cd web-frontend
npm ci --include=dev
npm run dev -- --host 127.0.0.1 --port 5173
```

預設透過 Vite proxy 連後端；不同位置的設定見 [Web 開發說明](../web-frontend/README.md)。部署產物使用相對 API：

```bash
VITE_API_BASE_URL='' npm run build
```

正式環境由 Caddy 提供 build，不用 `npm run dev`／`vite preview` 取代正式入口。改動原始碼不會自動更新伺服器 image。

## 選擇驗證範圍

| 改動 | 執行方式 |
|---|---|
| 後端 | 在 `backend/` 執行 `python -m pytest -q`，或先跑受影響測試檔 |
| 沒有私人模型 | `python -m pytest -q -m 'not checkpoints'`；回報被排除項目 |
| Web | `npm run build`，再查實際瀏覽器流程與窄螢幕 |
| 部署工具 | 專案根目錄 `python3 -m unittest discover -s deploy/tests -q` |
| Agent 評分規則 | yolo-backend 環境，在專案根目錄 `python -m unittest discover -s tests/evals -p 'test_*.py' -q` |
| 文件 | 專案根目錄 `python3 scripts/check_docs.py` |
| 文件檢查器 | `python3 -m unittest discover -s scripts/tests -q` |
| 提交差異 | `python3 scripts/check_docs.py --staged`、`git -c core.whitespace=cr-at-eol diff --check` |

沒有 `npm test` 或 lint script，請勿宣稱已執行。真實 GPU／MySQL／Ollama／HTTPS 與單元測試結果分開，完整歷史驗證見 [歷史索引](archive/README.md)。

Agent 評測可執行 `python tests/evals/evaluate_agent_engines.py --rescore`，使用固定的記憶體 SQLite 測試資料重新評分已保存的回答，不呼叫 LLM 或正式 DB。內容必要／禁止字詞比對會還原 Markdown 跳脫底線，避免檔名 `harbor\_1.jpg` 被誤判。重新評分保留原始執行時間與回答，JSON 的 `rescore_history` 記錄來源 SHA-256、原始檢查與補正差異；報告區分模型執行與評分補正，不把重新評分當成新的模型實測。`--rescore` 不可搭配只涵蓋部分既存案例的 `--cases`，避免覆寫掉其他結果。

## 影片與容器依賴

影片走 `YoloEngine.detect_video()` 的 `model.track()`，需 `lap==0.5.13`；一般圖片測試不會觸發追蹤依賴。本機 requirements 已列入。正式 Docker 使用原始 `deploy/backend-linux.lock` 加上 `deploy/backend-runtime.lock` 補充固定版本；補充層以 binary wheel／不更新既有依賴安裝，再驗證 pip check。原始 CUDA lock 保留，避免為新增追蹤套件重建大型依賴層。

`deploy/ci_requirements.py` 合併兩份 lock，保留 lap，只將 Torch 改 CPU 版本並移除 CUDA 專用依賴。容器關閉 Ultralytics 執行時自動安裝；新增使用到的選用功能時，必須明列依賴並在候選 image 實測。

`deploy/backend_smoke.py --video` 為容器的核准模型／CUDA 四影格影片追蹤及輸出解碼驗證，沒有私人資料或 DB 需求；`lab_finalize.py` 已將它放在正式服務切換之前。實機執行方式與最新結果見 [Phase 6 收尾批次](lab-phase6-finalization.md)。

## CI 與文件同步

`.github/workflows/verify.yml` 目前是手動 `workflow_dispatch`，避免自行消耗私人 repository 的 Actions 額度。它固定 action commit、採唯讀權限、建 CPU 測試環境、排除私人 checkpoint、執行部署工具與文件檢查，再建置前端。檔案已準備好不代表 GitHub 已有成功 run；目前狀態見 [roadmap](roadmap.md)。

後續每次改動依 [文件同步政策](documentation-policy.md) 更新對應內容。可選擇啟用本機 pre-commit hook；未啟用時仍可手動執行檢查，不會自動改 Git 設定。
