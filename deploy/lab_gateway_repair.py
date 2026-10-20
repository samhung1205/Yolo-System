"""Verify Docker Snap's NNP incompatibility, then replace gateway only.

Run from the project's deploy/ as sam after sudo -v. Existing Compose and backup
helpers must remain alongside this file. No image build, download or GPU test.
"""
from __future__ import annotations

import argparse
import fcntl
import getpass
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

import requests
from lab_compose_apply import Batch, Failed, need
from lab_backup_verify import keep_sudo_alive, private_write


NNP_ORIGINAL = "security_opt: [no-new-privileges:true]"
NNP_TEMPLATE = 'security_opt: ["no-new-privileges:${YOLO_GATEWAY_NNP:-true}"]'
RUNTIME_CHECK = (
    "awk '/^(NoNewPrivs|Seccomp|CapEff|CapBnd):/ {print}' /proc/self/status; "
    "printf 'AppArmor: '; cat /proc/self/attr/current; /usr/bin/caddy version"
)


def nnp_env(content):
    pattern = r"(?m)^YOLO_GATEWAY_NNP=(?:true|false)$"
    count = len(re.findall(pattern, content))
    need(count <= 1 and content.count("YOLO_GATEWAY_NNP=") == count, "NNP 參數格式不符，未覆寫")
    if count:
        return re.sub(pattern, "YOLO_GATEWAY_NNP=false", content)
    return content.rstrip("\n") + "\nYOLO_GATEWAY_NNP=false\n"


def source_patch(content):
    if NNP_TEMPLATE in content:
        need(NNP_ORIGINAL not in content and content.count(NNP_TEMPLATE) == 1, "NNP 設定重複")
        return content
    need(content.count(NNP_ORIGINAL) == 1, "compose.public.yaml 不是預期版本，未覆寫")
    return content.replace(NNP_ORIGINAL, NNP_TEMPLATE, 1)


def check_spec(config, image, nnp="false"):
    gateway = config.get("services", {}).get("gateway", {})
    need(config.get("name") == "sam-yolo" and gateway.get("container_name") == "sam-yolo-gateway"
         and gateway.get("image") == image, "Compose gateway 身分／image 不符")
    need(gateway.get("network_mode") == "host" and gateway.get("read_only") is True
         and gateway.get("cap_drop") == ["ALL"] and gateway.get("cap_add") == ["NET_BIND_SERVICE"]
         and gateway.get("security_opt") == ["no-new-privileges:" + nnp]
         and not gateway.get("privileged") and not gateway.get("entrypoint") and not gateway.get("command"),
         "gateway 權限不符；只允許已驗證的 Snap NNP 相容例外")
    volumes = gateway.get("volumes", [])
    need(len(volumes) == 1 and volumes[0].get("type") == "volume"
         and volumes[0].get("source") == "caddy_data" and volumes[0].get("target") == "/data"
         and not volumes[0].get("read_only")
         and config.get("volumes", {}).get("caddy_data", {}).get("name") == "sam-yolo-caddy-data"
         and config.get("volumes", {}).get("caddy_data", {}).get("external") is True,
         "憑證持久 volume 不符")


