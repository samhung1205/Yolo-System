# Web 真實整合驗收（2026-10-15）

## 環境與隔離

- FastAPI / MySQL 真實服務，`GET /api/health` 回報 `database=connected`。
- Alembic 已在 `0011 (head)`，本次未執行 migration、未修改 `.env`。
- 使用獨立暫時帳號；測試圖為已安裝 Ultralytics 隨附的 `assets/bus.jpg`，不使用使用者私人影像。
- 推論模型 `coco80_base`（`yolo11n.pt`）；Chat / Agent 明確指定本機 Ollama `llama3.2:latest`，未呼叫雲端付費模型。

## 實測結果

| 流程 | 結果 |
| --- | --- |
| 註冊 / JWT 登入 | API 201 / 200；原生瀏覽器登入成功、工作台顯示測試帳號 |
| 真實影像上傳 API → YOLO → MySQL | 201、completed，1 bus + 4 person；推論 59.83ms，完整請求約 3.69 秒 |
| 歷史清單與詳情 | API 查到新紀錄；瀏覽器顯示檔名、標註圖、5 個物件及完整 bbox |
| 結果圖下載 | 簽章 URL 回傳 image，207,671 bytes |
| 確定性報告 | Markdown 1,735 bytes；PDF 34,416 bytes 且具有 `%PDF-` 檔頭 |
| 一般 Chat | 真實 Ollama 回覆，provider/model 儲存為 ollama / llama3.2:latest，約 2.51 秒 |
| Agent 非串流 | success=true，yolo_explainer 工具與 detection reference，約 2.93 秒；非 mock |
| Agent 瀏覽器串流 | URL ID 成功選取真實結果；送出後由等待轉為完整回覆「4 people and 1 bus」，顯示可點擊的分析依據 |

## 驗收界線與重現方式

這是單張影像與本機小模型的整合煙霧測試，不是準確率評估、壓力測試或部署驗收。小模型非串流回覆曾把物件 confidence 稱為 threshold；以結構化偵測資料與確定性報告為準，流程成功不表示自然語言敘述逐句正確。

瀏覽器檔案選擇器在自動化 `setFiles` 時失敗，因此本次真實上傳由 multipart API 驗證；未把這項結果算成瀏覽器選檔到上傳的完整通過。瀏覽器已驗證真實登入、歷史資料呈現、分析資料帶入與 LLM 串流。原生選檔操作仍需人工回歸。

重現：啟動 README 所述後端與 Vite，確認 MySQL 與 Ollama；建立獨立測試帳號，使用 COCO 模型上傳公車範例圖，從偵測紀錄進入「解釋偵測結果」，手動選擇本機模型後送出；確認 1 公車、4 行人，下載標註圖與 Markdown / PDF。測試完成後只清理該測試帳號與其資料。

後續 UI 分組另以獨立 commit 記錄；本文件不代表已驗證大批次、影片、跨瀏覽器或 1000 張架構。
