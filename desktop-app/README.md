# Desktop App

> **狀態**: Phase 2 已完成。桌面版透過本目錄的共用元件呼叫 backend API，
> 不再直接連 MySQL 或持有外部模型 API key。

## 目前內容

| 檔案 | 用途 |
|------|------|
| `api_client.py` | Desktop 端共用 API client（標準函式庫 `urllib`，依操作類型分開設定 timeout：推論 180s／上傳 600s／SSE 300s／二進位下載 120s） |
| `avatar_cache.py` | backend avatar 的本地快取工具 |
| `ui_state.py` | 桌面視窗間的共享狀態（取代 legacy 的全域 `mysql.dataDB.SI`） |

## 進入點

桌面版的視窗程式仍位於 repo 根目錄，入口點為 [`../Login.py`](../Login.py)。
這些檔案尚未遷入本目錄。

## API base URL

預設為 `http://127.0.0.1:8000`，可用環境變數覆寫：

```bash
export YOLO_API_BASE_URL=http://127.0.0.1:8001
```

詳見 [docs/architecture.md](../docs/architecture.md) 與 [docs/roadmap.md](../docs/roadmap.md)。
