"""Package only reviewed runtime source; no models, media, env or credentials."""
import hashlib
import io
import json
from pathlib import Path
import tarfile

from lab_public_apply import ALLOWED

ROOT = Path(__file__).resolve().parents[1]


def package(output):
    before = json.loads((ROOT / "deploy/public-preimages.json").read_text())
    manifest = {"release":"lab-public-20261020", "files":{}}
    payload = {}
    for name in sorted(ALLOWED):
        data = (ROOT / name).read_bytes()
        payload["payload/" + name] = data
        manifest["files"][name] = {
            "before":before.get(name, {}).get("sha256"),
            "before_lf":before.get(name, {}).get("lf_sha256"),
            "after":hashlib.sha256(data).hexdigest(),
            "after_lf":hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest(),
        }
    payload["manifest.json"] = json.dumps(manifest, sort_keys=True, indent=2).encode()
    payload["apply.py"] = (ROOT / "deploy/lab_public_apply.py").read_bytes()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    with tarfile.open(temporary, "w:gz") as archive:
        for name, content in sorted(payload.items()):
            info = tarfile.TarInfo("yolo-public-update-20261020/" + name)
            info.size = len(content)
            info.mode = 0o644
            info.mtime = 0
            archive.addfile(info, io.BytesIO(content))
    temporary.replace(output)
    print(str(output))
    print("SHA-256: " + hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == "__main__":
    package(ROOT / "deploy/out/yolo-public-update-20261020.tar.gz")
