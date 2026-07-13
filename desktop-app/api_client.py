import json
import mimetypes
import os
import socket
import uuid
from urllib import error, request
from urllib.parse import urlencode, urljoin


class ApiError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DesktopApiClient:
    # Per-operation timeouts (seconds). The default `timeout` only suits fast
    # JSON endpoints; uploads, synchronous inference, SSE streams and binary
    # downloads need much larger budgets or they get killed mid-operation.
    INFERENCE_TIMEOUT = 180  # image detection: upload + synchronous YOLO inference
    UPLOAD_TIMEOUT = 600     # video multipart upload (up to 200 MB)
    STREAM_TIMEOUT = 300     # SSE: applies to connect and gaps between chunks
    BINARY_TIMEOUT = 120     # static asset downloads (result images / videos)

    def __init__(self, base_url=None, timeout=10):
        self.base_url = (base_url or os.getenv("YOLO_API_BASE_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.timeout = timeout

    def login(self, username, password):
        return self._request(
            "POST",
            "/api/auth/login",
            {
                "username": username,
                "password": password,
            },
        )

    def register(self, username, email, password, nickname):
        return self._request(
            "POST",
            "/api/auth/register",
            {
                "username": username,
                "email": email,
                "password": password,
                "nickname": nickname,
            },
        )

    def get_me(self, access_token):
        return self._request(
            "GET",
            "/api/auth/me",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

    def chat(self, access_token, question, conversation_id=None):
        payload = {
            "question": question,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id
        return self._request(
            "POST",
            "/api/chat",
            payload,
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

    def stream_chat(self, access_token, question, conversation_id=None):
        payload = {
            "question": question,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id

        req = request.Request(
            f"{self.base_url}/api/chat/stream",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "text/event-stream",
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.STREAM_TIMEOUT) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if not data_str:
                        continue
                    try:
                        yield json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            message = self._extract_error_message(body) or "請求失敗"
            raise ApiError(message, status_code=exc.code) from exc
        except error.URLError as exc:
            if self._is_timeout_error(exc):
                raise ApiError("連線後端 API 逾時，請確認 backend 是否正常回應") from exc
            raise ApiError("無法連線到後端 API，請確認 backend 是否已啟動") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise ApiError("連線後端 API 逾時，請確認 backend 是否正常回應") from exc

    def list_chat_conversations(self, access_token, limit=20):
        return self._request(
            "GET",
            f"/api/chat?{urlencode({'limit': limit})}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

    def get_chat_conversation(self, access_token, conversation_id):
        return self._request(
            "GET",
            f"/api/chat/{conversation_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

    def agent_chat(
        self,
        access_token,
        message,
        conversation_id=None,
        mode="auto",
        detection_id=None,
    ):
        """Phase 6A-1 agent assistant.

        Calls POST /api/agent/chat. Does not affect existing chat() /
        stream_chat() flows.
        """
        payload = {
            "message": message,
            "mode": mode or "auto",
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id
        if detection_id is not None:
            payload["detection_id"] = detection_id
        return self._request(
            "POST",
            "/api/agent/chat",
            payload,
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

    def list_agent_modes(self, access_token):
        """Fetch the supported agent modes (mirrors GET /api/agent/modes)."""
        return self._request(
            "GET",
            "/api/agent/modes",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

    def stream_agent_chat(
        self,
        access_token,
        message,
        conversation_id=None,
        mode="auto",
        detection_id=None,
    ):
        """Phase 6A-3 SSE streaming for POST /api/agent/chat/stream.

        Yields parsed SSE event dicts with keys ``type``, ``delta``, ``answer``,
        ``conversation_id``, ``mode``, ``tool_calls``, ``references``, or ``message``
        (error).  Does not affect existing ``agent_chat()`` / ``chat()`` flows.
        """
        payload = {
            "message": message,
            "mode": mode or "auto",
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id
        if detection_id is not None:
            payload["detection_id"] = detection_id

        req = request.Request(
            f"{self.base_url}/api/agent/chat/stream",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "text/event-stream",
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.STREAM_TIMEOUT) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if not data_str:
                        continue
                    try:
                        yield json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            message_text = self._extract_error_message(body) or "請求失敗"
            raise ApiError(message_text, status_code=exc.code) from exc
        except error.URLError as exc:
            if self._is_timeout_error(exc):
                raise ApiError("連線後端 API 逾時，請確認 backend 是否正常回應") from exc
            raise ApiError("無法連線到後端 API，請確認 backend 是否已啟動") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise ApiError("連線後端 API 逾時，請確認 backend 是否正常回應") from exc

    def upload_avatar(self, access_token, file_path):
        return self._multipart_request(
            endpoint="/api/upload/avatar",
            access_token=access_token,
            file_path=file_path,
        )

    def detect_image(self, access_token, file_path, conf=0.25, iou=0.45):
        endpoint = f"/api/detections/image?{urlencode({'conf': conf, 'iou': iou})}"
        return self._multipart_request(
            endpoint=endpoint,
            access_token=access_token,
            file_path=file_path,
            timeout=self.INFERENCE_TIMEOUT,
        )

    def detect_video(self, access_token, file_path, conf=0.25, iou=0.45):
        endpoint = f"/api/detections/video?{urlencode({'conf': conf, 'iou': iou})}"
        return self._multipart_request(
            endpoint=endpoint,
            access_token=access_token,
            file_path=file_path,
            timeout=self.UPLOAD_TIMEOUT,
        )

    def fetch_binary(self, path_or_url, timeout=None, access_token=None):
        url = self.resolve_url(path_or_url)
        headers = {"Accept": "*/*"}
        if access_token and "sig=" not in url:
            headers["Authorization"] = f"Bearer {access_token}"
        req = request.Request(
            url,
            headers=headers,
            method="GET",
        )
        try:
            with request.urlopen(req, timeout=timeout or self.BINARY_TIMEOUT) as response:
                return response.read()
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            message = self._extract_error_message(body) or "請求失敗"
            raise ApiError(message, status_code=exc.code) from exc
        except error.URLError as exc:
            if self._is_timeout_error(exc):
                raise ApiError("連線後端 API 逾時，請確認 backend 是否正常回應") from exc
            raise ApiError("無法連線到後端 API，請確認 backend 是否已啟動") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise ApiError("連線後端 API 逾時，請確認 backend 是否正常回應") from exc

    def list_users(self, access_token, page=1, limit=100, search=None):
        params = {
            "page": page,
            "limit": limit,
        }
        if search:
            params["search"] = search

        return self._request(
            "GET",
            f"/api/users?{urlencode(params)}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

    def list_detections(
        self,
        access_token,
        *,
        status: str | None = None,
        source_type: str | None = None,
        limit: int = 50,
        page: int = 1,
        with_meta: bool = False,
    ):
        """List detection tasks.

        When ``with_meta`` is True, returns ``(items, meta)`` where ``meta``
        contains ``total`` / ``total_pages`` parsed from the backend's
        ``X-Total-Count`` / ``X-Total-Pages`` headers (used for pagination).
        """
        params: dict = {"limit": limit, "page": page}
        if status:
            params["status"] = status
        if source_type:
            params["source_type"] = source_type
        qs = urlencode(params)
        result = self._request(
            "GET",
            f"/api/detections?{qs}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
            return_headers=with_meta,
        )
        if not with_meta:
            return result

        items, headers = result
        normalized = {key.lower(): value for key, value in headers.items()}

        def _to_int(value, default):
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        meta = {
            "total": _to_int(normalized.get("x-total-count"), len(items)),
            "total_pages": _to_int(normalized.get("x-total-pages"), 1),
        }
        return items, meta

    def get_detection(self, access_token, detection_id):
        return self._request(
            "GET",
            f"/api/detections/{detection_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

    def delete_detection(self, access_token, detection_id):
        return self._request(
            "DELETE",
            f"/api/detections/{detection_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

    def delete_user(self, access_token, user_id):
        return self._request(
            "DELETE",
            f"/api/users/{user_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

    def create_user(self, access_token, username, email, password, nickname, avatar=None):
        payload = {
            "username": username,
            "email": email,
            "password": password,
            "nickname": nickname,
        }
        if avatar is not None:
            payload["avatar"] = avatar

        return self._request(
            "POST",
            "/api/users",
            payload=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

    def update_user(self, access_token, user_id, username=None, email=None, nickname=None, password=None, is_admin=None, avatar=None):
        payload = {}
        if username is not None:
            payload["username"] = username
        if email is not None:
            payload["email"] = email
        if nickname is not None:
            payload["nickname"] = nickname
        if password is not None:
            payload["password"] = password
        if is_admin is not None:
            payload["is_admin"] = is_admin
        if avatar is not None:
            payload["avatar"] = avatar

        return self._request(
            "PUT",
            f"/api/users/{user_id}",
            payload=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

    def _request(self, method, path, payload=None, headers=None, timeout=None, return_headers=False):
        url = f"{self.base_url}{path}"
        data = None
        request_headers = {
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"

        req = request.Request(url, data=data, headers=request_headers, method=method)
        return self._send_request(req, timeout=timeout, return_headers=return_headers)

    def _multipart_request(self, endpoint, access_token, file_path, timeout=None):
        url = f"{self.base_url}{endpoint}"
        filename = os.path.basename(file_path)
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        boundary = f"----CodexBoundary{uuid.uuid4().hex}"

        with open(file_path, "rb") as file_obj:
            file_bytes = file_obj.read()

        body = b"".join(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode("utf-8"),
                f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
                file_bytes,
                b"\r\n",
                f"--{boundary}--\r\n".encode("utf-8"),
            ]
        )

        req = request.Request(
            url,
            data=body,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {access_token}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        return self._send_request(req, timeout=timeout)

    def _send_request(self, req, timeout=None, return_headers=False):
        try:
            with request.urlopen(req, timeout=timeout or self.timeout) as response:
                body = response.read().decode("utf-8")
                data = json.loads(body) if body else {}
                if return_headers:
                    return data, dict(response.headers)
                return data
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            message = self._extract_error_message(body) or "請求失敗"
            raise ApiError(message, status_code=exc.code) from exc
        except error.URLError as exc:
            if self._is_timeout_error(exc):
                raise ApiError("連線後端 API 逾時，請確認 backend 是否正常回應") from exc
            raise ApiError("無法連線到後端 API，請確認 backend 是否已啟動") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise ApiError("連線後端 API 逾時，請確認 backend 是否正常回應") from exc

    def _absolute_url(self, path_or_url):
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        return urljoin(f"{self.base_url}/", path_or_url.lstrip("/"))

    def resolve_url(self, path_or_url):
        return self._absolute_url(path_or_url)

    @staticmethod
    def _extract_error_message(body):
        if not body:
            return None
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return body

        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list) and detail:
            first_error = detail[0]
            if isinstance(first_error, dict):
                return first_error.get("msg")
        return None

    @staticmethod
    def _is_timeout_error(exc):
        reason = getattr(exc, "reason", None)
        return isinstance(reason, (TimeoutError, socket.timeout))
