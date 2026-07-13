import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import detectionService from "../services/detectionService";
import { buildAssetUrl, normalizeApiError } from "../services/api";

export default function DetectionPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [conf, setConf] = useState(0.25);
  const [iou, setIou] = useState(0.45);
  const [downloading, setDownloading] = useState(false);

  const previewUrl = useMemo(() => {
    if (!file) {
      return "";
    }
    return URL.createObjectURL(file);
  }, [file]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  async function handleDownloadResult() {
    if (!result?.result_image_url) return;
    setDownloading(true);
    try {
      await detectionService.downloadAsset(
        result.result_image_url,
        `detection_${result.id}_result.jpg`
      );
    } catch (err) {
      setError(normalizeApiError(err, "下載結果圖失敗"));
    } finally {
      setDownloading(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!file) {
      return;
    }

    setLoading(true);
    setError("");

    try {
      const detection = await detectionService.detectImage(file, { conf, iou });
      setResult(detection);
    } catch (err) {
      setError(normalizeApiError(err, "圖片偵測失敗"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="page-header">
        <div>
          <div className="eyebrow">DETECTION</div>
          <h1>Object Detection</h1>
          <p className="muted">Upload an image and use the YOLO model to identify and label detected objects.</p>
        </div>
      </section>

      <section className="panel">
        <form className="form-grid" onSubmit={handleSubmit}>
          <label className="field">
            <span>選擇圖片</span>
            <input
              type="file"
              accept="image/*"
              onChange={(event) => {
                const nextFile = event.target.files?.[0] || null;
                setFile(nextFile);
                setResult(null);
              }}
              required
            />
            <p className="muted small" style={{ marginTop: 6 }}>支援 JPG、PNG、WEBP，單檔最大 10 MB</p>
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
              <span className="threshold-hint">越高 → 只保留高把握的偵測；越低 → 保留更多但可能有誤報</span>
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
              <span className="threshold-hint">越高 → 允許更多重疊框並存；越低 → 更嚴格去除重疊</span>
            </label>
          </div>

          {error ? <div className="alert alert-error" role="alert" aria-live="assertive">{error}</div> : null}

          <button type="submit" className="button" disabled={!file || loading}>
            {loading ? "辨識中..." : "開始偵測"}
          </button>
        </form>
      </section>

      <section className="two-column-grid">
        <div className="panel">
          <h2>Original Image</h2>
          {previewUrl ? (
            <img className="result-image" src={previewUrl} alt="Original preview" />
          ) : (
            <p className="muted">尚未選擇圖片。</p>
          )}
        </div>

        <div className="panel">
          <div className="section-title">
            <h2>Detection Result</h2>
            {result?.result_image_url ? (
              <button
                type="button"
                className="button button-secondary"
                onClick={handleDownloadResult}
                disabled={downloading}
              >
                {downloading ? "下載中..." : "下載結果圖"}
              </button>
            ) : null}
          </div>
          {result?.result_image_url ? (
            <img
              className="result-image"
              src={buildAssetUrl(result.result_image_url)}
              alt={`${file?.name ?? "圖片"} — YOLO 偵測結果`}
            />
          ) : (
            <p className="muted">尚未取得 detection 結果。</p>
          )}
        </div>
      </section>

      {result?.id ? (
        <section className="panel">
          <div className="section-title">
            <h2>AI 深入分析</h2>
            <span className="muted small">Detection ID: {result.id}</span>
          </div>
          <div className="agent-shortcut-row">
            <button
              type="button"
              className="button button-secondary"
              onClick={() =>
                navigate(`/agent?mode=explain_detection&detection_id=${result.id}`)
              }
            >
              Ask Agent to Explain
            </button>
            <button
              type="button"
              className="button button-secondary"
              onClick={() =>
                navigate(`/agent?mode=report&detection_id=${result.id}`)
              }
            >
              Generate Report
            </button>
          </div>
        </section>
      ) : null}

      {result && (
        <section className="panel">
          <div className="section-title">
            <h2>偵測到的物件</h2>
            <span className="muted">
              {result.objects?.length || 0} 個物件 · {result.inference_ms ?? "-"} ms
            </span>
          </div>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">類別</th>
                  <th scope="col">信心值</th>
                  <th scope="col">Bounding Box</th>
                </tr>
              </thead>
              <tbody>
                {result.objects?.length ? (
                  result.objects.map((item) => (
                    <tr key={item.id}>
                      <td>{item.object_index}</td>
                      <td>{item.class_name}</td>
                      <td>{item.confidence.toFixed(3)}</td>
                      <td>{item.bbox.join(", ")}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} className="muted center-cell">
                      未偵測到任何物件。
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
