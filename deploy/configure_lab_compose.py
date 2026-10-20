"""Write private Compose path/UID settings on the lab Linux host.

Does not read credentials or call Docker. Existing configuration is not replaced.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat
import sys


def main() -> None:
    if sys.platform != "linux" or os.getuid() == 0:
        raise ValueError("請在 Ubuntu 以自己的帳號執行 Python，不要使用 sudo。")
    repo = Path(__file__).resolve().parents[1]
    config = Path.home() / ".config" / "yolo-system"
    for path in (repo / "backend/pt", repo / "backend/static", config):
        if not path.is_dir():
            raise ValueError(f"缺少必要目錄：{path}")
    for path in (repo / "backend/.env", repo / "web-frontend/dist/index.html",
                 config / "nginx.lab.conf", repo / "deploy/compose.lab.yaml"):
        if not path.is_file() or not os.access(path, os.R_OK):
            raise ValueError(f"缺少或無法讀取必要檔案：{path}")
    for path in (config, repo / "backend/.env"):
        metadata = path.stat()
        if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
            raise ValueError(f"必須由目前帳號擁有且不允許群組／其他人存取：{path}")
    if not os.access(repo / "backend/static", os.W_OK):
        raise ValueError("目前帳號無法寫入 backend/static。")
    values = {
        "YOLO_REPO_ROOT": str(repo),
        "YOLO_CONFIG_ROOT": str(config),
        "YOLO_UID": str(os.getuid()),
        "YOLO_GID": str(os.getgid()),
    }
    # Keep generated dotenv values literal and unambiguous, even under sudo.
    if any(any(c in value for c in "\r\n'\"$\\") for value in values.values()):
        raise ValueError("路徑含需額外處理的特殊字元，請回報此訊息。")
    target = config / "compose.env"
    content = "# Paths and numeric identity only; no application credentials.\n"
    content += "".join(f"{key}='{value}'\n" for key, value in values.items())
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(content)
    print(f"Compose host configuration created: {target}")
    print("未變更 backend/.env，未執行 Docker 或重新啟動服務。")


if __name__ == "__main__":
    try:
        main()
    except FileExistsError:
        print("compose.env 已存在，未覆蓋；請回報此訊息。", file=sys.stderr)
        raise SystemExit(1)
    except (ValueError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
