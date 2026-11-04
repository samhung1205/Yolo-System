import { useId } from "react";

import Modal from "./Modal";

/**
 * Shared destructive-action confirmation: names the object and consequence,
 * focuses the safe choice first, and stays open (with Escape disabled) while
 * the request runs so the outcome is never hidden.
 */
export default function ConfirmDialog({
  title,
  children,
  confirmLabel,
  busyLabel = "刪除中…",
  cancelLabel = "取消",
  busy = false,
  error = "",
  onConfirm,
  onCancel,
}) {
  const titleId = useId();
  return (
    <Modal aria-labelledby={titleId} onClose={() => { if (!busy) onCancel(); }}>
      <div className="modal-panel">
        <h2 id={titleId}>{title}</h2>
        {children}
        <div className="action-row">
          <button autoFocus type="button" className="button button-secondary" disabled={busy} onClick={onCancel}>
            {cancelLabel}
          </button>
          <button type="button" className="button button-danger" aria-disabled={busy || undefined}
            onClick={() => { if (!busy) onConfirm(); }}>
            {busy ? busyLabel : confirmLabel}
          </button>
        </div>
        {error ? <div className="alert alert-error" role="alert">{error}</div> : null}
      </div>
    </Modal>
  );
}
