import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";

import authService from "../services/authService";
import { normalizeApiError } from "../services/api";

export default function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
    nickname: "",
  });
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);

    try {
      await authService.register(form);
      setSuccess("註冊成功，請回登入頁登入。");
      setTimeout(() => navigate("/login", { replace: true }), 800);
    } catch (err) {
      setError(normalizeApiError(err, "註冊失敗"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-panel">
        <div>
          <div className="eyebrow">Registration</div>
          <h1>建立帳號</h1>
          <p className="muted">填寫以下資訊建立您的帳號。</p>
        </div>

        <form className="form-grid" onSubmit={handleSubmit}>
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              value={form.email}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, email: event.target.value }))
              }
              placeholder="name@example.com"
              required
            />
          </label>

          <label className="field">
            <span>使用者名稱</span>
            <input
              value={form.username}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, username: event.target.value }))
              }
              placeholder="3-32 位英數字"
              required
            />
          </label>

          <label className="field">
            <span>暱稱</span>
            <input
              value={form.nickname}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, nickname: event.target.value }))
              }
              placeholder="顯示名稱"
              required
            />
          </label>

          <label className="field">
            <span>密碼</span>
            <input
              type="password"
              value={form.password}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, password: event.target.value }))
              }
              placeholder="至少 8 位，且需同時包含英文字母與數字"
              required
            />
          </label>

          {error ? <div className="alert alert-error" role="alert" aria-live="assertive">{error}</div> : null}
          {success ? <div className="alert alert-success" role="status" aria-live="polite">{success}</div> : null}

          <button type="submit" className="button" disabled={loading}>
            {loading ? "註冊中..." : "註冊"}
          </button>
        </form>

        <div className="auth-footer">
          已有帳號？ <Link to="/login">返回登入</Link>
        </div>
      </div>
    </div>
  );
}
