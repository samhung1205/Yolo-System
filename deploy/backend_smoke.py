"""Container health probe or explicit custom-checkpoint CUDA smoke test.

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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--health", action="store_true")
    mode.add_argument("--gpu", action="store_true")
    args = parser.parse_args()
    if args.health:
        raise SystemExit(health())
    gpu_smoke()


if __name__ == "__main__":
    main()
