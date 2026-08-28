# 資料庫設計文件

> **版本**: v0.9 (批次影像分析 Phase 1)  
> **Database**: MySQL 8.0, database name: `yolo`  
> **最後更新**: 2026-07-23

---

## 1. Legacy vs 新版對比

| 項目 | Legacy | 新版 |
|------|--------|------|
| 資料表數量 | 1 (`user`) | 4+ |
| 密碼儲存 | 明文 | bcrypt hash |
| Detection 任務 | 無 | `detection_tasks` |
| Detection 物件 | 無 | `detection_objects` |
| 連線方式 | `pymysql` 直連 | SQLAlchemy ORM |
| Migration | 無 | Alembic |

---

## 2. 實際資料表設計

### 2.1 `users`
```sql
CREATE TABLE users (
    id              INT          NOT NULL AUTO_INCREMENT,
    username        VARCHAR(50)  NOT NULL UNIQUE,
    email           VARCHAR(255) NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    nickname        VARCHAR(50)  NULL,
    avatar          VARCHAR(255) NULL,
    register_time   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_admin        BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    last_login      DATETIME     NULL,
    PRIMARY KEY (id),
    INDEX idx_username (username),
    INDEX idx_email (email)
);
```

補充：
- `email` 在資料表層仍允許 `NULL`，是為了與既有 legacy user 資料相容
- 新的 Web / Desktop 註冊流程已要求 `email` 必填

### 2.2 `detection_tasks`
```sql
CREATE TABLE detection_tasks (
    id                INT          NOT NULL AUTO_INCREMENT,
    user_id           INT          NOT NULL,
    batch_id          INT          NULL,       -- migration 0010, nullable
    source_type       VARCHAR(20)  NOT NULL,   -- image / video
    source_filename   VARCHAR(255) NOT NULL,
    source_image_path VARCHAR(255) NULL,
    result_image_path VARCHAR(255) NULL,
    source_video_path VARCHAR(255) NULL,
    result_video_path VARCHAR(255) NULL,
    preview_image_path VARCHAR(255) NULL,
    model_name        VARCHAR(255) NOT NULL,
    model_key         VARCHAR(100) NULL,       -- migration 0009
    model_sha256      VARCHAR(64)  NULL,       -- migration 0009
    model_class_map_json JSON      NULL,       -- migration 0009
    confidence_threshold FLOAT     NULL,        -- migration 0009
    iou_threshold     FLOAT        NULL,        -- migration 0009
    status            VARCHAR(20)  NOT NULL,   -- pending / processing / completed / failed
    inference_ms      FLOAT        NULL,
    image_width       INT          NULL,
    image_height      INT          NULL,
    frame_count       INT          NULL,
    error_message     TEXT         NULL,
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (batch_id) REFERENCES detection_batches(id) ON DELETE CASCADE,
    INDEX idx_detection_tasks_user_id (user_id),
    INDEX idx_detection_tasks_status (status),
    INDEX idx_detection_tasks_batch_id (batch_id)
);
```

**欄位說明**
- `source_type`
  - `image`: 單張圖片 detection
  - `video`: 單支影片 detection
- `source_image_path` / `result_image_path`
  - image detection 使用
- `source_video_path` / `result_video_path`
  - video detection 使用
- `preview_image_path`
  - video detection 的 preview frame 圖
- `frame_count`
  - video detection 處理的總 frame 數
- `batch_id`
  - 單張/單支影片 detection（`POST /api/detections/image` / `/video`）維持 `NULL`
  - 批次影像上傳（`POST /api/detections/batch`）建立的每一張圖片 task 都會帶入所屬 `detection_batches.id`
  - `status` 在批次流程中新增 `pending`：批次上傳時所有圖片先建立為 `pending`，背景任務逐張推論後才轉為 `completed` / `failed`

