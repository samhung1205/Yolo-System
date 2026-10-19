import api from "./api";

/**
 * Fetches available LLM providers and their model lists from GET /api/models.
 *
 * Returns an array of:
 *   { provider, label, models: string[], available, is_default, default_model }
 *
 * `purpose` ("chat" | "agent") picks which backend default is flagged:
 * CHAT_PROVIDER for /chat, AGENT_PROVIDER / AGENT_OLLAMA_MODEL for /agent.
 */
const modelService = {
  async listModels(purpose = "chat") {
    const response = await api.get("/api/models", { params: { purpose } });
    return response.data;
  },
};

/**
 * Initial provider/model for a picker: the backend default when it is usable,
 * otherwise the first usable provider. Unavailable providers (no API key) are
 * only display placeholders.
 */
export function pickDefaultSelection(groups) {
  const usable = groups.filter((g) => g.available !== false);
  const group = usable.find((g) => g.is_default) || usable[0] || groups[0];
  const model = group.models.includes(group.default_model) ? group.default_model : group.models[0];
  return { provider: group.provider, model: model || null };
}

export default modelService;
