import api from "./api";

/**
 * Fetches available LLM providers and their model lists from GET /api/models.
 *
 * Returns an array of:
 *   { provider: string, label: string, models: string[] }
 */
const modelService = {
  async listModels() {
    const response = await api.get("/api/models");
    return response.data;
  },
};

export default modelService;
