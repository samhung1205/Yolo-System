import { useEffect, useState } from "react";

import ConfirmDialog from "../../components/ConfirmDialog";
import Modal from "../../components/Modal";
import authService from "../../services/authService";
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
  const [usersPage, setUsersPage] = useState(1);
  const [usersPages, setUsersPages] = useState(1);
  const [deletingUser, setDeletingUser] = useState(null);
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
  const [deleteError, setDeleteError] = useState("");
  const currentUserId = authService.getCurrentUser()?.id;
  const confirmDeleteUser = users.find((user) => user.id === confirmDeleteId) || null;

  async function loadUsers(keyword = "", page = usersPage) {
    setLoading(true);
    setError("");
    try {
      const result = await userService.listUsers({
        page,
        limit: 20,
        search: keyword || undefined,
      });
      const pageCount = Math.max(1, Math.ceil(result.total / 20));
      if (page > pageCount) { await loadUsers(keyword, pageCount); return; }
      setUsersPage(page); setUsersPages(pageCount);
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
    if (deletingUser) return;
    setDeletingUser(userId);
    setDeleteError("");
    try {
      await userService.deleteUser(userId);
      setConfirmDeleteId(null);
      await loadUsers(search);
    } catch (err) {
      setDeleteError(normalizeApiError(err, "刪除使用者失敗，請稍後再試。"));
    } finally { setDeletingUser(null); }
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
          <h1>使用者管理</h1>
        </div>
      </section>

      {error ? <div className="alert alert-error" role="alert" aria-live="assertive">{error}</div> : null}

      {/* Edit Modal */}
      {editTarget ? (
        <Modal aria-labelledby="edit-modal-title" onClose={() => { if (!editSaving) setEditTarget(null); }}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 id="edit-modal-title">編輯使用者 — {editTarget.username}</h2>
              <button autoFocus disabled={editSaving} type="button" className="button-ghost" aria-label="關閉" onClick={() => setEditTarget(null)}>✕</button>
            </div>

            {editError ? <div className="alert alert-error" role="alert" aria-live="assertive">{editError}</div> : null}

            <form className="form-grid" onSubmit={handleEditSave}>
              <label className="field">
                <span>暱稱</span>
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
                <span>新密碼</span>
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
                  <span>管理員權限</span>
                </label>
                <label className="field-checkbox">
                  <input
                    type="checkbox"
                    checked={editForm.is_active}
                    onChange={(e) => setEditForm((p) => ({ ...p, is_active: e.target.checked }))}
                  />
                  <span>啟用帳號</span>
                </label>
              </div>

              <div className="agent-shortcut-row">
                <button type="submit" className="button" disabled={editSaving}>
                  {editSaving ? "儲存中…" : "儲存"}
                </button>
                <button type="button" className="button button-ghost" disabled={editSaving} onClick={() => setEditTarget(null)}>
                  取消
                </button>
              </div>
            </form>
          </div>
        </Modal>
      ) : null}

      {confirmDeleteUser && (
        <ConfirmDialog
          title={`刪除使用者 ${confirmDeleteUser.username}？`}
          confirmLabel="確認刪除"
          busy={deletingUser === confirmDeleteUser.id}
          error={deleteError}
          onConfirm={() => handleDelete(confirmDeleteUser.id)}
          onCancel={() => { setConfirmDeleteId(null); setDeleteError(""); }}
        >
          <p>此帳號的偵測紀錄、批次、對話與上傳檔案會一併刪除，無法復原。若只是暫停使用，請改用「編輯」取消「啟用帳號」。</p>
        </ConfirmDialog>
      )}

      <section className="admin-workspace">
        <details className="panel admin-create">
          <summary>建立使用者</summary>
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
              <span>使用者名稱</span>
              <input
                value={form.username}
                onChange={(e) => setForm((p) => ({ ...p, username: e.target.value }))}
                placeholder="3-32 位英數字"
                required
              />
            </label>
            <label className="field">
              <span>暱稱</span>
              <input
                value={form.nickname}
                onChange={(e) => setForm((p) => ({ ...p, nickname: e.target.value }))}
                placeholder="顯示名稱"
                required
              />
            </label>
            <label className="field">
              <span>密碼</span>
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))}
                placeholder="8–64 位，含英文字母與數字，可用符號"
                required
              />
            </label>
            <button type="submit" className="button" disabled={submitting}>
              {submitting ? "建立中…" : "建立使用者"}
            </button>
          </form>
        </details>

        <div className="panel admin-user-list">
          <div className="section-title section-title-row">
            <h2>使用者清單</h2>
            <div className="inline-form">
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                aria-label="搜尋使用者名稱、Email 或暱稱"
                onKeyDown={(event) => { if (event.key === "Enter") loadUsers(search, 1); }}
                placeholder="搜尋使用者名稱、Email 或暱稱"
              />
              <button
                type="button"
                className="button button-secondary"
                aria-disabled={loading || undefined} onClick={() => { if (!loading) loadUsers(search, 1); }}
              >
                搜尋
              </button>
            </div>
          </div>

          <nav className="pagination-controls" aria-label="使用者分頁">
            <button type="button" className="button-ghost" disabled={loading || usersPage <= 1} onClick={() => loadUsers(search, usersPage - 1)}>上一頁</button>
            <span>{usersPage} / {usersPages}</span>
            <button type="button" className="button-ghost" disabled={loading || usersPage >= usersPages} onClick={() => loadUsers(search, usersPage + 1)}>下一頁</button>
          </nav>
          {loading ? (
            <p className="muted">載入中…</p>
          ) : (
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th scope="col">編號</th>
                    <th scope="col">使用者名稱</th>
                    <th scope="col">Email</th>
                    <th scope="col">暱稱</th>
                    <th scope="col">角色</th>
                    <th scope="col">狀態</th>
                    <th scope="col">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id}>
                      <td>{user.id}</td>
                      <td>{user.username}</td>
                      <td>{user.email || "-"}</td>
                      <td>{user.nickname || "-"}</td>
                      <td>{user.is_admin ? "管理員" : "一般使用者"}</td>
                      <td>
                        <span className={`status-badge ${user.is_active ? "status-completed" : "status-failed"}`}>
                          {user.is_active ? "啟用" : "停用"}
                        </span>
                      </td>
                      <td>
                        <div className="table-actions">
                          <button
                            type="button"
                            className="button button-secondary"
                            onClick={() => openEdit(user)}
                          >
                            編輯
                          </button>
                          {user.id !== currentUserId ? (
                            <button
                              type="button"
                              className="button button-danger"
                              onClick={() => setConfirmDeleteId(user.id)}
                            >
                              刪除
                            </button>
                          ) : null}
                        </div>
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
