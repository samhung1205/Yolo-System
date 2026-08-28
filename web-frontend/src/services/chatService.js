import api from "./api";

const chatService = {
  async sendMessage(question, conversationId = null, provider = null, model = null) {
    const payload = { question };
    if (conversationId) payload.conversation_id = conversationId;
    if (provider) payload.provider = provider;
    if (model) payload.model = model;
    const response = await api.post("/api/chat", payload);
    return response.data;
  },

  async listConversations(limit = 20) {
    const response = await api.get("/api/chat", {
      params: { limit },
    });
    return response.data;
  },

  async getConversation(conversationId) {
    const response = await api.get(`/api/chat/${conversationId}`);
    return response.data;
  },

  async deleteConversation(conversationId) {
    await api.delete(`/api/chat/${conversationId}`);
  },
};

export default chatService;
