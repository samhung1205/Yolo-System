"""
YOLO integration wrapper for backend detection.
"""
import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import cv2
from fastapi import HTTPException, status
from PIL import Image

from app.core.config import settings
from app.integrations.legacy_checkpoint_compat import (
    LegacyCheckpointCompatibilityError,
    install_legacy_checkpoint_modules,
)
from app.integrations.model_registry import (
    YoloModelRegistryError,
    YoloModelSpec,
    get_yolo_model,
)

logger = logging.getLogger(__name__)

_MODEL_CACHE: dict[str, object] = {}


@dataclass(frozen=True)
class ClassThreshold:
    """Confidence and NMS IoU threshold for one class id."""

    conf: float
    iou: float


@dataclass
class DetectionRunResult:
    model_key: str
    model_name: str
    model_sha256: str
    model_class_map: dict[str, dict[str, str]]
    image_width: int
    image_height: int
    inference_ms: float
    objects: list[dict]
    annotated_image: Image.Image


@dataclass
class VideoDetectionRunResult:
    model_key: str
    model_name: str
    model_sha256: str
    model_class_map: dict[str, dict[str, str]]
    image_width: int
    image_height: int
    inference_ms: float
    frame_count: int
    objects: list[dict]
    preview_image: Image.Image


def _apply_per_class_thresholds(
    result,
    *,
    default_conf: float,
    default_iou: float,
    class_thresholds: dict[int, ClassThreshold],
    max_det: int,
) -> None:
    """Narrow an unsuppressed prediction down to per-class thresholds in place.

    Ultralytics' ``predict()`` only accepts scalar ``conf``/``iou``, so the
    caller runs one pass at the most permissive settings and this function
    re-applies each class's own thresholds. Both halves are exact rather than
    approximate:

    * Confidence: greedy NMS walks boxes in descending confidence, so adding
      candidates *below* a class's threshold can never change which boxes
      above it survive. Filtering afterwards therefore matches running that
      class at its own ``conf`` directly.
    * IoU: the caller disabled suppression with ``iou=1.0``, and Ultralytics'
      default NMS is already class-aware (boxes of different classes never
      suppress each other), so re-running NMS per class reproduces what
      Ultralytics would have produced for that class's ``iou``.

    ``result.boxes`` is replaced so both ``result.plot()`` and object
    extraction observe the filtered set.
    """
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return

    try:
        import torch
        from torchvision.ops import nms
    except ImportError as exc:  # pragma: no cover - torch ships with ultralytics
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="torch/torchvision are required for per-class threshold detection",
        ) from exc

    from ultralytics.engine.results import Boxes

    if len(boxes) >= max_det:
        # Ultralytics truncates to max_det *after* NMS, so hitting the cap with
        # suppression disabled means the lowest-confidence candidates were
        # dropped before we could apply per-class thresholds.
        logger.warning(
            "Per-class detection hit the %d candidate ceiling; raise "
            "DETECTION_PERCLASS_MAX_DET if dense images look truncated.",
            max_det,
        )

    # Run the arithmetic on CPU so this works the same on CPU/MPS/CUDA.
    device_data = boxes.data
    data = device_data.detach().cpu()
    # Ultralytics keeps the class id in the last column and confidence in the
    # second-to-last, whether or not a tracking id column is present.
    cls_col, conf_col = data[:, -1], data[:, -2]

    keep_chunks = []
    for raw_class_id in cls_col.unique().tolist():
        threshold = class_thresholds.get(int(raw_class_id))
        conf_thr = threshold.conf if threshold else default_conf
        iou_thr = threshold.iou if threshold else default_iou

        candidate_idx = ((cls_col == raw_class_id) & (conf_col >= conf_thr)).nonzero(as_tuple=True)[0]
        if candidate_idx.numel() == 0:
            continue

        candidates = data[candidate_idx]
        kept = nms(candidates[:, :4].float(), candidates[:, -2].float(), iou_thr)
        keep_chunks.append(candidate_idx[kept])

    if keep_chunks:
        keep_idx = torch.cat(keep_chunks)
        # Grouping by class scrambled Ultralytics' confidence-descending output
        # order; restore it so downstream object_index numbering is unchanged.
        keep_idx = keep_idx[torch.argsort(data[keep_idx][:, -2], descending=True)]
        filtered = device_data[keep_idx.to(device_data.device)]
    else:
        filtered = device_data[:0]

    result.boxes = Boxes(filtered, boxes.orig_shape)


