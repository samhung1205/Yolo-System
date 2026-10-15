import { useEffect, useState } from "react";
import detectionService from "../services/detectionService";
import { buildAssetUrl, normalizeApiError } from "../services/api";

/** Read saved artifacts only; selecting a result never starts inference. */
export default function SavedResultPicker({ kind, value, onChange, disabled, onAvailabilityChange }) {
  const [page, setPage] = useState(1);
  const [items, setItems] = useState([]);
  const [pages, setPages] = useState(1);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => { setPage(1); }, [kind]);
  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    const list = kind === "batch" ? detectionService.listBatches : detectionService.listDetections;
    list({ page, limit: 20 }).then((result) => {
      if (active) { setItems(result.items); setPages(result.totalPages); }
    }).catch((err) => { if (active) setError(normalizeApiError(err, "無法載入已保存的結果，請重試")); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [kind, page, revision]);
  useEffect(() => {
    let active = true;
    setSelected(null);
    setDetailError("");
    onAvailabilityChange(false);
    if (!value) return () => { active = false; };
    const read = kind === "batch" ? detectionService.getBatch : detectionService.getDetection;
    read(value).then((result) => {
      if (active) {
        setSelected(result);
        onAvailabilityChange(["completed", "completed_with_errors"].includes(result.status));
      }
    }).catch((err) => { if (active) setDetailError(normalizeApiError(err, "無法讀取這筆結果，請重新選擇")); });
    return () => { active = false; };
  }, [kind, value, revision, onAvailabilityChange]);
  const isBatch = kind === "batch";
  const image = selected?.result_image_url || selected?.preview_image_url;
  return (
    <div className="saved-result-picker">
      <label className="field">
        <span>{isBatch ? "選擇已保存批次" : "選擇已保存偵測"}</span>
        <select value={value} disabled={disabled || loading} onChange={(event) => onChange(event.target.value)}>
          <option value="">{loading ? "載入結果中…" : "請選擇分析資料"}</option>
          {value && !items.some((item) => String(item.id) === String(value)) && <option value={value}>已指定紀錄 #{value}</option>}
          {items.map((item) => <option key={item.id} value={item.id}
            disabled={!["completed", "completed_with_errors"].includes(item.status)}>
            #{item.id} · {isBatch ? item.name || `${item.total_files} 張影像` : item.source_filename}
            {!["completed", "completed_with_errors"].includes(item.status) ? "（尚未完成）" : ""}
          </option>)}
        </select>
      </label>
      {pages > 1 && <div className="pagination-controls">
        <button type="button" className="button-ghost" disabled={disabled || loading || page <= 1} onClick={() => setPage(page - 1)}>上一頁</button>
        <span>{page} / {pages}</span>
        <button type="button" className="button-ghost" disabled={disabled || loading || page >= pages} onClick={() => setPage(page + 1)}>下一頁</button>
      </div>}
      {(error || detailError) && <div role="alert" className="alert alert-error">{detailError || error} <button type="button" className="button-ghost" disabled={disabled} onClick={() => setRevision(revision + 1)}>重試載入</button></div>}
      {!loading && !error && !items.length && <p className="muted small">尚無結果，請先到{isBatch ? "批次分析" : "物件偵測"}完成偵測。</p>}
      {selected && <div className="selected-artifact">
        {image && <img src={buildAssetUrl(image)} alt="目前分析的偵測結果" loading="lazy" />}
        <strong>{isBatch ? selected.name || `批次 #${selected.id}` : selected.source_filename}</strong>
        <span className="muted small">{isBatch ? `${selected.total_files} 張影像` : `${selected.object_count ?? selected.objects?.length ?? 0} 個物件`} · {String(selected.created_at || "").slice(0, 10)}</span>
        {!["completed", "completed_with_errors"].includes(selected.status) && <p role="status">此結果尚未完成，請完成後再分析。</p>}
      </div>}
    </div>
  );
}
