import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router";

import ClassThresholdEditor from "../components/ClassThresholdEditor";
import YoloModelSelect, { orderedClassNames } from "../components/YoloModelSelect";
import ThresholdSummary from "../components/ThresholdSummary";
import ZoomableImage from "../components/ZoomableImage";
import detectionService from "../services/detectionService";
import { buildAssetUrl, normalizeApiError } from "../services/api";

const MIN_CONF = 0.05;

/** Pixel coordinates: sub-pixel precision adds noise and widens the table. */
function formatBbox(bbox) {
  return (bbox || []).map((value) => Math.round(value)).join(", ");
}

export default function DetectionPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [conf, setConf] = useState(0.25);
  const [iou, setIou] = useState(0.45);
  const [perClassEnabled, setPerClassEnabled] = useState(false);
  const [classThresholds, setClassThresholds] = useState({});
  const [downloading, setDownloading] = useState(false);
  const [yoloModels, setYoloModels] = useState([]);
  const [modelKey, setModelKey] = useState("");
  const [modelsLoading, setModelsLoading] = useState(true);
  const [modelsError, setModelsError] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  const submitRef = useRef(null);
  const resultsHeadingRef = useRef(null);
  const advancedRef = useRef(null);
  const confInputRef = useRef(null);
  const focusResultsRef = useRef(false);

  const unavailableModels = useMemo(
    () => yoloModels.filter((model) => !model.available),
    [yoloModels]
  );

  const selectedModel = useMemo(
    () => yoloModels.find((model) => model.key === modelKey),
    [yoloModels, modelKey]
  );

  const resultModel = useMemo(
    () => yoloModels.find((model) => model.key === result?.model_key),
    [yoloModels, result?.model_key]
  );

  const cocoModel = useMemo(
    () => yoloModels.find((model) => model.available && model.task !== "obb"
      && /\bcoco\b/i.test(model.dataset_variant || "")),
    [yoloModels]
  );

  const resultClassNames = orderedClassNames(
    result?.model_class_map?.canonical || resultModel?.canonical_class_names
  );
  const resultIsStale = Boolean(result?.model_key && modelKey && result.model_key !== modelKey);

  // Move focus to the results only when it is still on the submit button,
  // so a user who moved on during a long inference is not pulled back.
  useEffect(() => {
    if (!focusResultsRef.current || !result) return;
    focusResultsRef.current = false;
    if (document.activeElement === submitRef.current || document.activeElement === document.body) {
      resultsHeadingRef.current?.focus();
    }
  }, [result]);

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

  useEffect(() => {
    let active = true;

    detectionService
      .listYoloModels()
      .then((models) => {
        if (!active) return;
        setYoloModels(models);
        const defaultModel =
          models.find((model) => model.available && model.is_default) ||
          models.find((model) => model.available);
        if (defaultModel) {
          setModelKey(defaultModel.key);
        } else {
          setModelsError("目前沒有可用的 YOLO checkpoint。");
        }
      })
      .catch((err) => {
        if (!active) return;
        setModelsError(normalizeApiError(err, "無法取得 YOLO 模型清單"));
      })
      .finally(() => {
        if (active) setModelsLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

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

  async function runDetection(key, thresholds) {
    if (!file || !key || loading) {
      return;
    }

    setLoading(true);
    setError("");
    setStatusMessage("正在偵測，請稍候。");

    try {
      const detection = await detectionService.detectImage(file, {
        conf,
        iou,
        modelKey: key,
        classThresholds: thresholds,
      });
      const count = detection.objects?.length || 0;
      focusResultsRef.current = true;
      setResult(detection);
      setStatusMessage(count
        ? `偵測完成：找到 ${count} 個物件，耗時 ${detection.inference_ms ?? "-"} ms。`
        : "偵測完成：沒有偵測到物件。");
    } catch (err) {
      setStatusMessage("");
      setError(normalizeApiError(err, "圖片偵測失敗"));
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    runDetection(modelKey, perClassEnabled ? classThresholds : null);
  }

  function retryWithCoco() {
    // Per-class overrides are keyed by the previous model's class ids and
    // cannot apply to COCO, so the retry uses the global thresholds only.
    setModelKey(cocoModel.key);
    setPerClassEnabled(false);
    setClassThresholds({});
    runDetection(cocoModel.key, null);
  }

  function openConfidenceSetting() {
    if (advancedRef.current) advancedRef.current.open = true;
    confInputRef.current?.focus();
  }

  return (
    <div className="page-stack detection-page">
      <section className="page-header">
        <div>
          <h1>物件偵測</h1>
          <p className="muted">選擇影像與模型，對照原圖、標註結果與偵測物件。</p>
        </div>
      </section>

      <div className="detection-workspace">
      <section className="panel detection-config">
        <h2>偵測設定</h2>
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

          <YoloModelSelect models={yoloModels} value={modelKey} loading={modelsLoading}
            onChange={setModelKey} />

          {modelsError ? (
            <div className="alert alert-error" role="alert">
              {modelsError}
            </div>
          ) : null}

          {unavailableModels.length ? (
            <details className="model-availability">
              <summary>{unavailableModels.length} 個 checkpoint 暫不可用</summary>
              <ul>
                {unavailableModels.map((model) => (
                  <li key={model.key}>
                    <strong>{model.display_name}</strong>：{model.unavailable_reason}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}

          <details className="advanced-settings" ref={advancedRef}>
            <ThresholdSummary conf={conf} iou={iou} />
          <div className="threshold-controls">
            <label className="threshold-row">
              <span>信心閾值 <strong>(conf = {conf.toFixed(2)})</strong></span>
              <input
                ref={confInputRef}
                type="range"
                min={MIN_CONF}
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

          <ClassThresholdEditor
            classNames={selectedModel?.canonical_class_names}
            enabled={perClassEnabled}
            onToggle={setPerClassEnabled}
            values={classThresholds}
            onChange={setClassThresholds}
            defaultConf={conf}
            defaultIou={iou}
            disabled={loading}
          />

          </details>

          {error ? <div className="alert alert-error" role="alert" aria-live="assertive">{error}</div> : null}

          <button ref={submitRef} type="submit" className="button" disabled={!file || !modelKey}
            aria-disabled={loading || undefined}>
            {loading ? "辨識中…" : "開始偵測"}
          </button>
        </form>
        <p className="sr-only" role="status">{statusMessage}</p>
      </section>

      <section className="two-column-grid detection-media-grid">
        <div className={previewUrl ? "panel detection-media-panel" : "panel detection-media-panel is-empty"}>
          <div className="section-title detection-media-header">
            <h2>原始影像</h2>
          </div>
          <div className="detection-media-body">
            {previewUrl ? (
              <ZoomableImage
                src={previewUrl}
                alt="Original preview"
                title="原始影像"
              />
            ) : (
              <p className="muted">先選擇圖片，原圖會顯示在這裡。</p>
            )}
          </div>
        </div>

        <div className={result?.result_image_url ? "panel detection-media-panel" : "panel detection-media-panel is-empty"}>
          <div className="section-title detection-media-header">
            <h2>標註結果</h2>
            {result?.result_image_url ? (
              <button
                type="button"
                className="button button-secondary"
                onClick={handleDownloadResult}
                disabled={downloading}
              >
                {downloading ? "下載中…" : "下載"}
              </button>
            ) : null}
          </div>
          <div className="detection-media-body">
            {result?.result_image_url ? (
              <ZoomableImage
                src={buildAssetUrl(result.result_image_url)}
                alt={`${file?.name ?? "圖片"} — YOLO 偵測結果`}
                title="標註結果"
              />
            ) : (
              <p className="muted">完成偵測後，這裡會顯示標註結果。</p>
            )}
          </div>
        </div>
      </section>

      </div>

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
            <h2 ref={resultsHeadingRef} tabIndex={-1}>偵測到的物件</h2>
            <span className="muted">
              {result.objects?.length || 0} 個物件 · {result.inference_ms ?? "-"} ms
            </span>
          </div>
          {resultIsStale ? (
            <p className="alert alert-warning result-stale-note">
              以下是 {resultModel?.display_name || result.model_key} 的結果；已改選
              {" "}{selectedModel?.display_name || modelKey}，按「開始偵測」後更新。
            </p>
          ) : null}
          <div className="model-provenance result-provenance">
            <span>{result.model_key || result.model_name}</span>
            <span>conf {result.confidence_threshold ?? conf}</span>
            <span>IoU {result.iou_threshold ?? iou}</span>
            {result.model_sha256 ? (
              <code>sha256:{result.model_sha256.slice(0, 12)}</code>
            ) : null}
          </div>
          {result.class_thresholds ? (
            <div className="model-provenance result-provenance">
              <span>各類別自訂閾值</span>
              {Object.entries(result.class_thresholds).map(([classId, threshold]) => (
                <span key={classId}>
                  {result.model_class_map?.canonical?.[classId] || `#${classId}`}: conf{" "}
                  {threshold.conf} / IoU {threshold.iou}
                </span>
              ))}
            </div>
          ) : null}
          {result.objects?.length ? (
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
                  {result.objects.map((item) => (
                    <tr key={item.id}>
                      <td>{item.object_index}</td>
                      <td>{item.class_name}</td>
                      <td>{item.confidence.toFixed(3)}</td>
                      <td>{formatBbox(item.bbox)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="detection-empty-result">
              <p className="detection-empty-title">這次沒有偵測到物件。</p>
              {resultClassNames.length ? (
                <p className="muted">
                  {resultModel?.display_name || result.model_key} 只會找出這 {resultClassNames.length} 類：
                  {resultClassNames.length > 12
                    ? `${resultClassNames.slice(0, 10).join("、")} 等`
                    : resultClassNames.join("、")}
                  。影像中沒有這些物件時，結果就會是空的。
                </p>
              ) : null}
              <div className="action-row">
                {cocoModel && cocoModel.key !== result.model_key ? (
                  <button type="button" className="button" onClick={retryWithCoco}
                    aria-disabled={loading || undefined}>
                    改用 COCO {cocoModel.class_count} 類模型重試
                  </button>
                ) : null}
                {conf > MIN_CONF ? (
                  <button type="button" className="button button-secondary" onClick={openConfidenceSetting}>
                    調低信心閾值
                  </button>
                ) : null}
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
