"""Container health probe, custom-checkpoint CUDA or video smoke test.

The CUDA test reads only the mounted approved checkpoints, uses temporary images,
and does not connect to the database or Ollama. No .env mount is needed for it.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import ProxyHandler, build_opener


def health() -> int:
    # Bypass proxy environment variables for this local-only health request.
    port = int(os.environ.get("APP_PORT", "8000"))
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{port}/api/health", timeout=5) as response:
            data = json.load(response)
        return 0 if data.get("status") == "ok" and data.get("database") == "connected" else 1
    except (OSError, ValueError):
        return 1


def gpu_smoke() -> None:
    import torch
    import torchvision
    from PIL import Image
    from torchvision.ops import nms
    from app.integrations.yolo_engine import YoloEngine

    if not torch.cuda.is_available():
        raise SystemExit("CUDA unavailable inside container")
    print(f"PyTorch: {torch.__version__}", flush=True)
    print(f"torchvision: {torchvision.__version__}", flush=True)
    print(f"CUDA runtime: {torch.version.cuda}", flush=True)
    print(f"GPU: {torch.cuda.get_device_name(0)}", flush=True)

    matrix = torch.randn(64, 64, device="cuda:0")
    if not torch.isfinite(matrix @ matrix).all().item():
        raise RuntimeError("GPU matrix test failed")
    boxes = torch.tensor([[0, 0, 10, 10], [1, 1, 9, 9]], dtype=torch.float32, device="cuda:0")
    scores = torch.tensor([0.9, 0.8], device="cuda:0")
    if nms(boxes, scores, 0.5).tolist() != [0]:
        raise RuntimeError("GPU NMS test failed")
    print("GPU matrix / NMS: PASS", flush=True)

    with TemporaryDirectory(prefix="yolo-container-") as folder:
        root = Path(folder)
        image = root / "input.png"
        Image.new("RGB", (640, 640), "white").save(image)
        for key in ("seven_class_asff", "seven_class_dysample", "four_class_evmblock"):
            engine = YoloEngine(model_key=key)
            model = engine._load_model()
            model.to("cuda:0")
            result = engine.detect_image(image)
            device = next(model.model.parameters()).device
            if device.type != "cuda":
                raise RuntimeError(f"{key} did not use CUDA")
            annotated = root / f"{key}.png"
            result.annotated_image.save(annotated)
            with Image.open(annotated) as output:
                output.load()
                if output.size != (640, 640):
                    raise RuntimeError(f"{key} annotation dimensions changed")
            print(f"{key}: PASS | device={device} | objects={len(result.objects)} | annotation=PNG", flush=True)
            del result, engine, model

    gc.collect()
    torch.cuda.empty_cache()
    print("Container custom YOLO GPU smoke test: PASS", flush=True)


def decoded_frames(path: Path) -> int:
    import cv2

    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise RuntimeError("Smoke-test video cannot be opened")
        count = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if frame.shape[:2] != (64, 64):
                raise RuntimeError("Smoke-test video dimensions changed")
            count += 1
        return count
    finally:
        capture.release()


def video_smoke(*, use_cuda: bool = True) -> None:
    """Exercise real tracking/encoding; CPU mode is for local verification only."""
    import cv2
    import numpy as np
    import torch
    from app.integrations.yolo_engine import YoloEngine

    if use_cuda and not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable for container video smoke test")
    with TemporaryDirectory(prefix="yolo-video-") as folder:
        root = Path(folder)
        source, target = root / "input.mp4", root / "result.mp4"
        writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 2, (64, 64))
        try:
            if not writer.isOpened():
                raise RuntimeError("Smoke-test input encoder unavailable")
            for _ in range(4):
                writer.write(np.full((64, 64, 3), 255, dtype=np.uint8))
        finally:
            writer.release()
        if decoded_frames(source) != 4:
            raise RuntimeError("Smoke-test input must contain four frames")
        engine = YoloEngine(model_key="seven_class_asff")
        model = engine._load_model()
        model.to("cuda:0" if use_cuda else "cpu")
        result = engine.detect_video(source, output_video_path=target)
        expected_device = "cuda" if use_cuda else "cpu"
        if next(model.model.parameters()).device.type != expected_device:
            raise RuntimeError("Video tracking used an unexpected device")
        if (result.frame_count, result.image_width, result.image_height) != (4, 64, 64):
            raise RuntimeError("Video tracking returned incomplete metadata")
        if result.preview_image.size != (64, 64):
            raise RuntimeError("Video tracking preview dimensions changed")
        if not target.is_file() or not target.stat().st_size or decoded_frames(target) != 4:
            raise RuntimeError("Video tracking output must decode to four frames")
    print("Container YOLO video smoke test: PASS", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--health", action="store_true")
    mode.add_argument("--gpu", action="store_true")
    mode.add_argument("--video", action="store_true")
    args = parser.parse_args()
    if args.health:
        raise SystemExit(health())
    if args.video:
        video_smoke()
    else:
        gpu_smoke()


if __name__ == "__main__":
    main()
