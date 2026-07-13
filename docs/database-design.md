# 資料庫設計文件

> **版本**: v0.6 (Phase 5 驗證同步)  
> **Database**: MySQL 8.0, database name: `yolo`  
> **最後更新**: 2026-04-28

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
    source_type       VARCHAR(20)  NOT NULL,   -- image / video
    source_filename   VARCHAR(255) NOT NULL,
    source_image_path VARCHAR(255) NULL,
    result_image_path VARCHAR(255) NULL,
    source_video_path VARCHAR(255) NULL,
    result_video_path VARCHAR(255) NULL,
    preview_image_path VARCHAR(255) NULL,
    model_name        VARCHAR(255) NOT NULL,
    status            VARCHAR(20)  NOT NULL,   -- processing / completed / failed
    inference_ms      FLOAT        NULL,
    image_width       INT          NULL,
    image_height      INT          NULL,
    frame_count       INT          NULL,
    error_message     TEXT         NULL,
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_detection_tasks_user_id (user_id),
    INDEX idx_detection_tasks_status (status)
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

### 2.3 `detection_objects`
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

### 2.4 `chat_logs`
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