### 2.3 `detection_batches`（migration 0010）
```sql
CREATE TABLE detection_batches (
    id                    INT          NOT NULL AUTO_INCREMENT,
    user_id               INT          NOT NULL,
    name                  VARCHAR(255) NULL,
    model_name            VARCHAR(255) NOT NULL,
    model_key             VARCHAR(100) NULL,
    model_sha256          VARCHAR(64)  NULL,
    confidence_threshold  FLOAT        NULL,
    iou_threshold         FLOAT        NULL,
    status                VARCHAR(30)  NOT NULL DEFAULT 'pending',
    -- pending / processing / completed / completed_with_errors / failed
    total_files           INT          NOT NULL DEFAULT 0,
    processed_count       INT          NOT NULL DEFAULT 0,
    failed_count          INT          NOT NULL DEFAULT 0,
    skipped_files         JSON         NULL,
    error_message         TEXT         NULL,
    created_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_detection_batches_user_id (user_id),
    INDEX idx_detection_batches_status (status)
);
```

**用途**：一次「多張影像 / 整個資料夾」上傳（`POST /api/detections/batch`）建立一筆 batch，底下每張圖片各自是一筆獨立的 `detection_tasks`（`batch_id` 指回這裡），沿用既有單張圖片偵測流程與 `detection_objects` 結構，不重造輪子。

**欄位說明**
- `status`
  - `processing`：批次已建立，背景任務正在逐張跑 YOLO 推論
  - `completed`：全部圖片都成功完成
  - `completed_with_errors`：部分圖片推論失敗，其餘成功
  - `failed`：全部圖片都失敗（例如全部上傳失敗，或模型載入失敗）
- `total_files` / `processed_count` / `failed_count`
  - 前端用 `processed_count / total_files` 呈現進度條；`failed_count` 是 `processed_count` 內失敗的子集
- `skipped_files`
  - 上傳時被判定為非圖片格式而略過的檔名清單（例如資料夾內的 `.DS_Store`），不會建立對應的 `detection_tasks`
- Agent 的 `batch_analysis` 模式（`summarize_batch_tool`）會用 SQL `GROUP BY class_name` 聚合這個 batch 底下所有 `detection_objects`，計算「這批影像總共偵測到幾艘船/幾架飛機」之類的問題；「零偵測影像數」只作為「疑似漏檢（估計）」提示，不是確定結論

### 2.4 `detection_objects`
```sql
CREATE TABLE detection_objects (
    id           INT           NOT NULL AUTO_INCREMENT,
    task_id      INT           NOT NULL,
    object_index INT           NOT NULL,
    class_id     INT           NOT NULL,
    class_name   VARCHAR(100)  NOT NULL,
    confidence   FLOAT         NOT NULL,
    bbox_x1      FLOAT         NOT NULL,
    bbox_y1      FLOAT         NOT NULL,
    bbox_x2      FLOAT         NOT NULL,
    bbox_y2      FLOAT         NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (task_id) REFERENCES detection_tasks(id) ON DELETE CASCADE,
    INDEX idx_detection_objects_task_id (task_id)
);
```

**欄位說明**
- `object_index`
  - image detection: 依結果順序自動編號
  - video detection: 若 YOLO track 有提供 ID，則優先使用 tracking id；否則退回順序編號

### 2.5 `chat_logs`
```sql
CREATE TABLE chat_logs (
    id          INT           NOT NULL AUTO_INCREMENT,
    user_id     INT           NOT NULL,
    conversation_id VARCHAR(64) NOT NULL,
    turn_index  INT           NOT NULL,
    provider    VARCHAR(50)   NOT NULL,
    model_name  VARCHAR(100)  NOT NULL,
    question    TEXT          NOT NULL,
    answer      TEXT          NOT NULL,
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX ix_chat_logs_user_id (user_id),
    INDEX ix_chat_logs_conversation_id (conversation_id),
    INDEX ix_chat_logs_created_at (created_at)
);
```

**欄位說明**
- `conversation_id`
  - 同一段對話的識別碼，用於 history 與 context 聚合
- `turn_index`
  - 對話內第幾輪問答
- `provider`
  - 目前支援 `openai`、`deepseek`
- `model_name`
  - 儲存實際回應使用的模型名稱
- `question` / `answer`
  - 先保存單輪聊天內容

---

## 3. 關聯圖

