import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import detectionService from "../services/detectionService";
import { buildAssetUrl, normalizeApiError } from "../services/api";

const STATUS_OPTIONS = ["", "completed", "failed", "processing", "pending"];
const SOURCE_OPTIONS = ["", "image", "video"];
const RECORD_DATE_FORMAT = new Intl.DateTimeFormat("zh-TW", {
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function formatRecordDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : RECORD_DATE_FORMAT.format(date);
}

export default function DetectionHistoryPage() {
  const navigate = useNavigate();

  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [downloadingAsset, setDownloadingAsset] = useState("");
  const [mobileDetailOpen, setMobileDetailOpen] = useState(false);

  // Filter state
  const [filterStatus, setFilterStatus] = useState("");
  const [filterSource, setFilterSource] = useState("");

  // Pagination state
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const LIMIT = 20;

  const abortRef = useRef(null);
  const listScrollRef = useRef(null);
  const detailScrollRef = useRef(null);

  const rangeStart = total === 0 ? 0 : (page - 1) * LIMIT + 1;
  const rangeEnd = Math.min(page * LIMIT, total);

  const loadHistory = useCallback(
    async (currentPage = 1) => {
      if (abortRef.current) abortRef.current.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setLoading(true);
      setError("");

      try {
        const { items: rows, total: count, totalPages: pages } = await detectionService.listDetections({
          status: filterStatus || undefined,
          source_type: filterSource || undefined,
          limit: LIMIT,
          page: currentPage,
          signal: controller.signal,
        });
        setItems(rows);
        setTotal(count);
        setTotalPages(pages);
        listScrollRef.current?.scrollTo({ top: 0 });

        if (rows.length > 0 && currentPage === 1) {
          const detail = await detectionService.getDetection(rows[0].id);
          setSelected(detail);
        } else if (rows.length === 0) {
          setSelected(null);
        }
        return pages;
      } catch (err) {
        if (err?.name !== "CanceledError") {
          setError(normalizeApiError(err, "無法載入 detection history"));
        }
        return null;
      } finally {
        // A newer load may already be in flight; only the latest request
        // controls the loading spinner.
        if (abortRef.current === controller) {
          setLoading(false);
        }
      }
    },
    [filterStatus, filterSource]
  );

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    setPage(1);
    setMobileDetailOpen(false);
    loadHistory(1);
  }, [filterStatus, filterSource, loadHistory]);

  useEffect(() => {
    detailScrollRef.current?.scrollTo({ top: 0 });
  }, [selected?.id]);

  async function handleSelect(id) {
    try {
      const detail = await detectionService.getDetection(id);
      setSelected(detail);
      setDeleteError("");
      setConfirmDelete(false);
      setMobileDetailOpen(true);
    } catch (err) {
      setError(normalizeApiError(err, "無法載入 detection detail"));
    }
  }

  async function handleDelete() {
    if (!selected) return;

    setDeleting(true);
    setDeleteError("");
    setConfirmDelete(false);
    try {
      await detectionService.deleteDetection(selected.id);
      setSelected(null);
      setMobileDetailOpen(false);
      const pages = await loadHistory(page);
      // Deleting the last item of the last page can leave us on an empty
      // page; clamp back to the new final page.
      if (pages !== null && page > pages) {
        const clamped = Math.max(1, pages);
        setPage(clamped);
        await loadHistory(clamped);
      }
    } catch (err) {
      setDeleteError(normalizeApiError(err, "刪除失敗"));
    } finally {
      setDeleting(false);
    }
  }

  async function handleDownload(pathOrUrl, filename) {
    if (!pathOrUrl) return;
    setDownloadingAsset(pathOrUrl);
    setDeleteError("");
    try {
      await detectionService.downloadAsset(pathOrUrl, filename);
    } catch (err) {
      setDeleteError(normalizeApiError(err, "下載失敗"));
    } finally {
      setDownloadingAsset("");
    }
  }

  function handlePageChange(newPage) {
    setPage(newPage);
    loadHistory(newPage);
    setSelected(null);
    setConfirmDelete(false);
    setMobileDetailOpen(false);
  }

  return (
    <div className="page-stack">
      <section className="page-header">
        <div>
          <div className="eyebrow">DETECTION RECORDS</div>
          <h1>Detection Records</h1>
          <p className="muted">
            Review past detection tasks, object counts, statuses, and available analysis actions.{" "}
            <strong>{total}</strong> records total.
          </p>
        </div>
      </section>

      {/* Filter Bar */}
      <div className="filter-bar">
        <label className="filter-label">
          Status
          <select
            className="filter-select"
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s || "All"}
              </option>
            ))}
          </select>
        </label>

        <label className="filter-label">
          Type
          <select
            className="filter-select"
            value={filterSource}
            onChange={(e) => setFilterSource(e.target.value)}
          >
            {SOURCE_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s || "All"}
              </option>
            ))}
          </select>
        </label>

        {(filterStatus || filterSource) && (
          <button
            type="button"
            className="button button-ghost"
            onClick={() => {
              setFilterStatus("");
              setFilterSource("");
            }}
          >
            × 清除篩選
          </button>
        )}
      </div>

      {error ? <div className="alert alert-error" role="alert" aria-live="assertive">{error}</div> : null}

      <section className={mobileDetailOpen ? "history-layout history-detail-open" : "history-layout"}>
        {/* List Panel */}
        <div className="panel history-panel history-list-panel">
          <div className="panel-header-row history-panel-header">
            <div>
              <h2>Task List</h2>
              <span className="muted small">
                顯示 {rangeStart}-{rangeEnd}，共 {total} 筆
              </span>
            </div>
            <span className="history-page-chip">Page {page}</span>
          </div>

          <div className="history-list-scroll" ref={listScrollRef}>
            {loading ? (
              <p className="muted">載入中...</p>
            ) : (
              <div className="list-stack">
                {items.map((item) => (
                  <button
                    type="button"
                    key={item.id}
                    className={selected?.id === item.id ? "list-item list-item-active" : "list-item"}
                    onClick={() => handleSelect(item.id)}
                    aria-pressed={selected?.id === item.id}
                  >
                    <div className="list-item-head">
                      <div className="list-item-title" title={item.source_filename}>
                        #{item.id} · {item.source_filename}
                      </div>
                      <time className="list-item-date" dateTime={item.created_at || undefined}>
                        {formatRecordDate(item.created_at)}
                      </time>
                    </div>
                    <div className="list-item-meta">
                      <span className={`status-badge status-${item.status}`}>{item.status}</span>
                      <span>{item.source_type}</span>
                      <span>{item.object_count} objects</span>
                    </div>
                  </button>
                ))}
                {!items.length ? <p className="muted">尚無符合條件的記錄。</p> : null}
              </div>
            )}
          </div>

          {/* Pagination remains visible while the records scroll. */}
          <nav className="pagination-row history-pagination" aria-label="Detection records pagination">
            <button
              type="button"
              className="button button-ghost"
              disabled={page <= 1 || loading}
              onClick={() => handlePageChange(page - 1)}
            >
              ← Prev
            </button>
            <span className="muted small">
              {page} / {totalPages}
            </span>
            <button
              type="button"
              className="button button-ghost"
              disabled={page >= totalPages || loading}
              onClick={() => handlePageChange(page + 1)}
            >
              Next →
            </button>
          </nav>
        </div>

        {/* Detail Panel */}
        <div className="panel history-panel history-detail-panel">
          <div className="panel-header-row history-panel-header">
            <div className="history-detail-title">
              <button
                type="button"
                className="button-ghost history-mobile-back"
                onClick={() => setMobileDetailOpen(false)}
              >
                ← Task List
              </button>
              <h2>Selected Detail</h2>
            </div>
            {selected && !confirmDelete && (
              <button
                type="button"
                className="button button-danger"
                disabled={deleting}
                onClick={() => setConfirmDelete(true)}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ marginRight: 6 }}><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/></svg>
                刪除
              </button>
            )}
            {selected && confirmDelete && (
              <div className="inline-confirm">
                <span className="inline-confirm-label">確定刪除？</span>
                <button
                  type="button"
                  className="button button-danger"
                  disabled={deleting}
                  onClick={handleDelete}
                >
                  {deleting ? "刪除中…" : "確認"}
                </button>
                <button
                  type="button"
                  className="button-ghost"
                  onClick={() => setConfirmDelete(false)}
                >
                  取消
                </button>
              </div>
            )}
          </div>

          <div className="history-detail-scroll" ref={detailScrollRef}>
            {deleteError ? <div className="alert alert-error" role="alert" aria-live="assertive">{deleteError}</div> : null}

            {selected ? (
              <div className="detail-stack">
                <div className="detail-grid">
                  <div>
                    <span className="detail-label">Task ID</span>
                    <strong>{selected.id}</strong>
                  </div>
                  <div>
                    <span className="detail-label">Model</span>
                    <strong>{selected.model_name}</strong>
                  </div>
                  <div>
                    <span className="detail-label">Status</span>
                    <span className={`status-badge status-${selected.status}`}>{selected.status}</span>
                  </div>
                  <div>
                    <span className="detail-label">Inference</span>
                    <strong>{selected.inference_ms ?? "-"} ms</strong>
                  </div>
                  <div>
                    <span className="detail-label">Type</span>
                    <strong>{selected.source_type}</strong>
                  </div>
                  <div>
                    <span className="detail-label">Objects</span>
                    <strong>{selected.objects?.length ?? 0}</strong>
                  </div>
                </div>

                <div className="agent-shortcut-row">
                  <button
                    type="button"
                    className="button button-secondary"
                    onClick={() => navigate(`/agent?mode=explain_detection&detection_id=${selected.id}`)}
                  >
                    Explain with Agent
                  </button>
                  <button
                    type="button"
                    className="button button-secondary"
                    onClick={() => navigate(`/agent?mode=report&detection_id=${selected.id}`)}
                  >
                    Generate Report
                  </button>
                  {selected.result_image_url ? (
                    <button
                      type="button"
                      className="button button-secondary"
                      disabled={downloadingAsset === selected.result_image_url}
                      onClick={() =>
                        handleDownload(
                          selected.result_image_url,
                          `detection_${selected.id}_result.jpg`
                        )
                      }
                    >
                      {downloadingAsset === selected.result_image_url ? "下載中..." : "下載結果圖"}
                    </button>
                  ) : null}
                  {selected.result_video_url ? (
                    <button
                      type="button"
                      className="button button-secondary"
                      disabled={downloadingAsset === selected.result_video_url}
                      onClick={() =>
                        handleDownload(
                          selected.result_video_url,
                          `detection_${selected.id}_result.mp4`
                        )
                      }
                    >
                      {downloadingAsset === selected.result_video_url ? "下載中..." : "下載結果影片"}
                    </button>
                  ) : null}
                </div>

                {selected.result_image_url ? (
                  <img
                    className="result-image"
                    src={buildAssetUrl(selected.result_image_url)}
                    alt="Detection detail result"
                  />
                ) : null}

                {selected.objects?.length > 0 && (
                  <div className="table-wrapper">
                    <table>
                      <thead>
                        <tr>
                          <th scope="col">#</th>
                          <th scope="col">Class</th>
                          <th scope="col">Confidence</th>
                          <th scope="col">Bounding Box</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selected.objects.map((obj) => (
                          <tr key={obj.id}>
                            <td>{obj.object_index}</td>
                            <td>{obj.class_name}</td>
                            <td>{obj.confidence.toFixed(3)}</td>
                            <td>{obj.bbox.join(", ")}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ) : (
              <p className="muted">請從左側選擇一筆紀錄。</p>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
