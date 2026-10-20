"""Apply the reviewed source bundle, close signup, then enable IP HTTPS.

Run the packaged apply.py as sam after sudo -v, while the site is idle.
No migration, firewall changes, host restart or paid services are involved.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import getpass
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip", required=True)
    parser.add_argument("--repo", type=Path, default=Path.home() / "apps/Yolo_system")
    arguments = parser.parse_args()
    sys.path.insert(0, str(arguments.repo / "deploy"))

import requests
from lab_compose_apply import Batch, Failed, IMAGES, need
from lab_backup_verify import Backup, file_hash, keep_sudo_alive, private_write

ALLOWED = {
    "backend/app/core/config.py", "backend/app/services/auth_service.py", "backend/app/api/routes/auth.py",
    "web-frontend/src/services/authService.js", "web-frontend/src/pages/LoginPage.jsx",
    "web-frontend/src/pages/RegisterPage.jsx", "web-frontend/src/hooks/useAuthConfig.js",
    "deploy/public.Dockerfile", "deploy/public.Dockerfile.dockerignore", "deploy/Caddyfile.public",
    "deploy/compose.public.yaml", "deploy/compose.lab.yaml",
}


class GatewaySession(requests.Session):
    public_url = None

    def request(self, method, url, **kwargs):
        prefix = "http://127.0.0.1:8080"
        if self.public_url and (url == prefix or url.startswith(prefix + "/")):
            url = self.public_url + url[len(prefix):]
        return super().request(method, url, **kwargs)


def bundle_plan(repo, package):
    raw = (package / "manifest.json").read_bytes()
    manifest = json.loads(raw)
    need(set(manifest["files"]) == ALLOWED, "更新包檔案範圍不符")
    plan = []
    for name, hashes in manifest["files"].items():
        source = package / "payload" / name
        target = repo / name
        need(source.is_file() and not source.is_symlink() and file_hash(source) == hashes["after"], "更新包內容雜湊不符")
        for parent in (target, *target.parents):
            if parent == repo:
                break
            need(not parent.is_symlink(), "拒絕更新 symlink 來源路徑")
        actual = file_hash(target) if target.is_file() else None
        normalized = hashlib.sha256(target.read_bytes().replace(b"\r\n", b"\n")).hexdigest() if target.is_file() else None
        need(actual in (hashes["before"], hashes["after"])
             or normalized is not None and normalized in (hashes.get("before_lf"), hashes.get("after_lf")),
             "伺服器檔案與更新包基準不同，未覆寫：" + name)
        if actual != hashes["after"]:
            plan.append((name, source, target))
    return hashlib.sha256(raw).hexdigest(), plan


def check_gateway_config(config, address):
    need(config.get("admin", {}).get("disabled") is True, "Caddy admin 必須關閉")
    servers = list(config["apps"]["http"]["servers"].values())
    need(servers and all(server["listen"] == [address + ":443"] for server in servers), "HTTPS 只能綁定指定 IP 的 TCP 443")
    issuers = [issuer for policy in config["apps"]["tls"]["automation"]["policies"]
               for issuer in policy.get("issuers", [])]
    need(issuers and all(i.get("module") == "acme" and i.get("profile") == "shortlived"
         and i.get("ca") == "https://acme-v02.api.letsencrypt.org/directory"
         and i.get("challenges", {}).get("http", {}).get("disabled") is True for i in issuers),
         "必須使用公開 Let's Encrypt shortlived／TLS-ALPN，不可退回本機 CA")


class Public(Batch):
    def __init__(self, repo, package, address):
        super().__init__(repo=repo)
        self.session.close()
        self.session = GatewaySession()
        self.session.trust_env = False
        self.address = str(ipaddress.IPv4Address(address))
        need(ipaddress.ip_address(self.address).is_global, "請使用主機已配置的公網 IPv4")
        self.package = package
        self.work = self.config / "releases" / self.stamp
        self.compose_env = self.config / "compose.env"
        self.full_compose = self.compose + ["-f", str(self.repo / "deploy/compose.public.yaml")]
        self.report = {"success":False, "checks":[], "public_ip":self.address}
        self.changed = False
        self.config_changed = False
        self.temp_id = None
        self.backend_ready = False

    def passed(self, message):
        super().passed(message.replace("nginx", "HTTPS") if self.session.public_url else message)

    def long_docker(self, *args):
        result = subprocess.run(["sudo", "-n", "docker", *args], env=self.env, timeout=1800)
        need(result.returncode == 0, "Docker 建置／驗證失敗，保留原服務與來源備份")

    def preflight(self):
        self.step = "public.preflight"
        need(self.config.is_dir() and self.config.stat().st_uid == os.getuid()
             and not self.config.stat().st_mode & 0o077, "缺少自己的私人部署設定目錄")
        self.work.mkdir(mode=0o700, parents=True)
        self.bundle_hash, self.plan = bundle_plan(self.repo, self.package)
        self.report["bundle_sha256"] = self.bundle_hash
        self.database = self.inspect("sam-yolo-mysql")
        self.original = {"backend":self.inspect("sam-yolo-backend"), "web":self.inspect("sam-yolo-web")}
        self.report["original_backend"] = {key:self.original["backend"][key] for key in ("id", "image")}
        for service, state in self.original.items():
            need(state["running"] and state["project"] == "sam-yolo" and state["service"] == service, "既有 Compose 服務身分不符")
        self.health(8000)
        self.health()
        backup_report = Path.home() / ".local/share/yolo-system/backups/20261020T081258Z-2556729/manifest.json"
        verified = json.loads(backup_report.read_text())
        need(verified.get("success") is True and verified.get("restore_verified") is True, "找不到本次已驗證的備份報告")
        verification = Backup(existing=verified.get("source_backup", str(backup_report.parent)))
        try:
            verification.load_existing()
            need(verification.report["artifacts"] == verified["artifacts"], "成功報告與備份產物不符")
        finally:
            verification.session.close()
        self.report["verified_backup_report"] = str(backup_report)
        inventory = json.loads(subprocess.check_output(["ip", "-j", "-4", "address", "show"], text=True))
        need(any(a.get("local") == self.address for nic in inventory for a in nic.get("addr_info", [])), "指定公網 IP 不在主機介面上")
        gateway = self.inspect("sam-yolo-gateway", optional=True)
        self.previous_gateway = gateway
        if gateway:
            need(gateway["project"] == "sam-yolo" and gateway["service"] == "gateway", "gateway 名稱由其他容器使用")
        else:
            listeners = subprocess.check_output(["ss", "-ltnH", "( sport = :443 )"], text=True)
            need(not listeners.strip(), "443 已被使用，未停止或修改該服務")
        need(shutil.disk_usage(self.repo).free > 20 * 1024**3, "建置至少需要 20 GiB 可用空間")
        self.passed("來源版本／已驗證備份／現有服務／公網介面與 443")
        account = input("專案管理員帳號（沿用原先測試帳號）：").strip()
        password = getpass.getpass("專案登入密碼：")
        auth = self.request("/api/auth/login", method="POST", json={"username":account, "password":password}).json()
        del password
        need(auth["user"]["is_admin"], "請使用專案管理員帳號")
        self.session.headers["Authorization"] = "Bearer " + auth["access_token"]
        self.idle()
        self.baseline = self.snapshot()
        self.report["baseline_fingerprints"] = self.baseline

    def idle(self):
        for status in ("pending", "processing"):
            need(not self.request(f"/api/detections?status={status}&limit=1").json(), "仍有偵測工作，請完成後再執行")

    def sources_and_images(self):
        self.step = "public.build"
        for name, source, target in self.plan:
            if target.exists():
                saved = self.work / "source-backup" / name
                saved.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                saved.write_bytes(target.read_bytes())
                saved.chmod(0o600)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".public-" + self.stamp)
            temporary.write_bytes(source.read_bytes())
            temporary.chmod(0o644)
            os.replace(temporary, target)
        suffix = self.bundle_hash[:12]
        backend_tag = "sam-yolo-backend:public-" + suffix
        gateway_tag = "sam-yolo-gateway:public-" + suffix
        digests = {}
        for tag in ("node:22-bookworm-slim", "caddy:2.11.7-alpine"):
            self.long_docker("pull", tag)
            values = json.loads(self.docker("image", "inspect", "--format", "{{json .RepoDigests}}", tag))
            digests[tag] = next((d for d in values if re.fullmatch(r"(?:node|caddy)@sha256:[0-9a-f]{64}", d)), None)
            need(digests[tag], "無法固定官方基底 image digest")
        self.report["build_base_digests"] = digests
        self.long_docker("build", "--platform", "linux/amd64", "--label", "sam.yolo.public.bundle=" + self.bundle_hash,
            "-f", str(self.repo / "deploy/backend.Dockerfile"), "-t", backend_tag, str(self.repo))
        self.long_docker("build", "--platform", "linux/amd64", "-f", str(self.repo / "deploy/public.Dockerfile"),
            "--label", "sam.yolo.public.bundle=" + self.bundle_hash,
            "--build-arg", "NODE_IMAGE=" + digests["node:22-bookworm-slim"],
            "--build-arg", "CADDY_IMAGE=" + digests["caddy:2.11.7-alpine"], "-t", gateway_tag, str(self.repo))
        self.images = {"backend":self.docker("image", "inspect", "--format", "{{.Id}}", backend_tag).strip(),
                       "gateway":self.docker("image", "inspect", "--format", "{{.Id}}", gateway_tag).strip()}
        need(all(re.fullmatch(r"sha256:[0-9a-f]{64}", value) for value in self.images.values()), "新 image ID 不合法")
        adapted = json.loads(self.docker("run", "--rm", "--network", "none", "-e", "YOLO_PUBLIC_IP=" + self.address,
            self.images["gateway"], "caddy", "adapt", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"))
        check_gateway_config(adapted, self.address)
        self.report["images"] = self.images
        self.passed("來源已備份／backend 與 React-Caddy image 建置／固定基底 digest／HTTPS 設定解析")

    def closed_signup(self, port=8080):
        policy = self.request("/api/auth/config", port=port, headers={"Authorization":None}).json()
        need(policy == {"registration_enabled":False}, "後端尚未關閉自行註冊，拒絕開放入口")
        # Send a valid probe only after the explicit closed policy is confirmed.
        self.request("/api/auth/register", port=port, method="POST", expected=403,
            headers={"Authorization":None}, json={"username":"SignupProbe", "email":"probe@example.com", "password":"Probe1" + secrets.token_hex(16)})

    def preflight_image(self):
        self.step = "public.image-test"
        need(not subprocess.check_output(["ss", "-ltnH", "( sport = :18000 )"], text=True).strip(), "暫用 18000 已被使用")
        args = ["create", "--name", "sam-yolo-public-check-" + self.stamp.lower(), "--network", "host",
            "--runtime=nvidia", "--gpus", "all", "--user", f"{os.getuid()}:{os.getgid()}",
            "--cpus", "4", "--memory", "8g", "--shm-size", "256m", "-e", "APP_PORT=18000", "-e", "ALLOW_REGISTRATION=false"]
        for folder in (".env", "pt", "static"):
            args += ["--mount", f"type=bind,source={self.repo}/backend/{folder},target=/opt/yolo/backend/{folder},readonly"]
        self.temp_id = self.docker(*args, self.images["backend"], "python", "-m", "uvicorn", "main:app",
            "--host", "127.0.0.1", "--port", "18000", "--workers", "1").strip()
        need(re.fullmatch(r"[0-9a-f]{64}", self.temp_id), "暫存容器 ID 不合法")
        self.docker("start", self.temp_id)
        deadline = time.monotonic() + 120
        while True:
            try:
                self.health(18000)
                break
            except (Failed, requests.RequestException):
                need(time.monotonic() < deadline, "新 image 暫用 API 未就緒")
                time.sleep(2)
        self.closed_signup(18000)
        self.long_docker("exec", self.temp_id, "python", "/opt/yolo/deploy/backend_smoke.py", "--gpu")
        self.long_docker("exec", self.temp_id, "python", "-m", "pytest", "-q", "tests/test_yolo_model_registry.py", "tests/test_legacy_checkpoint_compat.py")
        self.cleanup_temp()
        self.passed("新 image 於 18000 關閉註冊／DB health／自訂 YOLO GPU／12 項既有測試")

    def cleanup_temp(self):
        if self.temp_id:
            need(self.temp_id not in (self.database["id"], self.original["backend"]["id"]), "拒絕清除正式容器")
            self.docker("stop", "--time", "30", self.temp_id)
            self.docker("rm", self.temp_id)
            self.temp_id = None

    def update_backend(self):
        self.step = "public.backend"
        need(self.compose_env.is_file() and not self.compose_env.is_symlink()
             and self.compose_env.stat().st_uid == os.getuid() and not self.compose_env.stat().st_mode & 0o077,
             "compose.env 歸屬／權限不符")
        original = self.compose_env.read_text()
        private_write(self.work / "compose.env.before", original)
        names = ("YOLO_PUBLIC_IP", "YOLO_PUBLIC_BACKEND_IMAGE", "YOLO_PUBLIC_GATEWAY_IMAGE")
        common = "\n".join(line for line in original.splitlines() if not any(line.startswith(name + "=") for name in names)) + "\n"
        settings = {"YOLO_PUBLIC_IP":self.address, "YOLO_PUBLIC_BACKEND_IMAGE":self.images["backend"],
                    "YOLO_PUBLIC_GATEWAY_IMAGE":self.images["gateway"]}
        content = common + "".join(name + "=" + value + "\n" for name, value in settings.items())
        settings["YOLO_PUBLIC_BACKEND_IMAGE"] = self.original["backend"]["image"]
        private_write(self.work / "rollback.env", common + "".join(name + "=" + value + "\n" for name, value in settings.items()))
        temporary = self.work / "compose.env.new"
        private_write(temporary, content)
        os.replace(temporary, self.compose_env)
        self.config_changed = True
        self.docker(*self.full_compose, "config", "--quiet")
        self.idle()
        if self.original["backend"]["image"] != self.images["backend"]:
            if self.original["backend"]["image"] != IMAGES["backend"]:
                labels = json.loads(self.docker("image", "inspect", "--format", "{{json .Config.Labels}}", self.original["backend"]["image"])) or {}
                need(labels.get("sam.yolo.public.bundle") == self.bundle_hash, "既有 image 非預期基準／本更新包，未切換")
            self.changed = True
            self.docker(*self.full_compose, "up", "-d", "--no-deps", "--no-build", "--pull", "never", "backend")
        self.wait_backend()
        need(self.inspect("sam-yolo-backend")["image"] == self.images["backend"], "正式 backend image 不符")
        self.closed_signup()
        self.verify_existing()
        self.backend_ready = True
        self.passed("正式 backend 已關閉註冊／原有圖片與對話一致；管理員權限保留")

    def start_gateway(self):
        self.step = "public.https"
        if self.inspect("sam-yolo-gateway", optional=True) is None:
            need(not subprocess.check_output(["ss", "-ltnH", "( sport = :443 )"], text=True).strip(), "443 已由其他服務使用；未操作該服務")
        self.docker("volume", "create", "--label", "sam.yolo.owner=sam-yolo", "sam-yolo-caddy-data")
        labels = json.loads(self.docker("volume", "inspect", "--format", "{{json .Labels}}", "sam-yolo-caddy-data")) or {}
        need(labels.get("sam.yolo.owner") == "sam-yolo", "拒絕使用非本專案憑證 volume")
        self.docker(*self.full_compose, "up", "-d", "--no-deps", "--no-build", "--pull", "never", "gateway")
        gateway = self.inspect("sam-yolo-gateway")
        need(gateway["image"] == self.images["gateway"] and gateway["project"] == "sam-yolo"
             and gateway["service"] == "gateway", "HTTPS 容器身分不符")
        self.report["gateway_id"] = gateway["id"]
        url = "https://" + self.address
        print("申請公開 IP 憑證並驗證 HTTPS（最多 4 分鐘，網站服務已恢復）…", flush=True)
        deadline = time.monotonic() + 240
        with requests.Session() as anonymous:
            anonymous.trust_env = False
            while True:
                try:
                    response = anonymous.get(url + "/api/health", timeout=(5, 10))
                    need(response.status_code == 200 and response.json().get("database") == "connected", "HTTPS 已連通，但 DB health 不符")
                    break
                except requests.RequestException:
                    if time.monotonic() >= deadline:
                        self.report["https_pending"] = True
                        codes = []
                        try:
                            result = subprocess.run(["sudo", "-n", "docker", "logs", "--tail", "100", gateway["id"]],
                                                    capture_output=True, text=True, timeout=15)
                            logs = result.stdout + result.stderr
                            private_write(self.work / "gateway.log", logs)
                            codes = sorted(set(re.findall(r"urn:ietf:params:acme:error:([A-Za-z]+)", logs)))
                        except (OSError, subprocess.SubprocessError):
                            self.report["gateway_log_unavailable"] = True
                        self.report["acme_error_types"] = codes
                        print("ACME error types: " + json.dumps(codes), flush=True)
                        print("PENDING: 公開可信 HTTPS 尚未就緒；保留關閉註冊的 backend 與憑證服務。下一步檢查外部 TCP 443 與憑證申請；未修改防火牆。", flush=True)
                        return False
                    time.sleep(3)
        self.session.public_url = url
        try:
            with socket.create_connection((self.address, 443), timeout=5) as connection:
                with ssl.create_default_context().wrap_socket(connection, server_hostname=self.address) as secured:
                    self.report["certificate_not_after"] = secured.getpeercert().get("notAfter")
        except (OSError, ssl.SSLError):
            self.report["certificate_not_after"] = None
        self.report["automatic_renewal_configured"] = True
        self.passed("公開 CA／IP SAN／HTTPS health；憑證持久 volume 與自動續期設定")
        return True

    def rollback_backend(self):
        self.session.public_url = None
        gateway = self.inspect("sam-yolo-gateway", optional=True)
        if gateway:
            prior = getattr(self, "previous_gateway", None)
            need(gateway["project"] == "sam-yolo" and gateway["service"] == "gateway"
                 and gateway["image"] in (self.images["gateway"], prior["image"] if prior else None), "拒絕停止外來 gateway")
            self.docker("stop", "--time", "30", gateway["id"])
        if self.config_changed:
            rollback = self.work / "rollback.env"
            temporary = self.work / "compose.env.restore"
            private_write(temporary, rollback.read_text())
            os.replace(temporary, self.compose_env)
        if self.changed:
            current = self.inspect("sam-yolo-backend", optional=True)
            if current:
                need(current["project"] == "sam-yolo" and current["service"] == "backend"
                     and current["image"] in (self.images["backend"], IMAGES["backend"], self.original["backend"]["image"]), "拒絕回復外來 backend")
            self.docker(*self.compose, "up", "-d", "--no-deps", "--no-build", "--pull", "never", "backend")
            self.wait_backend()
            self.verify_existing()
            self.report["rollback_verified"] = True
            print("已回復原本的 loopback backend／原有資料；公網入口已停止。", flush=True)

    def run(self):
        try:
            self.preflight()
            self.sources_and_images()
            self.preflight_image()
            self.update_backend()
            if self.start_gateway():
                self.closed_signup()
                self.verify_existing()
                self.routes_and_gpu()
                self.stream_check()
                self.stream_check(agent=True)
                self.report["success"] = True
        except (Exception, KeyboardInterrupt) as exc:
            self.report.update(failed_step=self.step, error=str(exc) if isinstance(exc, Failed) else type(exc).__name__)
            print(f"FAIL [{self.step}]: " + self.report["error"], flush=True)
            if self.changed or self.backend_ready or self.config_changed:
                try:
                    self.rollback_backend()
                except Exception:
                    self.report["rollback_failed"] = True
                    print("需人工檢查本專案 backend／gateway；未操作 MySQL／Ollama。", flush=True)
        finally:
            try:
                self.cleanup_temp()
            except Exception:
                self.report["temporary_cleanup_failed"] = True
                self.report["success"] = False
            self.session.close()
            if self.work.exists():
                private_write(self.work / "report.json", json.dumps(self.report, ensure_ascii=False, indent=2))
            if self.report["success"]:
                print("Admin-only signup / public HTTPS / persistence / GPU / SSE: PASS", flush=True)
                print("網站：https://" + self.address, flush=True)
            print("批次報告：" + str(self.work / "report.json"), flush=True)
        return 0 if self.report["success"] else 2 if self.report.get("https_pending") else 1


if __name__ == "__main__":
    need(sys.platform == "linux" and os.getuid() != 0, "請在 Ubuntu 以 sam 執行，先 sudo -v，不使用 sudo python")
    os.umask(0o077)
    descriptor = os.open(Path.home() / ".config/yolo-system/compose-apply.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    stop = threading.Event()
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        authorization = subprocess.run(["sudo", "-n", "-v"], capture_output=True)
        need(authorization.returncode == 0, "請先執行 sudo -v")
        refresh = threading.Thread(target=keep_sudo_alive, args=(stop,), daemon=True)
        refresh.start()
        raise SystemExit(Public(arguments.repo.resolve(), Path(__file__).resolve().parent, arguments.ip).run())
    finally:
        stop.set()
        os.close(descriptor)
