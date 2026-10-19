import { Link } from "react-router";
import { useState } from "react";

import authService from "../services/authService";
import { normalizeApiError } from "../services/api";

export default function RegisterPage() {
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
              autoComplete="email"
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
              autoComplete="username" minLength={3} maxLength={32} pattern="[A-Za-z0-9]{3,32}" aria-describedby="username-hint"
              placeholder="例如 researcher01"
              required
            />
            <small id="username-hint" className="muted">使用者名稱需為 3–32 位英數字。</small>
          </label>

          <label className="field">
            <span>暱稱</span>
            <input
              value={form.nickname}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, nickname: event.target.value }))
              }
              autoComplete="nickname"
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
              autoComplete="new-password" minLength={8} pattern="(?=.*[A-Za-z])(?=.*[0-9])[\x21-\x7E]{8,64}" maxLength={64} aria-describedby="password-hint"
              placeholder="輸入新密碼"
              required
            />
            <small id="password-hint" className="muted">8–64 位，需同時包含英文字母與數字，可使用符號（不可含空白）。</small>
          </label>

          {error ? <div className="alert alert-error" role="alert" aria-live="assertive">{error}</div> : null}
          {success ? <div className="alert alert-success" role="status" aria-live="polite">{success}</div> : null}

          <button type="submit" className="button" disabled={loading || Boolean(success)}>
            {loading ? "註冊中..." : success ? "帳號已建立，請返回登入" : "註冊"}
          </button>
        </form>

        <div className="auth-footer">
          已有帳號？ <Link to="/login">返回登入</Link>
        </div>
      </div>
    </div>
  );
}
