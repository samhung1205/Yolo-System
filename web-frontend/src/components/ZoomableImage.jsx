import { useEffect, useRef, useState } from "react";

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

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    function handleKeyDown(event) {
      if (event.key === "Escape") closeViewer();
      if (event.key === "+" || event.key === "=") changeZoom(ZOOM_STEP);
      if (event.key === "-") changeZoom(-ZOOM_STEP);
      if (event.key === "0") resetView();
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

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
        <img className={imageClassName} src={src} alt={alt} />
        <span className="zoomable-image-hint" aria-hidden="true">View</span>
      </button>

      {open ? (
        <div
          className="image-viewer-overlay"
          onPointerDown={(event) => {
            if (event.target === event.currentTarget) closeViewer();
          }}
        >
          <section
            className="image-viewer-dialog"
            role="dialog"
            aria-modal="true"
            aria-label={title}
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
              Use the controls or mouse wheel to zoom. Drag while zoomed in; double-click to reset.
            </p>
          </section>
        </div>
      ) : null}
    </>
  );
}
