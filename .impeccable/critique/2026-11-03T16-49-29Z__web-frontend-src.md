---
target: 全站 Web 前端（web-frontend/src）
total_score: 20
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:/Users/SAM/Desktop/Agents/Yolo_system/web-frontend/src"
timestamp: 2026-11-03T16-49-29Z
slug: web-frontend-src
closed: true
---
Method: dual-agent（A：設計審查子代理 · B：detector／瀏覽器證據子代理）

**整體評分 20/40（Acceptable 下緣）。** 10/15 那次的 P1 大多已修好；這次實際跑完偵測、Agent、手機流程後，暴露出另一層問題：模型類別看不見、主要操作後焦點掉回 `<body>`、手機出結果後整頁橫向溢出、中英混雜。

範圍：`web-frontend/src` 全站 10 頁。隔離示範環境為記憶體 SQLite、媒體放暫存區、Ultralytics 公開範例圖＋合成圖，YOLO 為真實推論（CPU）。桌面 1440×900／1280×800、手機 375×812。未修改原始碼；測試伺服器已全部停止，`git status` 乾淨。

## 設計健康分數

| # | 準則 | 分數 | 主要問題 |
|---|---|---|---|
| 1 | 系統狀態可見性 | 2 | 批次輪詢有進度、斷線提示與最後更新時間；偵測完成沒有公告，Agent 約 30 秒只有閃爍游標 |
| 2 | 符合使用者語言 | 2 | conf／IoU／ASFF／DySample／Pre／OBB 無解釋；狀態顯示原始 enum `COMPLETED`；bbox 為原始浮點 |
| 3 | 使用者控制 | 2 | 有「停止接收」、取消、草稿保留；換模型直接清掉剛完成的結果，inline 確認不吃 Escape |
| 4 | 一致性 | 2 | 視覺 token 與元件一致；文案中英混雜，刪除確認有三種模式，同一模型三種名稱 |
| 5 | 錯誤預防 | 2 | 預設 7 類模型對一般照片即 0 結果；授予 Admin 無確認；自己那列也顯示 Delete |
| 6 | 辨識優於記憶 | 2 | 模型選單 12 項、4 項同名「YOLO11n Base」；類別只藏在進階閾值表 |
| 7 | 效率與彈性 | 2 | 深連結、Enter 送出、檢視器快捷鍵；紀錄頁無法依檔名／模型／日期搜尋，無法比較模型 |
| 8 | 美感與精簡 | 2 | 克制，但等高 stretch 造成大片空白；批次上傳表單佔滿第一屏 |
| 9 | 錯誤復原 | 2 | 重試普遍；後端原文外露（「Value error, …」「Network Error」）且顯示在頁頂、遠離欄位 |
| 10 | 說明與協助 | 2 | 閾值提示在脈絡內且實用；模型家族、Pre、OBB、Agent 模式完全沒有說明 |
| **合計** | | **20/40** | **Acceptable：需明顯改善** |

設計審查原評 18/40；整合時把「一致性」與「說明」各從 1 調為 2：視覺系統確實一致，問題在文案與確認模式；閾值提示是脈絡內、相關的說明，只是涵蓋太少。

## 設計辨識度判斷

**LLM 評估：** 側欄＋白底細框 panel＋藍色主按鈕＋膠囊徽章＋清單／詳情雙欄，換掉標題就能當任何 SaaS 後台。量身打造的部分是原圖／標註圖並排、provenance 晶片（`model_key`／conf／IoU／`sha256`）、棋盤格影像檢視器、Agent「分析依據」列。但產品最獨特的素材「框、類別、信心值」幾乎沒被設計：bbox 是長浮點字串、標註圖顏色和物件表沒有對應、紀錄與工作台沒有縮圖、批次沒有類別分布。紀錄、批次、Chat 三頁結構同質。藍白識別有守住，但產品性格只停在色彩 token。

**自動掃描：** CLI `impeccable detect` 掃 34 個檔案，0 項（`--no-config` 亦同）。瀏覽器內 detector 在 5 頁共回報 3 種規則，查核後皆為誤報或接近誤報：
- `text-occlusion`：被「遮住」的文字在收合的 `<details>` 內，展開後消失。
- `dark-glow`：頁面是淺色；`--shadow` 的 `#102033` 已被 styles.css:2198 覆寫為 `none`，detector 未計算 cascade。
- `first-viewport-column-overflow`：長內容在內部捲動容器；唯一真實偏差是 1280×800 下紀錄頁區塊底部超出視窗 30px。
detector 沒抓到焦點遺失、手機溢出、語言問題，這些都是行為層問題，只有實際操作才看得到。

**視覺 overlay：** 瀏覽器面板中標題為 `[Human] YOLO System Web` 的分頁（停在 `/admin/users`）仍顯示 overlay；伺服器已停，屬靜態畫面，僅剩一項 `dark-glow`（誤報）。

