"""Capture the verified Ubuntu environment without URLs, credentials or .env.

Run with the lab's yolo-backend Python, not the Mac or yolo-web environment.
The output is a pip version snapshot; wheel hashes and OS packages are not locked.
"""
from __future__ import annotations

import hashlib
from importlib.metadata import PackageNotFoundError, distribution, version
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from urllib.parse import urlsplit


EXPECTED = {
    "torch": "2.11.0+cu126",
    "torchvision": "0.26.0+cu126",
    "ultralytics": "8.4.38",
    "langchain": "1.3.0",
    "langchain-core": "1.4.0",
    "langchain-openai": "1.2.1",
    "langgraph": "1.2.0",
}
PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.!+_-]*)")
DIRECT = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)\s*@\s*(.+)")


def normalized_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def conda_owned_pins(prefix: Path) -> dict[str, str]:
    """Identify matching conda records that own installed direct_url metadata.

    This permits version-only snapshots of conda's embedded local build origins;
    it does not claim conda and PyPI artifacts are byte-for-byte identical.
    """
    pins: dict[str, str] = {}
    prefix = prefix.resolve()
    for record in (prefix / "conda-meta").glob("*.json"):
        try:
            data = json.loads(record.read_text(encoding="utf-8"))
            name, installed = data["name"], data["version"]
            if not PIN.fullmatch(f"{name}=={installed}"):
                continue
            dist = distribution(name)
            if dist.version != installed:
                continue
            owned = set(data.get("files", []))
            for item in dist.files or []:
                if item.name != "direct_url.json" or not item.parent.name.endswith(".dist-info"):
                    continue
                metadata_file = Path(dist.locate_file(item)).resolve()
                relative = metadata_file.relative_to(prefix).as_posix()
                if relative in owned:
                    pins[normalized_name(name)] = installed
        except (OSError, ValueError, KeyError, TypeError, PackageNotFoundError):
            # A source without matching provenance remains rejected below.
            continue
    return pins


def validated_pins(output: str, conda_pins: dict[str, str] | None = None) -> list[str]:
    pins: dict[str, str] = {}
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN.fullmatch(line)
        if not match:
            direct = DIRECT.fullmatch(line)
            if direct:
                name = direct[1]
                try:
                    source = urlsplit(direct[2])
                    is_local = source.scheme == "file" and not source.netloc
                except ValueError:
                    is_local = False
                installed = (conda_pins or {}).get(normalized_name(name))
                if is_local and installed and PIN.fullmatch(f"{name}=={installed}"):
                    line = f"{name}=={installed}"
                    match = PIN.fullmatch(line)
                else:
                    kind = "本機來源但無匹配 conda 紀錄" if is_local else "URL 來源"
                    raise ValueError(f"套件 {name}：{kind}；未寫入。完整來源已隱藏，請回報此訊息。")
            if not match:
                # Do not echo raw requirements: they can include tokens or paths.
                raise ValueError("存在 editable 或非固定版本項目；未寫入，完整來源已隱藏。")
        key = normalized_name(match[1])
        if key in pins:
            raise ValueError("套件清單有重複項目，未寫入。")
        pins[key] = line
    if not pins:
        raise ValueError("套件清單為空，未寫入。")
    for name, expected in EXPECTED.items():
        if pins.get(name, "").partition("==")[2] != expected:
            raise ValueError(f"{name} 與已驗證版本不同，未寫入。")
    return [pins[key] for key in sorted(pins)]


def main() -> None:
    if (
        platform.system() != "Linux"
        or platform.machine() != "x86_64"
        or sys.version_info[:2] != (3, 11)
    ):
        raise SystemExit("請在實驗室 Ubuntu 的 yolo-backend（Python 3.11）執行。")
    for name, expected in EXPECTED.items():
        try:
            actual = version(name)
        except PackageNotFoundError:
            raise SystemExit(f"找不到 {name}，請確認已啟用 yolo-backend。") from None
        if actual != expected:
            raise SystemExit(f"{name} 版本為 {actual}，與已驗證的 {expected} 不同；未寫入。")

    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
    frozen = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    try:
        conda_pins = conda_owned_pins(Path(sys.prefix))
        pins = validated_pins(frozen, conda_pins)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    body = (
        "# Verified lab environment: Linux x86_64, Python 3.11, CUDA 12.6 wheels.\n"
        "# Generated by deploy/export_backend_lock.py; no URLs or environment values.\n"
        "# Conda-owned local build origins are rebuilt by installed version, not artifact hash.\n"
        + "\n".join(pins)
        + "\n"
    ).encode()
    target = Path(__file__).resolve().with_name("backend-linux.lock")
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        raise SystemExit("backend-linux.lock 已存在，未覆蓋；請先回報目前狀態。") from None
    with os.fdopen(fd, "wb") as handle:
        handle.write(body)
    for line in frozen.splitlines():
        direct = DIRECT.fullmatch(line.strip())
        if direct:
            name = direct[1]
            print(f"Conda version snapshot: {name}=={conda_pins[normalized_name(name)]}")
    print(f"Created: {target.name} ({len(pins)} packages)")
    print(f"SHA256: {hashlib.sha256(body).hexdigest()}")
    print("環境快照完成；不包含密碼、token 或 .env。")


if __name__ == "__main__":
    main()