class YoloEngine:
    def __init__(self, model_key: str | None = None):
        try:
            self.model_spec: YoloModelSpec = get_yolo_model(model_key)
        except YoloModelRegistryError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        self.model_path = self.model_spec.checkpoint_path

    def detect_image(
        self,
        image_path: Path,
        conf: float = 0.25,
        iou: float = 0.45,
        class_thresholds: dict[int, ClassThreshold] | None = None,
    ) -> DetectionRunResult:
        """Run detection on one image.

        When ``class_thresholds`` is given, each listed class id is scored
        against its own confidence/IoU thresholds instead of the scalar
        ``conf``/``iou`` (which remain the default for unlisted classes).
        This still costs exactly one inference pass — see
        :func:`_apply_per_class_thresholds`.
        """
        model = self._load_model()

        if class_thresholds and self.model_spec.task == "obb":
            # _apply_per_class_thresholds() only knows how to re-filter
            # result.boxes; OBB models populate result.obb instead, so
            # silently accepting this combination would apply the widened
            # (min-conf, no-suppression) pass without ever narrowing it back.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Per-class thresholds are not supported for OBB (oriented bounding box) models yet.",
            )

        predict_kwargs = {
            "source": str(image_path),
            "conf": conf,
            "iou": iou,
            "imgsz": self.model_spec.input_size,
            "verbose": False,
        }
        if class_thresholds:
            # Widen the single pass to the most permissive settings any class
            # asked for, then narrow it back down per class afterwards.
            predict_kwargs["conf"] = min([conf, *(t.conf for t in class_thresholds.values())])
            predict_kwargs["iou"] = 1.0  # IoU can never exceed 1.0 -> suppresses nothing
            predict_kwargs["max_det"] = settings.DETECTION_PERCLASS_MAX_DET

        started_at = perf_counter()
        result = model.predict(**predict_kwargs)[0]
        if class_thresholds:
            _apply_per_class_thresholds(
                result,
                default_conf=conf,
                default_iou=iou,
                class_thresholds=class_thresholds,
                max_det=predict_kwargs["max_det"],
            )
        inference_ms = round((perf_counter() - started_at) * 1000, 2)

        image_height, image_width = result.orig_shape
        objects = self._extract_objects(result)

        annotated_bgr = result.plot()
        annotated_image = Image.fromarray(annotated_bgr[:, :, ::-1])

        return DetectionRunResult(
            model_key=self.model_spec.key,
            model_name=self.model_path.name,
            model_sha256=self.model_spec.current_sha256() or "",
            model_class_map=self.model_spec.provenance_snapshot(),
            image_width=image_width,
            image_height=image_height,
            inference_ms=inference_ms,
            objects=objects,
            annotated_image=annotated_image,
        )

    def detect_video(
        self,
        video_path: Path,
        output_video_path: Path,
        conf: float = 0.25,
        iou: float = 0.45,
    ) -> VideoDetectionRunResult:
        model = self._load_model()
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to open uploaded video",
            )

        fps = capture.get(cv2.CAP_PROP_FPS) or 0
        fps = fps if fps > 0 else 25.0
        image_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        image_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if image_width <= 0 or image_height <= 0:
            capture.release()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to read uploaded video metadata",
            )

        output_video_path.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(
            str(output_video_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (image_width, image_height),
        )
        if not writer.isOpened():
            capture.release()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to create result video",
            )

        frame_count = 0
        preview_frame = None
        preview_objects: list[dict] = []
        max_object_count = -1
        started_at = perf_counter()

        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break

                frame_count += 1
                result = model.track(
                    source=frame,
                    persist=True,
                    conf=conf,
                    iou=iou,
                    imgsz=self.model_spec.input_size,
                    verbose=False,
                )[0]
                annotated_bgr = result.plot()
                writer.write(annotated_bgr)

                frame_objects = self._extract_objects(result)
                if len(frame_objects) >= max_object_count:
                    max_object_count = len(frame_objects)
                    preview_objects = frame_objects
                    preview_frame = annotated_bgr[:, :, ::-1].copy()
        finally:
            writer.release()
            capture.release()

        if frame_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded video contains no readable frames",
            )

        inference_ms = round((perf_counter() - started_at) * 1000, 2)
        preview_image = Image.fromarray(preview_frame)

        return VideoDetectionRunResult(
            model_key=self.model_spec.key,
            model_name=self.model_path.name,
            model_sha256=self.model_spec.current_sha256() or "",
            model_class_map=self.model_spec.provenance_snapshot(),
            image_width=image_width,
            image_height=image_height,
            inference_ms=inference_ms,
            frame_count=frame_count,
            objects=preview_objects,
            preview_image=preview_image,
        )

    def _detection_source(self, result):
        """Return ``(xyxy, class_ids, confidences, object_indexes)`` from a
        prediction result, supporting both axis-aligned detect/track models
        (``result.boxes``) and oriented bounding-box models (``result.obb``).

        Ultralytics populates exactly one of ``result.boxes`` /
        ``result.obb`` depending on the model's task. For OBB models,
        ``obb.xyxy`` is the *axis-aligned rectangle enclosing the rotated
        box* — the rotation angle itself is not returned here (and is not
        persisted in ``detection_objects``, see the report "Limitations"
        section), but the annotated image (``result.plot()``) still renders
        the true rotated box, since Ultralytics' plotting handles OBB
        natively.
        """
        boxes = result.boxes
        if boxes is not None:
            return (
                boxes.xyxy.tolist(),
                boxes.cls.tolist(),
                boxes.conf.tolist(),
                boxes.id.tolist() if getattr(boxes, "id", None) is not None else None,
            )

        obb = getattr(result, "obb", None)
        if obb is not None:
            return (
                obb.xyxy.tolist(),
                obb.cls.tolist(),
                obb.conf.tolist(),
                obb.id.tolist() if getattr(obb, "id", None) is not None else None,
            )

        return None

    def _extract_objects(self, result) -> list[dict]:
        objects = []
        detections = self._detection_source(result)
        if detections is None:
            return objects

        xyxy, class_ids, confidences, object_indexes = detections

        for index, (bbox, class_id, confidence) in enumerate(zip(xyxy, class_ids, confidences), start=1):
            object_index = int(object_indexes[index - 1]) if object_indexes else index
            objects.append(
                {
                    "object_index": object_index,
                    "class_id": int(class_id),
                    "class_name": self.model_spec.canonical_class_names.get(
                        int(class_id),
                        str(result.names[int(class_id)]),
                    ),
                    "confidence": float(confidence),
                    "bbox": [float(value) for value in bbox],
                }
            )
        return objects

    def _load_model(self):
        model_key = str(self.model_path.resolve())
        if model_key in _MODEL_CACHE:
            return _MODEL_CACHE[model_key]

        if not self.model_path.exists():
            logger.error("YOLO checkpoint missing for %s: %s", self.model_spec.key, self.model_path)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"YOLO model '{self.model_spec.key}' checkpoint is missing",
            )

        try:
            install_legacy_checkpoint_modules(self.model_spec.key)
        except LegacyCheckpointCompatibilityError as exc:
            logger.exception("Unable to prepare YOLO model %s", self.model_spec.key)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unable to prepare registered YOLO model '{self.model_spec.key}'",
            ) from exc

        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ultralytics is not installed in the backend environment",
            ) from exc

        try:
            model = YOLO(str(self.model_path))
        except Exception as exc:
            logger.exception("Unable to load YOLO model %s", self.model_spec.key)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unable to load registered YOLO model '{self.model_spec.key}'",
            ) from exc

        loaded_names = {int(key): str(value) for key, value in model.names.items()}
        if model.task != self.model_spec.task:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"Registered YOLO model '{self.model_spec.key}' has task "
                    f"'{model.task}', expected '{self.model_spec.task}'."
                ),
            )
        if loaded_names != self.model_spec.checkpoint_class_names:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"Registered YOLO model '{self.model_spec.key}' has an unexpected "
                    "checkpoint class mapping."
                ),
            )
        _MODEL_CACHE[model_key] = model
        return model
