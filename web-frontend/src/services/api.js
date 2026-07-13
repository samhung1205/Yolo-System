import axios from "axios";

export const AUTH_STORAGE_KEY = "yolo_web_auth";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const raw = localStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) {
    return config;
  }

  try {
    const parsed = JSON.parse(raw);
    if (parsed?.accessToken) {
      config.headers.Authorization = `Bearer ${parsed.accessToken}`;
    }
  } catch {
    localStorage.removeItem(AUTH_STORAGE_KEY);
  }

  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export function getStoredSession() {
  const raw = localStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    return null;
  }
}

export function buildAssetUrl(pathOrUrl) {
  if (!pathOrUrl) {
    return "";
  }

  if (/^https?:\/\//.test(pathOrUrl)) {
    return pathOrUrl;
  }

  const base = import.meta.env.VITE_API_BASE_URL || window.location.origin;
  return new URL(pathOrUrl, base.endsWith("/") ? base : `${base}/`).toString();
}

export function buildAvatarUrl(avatar, avatarUrl) {
  if (avatarUrl) {
    return buildAssetUrl(avatarUrl);
  }

  if (!avatar) {
    return "";
  }

  if (/^https?:\/\//.test(avatar) || avatar.startsWith("/")) {
    return buildAssetUrl(avatar);
  }

  return buildAssetUrl(`/static/avatars/${avatar}`);
}

export function normalizeApiError(error, fallbackMessage = "Request failed") {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    return detail[0]?.msg || fallbackMessage;
  }

  return error?.message || fallbackMessage;
}

export default api;
