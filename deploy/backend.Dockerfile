# syntax=docker/dockerfile:1
FROM python:3.11.17-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    YOLO_AUTOINSTALL=false \
    HOME=/tmp/yolo-home \
    MPLCONFIGDIR=/tmp/matplotlib \
    YOLO_CONFIG_DIR=/tmp/ultralytics \
    PYTHONPATH=/opt/yolo/backend \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility

# OpenCV (Ultralytics also installs opencv-python), video encoding and reports.
# No GPU driver or system CUDA toolkit is installed by this image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates ffmpeg fonts-dejavu-core libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Generated on Ubuntu from the environment that passed the actual GPU tests.
# The exact +cu126 torch / torchvision pins select the official CUDA wheels.
COPY deploy/backend-linux.lock /opt/yolo/deploy/backend-linux.lock
RUN python -m pip install --prefer-binary \
        --extra-index-url https://download.pytorch.org/whl/cu126 \
        -r /opt/yolo/deploy/backend-linux.lock \
    && python -m pip check

WORKDIR /opt/yolo/backend
COPY backend/main.py backend/alembic.ini ./
COPY backend/app/ ./app/
COPY backend/migrations/ ./migrations/
COPY backend/scripts/ ./scripts/
COPY backend/tests/test_yolo_model_registry.py backend/tests/test_legacy_checkpoint_compat.py ./tests/

# Keep the platform root above backend: legacy_checkpoint_compat resolves these
# paths relative to app/integrations, and approved checkpoints depend on them.
COPY models/custom_modules/ASFFHead.py /opt/yolo/models/custom_modules/ASFFHead.py
COPY SCAM_DySample.py /opt/yolo/SCAM_DySample.py
COPY AddModules/EfficientViMBlock.py /opt/yolo/AddModules/EfficientViMBlock.py
COPY deploy/backend_smoke.py /opt/yolo/deploy/backend_smoke.py

# Models and media are runtime mounts, never image layers. Run with the host
# user's numeric UID/GID so new media remains owned by the lab account.
RUN mkdir -p pt static /tmp/ultralytics \
    && chmod 1777 /tmp/ultralytics
USER 10001:10001

# --user UID:GID can name a host UID absent from the image's /etc/passwd.
# Python getpass / PyTorch still need a login name and writable cache paths.
# These labels do not change the actual UID selected by Docker.
ENV USER=yolo \
    LOGNAME=yolo \
    XDG_CACHE_HOME=/tmp/yolo-cache \
    TORCHINDUCTOR_CACHE_DIR=/tmp/torchinductor \
    TRITON_CACHE_DIR=/tmp/triton

# Check the DB field, since the existing API can return HTTP 200 during DB loss.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD ["python", "/opt/yolo/deploy/backend_smoke.py", "--health"]

# Linux host networking keeps the existing localhost DB / Ollama settings valid.
# Override the whole command and APP_PORT for the isolated :18000 API preflight.
CMD ["python", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", "--workers", "1"]
