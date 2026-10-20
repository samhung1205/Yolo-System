"""Batch-adopt lab backend/web into Compose and verify; preserve originals.

Run as the lab user after `sudo -v`, while the website is idle. Credentials stay
in memory. MySQL/Ollama are inspected but never stopped or reconfigured.
"""
from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import getpass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import urlsplit

import requests

IMAGES = {
    "backend": "sha256:2fdf4814f7bef3919489586754819b7879059f8108dec8eb5a8ff09c8030a945",
    "web": "sha256:0d831f5435ede3eeaba5768270c9e6f542d58306f69bb61f148e5c2374b57c56",
}
SPEC_IMAGES = {"backend": IMAGES["backend"], "web":
               "nginx@sha256:970364228b1e4f932abc22d321932816782cca8a20b85a77552a7cfe9acfb3b5"}
INSPECT = ('{"id":{{json .Id}},"image":{{json .Image}},'
           '"state":{{json .State}},"user":{{json .Config.User}},'
           '"labels":{{json (index .Config "Labels")}},'
           '"restart":{{json .HostConfig.RestartPolicy.Name}},'
           '"network":{{json .HostConfig.NetworkMode}},"mounts":{{json .Mounts}}}')


class Failed(Exception):
    pass


def need(condition, message):
    if not condition:
        raise Failed(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def parse_inspect(raw):
    """Normalize optional metadata in Python, without nested Go lookups.

    Discard labels and health logs immediately; never select Config.Env.
    """
    value = json.loads(raw)
    state = value.pop("state") or {}
    labels = value.pop("labels") or {}
    value["running"] = bool(state.get("Running"))
    value["health"] = (state.get("Health") or {}).get("Status")
    value["project"] = labels.get("com.docker.compose.project")
    value["service"] = labels.get("com.docker.compose.service")
    return value


class Batch:
    def __init__(self, repo=None):
        self.repo = (repo or Path(__file__).resolve().parents[1]).resolve()
        self.config = Path.home() / ".config/yolo-system"
        self.stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{os.getpid()}"
        self.compose = ["compose", "--env-file", str(self.config / "compose.env"),
                        "-f", str(self.repo / "deploy/compose.lab.yaml")]
        self.session = requests.Session()
        self.session.trust_env = False
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("YOLO_")}
        self.original = {}
        self.touched = []
        self.report = {"success": False, "checks": [], "original_containers": {}, "backups": {}}
        self.step = "preflight"

    def passed(self, message):
        self.report["checks"].append(message)
        print("PASS: " + message, flush=True)

    def docker(self, *args, optional=False):
        result = subprocess.run(["sudo", "-n", "docker", *args], env=self.env,
                                text=True, capture_output=True, timeout=150)
        if result.returncode:
            error = result.stderr.lower()
            missing = "no such object" in error or "no such container" in error
            if optional and args[0] == "inspect" and missing:
                return None
            # Never dump arbitrary Docker output, inspect Env or config contents.
            if "template" in error:
                reason = "inspect 樣板解析失敗"
            elif "password is required" in error or "a terminal is required" in error:
                reason = "sudo 驗證已過期，請先執行 sudo -v"
            elif "permission denied" in error:
                reason = "Docker 存取權限不足"
            elif "cannot connect" in error or "is the docker daemon running" in error:
                reason = "無法連線 Docker daemon"
            elif missing:
                reason = "指定容器不存在"
            else:
                reason = "請查看該服務狀態與日誌"
            self.report["docker_error"] = {"operation": args[0], "exit_code": result.returncode, "reason": reason}
            raise Failed(f"Docker {args[0]} 失敗（exit {result.returncode}）：{reason}")
        return result.stdout

    def inspect(self, name, optional=False):
        raw = self.docker("inspect", "--type", "container", "--format", INSPECT, name, optional=optional)
        return parse_inspect(raw) if raw is not None else None

    def request(self, path, *, port=8080, method="GET", expected=200, **kwargs):
        response = self.session.request(method, f"http://127.0.0.1:{port}" + path,
                                        timeout=(5, 180), allow_redirects=False, **kwargs)
        endpoint = "/static/[media]" if path.startswith("/static/") else path.split("?")[0]
        need(response.status_code == expected,
             f"{method} {endpoint}: HTTP {response.status_code}，預期 {expected}")
        return response

    def health(self, port=8080):
        data = self.request("/api/health", port=port).json()
        need(data.get("status") == "ok" and data.get("database") == "connected", "DB health 未通過")

    def wait_backend(self):
        until = time.monotonic() + 180
        while time.monotonic() < until:
            state = self.inspect("sam-yolo-backend")
            if state["running"] and state["health"] == "healthy":
                self.health(8000)
                return
            time.sleep(3)
        raise Failed("backend 在 180 秒內未變成 healthy")

    def preflight(self):
        need(sys.platform == "linux" and os.getuid() != 0, "請在 Ubuntu 以自己的帳號執行 Python，不要 sudo Python")
        need((self.config / "compose.env").is_file(), "缺少已驗證的 compose.env")
        raw = self.docker(*self.compose, "config", "--format", "json")
        normalized = json.loads(raw)
        services = normalized["services"]
        need(normalized["name"] == "sam-yolo" and set(services) == {"backend", "web"}, "Compose project／服務範圍不符")
        for service in ("backend", "web"):
            name = "sam-yolo-" + service
            self.step = "preflight.inspect." + service
            state = self.inspect(name)
            spec = services[service]
            need(spec["image"] == SPEC_IMAGES[service] and spec.get("pull_policy") == "never",
                 "Compose 未固定使用已驗證的 image")
            need(not spec.get("build") and not spec.get("privileged") and not spec.get("entrypoint")
                 and not spec.get("command"), "Compose 啟動方式與已驗證設定不符")
            need(state["running"] and state["image"] == IMAGES[service], f"{name} 狀態或 image 不符")
            need(state["restart"] == "unless-stopped", "原容器 restart policy 與預期不符，避免備用容器自行啟動")
            need(state["network"] == spec["network_mode"] == "host", "網路模式不符")
            actual = {(m["Source"], m["Destination"], m["RW"]) for m in state["mounts"]}
            desired = {(m["source"], m["target"], not m.get("read_only", False)) for m in spec["volumes"]}
            need(actual == desired, f"{name} 掛載與目前服務不一致")
            if service == "backend":
                need(state["user"] == spec["user"] == f"{os.getuid()}:{os.getgid()}", "backend UID／GID 不符")
            managed = state["project"] == "sam-yolo" and state["service"] == service
            need(managed or not state["project"], f"{name} 屬於其他 Compose project")
            self.original[service] = state
            self.report["original_containers"][service] = state["id"]
            self.report["backups"][service] = name + "-before-compose-" + self.stamp
        self.step = "preflight.inspect.mysql"
        self.database = self.inspect("sam-yolo-mysql")
        need(self.database["running"] and any(m.get("Name") == "sam-yolo-mysql-data"
             and m["Destination"] == "/var/lib/mysql" for m in self.database["mounts"]), "現有 MySQL volume 不符")
        self.health(8000)
        self.health()
        self.step = "preflight.login"
        username = input("專案管理員帳號（與先前測試相同）：").strip()
        password = getpass.getpass("專案登入密碼：")
        auth = self.request("/api/auth/login", method="POST",
                            json={"username": username, "password": password}).json()
        del password
        need(auth["user"]["is_admin"], "請使用專案管理員，以檢查所有人的進行中偵測")
        self.session.headers["Authorization"] = "Bearer " + auth["access_token"]
        for status in ("pending", "processing"):
            tasks = self.request(f"/api/detections?status={status}&limit=1").json()
            need(not tasks, "仍有進行中偵測，請完成後再執行批次")
        self.baseline = self.snapshot()
        self.report["baseline_fingerprints"] = self.baseline
        self.report["mysql_container_id"] = self.database["id"]
        self.passed("前置檢查／帳號／原有圖片與對話基準")

    def snapshot(self):
        tasks = self.request("/api/detections?status=completed&source_type=image&limit=3").json()
        conversations = self.request("/api/chat?limit=5").json()
        need(tasks and len(conversations) >= 2, "沒有找到既有測試圖片／兩組對話，請使用先前測試的專案帳號")
        return {"tasks": {t["id"]: self.task_snapshot(t["id"]) for t in tasks},
                "chats": {c["conversation_id"]: digest(self.request("/api/chat/" + c["conversation_id"]).json()["messages"])
                          for c in conversations}}

    def task_snapshot(self, task_id):
        task = self.request(f"/api/detections/{task_id}").json()
        result = {"status": task["status"], "model_sha256": task["model_sha256"], "objects": digest(task["objects"])}
        for field in ("source_image_url", "result_image_url"):
            need(task.get(field), "既有偵測缺少原圖／標註圖 URL")
            url = urlsplit(task[field])
            need(not url.netloc and not url.scheme and url.path.startswith("/static/") and url.query, "媒體 URL 不符")
            response = self.request(url.path)
            values = (response.headers.get("X-Content-Type-Options") or "").split(",")
            need(all(value.strip().lower() == "nosniff" for value in values), "媒體 nosniff 標頭缺少或包含異常值")
            result[field] = hashlib.sha256(response.content).hexdigest()
            self.request(url.path, expected=401, headers={"Authorization": None})
            signed = self.request(url.path + "?" + url.query, headers={"Authorization": None})
            need(hashlib.sha256(signed.content).hexdigest() == result[field], "signed URL 圖片內容不符")
        return result

    def verify_existing(self):
        for task_id, baseline in self.baseline["tasks"].items():
            need(self.task_snapshot(task_id) == baseline, "切換後原有偵測／圖片內容不符")
        for conversation, baseline in self.baseline["chats"].items():
            need(digest(self.request("/api/chat/" + conversation).json()["messages"]) == baseline, "切換後原有對話不符")
        state = self.inspect("sam-yolo-mysql")
        need(state["id"] == self.database["id"] and state["mounts"] == self.database["mounts"] and state["running"], "MySQL 容器或掛載改變")

    def adopt(self, service):
        self.step = "adopt " + service
        state = self.original[service]
        if state["project"] == "sam-yolo" and state["service"] == service:
            self.passed(service + " 已由 Compose 管理，保留原容器")
            return
        name = "sam-yolo-" + service
        backup = self.report["backups"][service]
        need(self.inspect(backup, optional=True) is None, "備用容器名稱已存在")
        need(self.inspect(name)["id"] == state["id"], "切換前容器身分已改變")
        self.touched.append(service)  # Include a stop/rename failure in rollback.
        self.docker("stop", "--time", "120" if service == "backend" else "30", name)
        self.docker("rename", name, backup)
        self.docker(*self.compose, "up", "-d", "--no-deps", "--no-build", "--pull", "never", service)
        current = self.inspect(name)
        need(current["project"] == "sam-yolo" and current["service"] == service
             and current["image"] == IMAGES[service], "Compose 標籤或 image 不符")
        if service == "backend":
            self.wait_backend()
        else:
            until = time.monotonic() + 30
            while True:
                try:
                    self.health()
                    break
                except (Failed, requests.RequestException):
                    if time.monotonic() >= until:
                        raise Failed("nginx 在 30 秒內未恢復 DB health")
                    time.sleep(2)
        self.verify_existing()
        self.passed(service + " 納管／health／既有資料內容一致")

    def routes_and_gpu(self):
        self.step = "routes and GPU"
        anonymous = {"Authorization": None}
        for path, expected, html in (("/", 200, True), ("/agent", 200, True),
                                      ("/api/not-a-route", 404, False), ("/docs", 404, False),
                                      ("/static/avatars/not-a-file.png", 401, False),
                                      ("/assets/not-a-file.js", 404, False)):
            r = self.request(path, expected=expected, headers=anonymous)
            if html:
                need("text/html" in r.headers.get("Content-Type", ""), "SPA 未回 HTML")
                need(r.headers.get("Cache-Control") == "no-store", "SPA HTML 快取設定不符")
            else:
                need("text/html" not in r.headers.get("Content-Type", "") or path.startswith("/assets/"), "API／媒體錯誤被 SPA 吃掉")
        self.docker("exec", "sam-yolo-backend", "python", "-c",
                    "import torch; assert torch.cuda.is_available(); "
                    "x=torch.randn(64,64,device='cuda:0'); assert torch.isfinite(x@x).all().item(); print('CUDA PASS')")
        self.passed("首頁／深連結／API 與媒體錯誤分流／Compose CUDA kernel")

    def stream_check(self, agent=False):
        label = "Agent" if agent else "Chat"
        self.step = label + " SSE"
        groups = self.request("/api/models?purpose=" + ("agent" if agent else "chat")).json()
        need(not any(g["available"] for g in groups if g["provider"] in ("openai", "deepseek")), "付費 provider 仍啟用")
        path = "/api/agent/chat/stream" if agent else "/api/chat/stream"
        payload = ({"message": "請使用歷史統計工具，簡短告訴我偵測任務總數。", "mode": "history_analysis", "provider": "ollama"}
                   if agent else {"question": "請用繁體中文簡短問好。", "provider": "ollama"})
        started = time.monotonic()
        chunks = []
        done = None
        first = None
        with self.request(path, method="POST", json=payload, stream=True) as response:
            need("text/event-stream" in response.headers.get("Content-Type", ""), "SSE Content-Type 不符")
            response.encoding = "utf-8"
            for line in response.iter_lines(chunk_size=1, decode_unicode=True):
                need(time.monotonic() - started < 180, "SSE 超過測試時限")
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                need(event.get("type") != "error", label + " SSE 回傳 error 事件")
                if event.get("type") == "chunk" and event.get("delta"):
                    first = first if first is not None else time.monotonic() - started
                    chunks.append(event["delta"])
                if event.get("type") == "done":
                    done = event
                    break
        need(done is not None and chunks and done.get("answer", "").strip(), label + " SSE 缺少 chunk／done／答案")
        if agent:
            need(any(t.get("tool") == "summarize_detection_history" and t.get("ok") is True
                     for t in (done.get("tool_calls") or [])), "Agent SSE 歷史工具未成功")
        history = self.request("/api/chat/" + done["conversation_id"]).json()
        need(any(m["answer"] == done["answer"] for m in history["messages"]), label + " SSE 對話未保存")
        self.report[label.lower() + "_sse"] = {"first_chunk_seconds": round(first, 3),
            "total_seconds": round(time.monotonic() - started, 3), "chunks": len(chunks)}
        self.passed(f"{label} 經 nginx SSE／對話保存（首片段 {first:.2f}s，{len(chunks)} 個片段）")

    def rollback(self):
        errors = []
        for service in reversed(self.touched):
            name = "sam-yolo-" + service
            backup = self.report["backups"][service]
            original = self.original[service]
            try:
                current = self.inspect(name, optional=True)
                if current and current["id"] == original["id"]:
                    if not current["running"]:
                        self.docker("start", name)
                    continue
                saved = self.inspect(backup)
                need(saved["id"] == original["id"], "備用容器身分不符")
                if current:
                    need(current["project"] == "sam-yolo" and current["service"] == service
                         and current["image"] == IMAGES[service], "拒絕操作非本次 Compose 容器")
                    self.docker("stop", "--time", "120", name)
                    self.docker("rename", name, name + "-failed-" + self.stamp)
                self.docker("rename", backup, name)
                self.docker("start", name)
            except Exception:
                errors.append(service)
        if not errors:
            try:
                self.wait_backend()
                self.health()
                self.verify_existing()
                self.report["rollback_verified"] = True
            except Exception:
                errors.append("health/data")
                self.report["rollback_verified"] = False
        self.report["rollback_failed_services"] = errors
        print("回復結果：" + ("已回復原容器；請保留報告。" if not errors else "需手動處理：" + ", ".join(errors)), flush=True)

    def inventory(self):
        self.report["free_gib"] = round(shutil.disk_usage(self.repo).free / 1024**3, 1)
        for key, cmd in (("network", ["ip", "-j", "-4", "address", "show", "scope", "global"]),
                         ("ollama_enabled", ["systemctl", "is-enabled", "ollama"]),
                         ("ollama_active", ["systemctl", "is-active", "ollama"])):
            try:
                result = subprocess.run(cmd, text=True, capture_output=True, timeout=10)
                if key == "network":
                    data = json.loads(result.stdout)
                    self.report[key] = [addr["local"] for nic in data for addr in nic.get("addr_info", []) if addr.get("family") == "inet"]
                else:
                    self.report[key] = result.stdout.strip()
            except Exception:
                self.report[key] = "unavailable"
        print("後續盤點：" + json.dumps({k: self.report[k] for k in ("free_gib", "network", "ollama_enabled", "ollama_active")}, ensure_ascii=False), flush=True)

    def run(self):
        try:
            self.preflight()
            for service in ("backend", "web"):
                self.adopt(service)
            self.verify_existing()
            self.routes_and_gpu()
            self.stream_check()
            self.stream_check(agent=True)
            self.inventory()
            self.report["success"] = True
            print("Compose adoption / persistence / routing / GPU / Chat-Agent SSE: PASS", flush=True)
        except (Exception, KeyboardInterrupt) as exc:
            self.report["failed_step"] = self.step
            self.report["error"] = str(exc) if isinstance(exc, Failed) else type(exc).__name__
            print(f"FAIL [{self.step}]: " + self.report["error"], flush=True)
            if self.touched:
                self.rollback()
            else:
                print("本次未停止或更換任何容器。", flush=True)
        finally:
            self.session.close()
            self.report["changed_services"] = list(self.touched)
            report_dir = self.config / "reports"
            report_dir.mkdir(mode=0o700, exist_ok=True)
            target = report_dir / ("compose-" + self.stamp + ".json")
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(self.report, output, ensure_ascii=False, indent=2)
            print("批次報告：" + str(target), flush=True)
        return 0 if self.report["success"] else 1


if __name__ == "__main__":
    if sys.platform != "linux" or os.getuid() == 0:
        raise SystemExit("請在 Ubuntu 執行：sudo -v，接著以自己的帳號執行 Python。")
    lock_path = Path.home() / ".config/yolo-system/compose-apply.lock"
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("已有 Compose 批次正在執行，請勿重複啟動。")
        raise SystemExit(Batch().run())
    finally:
        os.close(descriptor)
