import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import detectionService from "../services/detectionService";
import { buildAssetUrl, normalizeApiError } from "../services/api";

const POLL_INTERVAL_MS = 2000;
const ACTIVE_STATUSES = new Set(["pending", "processing"]);

export default function BatchDetectionPage() {
  const navigate = useNavigate();

  const [files, setFiles] = useState([]);
  const [conf, setConf] = useState(0.25);
  const [iou, setIou] = useState(0.45);
  const [yoloModels, setYoloModels] = useState([]);
  const [modelKey, setModelKey] = useState("");
  const [modelsLoading, setModelsLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const [batches, setBatches] = useState([]);
  const [batchesLoading, setBatchesLoading] = useState(true);
  const [selectedBatch, setSelectedBatch] = useState(null);
  const [deleteError, setDeleteError] = useState("");
  const [deleting, setDeleting] = useState(false);

  const pollTimerRef = useRef(null);
  const fileInputRef = useRef(null);

  const maxFiles = 100;

  const loadBatches = useCallback(async () => {
    setBatchesLoading(true);
    try {
      const { items } = await detectionService.listBatches({ limit: 20 });
      setBatches(items);
      return items;
    } catch (err) {
      setError(normalizeApiError(err, "無法載入批次列表"));
      return [];
    } finally {
      setBatchesLoading(false);
    }
  }, []);

  useEffect(() => {
    detectionService
      .listYoloModels()
      .then((models) => {
        setYoloModels(models);
        const defaultModel =
          models.find((model) => model.available && model.is_default) ||
          models.find((model) => model.available);
        if (defaultModel) setModelKey(defaultModel.key);
      })
      .catch(() => {})
      .finally(() => setModelsLoading(false));

    loadBatches();

    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [loadBatches]);

  // Poll the selected batch while it is still processing.
  useEffect(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    if (!selectedBatch || !ACTIVE_STATUSES.has(selectedBatch.status)) {
      return;
    }
    pollTimerRef.current = setInterval(async () => {
      try {
        const detail = await detectionService.getBatch(selectedBatch.id);
        setSelectedBatch(detail);
        if (!ACTIVE_STATUSES.has(detail.status)) {
          loadBatches();
        }
      } catch {
        // transient polling errors are ignored; next tick retries
      }
    }, POLL_INTERVAL_MS);
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [selectedBatch?.id, selectedBatch?.status, loadBatches]);

  function handleFilesChange(event) {
    const list = Array.from(event.target.files || []);
    setFiles(list);
    setError("");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!files.length) return;
    if (files.length > maxFiles) {
      setError(`一次最多上傳 ${maxFiles} 張影像，目前選擇了 ${files.length} 張。`);
      return;
    }

    setUploading(true);
    setError("");
    try {
      const batch = await detectionService.detectImageBatch(files, {
        conf,
        iou,
        modelKey,
      });
      setSelectedBatch(batch);
      setFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = "";
      await loadBatches();
    } catch (err) {
      setError(normalizeApiError(err, "批次上傳失敗"));
    } finally {
      setUploading(false);
    }
  }

  async function handleSelectBatch(id) {
    try {
      const detail = await detectionService.getBatch(id);
      setSelectedBatch(detail);
      setDeleteError("");
    } catch (err) {
      setError(normalizeApiError(err, "無法載入批次詳情"));
    }
  }

  async function handleDeleteBatch(id) {
    setDeleting(true);
    setDeleteError("");
    try {
      await detectionService.deleteBatch(id);
      if (selectedBatch?.id === id) setSelectedBatch(null);
      await loadBatches();
    } catch (err) {
      setDeleteError(normalizeApiError(err, "刪除批次失敗"));
    } finally {
      setDeleting(false);
    }
  }

  const progressPercent = selectedBatch?.total_files
    ? Math.round((selectedBatch.processed_count / selectedBatch.total_files) * 100)
    : 0;

  return (
    <div className="page-stack">
      <section className="page-header">
        <div>
          <div className="eyebrow">BATCH DETECTION</div>
          <h1>Batch Image Analysis</h1>
          <p className="muted">
            一次上傳多張影像（或整個資料夾），逐張進行 YOLO 偵測，再用 Agent 針對整批結果進行彙總問答。
            單次最多 {maxFiles} 張。
          </p>
        </div>
      </section>

      <section className="panel">
        <form className="form-grid" onSubmit={handleSubmit}>
          <label className="field">
            <span>選擇多張影像（或整個資料夾）</span>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              // Non-standard attribute; lets Chromium browsers pick a whole
              // folder while still degrading gracefully to multi-file select
              // elsewhere.
              webkitdirectory=""
              directory=""
              onChange={handleFilesChange}
            />
            <p className="muted small" style={{ marginTop: 6 }}>
              {files.length > 0
                ? `已選擇 ${files.length} 個檔案`
                : "支援 JPG、PNG、WEBP，單檔最大 10 MB；非圖片檔案會自動略過"}
            </p>
          </label>

          <label className="field">
            <span>選擇推論模型</span>
            <select
              value={modelKey}
              onChange={(event) => setModelKey(event.target.value)}
              disabled={modelsLoading || !yoloModels.some((model) => model.available)}
              required
            >
              {modelsLoading ? <option value="">載入模型清單中...</option> : null}
              {yoloModels.map((model) => (
                <option key={model.key} value={model.key} disabled={!model.available}>
                  {model.display_name}
                  {model.available ? "" : "（不可用）"}
                </option>
              ))}
            </select>
          </label>

          <div className="threshold-controls">
            <label className="threshold-row">
              <span>信心閾值 <strong>(conf = {conf.toFixed(2)})</strong></span>
              <input
                type="range"
                min="0.05"
                max="0.95"
                step="0.05"
                value={conf}
                onChange={(e) => setConf(parseFloat(e.target.value))}
              />
            </label>
            <label className="threshold-row">
              <span>IOU 閾值 <strong>(iou = {iou.toFixed(2)})</strong></span>
              <input
                type="range"
                min="0.05"
                max="0.95"
                step="0.05"
                value={iou}
                onChange={(e) => setIou(parseFloat(e.target.value))}
              />
            </label>
          </div>

          {error ? <div className="alert alert-error" role="alert" aria-live="assertive">{error}</div> : null}

          <button type="submit" className="button" disabled={!files.length || !modelKey || uploading}>
            {uploading ? "上傳中..." : `開始批次偵測（${files.length || 0} 張）`}
          </button>
        </form>
      </section>

      <section className="history-layout">
        <div className="panel">
          <h2>Recent Batches</h2>
          {batchesLoading ? (
            <p className="muted">載入中...</p>
          ) : (
            <div className="list-stack">
              {batches.map((batch) => (
                <button
                  type="button"
                  key={batch.id}
                  className={
                    selectedBatch?.id === batch.id ? "list-item list-item-active" : "list-item"
                  }
                  onClick={() => handleSelectBatch(batch.id)}
                >
                  <div className="list-item-title">
                    #{batch.id} · {batch.name || "batch upload"}
                  </div>
                  <div className="muted small">
                    <span className={`status-badge status-${batch.status}`}>{batch.status}</span>{" "}
                    {batch.processed_count}/{batch.total_files} 張
                    {batch.failed_count ? ` · ${batch.failed_count} 失敗` : ""}
                  </div>
                </button>
              ))}
              {!batches.length ? <p className="muted">尚無批次紀錄。</p> : null}
            </div>
          )}
        </div>

        <div className="panel">
          <div className="panel-header-row">
            <h2>Batch Detail</h2>
            {selectedBatch ? (
              <button
                type="button"
                className="button button-danger"
                disabled={deleting}
                onClick={() => handleDeleteBatch(selectedBatch.id)}
              >
                {deleting ? "刪除中…" : "刪除批次"}
              </button>
            ) : null}
          </div>

          {deleteError ? <div className="alert alert-error" role="alert">{deleteError}</div> : null}

          {selectedBatch ? (
            <div className="detail-stack">
              <div className="detail-grid">
                <div>
                  <span className="detail-label">Batch ID</span>
                  <strong>{selectedBatch.id}</strong>
                </div>
                <div>
                  <span className="detail-label">Status</span>
                  <span className={`status-badge status-${selectedBatch.status}`}>
                    {selectedBatch.status}
                  </span>
                </div>
                <div>
                  <span className="detail-label">Model</span>
                  <strong>{selectedBatch.model_key || selectedBatch.model_name}</strong>
                </div>
                <div>
                  <span className="detail-label">Progress</span>
                  <strong>
                    {selectedBatch.processed_count}/{selectedBatch.total_files}
                  </strong>
                </div>
              </div>

              {ACTIVE_STATUSES.has(selectedBatch.status) ? (
                <div className="batch-progress-bar" role="progressbar" aria-valuenow={progressPercent}>
                  <div className="batch-progress-fill" style={{ width: `${progressPercent}%` }} />
                </div>
              ) : null}

              {selectedBatch.skipped_files?.length ? (
                <p className="muted small">
                  已略過 {selectedBatch.skipped_files.length} 個非圖片檔案：
                  {selectedBatch.skipped_files.join(", ")}
                </p>
              ) : null}

              <div className="agent-shortcut-row">
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() =>
                    navigate(`/agent?mode=batch_analysis&batch_id=${selectedBatch.id}`)
                  }
                >
                  用 Agent 分析這批
                </button>
              </div>

              <div className="batch-task-grid">
                {(selectedBatch.tasks || []).map((task) => (
                  <div key={task.id} className="batch-task-card">
                    {task.result_image_url ? (
                      <img
                        className="batch-task-thumb"
                        src={buildAssetUrl(task.result_image_url)}
                        alt={task.source_filename}
                      />
                    ) : (
                      <div className="batch-task-thumb batch-task-thumb-placeholder">
                        {task.status === "failed" ? "失敗" : "處理中..."}
                      </div>
                    )}
                    <div className="batch-task-meta">
                      <span className="muted small">{task.source_filename}</span>
                      <span className={`status-badge status-${task.status}`}>{task.status}</span>
                      <span className="muted small">{task.object_count} 個物件</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="muted">請從左側選擇一個批次，或上傳新的一批影像。</p>
          )}
        </div>
      </section>
    </div>
  );
}
