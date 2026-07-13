import api, { buildAssetUrl } from "./api";

const detectionService = {
  async detectImage(file, options = {}) {
    const formData = new FormData();
    formData.append("file", file);

    const params = new URLSearchParams();
    params.set("conf", String(options.conf ?? 0.25));
    params.set("iou", String(options.iou ?? 0.45));

    const response = await api.post(`/api/detections/image?${params.toString()}`, formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data;
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
   * API responses return signed `/static/...?sig=&exp=` URLs so downloads work
   * without Authorization headers.
   */
  async downloadAsset(pathOrUrl, filename) {
    if (!pathOrUrl) return;

    const url = /^https?:\/\//i.test(pathOrUrl) ? pathOrUrl : buildAssetUrl(pathOrUrl);

    let response = await fetch(url, { credentials: "omit" });
    if (!response.ok && !/^https?:\/\//i.test(url) && pathOrUrl.startsWith("/static/")) {
      response = await fetch(buildAssetUrl(pathOrUrl), { credentials: "omit" });
    }
    if (!response.ok) {
      throw new Error(`下載失敗（HTTP ${response.status}）`);
    }
    const blob = await response.blob();
    const blobUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = blobUrl;
    anchor.download =
      filename || decodeURIComponent(String(pathOrUrl).split("/").pop() || "detection-result");
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(blobUrl);
  },
};

export default detectionService;
