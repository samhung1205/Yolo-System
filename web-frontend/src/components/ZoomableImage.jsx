import { useEffect, useRef, useState } from "react";
import Modal from "./Modal";

const MIN_ZOOM = 0.5;
const MAX_ZOOM = 4;
const ZOOM_STEP = 0.25;

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

export default function ZoomableImage({
  src,
  alt,
  imageClassName = "result-image",
  triggerClassName = "",
  title = "Image preview",
}) {
  const [open, setOpen] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const triggerRef = useRef(null);
  const closeButtonRef = useRef(null);
  const dragOriginRef = useRef(null);

  function resetView() {
    setZoom(1);
    setOffset({ x: 0, y: 0 });
  }

  function openViewer() {
    resetView();
    setOpen(true);
  }

  function closeViewer() {
    setOpen(false);
    setDragging(false);
    triggerRef.current?.focus();
  }

  function changeZoom(delta) {
    setZoom((current) => clamp(current + delta, MIN_ZOOM, MAX_ZOOM));
  }

  useEffect(() => {
    if (zoom > 1) return;
    setOffset((current) =>
      current.x || current.y ? { x: 0, y: 0 } : current
    );
  }, [zoom]);

  useEffect(() => {
    if (!open) return undefined;


    function handleKeyDown(event) {
      if (zoom > 1 && ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
        event.preventDefault();
        setOffset((current) => ({ x: current.x + (event.key === "ArrowLeft" ? 40 : event.key === "ArrowRight" ? -40 : 0),
          y: current.y + (event.key === "ArrowUp" ? 40 : event.key === "ArrowDown" ? -40 : 0) }));
      }
      if (event.key === "+" || event.key === "=") changeZoom(ZOOM_STEP);
      if (event.key === "-") changeZoom(-ZOOM_STEP);
      if (event.key === "0") resetView();
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, zoom]);

  function handlePointerDown(event) {
    if (zoom <= 1) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragOriginRef.current = {
      pointerX: event.clientX,
      pointerY: event.clientY,
      offsetX: offset.x,
      offsetY: offset.y,
    };
    setDragging(true);
  }

  function handlePointerMove(event) {
    if (!dragging || !dragOriginRef.current) return;
    const origin = dragOriginRef.current;
    setOffset({
      x: origin.offsetX + event.clientX - origin.pointerX,
      y: origin.offsetY + event.clientY - origin.pointerY,
    });
  }

  function handlePointerUp(event) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    dragOriginRef.current = null;
    setDragging(false);
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className={`zoomable-image-trigger ${triggerClassName}`.trim()}
        onClick={openViewer}
        aria-label={`Open larger view: ${alt}`}
      >
        <img className={imageClassName} src={src} alt={alt} loading="lazy" />
        <span className="zoomable-image-hint" aria-hidden="true">View</span>
      </button>

      {open ? (
        <Modal className="image-viewer-overlay" aria-label={title} onClose={closeViewer}>
          <section
            className="image-viewer-dialog"
          >
            <header className="image-viewer-toolbar">
              <strong>{title}</strong>
              <div className="image-viewer-actions" aria-label="Image zoom controls">
                <button
                  type="button"
                  className="button-ghost image-viewer-control"
                  onClick={() => changeZoom(-ZOOM_STEP)}
                  disabled={zoom <= MIN_ZOOM}
                  aria-label="Zoom out"
                >
                  -
                </button>
                <output className="image-viewer-zoom" aria-live="polite">
                  {Math.round(zoom * 100)}%
                </output>
                <button
                  type="button"
                  className="button-ghost image-viewer-control"
                  onClick={() => changeZoom(ZOOM_STEP)}
                  disabled={zoom >= MAX_ZOOM}
                  aria-label="Zoom in"
                >
                  +
                </button>
                <button type="button" className="button-ghost" onClick={resetView}>
                  Reset
                </button>
                <button
                  autoFocus
                  ref={closeButtonRef}
                  type="button"
                  className="button button-secondary"
                  onClick={closeViewer}
                >
                  Close
                </button>
              </div>
            </header>

            <div
              className={`image-viewer-stage${dragging ? " is-dragging" : ""}`}
              onWheel={(event) => {
                event.preventDefault();
                changeZoom(event.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP);
              }}
              onDoubleClick={resetView}
            >
              <img
                src={src}
                alt={alt}
                draggable="false"
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                onPointerCancel={handlePointerUp}
                style={{
                  transform: `translate3d(${offset.x}px, ${offset.y}px, 0) scale(${zoom})`,
                  cursor: zoom > 1 ? (dragging ? "grabbing" : "grab") : "zoom-in",
                }}
              />
            </div>

            <p className="image-viewer-help">
              使用按鈕或滾輪縮放；放大後可拖曳或按方向鍵平移。按 0 重設，Esc 關閉。
            </p>
          </section>
        </Modal>
      ) : null}
    </>
  );
}
