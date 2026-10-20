# Desktop App（PySide6）

> **狀態：維護模式**（2026-10-19 起）。主力為 Web 版；桌面版保持可執行、修 bug，不再新增功能。
> 所有資料存取都走 FastAPI backend，桌面版不直接連 MySQL。

## 啟動

```bash
# 連接既有網站，或先啟動開發 backend（見 docs/development.md）：
conda activate yolo-backend          # 已含 PySide6 / ultralytics
cd /path/to/Yolo_system
# backend 不在 http://127.0.0.1:8000 時：
# export YOLO_API_BASE_URL=https://140.113.135.113
python Login.py
```

入口仍是根目錄的 `Login.py`；UI 檔案（`MainUI.py`、`AdminMainUI.py` 等）也還在根目錄，
本目錄只放共用模組。

## 本目錄模組

| 檔案 | 用途 |
|------|------|
| `api_client.py` | 所有 backend HTTP 呼叫（auth、profile、detection、chat、agent、users） |
| `validation.py` | 帳號 / Email / 密碼規則，與 `backend/app/schemas/user.py` 一致 |
| `avatar_cache.py` | 頭像本地快取（`user_avatars/`） |
| `ui_state.py` | 視窗間共享狀態（取代 legacy `mysql.dataDB.SI`） |

共用 UI 工具在 `utils/main_utils.py`（`utils/py37`–`py311` 只是相容用的 re-export）。

## 功能對照

| 功能 | 走 backend | 備註 |
|------|-----------|------|
| 登入 / 註冊 / 自動登入 | ✅ | 註冊選的頭像會在建立帳號後上傳 |
| 個人資料、頭像、改密碼 | ✅ `PUT /api/auth/profile` | 改密碼需輸入原密碼，由 backend 驗證 |
| 管理員：使用者 CRUD | ✅ `/api/users` | |
| 單張圖片 / 本地影片偵測 | ✅ | 固定使用 backend 預設模型（`YOLO_DEFAULT_MODEL_KEY`） |
| 偵測紀錄（篩選 / 分頁 / 刪除） | ✅ | |
| AI 對話 / AI Agent | ✅ | `AICSMain.py` / `AgentWindow.py` |
| Webcam / RTSP | ❌ 本機推論 | legacy `detect_mainui.py`；模型預設用 `backend/pt/yolo11n.pt`，可用 `YOLO_DESKTOP_MODEL` 覆寫 |

**Web 有、桌面版沒有**：模型選擇、批次分析、各類別閾值、報告下載。

## 已知限制

- Webcam / RTSP 仍在本機跑 YOLO，不經 backend，也不會存進偵測紀錄
- 登入資訊存在 `QSettings("Organization", "Application")`（明文 JWT）
- 只在 macOS 開發機上驗證；Windows 高 DPI 邏輯沿用 legacy 寫法

詳細架構與階段狀態見 [architecture.md](../docs/architecture.md) 與 [roadmap.md](../docs/roadmap.md)。

開發環境與驗證見 [development.md](../docs/development.md)；使用者操作見 [使用手冊](../README.md)。
