# Phase 6.3 — 備份與隔離還原驗證

> 專題／階段紀錄：內含初次建置、修復與當時待辦。現行日常操作以 [維運手冊](lab-operations.md) 為準，最新狀態以 [roadmap](roadmap.md) 為準；不要依舊待辦重跑納管或初次部署包。

2026-10-20：Compose backend／nginx、原有資料讀回、GPU 與 Chat／Agent SSE 已通過。原始備份為 `20261020T075232Z-2550504`。第一次重驗（`20261020T080318Z-2554383`）已確認全部備份檔案大小／SHA-256 一致、正式服務正常、暫存資源已清除；SQL 匯入未報錯，兩份 dump 都是 189 行，其中 30 行文字不同。**第二次重驗已通過**（成功報告 `20261020T081258Z-2556729`）：30 行差異全部確認只是等價 utf8mb4 標記（來源 0／還原 30），其餘完整 SQL 位元組一致；所有檔案大小／SHA-256 一致、正式服務正常、暫存資源清除。80／443 當次均未使用。

## 已知的 SQL 表示差異與驗證修正

第一個差異為 `alembic_version.version_num`：欄位仍是 varchar，定義由 65 bytes 增至 87 bytes，精確吻合 MySQL 已確認的 [#110825](https://bugs.mysql.com/bug.php?id=110825)：重建表格後，SHOW CREATE TABLE 可能在既有 `COLLATE utf8mb4_...` 前多印 `CHARACTER SET utf8mb4`。依 [MySQL 8.4 字元集規則](https://dev.mysql.com/doc/refman/8.4/en/charset-column.html)，該 COLLATE 已決定字元集，兩種表示等價。Ubuntu 成功重驗已確認全部 30 行差異都符合此規則。

修正版保留壓縮產物與原始 SQL 的雜湊驗證；SQL 原文不同時，僅在 CREATE TABLE 內 char／varchar／text 類欄位定義的開頭，移除緊鄰明確 utf8mb4 COLLATE 的冗餘 CHARACTER SET 標記，再對**完整 SQL**計算 SHA-256 比對。INSERT 值、DEFAULT 字串、欄位型別、實際 collation、索引、外鍵、AUTO_INCREMENT 與其餘位元組均不放寬；任何其他差異仍失敗，也不改寫或重新匯入修改後的 SQL。

`sql_verification` 記錄原文是否相同、採用的規則、兩份比對用雜湊與冗餘標記數量，並保存原始差異摘要。若只是該等價表示差異，顯示明確 PASS，仍保留私人 `restored.sql.gz` 供追溯；不把原始 SQL 雜湊記成相同。Mac 已完成 50 項部署工具測試，含此問題的 30 欄位案例與資料／結構變動仍須拒絕的案例；沒有在 Mac 執行真實 MySQL 還原。

## 重新驗證參考（這批已通過，不需再次執行）

更新 Ubuntu 的 `deploy/lab_backup_verify.py`，執行：

```bash
conda activate yolo-backend
cd ~/apps/Yolo_system
sudo -v
python deploy/lab_backup_verify.py --verify-existing \
  "$HOME/.local/share/yolo-system/backups/20261020T075232Z-2550504"
```

這個模式先核對原始壓縮產物與解壓 SQL 的雜湊，再建立新的無網路暫存 MySQL 重驗；**不停止 backend、不重新擷取正式 DB，也不覆寫原始備份或原 manifest**。只需留出少量暫存 MySQL CPU／RAM 與磁碟空間，網站可以繼續使用。

SQL 若仍有非等價差異，輸出 `SQL difference: {...}`：差異行數、第一個差異所屬 table／schema 或 data 區塊，以及白名單內的結構 token；不輸出 INSERT 值、帳號、密碼 hash 或對話。兩份 SQL 原文仍只留在私人目錄。所有媒體／設定檔案也會獨立驗證；不略過其他差異強行標記通過。

新 `manifest.json` 與不一致時的 `restored.sql.gz` 存在另一個時間戳目錄，終端機分別列出原始備份與本次驗證報告路徑。回報從 `SQL difference` 開始至結尾的摘要即可，勿貼兩份 SQL 原文。若有實際資料差異仍須修復並重新驗證，不能僅由匯入 exit 0 推論資料完全相同。

## 下一步

原始備份 `20261020T075232Z-2550504` 與成功報告 `20261020T081258Z-2556729` 已下載至 Mac 的 `/Users/SAM/Desktop/Yolo-system-backups/`（父目錄 0700）。2026-10-20 實際執行 `deploy/verify_downloaded_backup.py` 通過：壓縮產物、完整 SQL 與全部 52 個檔案（76,200,654 bytes）SHA-256 一致，成功報告與原始基準相符；未在 Mac 重跑 MySQL 還原。此副本保存的是原始備份時間點，早於公開 HTTPS 更新。校外瀏覽器也已由使用者確認正常；接續 [部署交接](lab-operations.md) 的每日排程、保留輪替與目前部署重建資訊。

## 建立新備份：一次執行

用 VS Code 將 [lab_backup_verify.py](../deploy/lab_backup_verify.py) 放到 Ubuntu 專案的 `deploy/`。它沿用已在該目錄的 `lab_compose_apply.py`，不需重新執行 Compose 納管、不需輸入專案帳密。

網站暫停操作，避免偵測、對話與設定變更；執行：

```bash
conda activate yolo-backend
cd ~/apps/Yolo_system
sudo -v
python deploy/lab_backup_verify.py
```

Python 保持 sam 身分，不使用 sudo python。腳本僅在本次執行期間刷新既有 sudo 驗證，避免較長備份途中逾期；不讀取或保存 sudo 密碼。腳本核對目前 Compose backend、既有 MySQL image／volume、DB 帳號、schema 字元集／collation 與 InnoDB；拒絕進行中的偵測及本流程未支援的 routines／events／其他儲存引擎。共享鎖避免與 Compose 切換批次同時執行。

備份時只短暫停止本專案 backend，以避免 DB 與媒體在不同時間被修改；完成 SQL 與檔案擷取後立即啟動原 backend，隔離還原在背景服務恢復期間進行。MySQL、nginx、Ollama、Docker daemon 與其他人的服務持續運行。一般例外或 Ctrl+C 會嘗試啟動原 backend；主機斷電、Docker／sudo 無法使用或強制終止仍可能需要人工恢復。

成功最後顯示：

```text
PASS: 無網路暫存 MySQL 還原／完整 SQL 等價比對與所有檔案 SHA-256 通過
PASS: 正式 backend／nginx／MySQL 正常；暫存還原資源已清除
HTTPS readiness: 80/443 currently unused
Backup / isolated restore / SQL-files verification: PASS
私人備份與報告：/home/sam/.local/share/yolo-system/backups/<UTC時間>-<PID>
```

80／443 若已被使用，會列出 listener 供下批判讀，不影響備份通過，也不停止該服務。此盤點不能證明校外防火牆允許連線。回報最後約 8 行即可，勿貼 SQL、私人設定或整份備份。

## 產物、保密與驗證界線

每次建立新的私人目錄（0700），不覆蓋舊備份；產物為 0600：

| 產物 | 內容與驗證 |
|---|---|
| `database.sql.gz` | `yolo` schema 的一致性邏輯匯出；同一 MySQL image 的隔離資料庫實際匯入，再比對完整 SQL；僅容許上述已知等價字元集表示差異 |
| `files.tar.gz` | backend/static、全部 YOLO checkpoint、React dist、deploy 工具／Ubuntu 版本快照，以及 backend／MySQL／nginx／Compose 私人設定；每個檔案解至獨立目錄並驗證大小與 SHA-256 |
| `manifest.json` | 通過狀態、來源檔案清單／雜湊、壓縮產物雜湊、正式 MySQL ID、清理結果與 80／443 listener 盤點，不記錄設定內容或密碼 |

還原目標是新建、無對外網路與 port 的 MySQL 容器及獨立 named volume（CPU 2、RAM 2 GiB）。腳本禁止向正式 MySQL 匯入，也禁止刪除正式容器／volume；只清除本次建立且身分符合的暫存還原資源。檔案還原拒絕 symlink、路徑穿越、重複或未列入 manifest 的項目。正式 DB 容器與掛載、backend 與 nginx health 在結束前重驗。

若失敗，不拿這份未通過的備份當作唯一副本。先看終端機階段與 `manifest.json`；SQL 工具錯誤另存私人 `sql-error.log`，可能含資料，勿直接貼公開訊息。清理失敗時保留 `.work` 及相關暫存資源以供查明，不執行 prune 或刪除正式 volume。

備份含密碼、JWT secret、使用者資料與媒體；壓縮不等於加密，禁止上傳 Git。成功後，透過 VS Code Remote 檔案總管的「Download」將整個時間戳目錄下載到 Mac 自己的私人資料夾，保留三個產物。確認下載完整後才有另一台主機的副本；同磁碟備份本身無法防止主機／磁碟故障。

若是 `--verify-existing` 通過，須下載「原始備份」與「本次成功驗證報告」兩個目錄。原始 manifest 保留首次未通過的歷程；新報告以相同產物雜湊指向原始備份，記錄本次成功驗證。不要只下載新報告而漏掉原始 SQL／檔案壓縮檔。

這批尚未安排每日排程、保留輪替或自動 Mac 同步；不會自動刪除歷史備份或媒體。Ollama 模型、Docker image 本體與整份應用程式 Git 原始碼不在此壓縮檔，換機仍需另外交付 image／Git revision 與模型版本。這是 DB／檔案還原驗證，不代表全新主機已完成災難復原演練。

## 本機檢查

`python3 -m unittest discover -s deploy/tests -q` 涵蓋備份檔案完整性、失敗後啟動 backend、拒絕還原／刪除正式 DB、暫存資源歸屬、port 盤點故障，以及既有 Compose 批次測試。Mac 沒有執行真實 MySQL 容器；Ubuntu 一次執行的結果才是這批實際驗收依據。

[MySQL 官方 mysqldump 說明](https://dev.mysql.com/doc/refman/8.4/en/mysqldump.html)：使用 InnoDB `--single-transaction`、`--no-tablespaces`、GTID OFF；移除註解／時間並依 primary key 排序，供同版本隔離還原後比對。