```text
users (1) ──────< detection_tasks (M)
                        │
                        └──< detection_objects (M)

users (1) ──────< detection_batches (M) ──────< detection_tasks (M)
                                                        │
                                                        └──< detection_objects (M)

users (1) ──────< chat_logs (M)
```

---

## 4. Migration 現況

### 已存在 migration
- `0001`: users 初始 migration
- `0002`: users 補充欄位 / auth 相關
- `0003`: 建立 `detection_tasks` / `detection_objects`
- `0004`: 補 `source_video_path` / `result_video_path` / `preview_image_path` / `frame_count`
- `0005`: 建立 `chat_logs`
- `0006`: 補 `conversation_id` / `turn_index`
- `0007`: `users` 新增 `email`，並擴充 `username` 長度
- `0008`: `chat_logs.user_id` FK 改為 `ON DELETE CASCADE`（修復刪除使用者時的 FK 衝突）
- `0009`: `detection_tasks` 新增 `model_key` / `model_sha256` / `model_class_map_json` / `confidence_threshold` / `iou_threshold`（YOLO checkpoint provenance）
- `0010`: 建立 `detection_batches` 表，並在 `detection_tasks` 新增 `batch_id`（nullable FK，`ON DELETE CASCADE`）— 批次影像分析 Phase 1

### 執行指令
```bash
cd /Users/SAM/Desktop/Agents/Yolo_system/backend
alembic upgrade head
```

---

## 5. Storage 對應

| 用途 | 路徑 |
|------|------|
| 原始圖片 | `static/detections/originals` |
| 結果圖片 | `static/detections/results` |
| 原始影片 | `static/detections/videos/originals` |
| 結果影片 | `static/detections/videos/results` |
| 影片 preview 圖 | `static/detections/previews` |

資料表中保存的是相對於 `static/` 的路徑，例如：
- `detections/originals/task_12_a1b2c3d4.jpg`
- `detections/videos/results/task_18_e5f6g7h8.mp4`

---

## 6. 目前限制

- video detection 目前只保存 preview frame 的 detection objects
- webcam / RTSP 目前仍未落地到 detection tables
- chat 目前以 `chat_logs` 聚合多輪上下文，但尚未拆成獨立 `chat_conversations` table
- 批次影像分析（`detection_batches`）目前以 `BackgroundTasks` 依序（非併發）處理，單次上限 `DETECTION_BATCH_MAX_FILES`（預設 100）；尚未支援影片批次或跨批次併發，屬 Phase 6 job queue 待辦範圍
- `summarize_batch_tool` 目前只做「每個類別的總數」聚合，不做 bbox 空間關係判斷（例如「船上有沒有飛機」），屬後續 Phase 待辦

---

## 7. 變更日誌

| 版本 | 日期 | 變更 |
|------|------|------|
| v0.1 | 2026-04-18 | 初稿（Phase 0 規劃） |
| v0.2 | 2026-04-18 | 對齊 Phase 3 實際 detection schema 與 migration |
| v0.3 | 2026-04-19 | 新增 `chat_logs` table 與 Phase 4 chat schema 說明 |
| v0.4 | 2026-04-19 | 補 `conversation_id` / `turn_index` 與 history/context 設計 |
| v0.5 | 2026-04-19 | `users` 新增 `email`，帳號規則改為 username/email + 英數密碼規則 |
| v0.6 | 2026-04-28 | 補充 `email` 欄位 nullable 的 legacy 相容理由與 Phase 5 驗證現況 |
| v0.7 | 2026-07-12 | migration `0008`：`chat_logs.user_id` FK 改為 `ON DELETE CASCADE`；刪除 user 時同步清理 detection / avatar 靜態檔案 |
| v0.8 | 2026-07-14 | migration `0009`：`detection_tasks` 新增 YOLO checkpoint provenance 欄位（`model_key`/`model_sha256`/`model_class_map_json`/`confidence_threshold`/`iou_threshold`） |
| v0.9 | 2026-07-23 | migration `0010`：新增 `detection_batches` 表 + `detection_tasks.batch_id`，支援批次影像分析（Phase 1：多圖上傳 + 每類別總數聚合 + Agent `batch_analysis` 模式） |
