---
target: 全面分析整個網站
total_score: 22
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 4
target_identity: "file:/Users/SAM/Desktop/Agents/Yolo_system/web-frontend/src"
timestamp: 2026-10-15T05-24-31Z
slug: web-frontend-src
---
Method: dual-agent (A: /root/design_assessment · B: /root/evidence_assessment)

**整體評價：22／40，功能基礎完整，操作體驗仍需明顯改善。**

這個網站已具備研究展示平台需要的主要能力，但資訊架構仍偏向「列出所有功能與設定」。最值得投入的方向，是讓「選影像 → 看偵測證據 → 解釋結果 → 匯出」成為整站最清楚的主線。

本次涵蓋全部 10 個頁面、共用元件、路由、CSS 與 service。已檢視正式建置版桌面畫面、390px 手機代表頁，以及圖片視窗鍵盤操作。登入後使用隔離的示範資料，未驗證真實 YOLO、LLM 或資料庫流程；分數屬設計啟發式評估，不是使用者實驗結果。未修改網站原始碼。

**設計辨識度與視覺判斷**

藍色主色、淺色背景、圓角卡片、表單與按鈕整體一致，登入頁也清楚易懂。問題是幾乎所有區塊都有相近的底色、邊框、陰影與留白，重要性被拉平；Dashboard 大幅介紹帳號，偵測頁先展示完整設定，真正的影像與分析證據出現得較晚。

目前的外觀很容易套用到其他管理系統。產品特色應從影像、物件、模型比較與分析來源的呈現建立。建議保留現有識別，先調整資訊層級。

| Nielsen 準則 | 分數 | 主要依據 |
|---|---:|---|
| 系統狀態可見性 | 2/4 | 有 loading／批次進度，但部分模型與輪詢錯誤被隱藏 |
| 符合使用者語言 | 2/4 | 中英文混用，ID、內部模式與 JSON 增加理解負擔 |
| 使用者控制 | 2/4 | 有取消編輯與圖片 Escape，生成缺少停止，批次刪除無確認 |
| 一致性 | 3/4 | 共用樣式良好，刪除與手機操作模式不一致 |
| 錯誤預防 | 2/4 | 有限制與停用狀態，但必要 ID 提示未阻止送出 |
| 辨識優於記憶 | 2/4 | 結果捷徑很好，直接進分析頁仍需記住數字 ID |
| 效率與彈性 | 3/4 | 批次、閾值、下載完整，搜尋與大量資料瀏覽不足 |
| 美感與精簡 | 2/4 | 畫面整齊，但框架與設定占用過多主要空間 |
| 錯誤復原 | 2/4 | 有錯誤提示，批次失敗與連線中斷缺少恢復入口 |
| 說明與協助 | 2/4 | 有實用閾值提示，缺少連貫的任務導引 |
| **合計** | **22/40** | **可用，但需改善主要 UX 弱點** |

**值得保留的三個優點**

- 偵測結果與歷史紀錄能直接帶 mode／ID 進分析頁；批次也有相同捷徑，省掉重填。
- 各類別閾值採漸進展開，切模型會清理不適用的覆寫，並提供重設；適合研究用途。
- 中文 IME 防誤送、歷史分頁、獨立捲動、圖片縮放與下載已具基礎；可在這些成果上補強。

**最優先的五個問題**

**1. [P1] 手機版把導覽與次要面板放在工作之前。**

在 390×844 設定、示範管理員帳號下，導覽區實測約 782px 高；Chat 歷史清單即使空白仍高 680px，輸入區約從整頁 y=2250px 才開始。使用者進入聊天頁，首屏幾乎只看到選單。

修正：手機改為精簡頂列與可收合導覽；Chat 採「對話清單／目前對話」切換，沿用歷史紀錄頁已有的單面板模式。分析頁讓設定可收合。
依據：[響應式規則](/Users/SAM/Desktop/Agents/Yolo_system/web-frontend/src/styles.css:1801)、[聊天堆疊規則](/Users/SAM/Desktop/Agents/Yolo_system/web-frontend/src/styles.css:1857)。對應：`$impeccable adapt`。

