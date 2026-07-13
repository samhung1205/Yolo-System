import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import authService from "../services/authService";
import { normalizeApiError } from "../services/api";

function ScanIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M7.5 3.75H6A2.25 2.25 0 003.75 6v1.5M16.5 3.75H18A2.25 2.25 0 0120.25 6v1.5m0 9V18A2.25 2.25 0 0118 20.25h-1.5m-9 0H6A2.25 2.25 0 013.75 18v-1.5M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}

function EyeIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
      <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}

function EyeSlashIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
    </svg>
  );
}

export default function LoginPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", password: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function handleChange(field) {
    return (e) => {
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
    };
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await authService.login(form);
      navigate("/", { replace: true });
    } catch (err) {
      setError(normalizeApiError(err, "登入失敗，請確認帳號名稱與密碼"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-panel">

        {/* Brand mark */}
        <div className="auth-brand">
          <div className="auth-brand-icon">
            <ScanIcon />
          </div>
          <span className="auth-brand-name">YOLO Detection Platform</span>
        </div>

        <div className="auth-divider" />

        {/* Header */}
        <div>
          <div className="eyebrow">Authentication</div>
          <h1>歡迎回來</h1>
          <p className="muted" style={{ maxWidth: "46ch" }}>
            登入後可執行物件偵測、查詢歷史紀錄，並使用 AI Agent 分析結果。
          </p>
        </div>

        {/* Form */}
        <form className="form-grid" onSubmit={handleSubmit} noValidate>
          <label className="field">
            <span>使用者名稱 / Email</span>
            <input
              type="text"
              value={form.username}
              onChange={handleChange("username")}
              placeholder="username 或 name@example.com"
              autoComplete="username"
              autoFocus
              required
              disabled={loading}
            />
          </label>

          <label className="field">
            <span>密碼</span>
            <div className="password-field">
              <input
                type={showPassword ? "text" : "password"}
                value={form.password}
                onChange={handleChange("password")}
                placeholder="請輸入密碼"
                autoComplete="current-password"
                required
                disabled={loading}
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "隱藏密碼" : "顯示密碼"}
                tabIndex={-1}
              >
                {showPassword ? <EyeSlashIcon /> : <EyeIcon />}
              </button>
            </div>
          </label>

          {error && (
            <div className="alert alert-error" role="alert" aria-live="assertive">
              {error}
            </div>
          )}

          <button type="submit" className="button" disabled={loading}>
            {loading ? "登入中..." : "登入"}
          </button>
        </form>

        {/* Footer */}
        <div className="auth-footer">
          還沒有帳號？{" "}
          <Link to="/register">立即註冊</Link>
        </div>
      </div>
    </div>
  );
}
