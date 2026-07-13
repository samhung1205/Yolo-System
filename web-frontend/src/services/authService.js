import api, { AUTH_STORAGE_KEY, getStoredSession } from "./api";

function saveSession({ access_token, token_type, user }) {
  localStorage.setItem(
    AUTH_STORAGE_KEY,
    JSON.stringify({
      accessToken: access_token,
      tokenType: token_type,
      user,
    })
  );
}

const authService = {
  async login(payload) {
    const response = await api.post("/api/auth/login", payload);
    saveSession(response.data);
    return response.data;
  },

  async register(payload) {
    const response = await api.post("/api/auth/register", payload);
    return response.data;
  },

  async fetchCurrentUser() {
    const response = await api.get("/api/auth/me");
    const existing = getStoredSession();

    if (existing?.accessToken) {
      localStorage.setItem(
        AUTH_STORAGE_KEY,
        JSON.stringify({
          ...existing,
          user: response.data,
        })
      );
    }

    return response.data;
  },

  getAccessToken() {
    return getStoredSession()?.accessToken || null;
  },

  getCurrentUser() {
    return getStoredSession()?.user || null;
  },

  isAuthenticated() {
    return Boolean(this.getAccessToken());
  },

  clearSession() {
    localStorage.removeItem(AUTH_STORAGE_KEY);
  },
};

export default authService;