**2. [P1] 批次流程缺少足夠的保護與失敗回饋。**

「刪除批次」直接發出刪除請求；歷史與聊天卻有確認。同時，模型清單失敗被吞掉、輪詢持續失敗沒有可見提示，使用者可能只看到無法操作或停住的畫面。

修正：刪除前顯示批次與影像數量；模型失敗提供重試；連續輪詢失敗顯示斷線與最後更新時間，保留已知進度。失敗圖片應能看到原因；重試功能另行評估 backend 範圍。
依據：[直接刪除](/Users/SAM/Desktop/Agents/Yolo_system/web-frontend/src/pages/BatchDetectionPage.jsx:335)、[模型錯誤處理](/Users/SAM/Desktop/Agents/Yolo_system/web-frontend/src/pages/BatchDetectionPage.jsx:58)。對應：`$impeccable harden`。

**3. [P1] 分析頁要求理解系統設定，卻沒有先建立「正在分析什麼」。**

Detection ID、Batch ID 同時出現，缺少可選取既有紀錄的入口與影像摘要。標示 Required 的欄位未納入送出條件；回覆後又直接展示 Tool Calls／References JSON。

修正：提供既有結果選擇器，顯示縮圖、檔名與日期；依模式顯示必要欄位並驗證；把來源呈現為可讀的證據連結，JSON 收到技術詳情。維持 `/chat`、`/agent` 與各自 service 獨立。
依據：[資料欄位](/Users/SAM/Desktop/Agents/Yolo_system/web-frontend/src/pages/AgentPage.jsx:453)、[JSON 輸出](/Users/SAM/Desktop/Agents/Yolo_system/web-frontend/src/pages/AgentPage.jsx:553)。對應：`$impeccable clarify`。

**4. [P1] 自訂元件的鍵盤與讀屏支援不完整。**

已實測：開啟批次結果圖後，焦點正確落在 Close，但按一次 Tab 就移到背景圖片的「下載」，視窗仍開著。Escape 關閉與返回圖片焦點則正常。

其他原始碼確認：管理員編輯視窗缺少完整焦點管理；ModelPicker 未實作 listbox 預期的方向鍵／Escape；各類別數值欄缺少能識別類別與用途的名稱；新聊天回覆缺少公告機制。

修正：補齊 modal 焦點限制與返回、背景 inert、鍵盤行為、欄位名稱及節制的回覆完成公告。保留現有框架。
依據：[圖片視窗](/Users/SAM/Desktop/Agents/Yolo_system/web-frontend/src/components/ZoomableImage.jsx:53)、[閾值欄位](/Users/SAM/Desktop/Agents/Yolo_system/web-frontend/src/components/ClassThresholdEditor.jsx:115)。對應：`$impeccable audit`／`harden`。

**5. [P2] 首頁與偵測頁缺少明確的主要行動。**

Dashboard 用大面積呈現 Role、Account Status、Member Since，再放六至七張同等卡片；這些帳號資訊與側欄重複。偵測頁的模型、滑桿與說明占據首屏，影像工作區被往下推。

修正：首頁突出「開始偵測」與「繼續最近工作」；帳號資料降級。偵測時提早展示選取影像，把閾值保留在可展開的進階設定，專家仍可快速取得。
依據：[首頁層級](/Users/SAM/Desktop/Agents/Yolo_system/web-frontend/src/pages/DashboardPage.jsx:141)、[偵測設定](/Users/SAM/Desktop/Agents/Yolo_system/web-frontend/src/pages/DetectionPage.jsx:127)。對應：`$impeccable distill`／`layout`。

**逐頁分析**

