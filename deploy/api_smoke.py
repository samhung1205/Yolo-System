"""Interactive lab API acceptance check; run on the Ubuntu host, not in image.

Creates one white-image detection and two conversations, retained for subsequent
persistence checks. Never reads .env or prints passwords, tokens or signed URLs.
"""
from __future__ import annotations

import argparse
import getpass
import io
import sys
from urllib.parse import urlsplit

import requests
from PIL import Image


class CheckFailed(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailed(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, choices=(8000, 18000), default=18000)
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}"
    session = requests.Session()
    session.trust_env = False

    def call(method: str, path: str, expected: int = 200, **kwargs):
        response = session.request(
            method, base + path, timeout=(5, 600), allow_redirects=False, **kwargs
        )
        # Keep signatures out of errors while identifying the failed operation.
        endpoint = "/static/[media]" if path.startswith("/static/") else path.split("?", 1)[0]
        require(response.status_code == expected,
                f"{method} {endpoint}: HTTP {response.status_code}，預期 {expected}；請檢查容器日誌。")
        return response

    require(call("GET", "/api/health").json().get("database") == "connected",
            "資料庫未連線。")
    call("GET", "/api/auth/me", expected=401)
    print("Health / unauthenticated access: PASS", flush=True)

    username = input("專案登入帳號（不是 Ubuntu 帳號）：").strip()
    password = getpass.getpass("專案登入密碼：")
    auth = call("POST", "/api/auth/login",
                json={"username": username, "password": password}).json()
    del password
    print("Login: PASS", flush=True)
    session.headers["Authorization"] = "Bearer " + auth["access_token"]
    me = call("GET", "/api/auth/me").json()
    require(me["id"] == auth["user"]["id"], "登入身分不一致。")
    del auth
    print("Login / current user: PASS", flush=True)

    for purpose, model in (("chat", "llama3.2"), ("agent", "gemma4")):
        groups = call("GET", f"/api/models?purpose={purpose}").json()
        defaults = [g for g in groups if g["is_default"]]
        require(len(defaults) == 1 and defaults[0]["provider"] == "ollama"
                and defaults[0]["available"]
                and (defaults[0]["default_model"] or "").split(":")[0] == model,
                f"{purpose} 預設 provider/model 與部署設定不符。")
        require(not any(g["available"] for g in groups
                        if g["provider"] in ("openai", "deepseek")),
                "付費 provider 仍啟用，請先確認免費部署設定。")
    print("Free Ollama defaults: PASS (Chat=llama3.2, Agent=gemma4)", flush=True)

    registry = call("GET", "/api/yolo-models").json()
    available = {item["key"]: item for item in registry if item["available"]}
    key = "seven_class_asff"
    require(key in available, "ASFF checkpoint 不可用。")
    print(f"YOLO registry: {len(available)} available", flush=True)
    image = io.BytesIO()
    Image.new("RGB", (640, 640), "white").save(image, format="PNG")
    print("Testing image detection...", flush=True)
    task = call("POST", "/api/detections/image", expected=201,
                params={"model_key": key},
                files={"file": ("container_api_smoke.png", image.getvalue(), "image/png")}).json()
    require(task["status"] == "completed" and task["model_key"] == key
            and bool(task["model_sha256"])
            and task["model_sha256"] == available[key]["sha256"],
            "圖片偵測未完成或模型指紋不符。")
    stored = call("GET", f"/api/detections/{task['id']}").json()
    require(stored["status"] == "completed" and stored["id"] == task["id"],
            "偵測紀錄讀回失敗。")

    for field in ("source_image_url", "result_image_url"):
        media = urlsplit(stored[field])
        require(not media.scheme and not media.netloc and media.path.startswith("/static/")
                and bool(media.query), "媒體 URL 格式不符。")
        call("GET", media.path, expected=401, headers={"Authorization": None})
        for path, kwargs in ((media.path, {}),
                             (media.path + "?" + media.query, {"headers": {"Authorization": None}})):
            response = call("GET", path, **kwargs)
            require(response.headers.get("X-Content-Type-Options") == "nosniff",
                    "媒體缺少 nosniff header。")
            with Image.open(io.BytesIO(response.content)) as decoded:
                decoded.load()
                require(decoded.size == (640, 640), "媒體影像尺寸不符。")
    print(f"YOLO / DB readback / protected media: PASS | detection_id={task['id']}", flush=True)

    print("Testing Chat (please wait)...", flush=True)
    chat = call("POST", "/api/chat", expected=201,
                json={"question": "請用繁體中文簡短回答：你好", "provider": "ollama"}).json()
    require(chat["provider"] == "ollama" and chat["model_name"].split(":")[0] == "llama3.2"
            and bool(chat["answer"].strip()), "Chat 回覆或模型不符。")
    print("Chat: PASS | model=" + chat["model_name"], flush=True)

    print("Testing Agent history tool (please wait)...", flush=True)
    agent = call("POST", "/api/agent/chat", json={
        "message": "請呼叫歷史統計工具，簡短告訴我目前偵測任務總數。",
        "mode": "history_analysis", "provider": "ollama",
    }).json()
    require(agent["success"] and not agent["errors"] and bool(agent["answer"].strip())
            and any(t.get("tool") == "summarize_detection_history" and t.get("ok") is True
                    for t in (agent.get("tool_calls") or [])), "Agent 未成功執行歷史統計工具。")
    print("Agent / summarize_detection_history: PASS", flush=True)
    for label, record in (("Chat", chat), ("Agent", agent)):
        history = call("GET", "/api/chat/" + record["conversation_id"]).json()
        require(any(m["answer"] == record["answer"] for m in history["messages"]),
                f"{label} 對話讀回失敗。")
        print(f"{label} persisted | conversation_id={record['conversation_id']}", flush=True)
    print("Container API integration smoke test: PASS", flush=True)
    session.close()


if __name__ == "__main__":
    try:
        main()
    except CheckFailed as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except (KeyboardInterrupt, EOFError):
        print("測試已中止；已建立的測試資料保留。", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        # Request errors may contain signed URLs; don't print their raw text.
        print(f"FAIL: {type(exc).__name__}；請回報此訊息及容器日誌。", file=sys.stderr)
        raise SystemExit(1)
