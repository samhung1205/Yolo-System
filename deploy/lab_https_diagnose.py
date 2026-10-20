"""Read-only lab HTTPS diagnostics; no login, restart, build or ACME order.

Run as sam: sudo -v; python lab_https_diagnose.py --ip 140.113.135.113
Only a sanitized report is written, under the user's private reports directory.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.request


INSPECT = ('{"id":{{json .Id}},"image":{{json .Image}},'
           '"state":{{json .State}},"restarts":{{json .RestartCount}},'
           '"labels":{{json .Config.Labels}},"mounts":{{json .Mounts}},'
           '"network":{{json .HostConfig.NetworkMode}},'
           '"read_only":{{json .HostConfig.ReadonlyRootfs}}}')
EVENTS = {
    "enabling automatic TLS certificate management": "auto_tls_enabled",
    "obtaining certificate": "obtaining_certificate",
    "trying to solve challenge": "challenge_started",
    "authorization finalized": "authorization_finalized",
    "certificate obtained successfully": "certificate_obtained",
    "server running": "server_running",
    "will retry": "retry_scheduled",
}


def redact(value):
    """Only used on gateway startup/TLS errors, never access/request logs."""
    value = str(value)
    value = re.sub(r"https?://[^\s\"'<>]+", "[url]", value)
    value = re.sub(r"[\w.+-]+@[\w.-]+", "[email]", value)
    value = re.sub(r"(?i)Bearer\s+[^\s\"']+", "Bearer [redacted]", value)
    value = re.sub(r"(?i)\b(password|passwd|token|secret|api[_-]?key|authorization)\b[\"']?\s*[:=]\s*[^\s,;]+",
                   r"\1=[redacted]", value)
    value = re.sub(r"\?[^\s\"']+", "?[redacted]", value)
    value = re.sub(r"[A-Za-z0-9_+/=-]{24,}", "[identifier]", value)
    return " ".join(value.split())[:500]


def summarize_logs(raw):
    events, errors = set(), []
    unparsed = 0
    levels = {"warn", "error", "fatal", "panic"}
    for line in raw.splitlines():
        line = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", line).strip()
        try:
            entry = json.loads(line)
        except ValueError:
            unparsed += 1
            # CLI/loader/runtime failures need not use Caddy's JSON logger or
            # start with "Error:". Never include plaintext HTTP access lines.
            if not re.search(r"\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+\S+|HTTP/[123]", line) and re.search(
                r"error|fail|fatal|panic|denied|not permitted|not found|cannot|can't|unknown command|usage:", line, re.I
            ):
                errors.append(redact(line))
            continue
        if not isinstance(entry, dict):
            continue
        logger = str(entry.get("logger", ""))
        # Request fields/headers/URIs are never selected, including access errors.
        if "request" in entry or (logger and not (
            logger.startswith("tls") or logger in ("http", "http.auto_https", "admin")
        )):
            continue
        message = str(entry.get("msg", ""))
        for marker, event in EVENTS.items():
            if marker in message.lower():
                events.add(event)
        if entry.get("level") in levels:
            error = entry.get("error", "")
            if isinstance(error, dict):
                error = error.get("detail", error.get("message", ""))
            errors.append(redact(message + (": " + str(error) if error else "")))
    # Preserve the most recent distinct errors; repeated retries are summarized.
    unique = list(dict.fromkeys(errors))
    codes = sorted(set(re.findall(r"urn:ietf:params:acme:error:([A-Za-z]+)", raw)))
    return {"lines": len(raw.splitlines()), "unparsed_lines": unparsed,
            "events": sorted(events), "acme_types": codes, "errors": unique[-4:]}


def command(args, timeout=15):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, type(exc).__name__
    if result.returncode:
        text = result.stderr.lower()
        reason = ("sudo_not_authorized" if "password" in text or "terminal" in text else
                  "container_missing" if "no such" in text else
                  "permission_denied" if "permission denied" in text else "command_failed")
        return None, reason
    return result.stdout, result.stderr


def http_json(address, path, port):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://{address}:{port}{path}", timeout=5) as response:
            value = json.loads(response.read(16384))
            if path.endswith("config"):
                return {"http": response.status, "registration_enabled": value.get("registration_enabled")}
            return {"http": response.status, "database": value.get("database"), "status": value.get("status")}
    except (OSError, ValueError) as exc:
        return {"error": type(exc).__name__}


def verified_tls(address):
    # The IP is validated by the standard CA store and certificate IP SAN.
    try:
        with socket.create_connection((address, 443), timeout=5) as connection:
            with ssl.create_default_context().wrap_socket(connection, server_hostname=address) as secured:
                cert = secured.getpeercert()
                return {"verified": True, "expires": cert.get("notAfter"), "protocol": secured.version()}
    except ssl.SSLCertVerificationError as exc:
        return {"verified": False, "error": "certificate_verify_failed", "verify_code": exc.verify_code,
                "reason": redact(exc.verify_message)}
    except (OSError, ssl.SSLError) as exc:
        return {"verified": False, "error": type(exc).__name__, "errno": getattr(exc, "errno", None),
                "reason": redact(getattr(exc, "reason", ""))}


def requests_tls(address):
    # Matches apply.py's requests CA store, which may differ from system Python.
    try:
        import requests
    except ImportError:
        return {"available": False}
    with requests.Session() as session:
        session.trust_env = False
        try:
            response = session.get(f"https://{address}/api/health", timeout=(5, 8), allow_redirects=False)
            value = response.json() if response.status_code == 200 else {}
            return {"verified": True, "http": response.status_code, "database": value.get("database")}
        except requests.RequestException as exc:
            message = str(exc).lower()
            detail = ("certificate_verify_failed" if "certificate_verify_failed" in message else
                      "tls_internal_error" if "alert_internal_error" in message else
                      "connection_refused" if "refused" in message else type(exc).__name__)
            return {"verified": False, "error": detail}
        except ValueError:
            return {"verified": True, "error": "non_json_health"}


def inspect_gateway():
    raw, error = command(["sudo", "-n", "docker", "inspect", "--type", "container",
                          "--format", INSPECT, "sam-yolo-gateway"])
    if raw is None:
        return {"error": error}, None
    value = json.loads(raw)
    state, labels = value["state"] or {}, value["labels"] or {}
    owned = labels.get("com.docker.compose.project") == "sam-yolo" and labels.get("com.docker.compose.service") == "gateway"
    summary = {
        "owned": owned, "status": state.get("Status"), "running": state.get("Running"),
        "restarting": state.get("Restarting"), "exit": state.get("ExitCode"),
        "oom": state.get("OOMKilled"), "restart_count": value["restarts"],
        "health": (state.get("Health") or {}).get("Status"), "network": value["network"],
        "read_only": value["read_only"], "state_error": redact(state.get("Error", "")),
        "certificate_volume": any(m.get("Name") == "sam-yolo-caddy-data" and m.get("Destination") == "/data"
                                  and m.get("RW") for m in value["mounts"]),
    }
    # No labels, healthcheck output, env, mount paths or other containers' logs.
    return summary, value["id"] if owned else None


def collect(address):
    report = {"ip": address}
    for name, port in (("backend", 8000), ("nginx", 8080)):
        report[name] = http_json("127.0.0.1", "/api/health", port)
    report["signup_policy"] = http_json("127.0.0.1", "/api/auth/config", 8000)
    report["gateway"], identifier = inspect_gateway()
    listeners, error = command(["ss", "-ltnH", "( sport = :443 )"])
    report["tcp443_listener"] = ({"present": bool(listeners.strip()), "on_public_ip": address + ":443" in listeners}
                                 if listeners is not None else {"error": error})
    report["system_tls"] = verified_tls(address)
    report["requests_https"] = requests_tls(address)
    if identifier:
        stdout, stderr = command(["sudo", "-n", "docker", "logs", "--tail", "200", identifier])
        report["caddy_logs"] = summarize_logs(stdout + stderr) if stdout is not None else {"error": stderr}
    else:
        report["caddy_logs"] = {"skipped": "gateway_missing_or_not_owned"}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip", required=True)
    args = parser.parse_args()
    address = ipaddress.ip_address(args.ip)
    if address.version != 4 or not address.is_global or sys.platform != "linux" or os.getuid() == 0:
        parser.error("請在 Ubuntu 以 sam 執行，指定已確認的公網 IPv4；不要 sudo python")
    os.umask(0o077)
    report = collect(str(address))
    root = Path.home() / ".config/yolo-system/reports"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = root / (datetime.now(timezone.utc).strftime("https-diagnose-%Y%m%dT%H%M%SZ-") + str(os.getpid()) + ".json")
    with target.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    for key, value in report.items():
        print(key + ": " + json.dumps(value, ensure_ascii=False), flush=True)
    print("診斷報告：" + str(target), flush=True)
    print("只讀診斷完成；未建置／重啟／申請憑證或修改防火牆。", flush=True)


if __name__ == "__main__":
    main()
