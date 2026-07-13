# Desktop App

> **狀態**: Phase 2 開始前，桌面版 legacy 程式碼仍位於專案根目錄。
> 本目錄預留給 Phase 2 後逐步遷入的桌面版程式碼。

## 當前狀態

Legacy 桌面版入口點：`../Login.py`

## Phase 2 計畫

Phase 2 完成後，以下檔案將遷入此目錄並重構：
- `api_client.py` — httpx-based API client（取代直接 DB 呼叫）
- `services/` — 本地 service layer

詳見 [docs/roadmap.md](../docs/roadmap.md)
