import api, { AUTH_STORAGE_KEY, getStoredSession } from "./api";

const agentService = {
  /**
   * POST /api/agent/chat
   *
   * @param {string} message
   * @param {{ conversationId?: string, mode?: string, detectionId?: number, stream?: boolean }} options
   */
  async sendAgentMessage(message, options = {}) {
    const { conversationId, mode, detectionId, stream, provider, model } = options;
    const payload = {
      message,
      mode: mode || "auto",
    };
    if (conversationId) payload.conversation_id = conversationId;
    if (detectionId != null) payload.detection_id = detectionId;
    if (stream != null) payload.stream = stream;
    if (provider) payload.provider = provider;
    if (model) payload.model = model;
    const response = await api.post("/api/agent/chat", payload);
    return response.data;
  },

  /**
   * POST /api/agent/chat/stream  (SSE)
   *
   * Returns an async generator that yields parsed SSE event objects:
   *   { type: "start", conversation_id, mode, tool_calls, references }
   *   { type: "chunk", delta }
   *   { type: "done",  conversation_id, answer, mode, tool_calls, references }
   *   { type: "error", message }
   *
   * Uses native fetch (not axios) so we can read the response body as a stream.
   * Auth token is read from localStorage via getStoredSession() — same source
   * the axios interceptor in api.js uses.
   *
   * @param {string} message
   * @param {{ conversationId?: string, mode?: string, detectionId?: number }} options
   * @param {AbortSignal} [signal]
   */
  async *streamAgentMessage(message, options = {}, signal) {
    const { conversationId, mode, detectionId, provider, model } = options;
    const payload = { message, mode: mode || "auto" };
    if (conversationId) payload.conversation_id = conversationId;
    if (detectionId != null) payload.detection_id = detectionId;
    if (provider) payload.provider = provider;
    if (model) payload.model = model;

    const token = getStoredSession()?.accessToken || "";
    const baseUrl = import.meta.env.VITE_API_BASE_URL || "";

    const response = await fetch(`${baseUrl}/api/agent/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
      signal,
    });

    if (!response.ok) {
      // Mirror the axios 401 interceptor in api.js: clear the stale session
      // and send the user back to login instead of leaving a dead session.
      if (response.status === 401) {
        localStorage.removeItem(AUTH_STORAGE_KEY);
        if (window.location.pathname !== "/login") {
          window.location.href = "/login";
        }
      }
      let detail = `HTTP ${response.status}`;
      try {
        const body = await response.json();
        detail = body?.detail || detail;
      } catch {
        // ignore
      }
      throw new Error(detail);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith("data:")) continue;
        const jsonStr = trimmed.slice(5).trim();
        if (!jsonStr) continue;
        try {
          yield JSON.parse(jsonStr);
        } catch {
          // skip malformed lines
        }
      }
    }
  },

  /**
   * GET /api/agent/modes
   */
  async listAgentModes() {
    const response = await api.get("/api/agent/modes");
    return response.data;
  },

  async downloadDetectionReport(detectionId, format = "pdf") {
    const response = await api.get(`/api/reports/detections/${detectionId}`, {
      params: { format },
      responseType: "blob",
    });
    const extension = format === "markdown" ? "md" : "pdf";
    const blobUrl = URL.createObjectURL(response.data);
    const anchor = document.createElement("a");
    anchor.href = blobUrl;
    anchor.download = `yolo-detection-${detectionId}-report.${extension}`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(blobUrl);
  },
};

export default agentService;