class Repair(Batch):
    def __init__(self, repo, address):
        super().__init__(repo)
        self.address = address
        self.work = self.config / "releases" / ("gateway-snap-nnp-" + self.stamp)
        self.env_path = self.config / "compose.env"
        self.full = self.compose + ["-f", str(repo / "deploy/compose.public.yaml")]
        self.env_changed = False
        self.startup_ok = False
        self.public = False
        self.compatibility_confirmed = False

    def docker(self, *args, optional=False):
        result = subprocess.run(["sudo", "-n", "docker", *args], env=self.env,
                                capture_output=True, text=True, timeout=150)
        if result.returncode:
            missing = "no such object" in result.stderr.lower() or "no such container" in result.stderr.lower()
            if optional and args[0] == "inspect" and missing:
                return None
            # These commands never receive project credentials or Config.Env.
            # Preserve the failure privately instead of losing exec/build errors.
            if self.work.is_dir():
                path = self.work / ("docker-error-" + str(time.time_ns()) + ".log")
                private_write(path, result.stdout + result.stderr)
            try:
                from lab_https_diagnose import redact
                reason = redact(result.stderr[-1000:])
            except ImportError:
                reason = "詳細錯誤已存私人報告目錄"
            raise Failed(f"Docker {args[0]} 失敗（exit {result.returncode}）：" + reason)
        return result.stdout

    def request(self, path, *, port=8080, method="GET", expected=200, **kwargs):
        if not self.public or port != 8080:
            return super().request(path, port=port, method=method, expected=expected, **kwargs)
        response = self.session.request(method, "https://" + self.address + path,
                                        timeout=(5, 180), allow_redirects=False, **kwargs)
        endpoint = "/static/[media]" if path.startswith("/static/") else path.split("?")[0]
        need(response.status_code == expected, f"{method} {endpoint}: HTTP {response.status_code}，預期 {expected}")
        return response

    def passed(self, message):
        super().passed(message.replace("nginx", "HTTPS") if self.public else message)

    def owned_gateway(self, images=None):
        current = self.inspect("sam-yolo-gateway")
        need(current["project"] == "sam-yolo" and current["service"] == "gateway", "拒絕操作非本專案 gateway")
        if images is not None:
            need(current["image"] in images, "gateway image 已被其他操作變更，未更換")
        return current

    def unchanged(self):
        for name, original in self.protected.items():
            current = self.inspect(name)
            need(current["id"] == original["id"] and current["image"] == original["image"]
                 and current["mounts"] == original["mounts"] and current["running"], name + " 身分／掛載／狀態改變")
        self.health(8000)
        need(self.request("/api/auth/config", port=8000).json() == {"registration_enabled":False}, "關閉註冊政策不符")

    def probe(self, image, script, nnp):
        # No mounts, published ports, website process or ACME activity. Only NNP
        # differs between these two otherwise identical isolated probes.
        return self.docker("run", "--rm", "--network", "none", "--read-only",
                           "--cap-drop", "ALL", "--cap-add", "NET_BIND_SERVICE",
                           "--security-opt", "no-new-privileges:" + nnp, "--cpus", "1", "--memory", "384m",
                           "--entrypoint", "/bin/sh", image, "-ec", script)

    def prepare(self):
        self.step = "gateway.preflight"
        need(self.config.is_dir() and self.config.stat().st_uid == os.getuid()
             and not self.config.stat().st_mode & 0o077, "私人設定目錄權限不符")
        need(self.env_path.is_file() and not self.env_path.is_symlink()
             and self.env_path.stat().st_uid == os.getuid() and not self.env_path.stat().st_mode & 0o077,
             "compose.env 不是自己的私人一般檔案")
        self.work.mkdir(mode=0o700)
        self.protected = {name:self.inspect(name) for name in ("sam-yolo-backend", "sam-yolo-web", "sam-yolo-mysql")}
        self.unchanged()
        gateway = self.owned_gateway()
        self.old_image = gateway["image"]
        self.new_image = self.old_image
        self.env_before = self.env_path.read_text()
        need(len(re.findall(r"(?m)^YOLO_PUBLIC_GATEWAY_IMAGE=" + re.escape(self.old_image) + r"$", self.env_before)) == 1,
             "compose.env 的 gateway image 與現有容器不同，未覆寫")
        need(re.search(r"(?m)^YOLO_PUBLIC_IP=" + re.escape(self.address) + r"$", self.env_before), "公網 IP 與私人 Compose 設定不符")
        labels = json.loads(self.docker("image", "inspect", "--format", "{{json .Config.Labels}}", self.old_image)) or {}
        need(re.fullmatch(r"[0-9a-f]{64}", labels.get("sam.yolo.public.bundle", "")), "gateway image 缺少原更新包標記")
        self.report["original_gateway_image"] = self.old_image
        self.report["protected_container_ids"] = {name:state["id"] for name,state in self.protected.items()}
        snap = subprocess.run(["snap", "list", "docker"], capture_output=True, text=True, timeout=15)
        need(snap.returncode == 0 and any(line.startswith("docker ") for line in snap.stdout.splitlines()),
             "未確認 Docker Snap；不變更 NNP")
        self.old_apparmor = json.loads(self.docker("inspect", "--format", "{{json .AppArmorProfile}}", gateway["id"]))
        source = self.repo / "deploy/compose.public.yaml"
        need(source.is_file() and not source.is_symlink(), "找不到一般 compose.public.yaml")
        self.source = source
        self.source_before = source.read_text()
        self.source_after = source_patch(self.source_before)
        self.passed("本專案 gateway／既有服務與關閉註冊／私人 image 參數／Docker Snap")

    def validate_runtime(self):
        self.step = "gateway.snap_ab"
        denied = False
        try:
            self.probe(self.old_image, RUNTIME_CHECK, "true")
        except Failed as exc:
            denied = "operation not permitted" in str(exc).lower()
        need(denied, "未重現 NNP=true 的 exec EPERM；不變更正式服務")
        output = self.probe(self.old_image, RUNTIME_CHECK, "false")
        fields = dict(re.findall(r"^(NoNewPrivs|Seccomp|CapEff|CapBnd|AppArmor):\s*(.+)$", output, re.M))
        need(fields.get("NoNewPrivs") == "0" and fields.get("Seccomp") == "2"
             and int(fields.get("CapEff", "0"), 16) == 0x400
             and int(fields.get("CapBnd", "0"), 16) == 0x400
             and "(enforce)" in fields.get("AppArmor", "")
             and re.search(r"(?m)^v2\.11\.7\b", output),
             "NNP=false 的 Caddy／AppArmor／seccomp／最小 capability 未全部通過，未變更正式服務")
        self.report["runtime_ab"] = {"nnp_true_exec_eperm":True, "nnp_false":fields, "caddy_version_pass":True}
        self.compatibility_confirmed = True
        self.passed("隔離 A/B：NNP=true 重現 exec EPERM；false 可執行 Caddy，AppArmor enforce／seccomp／唯一 NET_BIND_SERVICE 通過")

    def switch(self):
        self.step = "gateway.switch"
        need(self.compatibility_confirmed, "尚未通過 Snap A/B 驗證，未切換")
        self.owned_gateway({self.old_image})
        self.unchanged()
        need(self.env_path.read_text() == self.env_before and self.source.read_text() == self.source_before,
             "切換前私人設定／Compose 來源已改變，未覆寫")
        updated = nnp_env(self.env_before)
        candidate = self.work / "compose.env.candidate"
        private_write(candidate, updated)
        candidate_source = self.work / "compose.public.candidate.yaml"
        private_write(candidate_source, self.source_after)
        configuration = json.loads(self.docker("compose", "--env-file", str(candidate), "-f", str(self.repo / "deploy/compose.lab.yaml"),
                                              "-f", str(candidate_source), "config", "--format", "json"))
        check_spec(configuration, self.new_image)
        private_write(self.work / "compose.env.before", self.env_before)
        private_write(self.work / "compose.public.yaml.before", self.source_before)
        temporary = self.work / "compose.env.next"
        private_write(temporary, updated)
        self.env_changed = True
        os.replace(temporary, self.env_path)
        temporary = self.source.with_name("compose.public.yaml.snap-" + self.stamp)
        temporary.write_text(self.source_after)
        temporary.chmod(0o644)
        os.replace(temporary, self.source)
        self.docker(*self.full, "up", "-d", "--no-deps", "--no-build", "--pull", "never", "gateway")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            gateway = self.owned_gateway({self.new_image})
            state = json.loads(self.docker("inspect", "--format", "{{json .State}}", gateway["id"]))
            listeners = subprocess.check_output(["ss", "-ltnH", "( sport = :443 )"], text=True)
            if state.get("Running") and not state.get("Restarting") and self.address + ":443" in listeners:
                self.docker("exec", gateway["id"], "/usr/bin/caddy", "version")
                profile = json.loads(self.docker("inspect", "--format", "{{json .AppArmorProfile}}", gateway["id"]))
                need(profile == self.old_apparmor, "gateway AppArmor profile 改變，回復原設定")
                self.startup_ok = True
                break
            time.sleep(2)
        need(self.startup_ok, "修復 gateway 未穩定監聽 443，回復原設定")
        self.unchanged()
        self.passed("只替換 gateway（同 image／NNP Snap 例外）；Caddy 與 IP:443 正常；backend／web／MySQL 原容器不變")

    def trusted_https(self):
        self.step = "gateway.https"
        print("驗證公開可信 HTTPS（最多約 2 分鐘；不跳過憑證驗證）…", flush=True)
        deadline = time.monotonic() + 120
        with requests.Session() as anonymous:
            anonymous.trust_env = False
            while True:
                self.owned_gateway({self.new_image})
                try:
                    response = anonymous.get("https://" + self.address + "/api/health", timeout=(3, 5), allow_redirects=False)
                    need(response.status_code == 200 and response.json().get("database") == "connected", "HTTPS health 不符")
                    self.public = True
                    self.report["trusted_https"] = True
                    self.passed("公開 CA／IP SAN／HTTPS DB health")
                    return True
                except requests.RequestException as exc:
                    self.report["last_tls_exception"] = type(exc).__name__
                if time.monotonic() >= deadline:
                    self.report["https_pending"] = True
                    print("PENDING: Caddy 啟動已修復；公開可信 HTTPS 仍待確認，保留入口與憑證自動重試。", flush=True)
                    return False
                time.sleep(3)

    def acceptance(self):
        self.step = "gateway.acceptance"
        anonymous = {"Authorization":None}
        need(self.request("/api/auth/config", headers=anonymous).json() == {"registration_enabled":False}, "HTTPS 註冊政策不符")
        for path, expected in (("/",200), ("/agent",200), ("/api/not-a-route",404), ("/docs",404),
                               ("/static/avatars/not-a-file.png",401), ("/assets/not-a-file.js",404)):
            response = self.request(path, expected=expected, headers=anonymous)
            if expected == 200:
                need("text/html" in response.headers.get("Content-Type", "")
                     and response.headers.get("Cache-Control") == "no-store", "SPA／快取設定不符")
            elif not path.startswith("/assets/"):
                need("text/html" not in response.headers.get("Content-Type", ""), "API／媒體錯誤被 SPA 吃掉")
        self.passed("HTTPS 首頁／深連結／關閉註冊／API 與媒體分流")
        print("接續公開入口驗收，沿用先前測試的專案管理員；新增 Chat／Agent 各一組測試對話。", flush=True)
        account = input("專案管理員帳號：").strip()
        password = getpass.getpass("專案登入密碼：")
        auth = self.request("/api/auth/login", method="POST", json={"username":account,"password":password}).json()
        del password
        need(auth["user"]["is_admin"], "請使用原先的專案管理員帳號")
        self.session.headers["Authorization"] = "Bearer " + auth["access_token"]
        self.database = self.protected["sam-yolo-mysql"]
        previous = self.config / "releases/20261020T084747Z-2562377/report.json"
        self.baseline = json.loads(previous.read_text())["baseline_fingerprints"]
        self.verify_existing()
        self.stream_check()
        self.stream_check(agent=True)
        self.unchanged()
        self.report["success"] = True

    def rollback(self):
        self.public = False
        current = self.inspect("sam-yolo-gateway", optional=True)
        if current:
            self.owned_gateway({self.old_image, self.new_image})
        need(self.env_path.read_text() == nnp_env(self.env_before)
             and self.source.read_text() in (self.source_before, self.source_after),
             "拒絕回復已被其他操作變更的私人設定")
        temporary = self.work / "compose.env.restore"
        private_write(temporary, self.env_before)
        os.replace(temporary, self.env_path)
        temporary = self.source.with_name("compose.public.yaml.restore-" + self.stamp)
        temporary.write_text(self.source_before)
        temporary.chmod(0o644)
        os.replace(temporary, self.source)
        self.docker(*self.full, "up", "-d", "--no-deps", "--no-build", "--pull", "never", "gateway")
        self.report["gateway_config_restored"] = True

    def logs(self):
        gateway = self.owned_gateway({self.old_image, self.new_image})
        result = subprocess.run(["sudo", "-n", "docker", "logs", "--tail", "100", gateway["id"]],
                                capture_output=True, text=True, timeout=15)
        need(result.returncode == 0, "無法讀取本專案 gateway 日誌")
        raw = result.stdout + result.stderr
        private_write(self.work / "gateway.log", raw)
        # The diagnostic helper is already in deploy/ on the lab host.
        from lab_https_diagnose import summarize_logs
        self.report["gateway_logs"] = summarize_logs(raw)
        print("Caddy summary: " + json.dumps(self.report["gateway_logs"], ensure_ascii=False), flush=True)

    def run(self):
        try:
            self.prepare()
            self.validate_runtime()
            self.switch()
            if self.trusted_https():
                self.acceptance()
        except (Exception, KeyboardInterrupt) as exc:
            self.report.update(failed_step=self.step, error=str(exc) if isinstance(exc, Failed) else type(exc).__name__)
            print(f"FAIL [{self.step}]: " + self.report["error"], flush=True)
            if self.env_changed and not self.startup_ok:
                try:
                    self.rollback()
                except Exception:
                    self.report["gateway_rollback_failed"] = True
                    print("gateway 需人工檢查；未操作 backend／web／MySQL。", flush=True)
        finally:
            if self.work.is_dir():
                try:
                    self.unchanged()
                    self.logs()
                except Exception:
                    self.report["final_check_or_log_failed"] = True
                    self.report["success"] = False
                private_write(self.work / "report.json", json.dumps(self.report, ensure_ascii=False, indent=2))
                print("批次報告：" + str(self.work / "report.json"), flush=True)
            self.session.close()
        if self.report["success"]:
            print("Gateway Snap compatibility / trusted HTTPS / persistence / Chat-Agent SSE: PASS", flush=True)
            print("網站：https://" + self.address, flush=True)
        return 0 if self.report["success"] else 2 if self.report.get("https_pending") else 1


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
        return Repair(args.repo.resolve(), str(address)).run()
    finally:
        stop.set()
        os.close(descriptor)


if __name__ == "__main__":
    raise SystemExit(main())
