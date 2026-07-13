import { useEffect, useState } from "react";

import authService from "../services/authService";
import userService from "../services/userService";
import { buildAvatarUrl, normalizeApiError } from "../services/api";

export default function ProfilePage() {
  const [user, setUser] = useState(authService.getCurrentUser());
  const [loadError, setLoadError] = useState("");

  // Edit form state
  const [editing, setEditing] = useState(false);
  const [nickname, setNickname] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    let mounted = true;
    authService.fetchCurrentUser().then((u) => {
      if (mounted) setUser(u);
    }).catch((err) => {
      if (mounted) setLoadError(normalizeApiError(err, "無法載入 profile"));
    });
    return () => { mounted = false; };
  }, []);

  function openEdit() {
    setNickname(user?.nickname || "");
    setNewPassword("");
    setConfirmPassword("");
    setSaveError("");
    setSaveSuccess(false);
    setEditing(true);
  }

  async function handleSave(event) {
    event.preventDefault();
    setSaveError("");
    setSaveSuccess(false);

    if (newPassword && newPassword !== confirmPassword) {
      setSaveError("兩次密碼輸入不一致");
      return;
    }

    const payload = {};
    if (nickname.trim() !== (user?.nickname || "")) payload.nickname = nickname.trim() || null;
    if (newPassword) payload.password = newPassword;

    if (!Object.keys(payload).length) {
      setEditing(false);
      return;
    }

    setSaving(true);
    try {
      const updated = await userService.updateProfile(payload);
      // Refresh stored session user
      await authService.fetchCurrentUser();
      setUser(updated);
      setSaveSuccess(true);
      setEditing(false);
    } catch (err) {
      setSaveError(normalizeApiError(err, "儲存失敗"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="page-header">
        <div>
          <div className="eyebrow">Profile</div>
          <h1>My Profile</h1>
        </div>
      </section>

      {loadError ? <div className="alert alert-error" role="alert" aria-live="assertive">{loadError}</div> : null}
      {saveSuccess ? <div className="alert alert-success" role="status" aria-live="polite">已成功更新個人資料。</div> : null}

      <section className="panel profile-panel">
        <div className="profile-avatar-shell">
          {user?.avatar ? (
            <img className="profile-avatar" src={buildAvatarUrl(user.avatar, user.avatar_url)} alt={`${user?.nickname || user?.username || "使用者"} 的頭像`} />
          ) : (
            <div className="profile-avatar profile-avatar-empty">
              {(user?.nickname || user?.username || "?").slice(0, 1).toUpperCase()}
            </div>
          )}
        </div>

        <div className="detail-stack profile-detail">
          <div className="detail-grid">
            <div>
              <span className="detail-label">Username</span>
              <strong>{user?.username || "-"}</strong>
            </div>
            <div>
              <span className="detail-label">Email</span>
              <strong>{user?.email || "-"}</strong>
            </div>
            <div>
              <span className="detail-label">Nickname</span>
              <strong>{user?.nickname || "-"}</strong>
            </div>
            <div>
              <span className="detail-label">Role</span>
              <strong>{user?.is_admin ? "Administrator" : "User"}</strong>
            </div>
            <div>
              <span className="detail-label">Status</span>
              <strong>{user?.is_active ? "Active" : "Inactive"}</strong>
            </div>
            <div>
              <span className="detail-label">Since</span>
              <strong>{user?.register_time ? String(user.register_time).slice(0, 10) : "-"}</strong>
            </div>
          </div>

          {!editing ? (
            <div>
              <button type="button" className="button button-secondary" onClick={openEdit}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ marginRight: 6 }}><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                編輯個人資料
              </button>
            </div>
          ) : (
            <form className="form-grid" onSubmit={handleSave}>
              <div className="form-section-title">編輯資料</div>

              {saveError ? <div className="alert alert-error" role="alert" aria-live="assertive">{saveError}</div> : null}

              <label className="field">
                <span>Nickname</span>
                <input
                  value={nickname}
                  onChange={(e) => setNickname(e.target.value)}
                  placeholder="顯示名稱（留空保持不變）"
                />
              </label>

              <label className="field">
                <span>New Password</span>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="至少 8 位英數組合（留空表示不更改）"
                  autoComplete="new-password"
                />
              </label>

              {newPassword ? (
                <label className="field">
                  <span>Confirm Password</span>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="再輸入一次新密碼"
                    autoComplete="new-password"
                  />
                </label>
              ) : null}

              <div className="action-row">
                <button type="submit" className="button" disabled={saving}>
                  {saving ? "儲存中..." : "儲存"}
                </button>
                <button type="button" className="button button-ghost" onClick={() => setEditing(false)}>
                  取消
                </button>
              </div>
            </form>
          )}
        </div>
      </section>
    </div>
  );
}
