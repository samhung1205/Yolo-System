"""
YOLO integration wrapper for backend detection.
"""
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import cv2
from fastapi import HTTPException, status
from PIL import Image

from app.integrations.legacy_checkpoint_compat import (
    LegacyCheckpointCompatibilityError,
    install_legacy_checkpoint_modules,
)
from app.integrations.model_registry import (
    YoloModelRegistryError,
    YoloModelSpec,
    get_yolo_model,
)

_MODEL_CACHE: dict[str, object] = {}


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

    def detect_image(self, image_path: Path, conf: float = 0.25, iou: float = 0.45) -> DetectionRunResult:
        model = self._load_model()

        started_at = perf_counter()
        result = model.predict(source=str(image_path), conf=conf, iou=iou, verbose=False)[0]
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
                result = model.track(source=frame, persist=True, conf=conf, iou=iou, verbose=False)[0]
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

    def _extract_objects(self, result) -> list[dict]:
        objects = []
        boxes = result.boxes
        if boxes is None:
            return objects

        xyxy = boxes.xyxy.tolist()
        class_ids = boxes.cls.tolist()
        confidences = boxes.conf.tolist()
        object_indexes = None
        if getattr(boxes, "id", None) is not None:
            object_indexes = boxes.id.tolist()

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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"YOLO model not found: {self.model_path}",
            )

        try:
            install_legacy_checkpoint_modules(self.model_spec.key)
        except LegacyCheckpointCompatibilityError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"Unable to prepare registered YOLO model '{self.model_spec.key}': "
                    f"{exc}"
                ),
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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"Unable to load registered YOLO model '{self.model_spec.key}': "
                    f"{exc}"
                ),
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
