import { useEffect, useState } from "react";

import userService from "../../services/userService";
import { normalizeApiError } from "../../services/api";

const DEFAULT_CREATE_FORM = {
  username: "",
  email: "",
  password: "",
  nickname: "",
};

const DEFAULT_EDIT_FORM = {
  nickname: "",
  email: "",
  password: "",
  is_admin: false,
  is_active: true,
};

export default function UserManagementPage() {
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState(DEFAULT_CREATE_FORM);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Edit modal state
  const [editTarget, setEditTarget] = useState(null);
  const [editForm, setEditForm] = useState(DEFAULT_EDIT_FORM);
  const [editError, setEditError] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);

  async function loadUsers(keyword = "") {
    setLoading(true);
    setError("");
    try {
      const result = await userService.listUsers({
        page: 1,
        limit: 100,
        search: keyword || undefined,
      });
      setUsers(result.items || []);
    } catch (err) {
      setError(normalizeApiError(err, "無法載入使用者列表"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadUsers();
  }, []);

  async function handleCreate(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await userService.createUser(form);
      setForm(DEFAULT_CREATE_FORM);
      setLoading(true);
      await loadUsers(search);
    } catch (err) {
      setError(normalizeApiError(err, "建立使用者失敗"));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(userId) {
    try {
      await userService.deleteUser(userId);
      setConfirmDeleteId(null);
      await loadUsers(search);
    } catch (err) {
      setError(normalizeApiError(err, "刪除使用者失敗"));
    }
  }

  function openEdit(user) {
    setEditTarget(user);
    setEditForm({
      nickname: user.nickname || "",
      email: user.email || "",
      password: "",
      is_admin: user.is_admin,
      is_active: user.is_active,
    });
    setEditError("");
  }

  async function handleEditSave(event) {
    event.preventDefault();
    setEditSaving(true);
    setEditError("");
    const payload = {};
    if (editForm.nickname !== (editTarget.nickname || "")) payload.nickname = editForm.nickname || null;
    if (editForm.email !== (editTarget.email || "")) payload.email = editForm.email || null;
    if (editForm.password) payload.password = editForm.password;
    if (editForm.is_admin !== editTarget.is_admin) payload.is_admin = editForm.is_admin;
    if (editForm.is_active !== editTarget.is_active) payload.is_active = editForm.is_active;

    try {
      await userService.updateUser(editTarget.id, payload);
      setEditTarget(null);
      await loadUsers(search);
    } catch (err) {
      setEditError(normalizeApiError(err, "更新失敗"));
    } finally {
      setEditSaving(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="page-header">
        <div>
          <div className="eyebrow">Admin</div>
          <h1>User Management</h1>
        </div>
      </section>

      {error ? <div className="alert alert-error" role="alert" aria-live="assertive">{error}</div> : null}

      {/* Edit Modal */}
      {editTarget ? (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="edit-modal-title" onClick={() => setEditTarget(null)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 id="edit-modal-title">編輯使用者 — {editTarget.username}</h2>
              <button type="button" className="button-ghost" aria-label="關閉" onClick={() => setEditTarget(null)}>✕</button>
            </div>

            {editError ? <div className="alert alert-error" role="alert" aria-live="assertive">{editError}</div> : null}

            <form className="form-grid" onSubmit={handleEditSave}>
              <label className="field">
                <span>Nickname</span>
                <input
                  value={editForm.nickname}
                  onChange={(e) => setEditForm((p) => ({ ...p, nickname: e.target.value }))}
                  placeholder="顯示名稱"
                />
              </label>

              <label className="field">
                <span>Email</span>
                <input
                  type="email"
                  value={editForm.email}
                  onChange={(e) => setEditForm((p) => ({ ...p, email: e.target.value }))}
                  placeholder="name@example.com"
                />
              </label>

              <label className="field">
                <span>New Password</span>
                <input
                  type="password"
                  value={editForm.password}
                  onChange={(e) => setEditForm((p) => ({ ...p, password: e.target.value }))}
                  placeholder="留空表示不更改"
                  autoComplete="new-password"
                />
              </label>

              <div className="field-row">
                <label className="field-checkbox">
                  <input
                    type="checkbox"
                    checked={editForm.is_admin}
                    onChange={(e) => setEditForm((p) => ({ ...p, is_admin: e.target.checked }))}
                  />
                  <span>Admin</span>
                </label>
                <label className="field-checkbox">
                  <input
                    type="checkbox"
                    checked={editForm.is_active}
                    onChange={(e) => setEditForm((p) => ({ ...p, is_active: e.target.checked }))}
                  />
                  <span>Active</span>
                </label>
              </div>

              <div className="agent-shortcut-row">
                <button type="submit" className="button" disabled={editSaving}>
                  {editSaving ? "儲存中..." : "儲存"}
                </button>
                <button type="button" className="button button-ghost" onClick={() => setEditTarget(null)}>
                  取消
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      <section className="history-layout">
        <div className="panel">
          <div className="section-title">
            <h2>Create User</h2>
          </div>
          <form className="form-grid" onSubmit={handleCreate}>
            <label className="field">
              <span>Email</span>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
                placeholder="name@example.com"
                required
              />
            </label>
            <label className="field">
              <span>Username</span>
              <input
                value={form.username}
                onChange={(e) => setForm((p) => ({ ...p, username: e.target.value }))}
                placeholder="3-32 位英數字"
                required
              />
            </label>
            <label className="field">
              <span>Nickname</span>
              <input
                value={form.nickname}
                onChange={(e) => setForm((p) => ({ ...p, nickname: e.target.value }))}
                placeholder="顯示名稱"
                required
              />
            </label>
            <label className="field">
              <span>Password</span>
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))}
                placeholder="至少 8 位英數組合"
                required
              />
            </label>
            <button type="submit" className="button" disabled={submitting}>
              {submitting ? "建立中..." : "建立使用者"}
            </button>
          </form>
        </div>

        <div className="panel">
          <div className="section-title section-title-row">
            <h2>User List</h2>
            <div className="inline-form">
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search username / email / nickname"
              />
              <button
                type="button"
                className="button button-secondary"
                onClick={() => loadUsers(search)}
              >
                搜尋
              </button>
            </div>
          </div>

          {loading ? (
            <p className="muted">載入中...</p>
          ) : (
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th scope="col">ID</th>
                    <th scope="col">Username</th>
                    <th scope="col">Email</th>
                    <th scope="col">Nickname</th>
                    <th scope="col">Role</th>
                    <th scope="col">Status</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id}>
                      <td>{user.id}</td>
                      <td>{user.username}</td>
                      <td>{user.email || "-"}</td>
                      <td>{user.nickname || "-"}</td>
                      <td>{user.is_admin ? "Admin" : "User"}</td>
                      <td>
                        <span className={`status-badge ${user.is_active ? "status-completed" : "status-failed"}`}>
                          {user.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td>
                        {confirmDeleteId === user.id ? (
                          <div className="inline-confirm">
                            <span className="inline-confirm-label">確定？</span>
                            <button
                              type="button"
                              className="button button-danger"
                              onClick={() => handleDelete(user.id)}
                            >
                              確認
                            </button>
                            <button
                              type="button"
                              className="button-ghost"
                              onClick={() => setConfirmDeleteId(null)}
                            >
                              取消
                            </button>
                          </div>
                        ) : (
                          <div className="table-actions">
                            <button
                              type="button"
                              className="button button-secondary"
                              onClick={() => openEdit(user)}
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              className="button button-danger"
                              onClick={() => setConfirmDeleteId(user.id)}
                            >
                              Delete
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                  {!users.length ? (
                    <tr>
                      <td colSpan={7} className="muted center-cell">
                        查無資料。
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
