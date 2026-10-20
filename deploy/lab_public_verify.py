"""Resume HTTPS data/SSE acceptance without changing any Docker service.

Run alongside the existing lab_gateway_repair.py and other deployment helpers.
Repeated identical nosniff values are validated as tokens, not one raw string.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from urllib.parse import urlsplit

from lab_gateway_repair import Repair
from lab_compose_apply import Failed, digest, need
from lab_backup_verify import keep_sudo_alive, private_write


def nosniff_values(value):
    tokens = [token.strip().lower() for token in (value or "").split(",")]
    # Stricter than browsers' first-token test: every supplied value must agree.
    need(tokens and all(token == "nosniff" for token in tokens),
         "nosniff 標頭缺少或包含異常值（非單純重複）")
    return tokens


class Verify(Repair):
    def __init__(self, repo, address):
        super().__init__(repo, address)
        self.work = self.config / "releases" / ("public-verify-" + self.stamp)

    def docker(self, *args, **kwargs):
        # This acceptance run cannot build, start, stop, exec into or replace a
        # container, even through inherited methods.
        need(args and args[0] == "inspect", "此驗收只允許 Docker inspect")
        return super().docker(*args, **kwargs)

    def preflight(self):
        self.step = "https.preflight"
        need(self.config.is_dir() and self.config.stat().st_uid == os.getuid()
             and not self.config.stat().st_mode & 0o077, "私人設定目錄權限不符")
        self.work.mkdir(mode=0o700)
        self.protected = {name:self.inspect(name) for name in
                          ("sam-yolo-backend", "sam-yolo-web", "sam-yolo-mysql", "sam-yolo-gateway")}
        gateway = self.protected["sam-yolo-gateway"]
        need(gateway["project"] == "sam-yolo" and gateway["service"] == "gateway" and gateway["running"],
             "HTTPS gateway 身分／狀態不符")
        self.unchanged()
        self.public = True
        response = self.request("/api/health", headers={"Authorization":None})
        need(response.json().get("database") == "connected", "HTTPS DB health 不符")
        tokens = nosniff_values(response.headers.get("X-Content-Type-Options"))
        self.report["trusted_https"] = True
        self.report["health_nosniff_values"] = tokens
        self.report["protected_container_ids"] = {name:state["id"] for name,state in self.protected.items()}
        self.passed("正常 CA／IP SAN／HTTPS DB health；nosniff 有效（" + str(len(tokens)) + " 個相同值）")

    def task_snapshot(self, task_id):
        # Same media/data contract as Batch.task_snapshot, with token validation
        # for combined response headers. Kept here to support the already-copied
        # older Batch helper on Ubuntu without another source-file upload.
        task = self.request(f"/api/detections/{task_id}").json()
        result = {"status":task["status"], "model_sha256":task["model_sha256"], "objects":digest(task["objects"])}
        for field in ("source_image_url", "result_image_url"):
            need(task.get(field), "既有偵測缺少原圖／標註圖 URL")
            url = urlsplit(task[field])
            need(not url.netloc and not url.scheme and url.path.startswith("/static/") and url.query, "媒體 URL 不符")
            response = self.request(url.path)
            tokens = nosniff_values(response.headers.get("X-Content-Type-Options"))
            self.report.setdefault("media_nosniff_counts", []).append(len(tokens))
            result[field] = hashlib.sha256(response.content).hexdigest()
            self.request(url.path, expected=401, headers={"Authorization":None})
            signed = self.request(url.path + "?" + url.query, headers={"Authorization":None})
            nosniff_values(signed.headers.get("X-Content-Type-Options"))
            need(hashlib.sha256(signed.content).hexdigest() == result[field], "signed URL 圖片內容不符")
        return result

    def run(self):
        try:
            self.preflight()
            # Reuses routing, admin login, original baseline fingerprints,
            # protected media checks and both persisted Ollama SSE checks.
            self.acceptance()
            self.passed("既有圖片／對話 SHA-256 與基準一致；Bearer／signed URL／未登入保護通過")
        except (Exception, KeyboardInterrupt) as exc:
            self.report["success"] = False
            self.report.update(failed_step=self.step, error=str(exc) if isinstance(exc, Failed) else type(exc).__name__)
            print(f"FAIL [{self.step}]: " + self.report["error"], flush=True)
        finally:
            try:
                self.unchanged()
            except Exception:
                self.report["success"] = False
                self.report["final_service_check_failed"] = True
            if self.work.is_dir():
                private_write(self.work / "report.json", json.dumps(self.report, ensure_ascii=False, indent=2))
                print("驗收報告：" + str(self.work / "report.json"), flush=True)
            self.session.close()
        print("本輪未建置／重啟／替換服務；Chat／Agent 測試各新增一組對話（執行成功時）。", flush=True)
        if self.report["success"]:
            print("Public HTTPS / existing data / protected media / Chat-Agent SSE: PASS", flush=True)
            print("網站：https://" + self.address, flush=True)
        return 0 if self.report["success"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip", required=True)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    address = ipaddress.ip_address(args.ip)
    need(sys.platform == "linux" and os.getuid() != 0 and address.version == 4 and address.is_global,
         "請在 Ubuntu 以 sam 執行，先 sudo -v；不要 sudo python")
    os.umask(0o077)
    descriptor = os.open(Path.home() / ".config/yolo-system/compose-apply.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    stop = threading.Event()
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        need(subprocess.run(["sudo","-n","-v"], capture_output=True).returncode == 0, "請先執行 sudo -v")
        threading.Thread(target=keep_sudo_alive, args=(stop,), daemon=True).start()
        return Verify(args.repo.resolve(), str(address)).run()
    finally:
        stop.set()
        os.close(descriptor)


if __name__ == "__main__":
    raise SystemExit(main())