## 整體印象

工程基礎紮實（dialog、重試、深連結、只讀證據），但真正卡住使用者的是「第一次偵測就 0 結果，又不知道為什麼」。最大機會：讓「框」成為介面主角，類別看得見，標註圖、物件表、AI 回答共用同一套類別色票並互相對應。

## 做得好的地方

1. 原生 `<dialog>` 焦點管理到位：批次刪除、使用者編輯、影像檢視器三處實測焦點隔離、Escape 回到觸發鈕；批次刪除 modal 預設焦點在「保留批次」並寫明張數與無法復原，完整修正上次 P1。另有 skip link、44px 主要目標、reduced-motion。
2. 證據串接：偵測／批次可深連結到 Agent 並預填；`SavedResultPicker` 附縮圖且只讀既有結果；provenance 晶片很適合研究者。
3. 可復原狀態：工作台、模型清單、已保存結果、批次輪詢都有重試；輪詢退避並顯示最後更新時間；Agent 失敗把訊息還回輸入框；AI 分頁切換保留草稿。

## 優先問題

### 1. [P1] 看不到模型能偵測哪些類別，預設流程很容易得到 0 結果（實測重現）
- 問題：預設 `seven_class_asff`（backend/app/core/config.py:108），選單只寫「YOLO11n + ASFF (7 classes)」。公車照片配預設模型得到 0 物件，提示要人「確認模型的類別」，但類別只在進階的各類別閾值表。換模型還會直接清掉剛完成的結果（DetectionPage.jsx:148），無法比較。
- 為何重要：第一次偵測就空手而回，對新使用者與展示場合最傷；同時拉低 #2、#6、#10。
- 修法：選單下方顯示類別晶片（多類別可展開）；選項名稱自帶族群（「7 類 · ASFF」）；0 結果時列出該模型類別並提供「改用 COCO 重試」；換模型時保留上次結果直到重新偵測。
- 依據：YoloModelSelect.jsx:29、DetectionPage.jsx:345、ClassThresholdEditor.jsx:105
- 建議指令：/impeccable clarify、/impeccable onboard

### 2. [P1] 主要操作後焦點掉回 `<body>`，完成時沒有公告（以 document.activeElement 實測）
- 問題：送出時把聚焦中的按鈕設成 disabled 或卸載，焦點就掉到 body。重現於登入失敗、開始偵測、Chat 送出、Agent 送出、紀錄頁 inline 刪除、手機清單進詳情、編輯個人資料。偵測完成沒有 role="status" 公告。
- 為何重要：鍵盤／讀屏使用者每做一次主要操作就得從頁首重 Tab；違反 DESIGN.md「成功要有文字」。
- 修法：忙碌時用 aria-disabled 保持可聚焦；完成後焦點移到結果標題並公告「偵測完成：5 個物件，330 ms」；inline 確認出現時聚焦「取消」並支援 Escape，或統一改用共用 Modal。
- 依據：DetectionPage.jsx:213、ChatPage.jsx:363、AgentPage.jsx:623、DetectionHistoryPage.jsx:316
- 建議指令：/impeccable harden

### 3. [P1] 手機版：出結果後整頁橫向溢出，換頁會把選單鈕捲出畫面（375×812 實測）
- .page-stack grid 沒有 minmax(0,1fr)（styles.css:193），被未取整的 bbox（DetectionPage.jsx:340）撐到 428px，整頁 444px 寬並被縮小。
- 換頁 main.focus() 沒加 preventScroll（Layout.jsx:17），頁面捲過非 sticky 的頂列。
- ≤720px 時管理頁搜尋框高 262px（styles.css:2258）。
- 出結果前兩個約 350px 的空白佔位面板。
- 修法：minmax(0,1fr)、bbox 取整數、focus({ preventScroll: true })、欄方向重設 flex-basis、結果前合併成單一上傳區。
- 建議指令：/impeccable adapt

### 4. [P2] 中英混雜，同一個東西有多種名稱
- 紀錄頁幾乎全英文（Status、← Prev／Next →、Task ID、Explain with Agent）；偵測頁 Ask Agent to Explain、Generate Report；管理頁 Edit／Delete；影像檢視器 View／Close／Reset；Chat「1 conversations」。狀態用 CSS 轉大寫 enum（styles.css:1599）。同一模型有顯示名、model_key、.pt 檔名三種寫法；品牌名三種；刪除確認三種模式。
- 修法：單一 zh-TW 文案表、狀態對照表、模型名稱格式化函式；刪除一律用 Modal 並寫明影響範圍。
- 依據：DetectionHistoryPage.jsx:179、UserManagementPage.jsx:291、ZoomableImage.jsx:111
- 建議指令：/impeccable clarify、/impeccable polish

