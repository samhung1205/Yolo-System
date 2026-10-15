import api, { normalizeApiError } from "./api";

/**
 * Drop the `sig`/`exp` query params (and any origin) from a static asset
 * path/URL, returning a path relative to the API root — e.g.
 * `/static/detections/results/task_1.jpg?sig=...&exp=...` becomes
 * `/static/detections/results/task_1.jpg`. Letting the shared `api`
 * instance request that path means the Authorization header (attached by
 * its request interceptor) grants access instead, so downloads don't
 * depend on the signature still being unexpired.
 */
function _staticPathWithoutSignature(pathOrUrl) {
  try {
    const isAbsolute = /^https?:\/\//i.test(pathOrUrl);
    const parsed = new URL(pathOrUrl, isAbsolute ? undefined : window.location.origin);
    return parsed.pathname;
  } catch {
    return String(pathOrUrl).split("?")[0];
  }
}

/**
 * axios resolves error responses as a Blob when `responseType: "blob"` is
 * set, so the usual `error.response.data.detail` JSON shape isn't directly
 * readable. Decode it back to text/JSON when possible for a useful message.
 */
async function _describeBlobError(error) {
  const data = error?.response?.data;
  if (data instanceof Blob) {
    try {
      const text = await data.text();
      const parsed = JSON.parse(text);
      if (typeof parsed?.detail === "string" && parsed.detail.trim()) {
        return parsed.detail;
      }
    } catch {
      // fall through to generic message below
    }
  }
  return normalizeApiError(error, "下載失敗");
}

/** Trigger a browser "Save As" for an in-memory blob via a throwaway anchor. */
function _saveBlob(blob, filename) {
  const blobUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = blobUrl;
  anchor.download = filename || "download";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(blobUrl);
}

// Image detection is a synchronous request: the backend blocks on YOLO
// model load (cold start) + inference + result-image save before replying.
// The shared axios instance's default timeout (30s) is tuned for fast JSON
// endpoints and is too short for this call, so we override it per-request
// (still using the same `api` instance, no second axios instance created).
// 180s mirrors the desktop client's INFERENCE_TIMEOUT for consistency.
const INFERENCE_TIMEOUT_MS = 180000;

/**
 * Serialize per-class thresholds for the `class_thresholds` form field.
 *
 * The backend expects a JSON object keyed by class id — `{"0": {"conf": 0.2,
 * "iou": 0.4}}` — and treats an absent field as "use the scalar conf/iou for
 * every class", so an empty selection is omitted entirely.
 */
function _appendClassThresholds(formData, classThresholds) {
  if (!classThresholds || Object.keys(classThresholds).length === 0) return;
  formData.append("class_thresholds", JSON.stringify(classThresholds));
}

const detectionService = {
  async detectImage(file, options = {}) {
    const formData = new FormData();
    formData.append("file", file);
    _appendClassThresholds(formData, options.classThresholds);

    const params = new URLSearchParams();
    params.set("conf", String(options.conf ?? 0.25));
    params.set("iou", String(options.iou ?? 0.45));
    if (options.modelKey) {
      params.set("model_key", options.modelKey);
    }

    const response = await api.post(`/api/detections/image?${params.toString()}`, formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      timeout: INFERENCE_TIMEOUT_MS,
    });
    return response.data;
  },

  async listYoloModels() {
    const response = await api.get("/api/yolo-models");
    return response.data;
  },

  /**
   * POST /api/detections/batch — upload multiple images (or a whole folder)
   * for batch YOLO detection. The endpoint stores every file and returns
   * immediately (202); inference itself runs in the background, so callers
   * should poll `getBatch(id)` for progress.
   */
  async detectImageBatch(files, options = {}) {
    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file);
    }
    _appendClassThresholds(formData, options.classThresholds);

    const params = new URLSearchParams();
    params.set("conf", String(options.conf ?? 0.25));
    params.set("iou", String(options.iou ?? 0.45));
    if (options.modelKey) {
      params.set("model_key", options.modelKey);
    }
    if (options.name) {
      params.set("name", options.name);
    }

    const response = await api.post(`/api/detections/batch?${params.toString()}`, formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      timeout: INFERENCE_TIMEOUT_MS,
    });
    return response.data;
  },

  async listBatches({ status, limit = 20, page = 1, signal } = {}) {
    const params = { limit, page };
    if (status) params.status = status;
    const response = await api.get("/api/detections/batches", { params, signal });
    return {
      items: response.data,
      total: parseInt(response.headers["x-total-count"] || "0", 10),
      totalPages: parseInt(response.headers["x-total-pages"] || "1", 10),
    };
  },

  async getBatch(id) {
    const response = await api.get(`/api/detections/batches/${id}`);
    return response.data;
  },

  async deleteBatch(id) {
    await api.delete(`/api/detections/batches/${id}`);
  },

  async listDetections({ status, source_type, limit = 50, page = 1, signal } = {}) {
    const params = { limit, page };
    if (status) params.status = status;
    if (source_type) params.source_type = source_type;
    const response = await api.get("/api/detections", { params, signal });
    return {
      items: response.data,
      total: parseInt(response.headers["x-total-count"] || "0", 10),
      totalPages: parseInt(response.headers["x-total-pages"] || "1", 10),
    };
  },

  async getDetection(id) {
    const response = await api.get(`/api/detections/${id}`);
    return response.data;
  },

  async deleteDetection(id) {
    await api.delete(`/api/detections/${id}`);
  },

  /**
   * Download a detection asset (result image / video) as a local file.
   *
   * `<img>` tags use the short-lived signed `/static/...?sig=&exp=` URLs
   * embedded in API responses (they can't send an Authorization header).
   * Downloads used to re-fetch that same signed URL directly with `fetch()`,
   * but that depends on the signature still being valid *and* on `fetch()`
   * succeeding cross-origin when `VITE_API_BASE_URL` points at a different
   * origin than the page (CORS applies to `fetch()`, unlike `<img>` loads —
   * so a thumbnail could render fine while the download still failed with a
   * generic "Failed to fetch"). To avoid both failure modes, strip the
   * signature and re-request the asset through the shared authenticated
   * `api` axios instance instead, the same one every other working request
   * in the app already uses (Bearer token, same base URL resolution).
   */
  async downloadAsset(pathOrUrl, filename) {
    if (!pathOrUrl) return;

    const assetPath = _staticPathWithoutSignature(pathOrUrl);

    let response;
    try {
      response = await api.get(assetPath, { responseType: "blob" });
    } catch (err) {
      throw new Error(await _describeBlobError(err));
    }

    _saveBlob(
      response.data,
      filename || decodeURIComponent(String(pathOrUrl).split("/").pop().split("?")[0] || "detection-result")
    );
  },

  /**
   * Download every completed result image in a batch as a single .zip.
   * The backend builds the archive on demand (`GET
   * /api/detections/batches/{id}/download`), so this is one authenticated
   * request rather than one per image — avoids browsers blocking/prompting
   * on a burst of simultaneous single-file downloads.
   */
  async downloadBatchZip(batchId, filename) {
    if (!batchId) return;

    let response;
    try {
      response = await api.get(`/api/detections/batches/${batchId}/download`, {
        responseType: "blob",
        timeout: INFERENCE_TIMEOUT_MS,
      });
    } catch (err) {
      throw new Error(await _describeBlobError(err));
    }

    _saveBlob(response.data, filename || `batch_${batchId}_results.zip`);
  },
};

export default detectionService;
