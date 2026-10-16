import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import ClassThresholdEditor from "../components/ClassThresholdEditor";
import YoloModelSelect from "../components/YoloModelSelect";
import ThresholdSummary from "../components/ThresholdSummary";
import ZoomableImage from "../components/ZoomableImage";
import Modal from "../components/Modal";
import detectionService from "../services/detectionService";
import { buildAssetUrl, normalizeApiError } from "../services/api";

const POLL_INTERVAL_MS = 2000;
const ACTIVE_STATUSES = new Set(["pending", "processing"]);

export default function BatchDetectionPage() {
  const navigate = useNavigate();

  const [modelsError, setModelsError] = useState("");
  const [modelsRevision, setModelsRevision] = useState(0);
  const [pollError, setPollError] = useState("");
  const [pollRevision, setPollRevision] = useState(0);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [batchPage, setBatchPage] = useState(1);
  const [batchPages, setBatchPages] = useState(1);
  const [files, setFiles] = useState([]);
  const [conf, setConf] = useState(0.25);
  const [iou, setIou] = useState(0.45);
  const [perClassEnabled, setPerClassEnabled] = useState(false);
  const [classThresholds, setClassThresholds] = useState({});
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
  const [downloadingAsset, setDownloadingAsset] = useState("");
  const [downloadError, setDownloadError] = useState("");

  const pollTimerRef = useRef(null);
  const fileInputRef = useRef(null);
  const folderInputRef = useRef(null);
  const selectSequenceRef = useRef(0);

  const maxFiles = 100;

  const selectedModel = useMemo(
    () => yoloModels.find((model) => model.key === modelKey),
    [yoloModels, modelKey]
  );

  const loadBatches = useCallback(async () => {
    setBatchesLoading(true);
    try {
      const { items, totalPages } = await detectionService.listBatches({ limit: 20, page: batchPage });
      setBatchPages(totalPages);
      setBatches(items);
      return items;
    } catch (err) {
      setError(normalizeApiError(err, "無法載入批次列表"));
      return [];
    } finally {
      setBatchesLoading(false);
    }
  }, [batchPage]);

  useEffect(() => {
    let active = true;
    setModelsLoading(true); setModelsError("");
    detectionService
      .listYoloModels()
      .then((models) => {
        if (!active) return;
        setYoloModels(models);
        const defaultModel =
          models.find((model) => model.available && model.is_default) ||
          models.find((model) => model.available);
        if (defaultModel) setModelKey((current) => models.some((item) => item.key === current && item.available) ? current : defaultModel.key);
        else { setModelKey(""); setModelsError("目前沒有可用的模型，請聯絡管理員或重試。"); }
      })
      .catch((err) => { if (active) setModelsError(normalizeApiError(err, "無法載入模型，請重試")); })
      .finally(() => { if (active) setModelsLoading(false); });

    loadBatches();

    return () => { active = false; };
  }, [loadBatches, modelsRevision]);

  // Schedule after each response, so slow polls cannot overlap.
  useEffect(() => {
    let active = true;
    let failures = 0;
    setPollError("");
    if (!selectedBatch || !ACTIVE_STATUSES.has(selectedBatch.status)) return undefined;
    async function poll() {
      try {
        const detail = await detectionService.getBatch(selectedBatch.id);
        if (!active) return;
        failures = 0; setPollError(""); setLastUpdated(new Date()); setSelectedBatch(detail);
        if (!ACTIVE_STATUSES.has(detail.status)) { loadBatches(); return; }
      } catch {
        if (!active) return;
        failures += 1;
        if (failures >= 3) setPollError("暫時無法更新進度。已保留最後結果，正在嘗試重新連線。");
      }
      if (active) pollTimerRef.current = setTimeout(poll, Math.min(POLL_INTERVAL_MS * Math.max(1, failures), 15000));
    }
    pollTimerRef.current = setTimeout(poll, POLL_INTERVAL_MS);
    return () => { active = false; clearTimeout(pollTimerRef.current); };
  }, [selectedBatch?.id, selectedBatch?.status, loadBatches, pollRevision]);

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

    if (files.some((file) => file.size > 10 * 1024 * 1024)) {
      setError("有檔案超過 10 MB，請縮小或移除後重新選擇。"); return;
    }
    setUploading(true);
    setError("");
    try {
      const batch = await detectionService.detectImageBatch(files, {
        conf,
        iou,
        modelKey,
        classThresholds: perClassEnabled ? classThresholds : null,
      });
      selectSequenceRef.current += 1;
      setSelectedBatch(batch);
      setLastUpdated(new Date());
      setConfirmDelete(false);
      setFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = "";
      if (folderInputRef.current) folderInputRef.current.value = "";
      await loadBatches();
    } catch (err) {
      setError(normalizeApiError(err, "批次上傳失敗"));
    } finally {
      setUploading(false);
    }
  }

  async function handleSelectBatch(id) {
    const sequence = ++selectSequenceRef.current;
    setConfirmDelete(false);
    try {
      const detail = await detectionService.getBatch(id);
      if (sequence !== selectSequenceRef.current) return;
      setLastUpdated(new Date());
      setSelectedBatch(detail);
      setDeleteError("");
    } catch (err) {
      setError(normalizeApiError(err, "無法載入批次詳情"));
    }
  }

  async function handleDownloadTaskImage(task) {
    if (!task.result_image_url) return;
    const key = `task-${task.id}`;
    setDownloadingAsset(key);
    setDownloadError("");
    try {
      await detectionService.downloadAsset(
        task.result_image_url,
        `${task.source_filename?.replace(/\.[^.]+$/, "") || `task_${task.id}`}_result.jpg`
      );
    } catch (err) {
      setDownloadError(normalizeApiError(err, "下載失敗"));
    } finally {
      setDownloadingAsset("");
    }
  }

  async function handleDownloadBatchZip() {
    if (!selectedBatch) return;
    setDownloadingAsset("batch-zip");
    setDownloadError("");
    try {
      await detectionService.downloadBatchZip(
        selectedBatch.id,
        `batch_${selectedBatch.id}_results.zip`
      );
    } catch (err) {
      setDownloadError(normalizeApiError(err, "整批下載失敗"));
    } finally {
      setDownloadingAsset("");
    }
  }

  async function handleDeleteBatch(id) {
    setDeleting(true);
    setDeleteError("");
    try {
      await detectionService.deleteBatch(id);
      setConfirmDelete(false);
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
          <h1>批次影像分析</h1>
          <p className="muted">
            一次上傳多張影像（或整個資料夾），逐張進行 YOLO 偵測，再用 Agent 針對整批結果進行彙總問答。
            單次最多 {maxFiles} 張。
          </p>
        </div>
      </section>

      <section className="panel">
        <form className="form-grid" onSubmit={handleSubmit}>
          <label className="field">
            <span>選擇多張影像</span>
            <input
              ref={fileInputRef}
              disabled={uploading}
              type="file"
              accept="image/*"
              multiple
              onChange={handleFilesChange}
            />
            <p className="muted small" style={{ marginTop: 6 }}>
              {files.length > 0
                ? `已選擇 ${files.length} 個檔案`
                : "支援 JPG、PNG、WEBP，單檔最大 10 MB；非圖片檔案會自動略過"}
            </p>
          </label>

          <label className="field">
            <span>或選擇整個資料夾</span>
            <input ref={folderInputRef} type="file" accept="image/*" multiple webkitdirectory="" directory=""
              disabled={uploading} onChange={handleFilesChange} />
          </label>
          <p className="muted small" role="status">已選擇 {files.length} 個檔案；重新選擇會取代目前清單。</p>
          <YoloModelSelect models={yoloModels} value={modelKey} loading={modelsLoading}
            onChange={setModelKey} />

          {modelsError && <div className="alert alert-error" role="alert">{modelsError}
            <button type="button" className="button-ghost" onClick={() => setModelsRevision((value) => value + 1)}>重試模型載入</button>
          </div>}
          <details className="advanced-settings">
            <ThresholdSummary conf={conf} iou={iou} />
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

          <ClassThresholdEditor
            classNames={selectedModel?.canonical_class_names}
            enabled={perClassEnabled}
            onToggle={setPerClassEnabled}
            values={classThresholds}
            onChange={setClassThresholds}
            defaultConf={conf}
            defaultIou={iou}
            disabled={uploading}
          />

          </details>

          {error ? <div className="alert alert-error" role="alert" aria-live="assertive">{error}</div> : null}

          <button type="submit" className="button" disabled={!files.length || !modelKey || uploading || modelsLoading || Boolean(modelsError)}>
            {uploading ? "上傳中..." : `開始批次偵測（${files.length || 0} 張）`}
          </button>
        </form>
      </section>

      <section className="batch-review-layout">
        <div className="panel batch-review-panel">
          <div className="panel-header-row batch-review-header">
            <h2>批次紀錄</h2>
            <div className="pagination-controls" aria-label="批次紀錄分頁">
              <button type="button" className="button-ghost" disabled={batchesLoading || batchPage <= 1} onClick={() => setBatchPage(batchPage - 1)}>上一頁</button>
              <span>{batchPage} / {batchPages}</span>
              <button type="button" className="button-ghost" disabled={batchesLoading || batchPage >= batchPages} onClick={() => setBatchPage(batchPage + 1)}>下一頁</button>
            </div>
          </div>
          <div className="batch-review-scroll">
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
        </div>

        <div className="panel batch-review-panel">
          <div className="panel-header-row batch-review-header">
            <h2>批次詳情</h2>
            {selectedBatch ? (
              <button
                type="button"
                className="button button-danger"
                disabled={deleting || ACTIVE_STATUSES.has(selectedBatch.status)}
                onClick={() => setConfirmDelete(true)}
              >
                {deleting ? "刪除中…" : "刪除批次"}
              </button>
            ) : null}
          </div>

          <div className="batch-review-scroll">
            {confirmDelete && selectedBatch && <Modal aria-labelledby="batch-delete-title" onClose={() => { if (!deleting) setConfirmDelete(false); }}>
              <div className="modal-panel">
                <h2 id="batch-delete-title">刪除批次 #{selectedBatch.id}？</h2>
                <p>此操作會刪除整批 {selectedBatch.total_files} 張影像的偵測紀錄與結果檔案，無法復原。</p>
                <div className="action-row">
                  <button autoFocus type="button" className="button button-secondary" disabled={deleting} onClick={() => setConfirmDelete(false)}>保留批次</button>
                  <button type="button" className="button button-danger" disabled={deleting} onClick={() => handleDeleteBatch(selectedBatch.id)}>{deleting ? "刪除中…" : "確認刪除整批"}</button>
                </div>
                {deleteError && <p role="alert">{deleteError}</p>}
              </div>
            </Modal>}
            {pollError && <div className="alert alert-error" role="status">{pollError}
              {lastUpdated && <span>最後更新：{lastUpdated.toLocaleTimeString("zh-TW")}</span>}
              <button type="button" className="button-ghost" onClick={() => setPollRevision((value) => value + 1)}>立即重新連線</button>
            </div>}
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
                  <div className="batch-progress-bar" role="progressbar" aria-label="批次偵測完成進度" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progressPercent}>
                    <div className="batch-progress-fill" style={{ width: `${progressPercent}%` }} />
                  </div>
                ) : null}

                {selectedBatch.class_thresholds ? (
                  <div className="model-provenance">
                    <span>各類別自訂閾值</span>
                    {Object.entries(selectedBatch.class_thresholds).map(([classId, threshold]) => (
                      <span key={classId}>
                        {selectedModel?.canonical_class_names?.[classId] || `#${classId}`}: conf{" "}
                        {threshold.conf} / IoU {threshold.iou}
                      </span>
                    ))}
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
                  <button
                    type="button"
                    className="button button-secondary"
                    disabled={
                      downloadingAsset === "batch-zip" ||
                      !(selectedBatch.tasks || []).some((task) => task.result_image_url)
                    }
                    onClick={handleDownloadBatchZip}
                  >
                    {downloadingAsset === "batch-zip" ? "打包中..." : "整批下載（ZIP）"}
                  </button>
                </div>

                {downloadError ? (
                  <div className="alert alert-error" role="alert" aria-live="assertive">
                    {downloadError}
                  </div>
                ) : null}

                <div className="batch-task-grid">
                  {(selectedBatch.tasks || []).map((task) => (
                    <div key={task.id} className="batch-task-card">
                      {task.result_image_url ? (
                        <ZoomableImage
                          src={buildAssetUrl(task.result_image_url)}
                          alt={task.source_filename}
                          title={task.source_filename || `Detection ${task.id}`}
                          imageClassName="batch-task-thumb"
                          triggerClassName="batch-task-image-trigger"
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
                        {task.status === "failed" && <p className="field-hint field-hint-warning">{task.error_message || "此影像偵測失敗，請檢查檔案後重新上傳。"}</p>}
                        {task.result_image_url ? (
                          <button
                            type="button"
                            className="button-ghost batch-task-download"
                            disabled={downloadingAsset === `task-${task.id}`}
                            onClick={() => handleDownloadTaskImage(task)}
                          >
                            {downloadingAsset === `task-${task.id}` ? "下載中..." : "下載"}
                          </button>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="muted">請從左側選擇一個批次，或上傳新的一批影像。</p>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
