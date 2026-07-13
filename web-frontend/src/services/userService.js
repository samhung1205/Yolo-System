import api from "./api";

const userService = {
  async listUsers(params = {}) {
    const response = await api.get("/api/users", { params });
    return response.data;
  },

  async createUser(payload) {
    const response = await api.post("/api/users", payload);
    return response.data;
  },

  async updateUser(userId, payload) {
    const response = await api.put(`/api/users/${userId}`, payload);
    return response.data;
  },

  /** Self-service: update own nickname / password. */
  async updateProfile(payload) {
    const response = await api.put("/api/auth/profile", payload);
    return response.data;
  },

  async deleteUser(userId) {
    const response = await api.delete(`/api/users/${userId}`);
    return response.data;
  },
};

export default userService;
