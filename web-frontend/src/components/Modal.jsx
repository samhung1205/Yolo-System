import { useLayoutEffect, useRef } from "react";
import { createPortal } from "react-dom";

/** Native modal behavior keeps background content inert and contains focus. */
export default function Modal({ children, onClose, className = "modal-overlay", ...props }) {
  const dialogRef = useRef(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  useLayoutEffect(() => {
    const dialog = dialogRef.current;
    const trigger = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    dialog.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      dialog.close();
      document.body.style.overflow = previousOverflow;
      if (trigger instanceof HTMLElement && trigger.isConnected) trigger.focus();
    };
  }, []);
  return createPortal(
    <dialog ref={dialogRef} className={className} {...props}
      onCancel={(event) => { event.preventDefault(); onCloseRef.current(); }}
      onClick={(event) => { if (event.target === event.currentTarget) onCloseRef.current(); }}>
      {children}
    </dialog>, document.body
  );
}