### 5. [P2] Agent 工作區負荷過重，批次缺少能直接算出的彙總
- 打字前要面對 8 個控制項、7 種模式（「一般聊天」和「一般對話」分頁重疊）。1440×900 下插入「分析依據」列與切換警告後，輸入框與「停止接收」被推到折線下。批次頁只提供「用 Agent 分析這批」，但預設問題「各類別總數、幾張沒偵測到」是 DB 能確定算出的數字。
- 修法：批次詳情直接顯示類別 × 影像彙總與零偵測張數（符合「統計用 DB 聚合」）；模式收斂成跟隨所選資料的 2–3 個意圖；版面改 flex column、輸入列 sticky；等待時顯示階段文字。
- 依據：AgentPage.jsx:15、AgentPage.jsx:490、BatchDetectionPage.jsx:438、styles.css:1237
- 建議指令：/impeccable distill、/impeccable layout

## Persona 紅旗

- Sam（鍵盤／讀屏）：七個主要操作後焦點掉回 body；偵測完成無公告；管理頁 DOM 順序與視覺順序相反（order:-1）；影像檢視器 autoFocus 被 showModal() 蓋掉、焦點落在「-」；同名模型選項難以用聽的分辨。
- Casey（手機）：偵測後整頁橫向溢出；每次換頁選單鈕被捲出畫面；結果前約 700px 空白；紀錄詳情「刪除」在最上方、影像排在 6 個欄位之後；管理頁搜尋框 262px 高。
- Jordan（新手）：預設模型 0 結果且看不到類別；術語無解釋；Agent 要先選 7 種模式之一、資料類型、#ID 才能提問；工作台每列都導向「繼續分析」（AI），連 0 物件結果也一樣（DashboardPage.jsx:135）。

## 認知負荷與情緒旅程

認知負荷：8 項中 5 項失敗、1 項部分失敗，屬高負荷。失敗：單一焦點、分組 ≤4、一次一件事、決策點 ≤4、工作記憶；部分：視覺階層。>4 選項決策點：YOLO 模型 12、Agent 模式 7、已保存偵測每頁 20 筆且檔名重複、AI 模型 5（2 個不可用）、紀錄狀態篩選 5 個原始 enum。

情緒旅程：高峰是標註圖出現在原圖旁；低谷一是預設模型 0 結果；低谷二是 Agent 約 30 秒只有游標且輸入列被推出畫面。高風險時刻落差大：批次刪除 modal 令人安心，單筆刪除只有「確定刪除？」、管理員刪人只有「確定？」、授予 Admin 完全沒確認。Agent 報告結束後沒有就地的下一步。

## 次要觀察

- 展開進階閾值後 align-items: stretch（styles.css:2233）把兩個影像面板拉到 1376px 高；COCO 類別表在 213px 欄寬內雙向巢狀捲動。
- 各類別閾值數字欄約 30px、勾選框 16px，低於 DESIGN.md 的 44px（styles.css:2071）。
- 偵測頁「AI 深入分析」排在物件表之前，與 DESIGN.md「檢視證據 → 分析」相反（DetectionPage.jsx:267）。物件表沒有類別小計，也不與標註圖連動。
- 批次產生的單筆混在紀錄中沒標示；「PAGE 1」與「1 / 1」重複。
- Chat 回覆是純文字 <p>，Agent 是 Markdown（ChatPage.jsx:343）。
- 管理頁自己那列仍顯示 Delete（後端有保護）；錯誤帶「Value error,」前綴。
- 批次上傳表單佔滿第一屏，也不會自動選取最新批次。

## 值得思考的問題

- 平台核心產物是「框」，為什麼介面上只以浮點字串出現？標註圖、物件表、AI 回答能否共用一套類別色票與 hover 對應？
- 哪些「分析」應該是確定性 UI（類別總數、零偵測張數），哪些才真的需要 Agent？
- 預設模型要服務研究者自己的 7 類資料，還是第一次看展示的訪客？
- Agent 已有「一般聊天」模式，「一般對話」分頁還要解決什麼？

## 驗證界線

- 已實測：一般使用者與管理員；單張偵測（COCO、4 類、7 類）、批次刪除 modal 與紀錄頁 inline 刪除（皆取消）、Chat／Agent 送出、個人資料編輯、使用者編輯 modal、不合規密碼建立使用者（未建立）；鍵盤 Tab／Escape／檢視器快捷鍵。
- Chat／Agent 實際走本機 Ollama（llama3.2／gemma4），不是設定的 mock：UI 模型選單只列真實 provider。未使用付費 provider；未評論回答品質。
- 沒測到：真實讀屏軟體（結論由 DOM／a11y tree 推斷）、768–1100px 平板、新批次即時輪詢、影片、報告／ZIP 下載、admin_help、註冊、改密碼、慢網路、真實 GPU。
- 環境附註：web-frontend/.env 的 VITE_API_BASE_URL 指向 127.0.0.1:8000，前端繞過 Vite proxy；評估期間以暫存區轉發器處理，已停止。僅影響本機測試設定。