| 頁面 | 判斷與具體改善 |
|---|---|
| 登入 | 最完整的小型流程；密碼顯示按鈕被排除於 Tab 巡覽，空值也因 noValidate 依賴後端回報。補前端驗證與鍵盤可達性。 |
| 註冊 | 版面清楚；帳號／密碼規則只放 placeholder，手機可見截斷，輸入後消失。改為持續可見提示、autocomplete 與欄位驗證；800ms 成功轉跳過快。 |
| Dashboard | 功能目錄清楚，缺少最近工作、明確第一步；縮減帳號展示，建立主次入口。 |
| 單張偵測 | 閾值說明實用；設定過重，零結果缺少下一步。加入檢查模型／調整門檻的情境提示與等待說明。 |
| 批次分析 | 單一 input 永遠帶 webkitdirectory，與「多圖或資料夾」承諾有落差；拆成兩個選擇入口。最近批次只取 20 筆，需可繼續查找。 |
| 偵測紀錄 | 分頁、清單／詳情與手機返回模式值得沿用；補檔名／日期等查找能力，空狀態區分首次使用與篩選無結果。 |
| AI Chat | 與偵測分析定位清楚；非串流等待時缺少立即顯示的待回覆訊息，手機輸入位置嚴重落後。補送出即時回饋與清單切換。 |
| Detection Analyst | 有上下文捷徑；直接進入時缺少結果選擇、預覽、可見歷史與停止生成操作，JSON 削弱報告可讀性。 |
| Profile | 查看／編輯／取消流程合理；桌面標籤與值黏在一起。暱稱提示「留空保持不變」卻會送出 null，需先統一行為與文案。 |
| Admin Users | 建立表單與清單競爭空間；桌面搜尋按鈕已出現兩字直排。清單固定第一批 100 筆，缺分頁；搜尋需標籤與 Enter 行為，編輯視窗需補可及性。 |

**認知負荷與使用者感受**

負擔最高的地方是七個平行導覽項目、七種分析模式，以及直接輸入 ID。各類別設定已採漸進展開，這個原則應延伸到分析設定與技術資料。

旅程中的低谷在「選模型／調參數」和「等待卻不知道是否仍正常運作」；高點是看到標註圖與可下載成果。應用清楚的預設值、執行回饋與可讀來源，讓使用者更有把握地走到成果。

- **Alex，熟練使用者：** 批次與閾值有價值，但歷史查找、清單上限、無停止生成降低效率。
- **Jordan，新使用者：** ID、mode、checkpoint、中英混用與 JSON 讓「選擇分析資料」變成理解系統的考驗。
- **Sam，鍵盤／讀屏使用者：** 圖片視窗焦點逃逸已重現；重複閾值欄位與回覆公告也需要補齊。

**其他需要排程的事項**

- 批次目前一次渲染全部圖片，共用 img 沒有 lazy loading；提高到 1000 張前先做分頁／虛擬化及輕量輪詢。尚未量測效能，不能宣稱目前已卡頓。
- 未設定 provider 時對一般使用者顯示 backend/.env，應改為可理解的不可用原因，技術操作放詳情。
- 顏色、陰影、圓角已有 tokens；優先減少重複容器與調整密度，再做字級和間距收尾。
- 建議之後用 `$impeccable init` 記錄研究者／展示觀眾的優先任務；目前缺 PRODUCT.md／DESIGN.md，但不影響本次檢查。

**自動檢查與證據界線**

detector 僅發現 **1 個 warning、0 error**：`styles.css:1742` 的進度條使用 `transition: width`，會觸發 layout。這是 P3 小問題，沒有確認的誤報，也不能據此判定整站慢。人工檢查找到的操作問題比這項機械規則更重要；「只有一項」不代表通過完整 UX／無障礙稽核。

`npm run build` 通過；初始 JavaScript 約 496KB、gzip 約 155KB。這只是產物大小，未量測 Lighthouse、Core Web Vitals、對比或真實推論耗時。

**後續方向問題**

1. 優先處理哪組：A「手機＋鍵盤可及性」、B「偵測→分析流程」、C「首頁＋資訊層級」？
2. 改善範圍偏向哪個：A「先修四項 P1，保留外觀」、B「全部 UX 問題，保留視覺識別」、C「UX 與版面視覺一起調整」？
