"""Real HTTPS regression with two disposable accounts and real GPU inference.

Credentials remain in memory. Deletes only accounts created by this run after
their jobs finish. Existing users/media/conversations are never changed.
"""
import getpass
import importlib.util
import io
import json
from pathlib import Path
import secrets
import tempfile
import time
from urllib.parse import urlsplit
import zipfile

import requests
from PIL import Image


def need(value, message):
    if not value:
        raise RuntimeError(message)


class Regression:
    def __init__(self, base, repo):
        url = urlsplit(base)
        need(url.scheme == 'https' and url.hostname and not url.username and not url.query and url.path in ('', '/'), 'Use the trusted HTTPS origin')
        self.base, self.repo = base.rstrip('/'), Path(repo)
        self.session = requests.Session()
        self.session.trust_env = False
        self.admin = None
        self.created = []
        self.tokens = {}
        self.report = {'success': False, 'checks': [], 'temporary_user_ids': []}

    def request(self, method, path, token=None, expected=200, **kwargs):
        need(path.startswith('/') and not path.startswith('//'), 'Unexpected request path')
        headers = {'Authorization': 'Bearer ' + token} if token else {}
        response = self.session.request(method, self.base + path, headers=headers,
                                        timeout=180, allow_redirects=False, **kwargs)
        need(response.status_code == expected, f'{method} {path.split("?")[0]} HTTP {response.status_code}, expected {expected}')
        return response

    def passed(self, label):
        self.report['checks'].append(label)
        print('PASS: ' + label, flush=True)

    def login(self, name, password):
        return self.request('POST', '/api/auth/login', json={'username': name, 'password': password}).json()['access_token']

    def account(self):
        username = 'P6' + secrets.token_hex(8)
        password = 'P6!' + secrets.token_hex(24)
        user = self.request('POST', '/api/users', self.admin, expected=201,
                            json={'username': username, 'password': password, 'nickname': 'Phase 6 temporary regression'}).json()
        need(user['username'] == username and not user['is_admin'], 'Unexpected temporary account')
        self.created.append((user['id'], username))
        self.report['temporary_user_ids'].append(user['id'])
        token = self.login(username, password)
        self.tokens[user['id']] = token
        return user, token, password

    @staticmethod
    def png(color='white'):
        stream = io.BytesIO()
        Image.new('RGB', (64, 64), color).save(stream, format='PNG')
        return stream.getvalue()

    def poll(self, path, token):
        deadline = time.monotonic() + 180
        while True:
            record = self.request('GET', path, token).json()
            if record['status'] not in ('pending', 'processing'):
                need(record['status'] == 'completed', 'Inference did not complete successfully')
                return record
            need(time.monotonic() < deadline, 'Inference timed out; temporary accounts retained until jobs finish')
            time.sleep(1)

    def media(self, url, owner, other):
        parts = urlsplit(url)
        need(not parts.netloc and parts.path.startswith('/static/') and parts.query, 'Unexpected protected media URL')
        content = self.request('GET', parts.path, owner).content
        need(content, 'Empty media')
        self.request('GET', parts.path, other, expected=403)
        self.request('GET', parts.path, expected=401)
        signed = self.request('GET', parts.path + '?' + parts.query)
        need(signed.content == content, 'Signed media differs')

    def exercise(self):
        need(self.request('GET', '/api/health').json().get('database') == 'connected', 'Database unavailable')
        need(self.request('GET', '/api/auth/config').json()['registration_enabled'] is False, 'Public registration enabled')
        name = input('專案管理員帳號：').strip()
        self.admin = self.login(name, getpass.getpass('專案管理員密碼：'))
        need(self.request('GET', '/api/auth/me', self.admin).json()['is_admin'], 'Administrator required')
        user_a, a, password = self.account()
        _, b, _ = self.account()
        self.request('GET', '/api/users', a, expected=403)
        self.request('POST', '/api/auth/register', expected=403, json={'username':'P6closed', 'password':'P6Closed123!'})
        self.passed('管理員建帳／一般帳號權限／關閉自行註冊')

        first = self.request('POST', '/api/upload/avatar', a, files={'file':('test.png', self.png(), 'image/png')}).json()
        self.request('PUT', '/api/auth/profile', a, json={'avatar':first['filename'], 'nickname':'Phase 6 test'})
        self.request('PUT', '/api/auth/profile', b, expected=400, json={'avatar':first['filename']})
        second = self.request('POST', '/api/upload/avatar', a, files={'file':('test.png', self.png('blue'), 'image/png')}).json()
        self.request('PUT', '/api/auth/profile', a, json={'avatar':second['filename']})
        self.request('GET', urlsplit(first['url']).path, a, expected=404)
        self.passed('頭像上傳／指定／跨帳號盜用拒絕／換圖清理')

        started = time.monotonic()
        image = self.request('POST', '/api/detections/image', a, expected=201,
                             files={'file':('test.png', self.png(), 'image/png')}).json()
        need(image['status'] == 'completed', 'Image failed')
        self.report['image_seconds'] = round(time.monotonic() - started, 3)
        self.request('GET', '/api/detections/' + str(image['id']), b, expected=403)
        self.media(image['source_image_url'], a, b)
        self.media(image['result_image_url'], a, b)
        self.passed('單圖真實推論／跨帳號資料與媒體拒絕／signed URL')

        started=time.monotonic()
        sample=self.png()
        batch = self.request('POST', '/api/detections/batch', a, expected=202,
            files=[('files',(f'{index:03d}.png',sample,'image/png')) for index in range(100)]).json()
        batch_path = '/api/detections/batches/' + str(batch['id'])
        batch = self.poll(batch_path, a)
        need(batch['processed_count'] == 100 and batch['failed_count'] == 0, 'Batch counters mismatch')
        self.report['batch_100_seconds']=round(time.monotonic()-started,3)
        self.request('GET', batch_path, b, expected=403)
        download = self.request('GET', batch_path + '/download', a)
        with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
            need(len(archive.namelist()) == 100 and archive.testzip() is None, 'Batch download invalid')
        self.passed('100 張批次真實推論／進度／跨帳號拒絕／ZIP 下載')

        import cv2
        import numpy as np
        with tempfile.TemporaryDirectory(prefix='yolo-video-') as folder:
            path = Path(folder) / 'smoke.mp4'
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), 2, (64,64))
            need(writer.isOpened(), 'Cannot encode test video')
            try:
                for _ in range(4):
                    writer.write(np.full((64,64,3),255,dtype=np.uint8))
            finally:
                writer.release()
            with path.open('rb') as stream:
                video = self.request('POST', '/api/detections/video', a, expected=202,
                                     files={'file':('smoke.mp4',stream,'video/mp4')}).json()
        video = self.poll('/api/detections/' + str(video['id']), a)
        need(video['frame_count'] == 4, 'Video frame count mismatch')
        self.media(video['result_video_url'], a, b)
        self.passed('四影格影片真實推論／完成狀態／受保護影片下載')

        spec = importlib.util.spec_from_file_location('phase6_desktop_client', self.repo / 'desktop-app/api_client.py')
        desktop = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(desktop)
        client = desktop.DesktopApiClient(base_url=self.base)
        need(client.get_me(a)['id'] == user_a['id'], 'Desktop identity mismatch')
        need(client.get_detection(a, image['id'])['id'] == image['id'], 'Desktop result mismatch')
        need(client.fetch_binary(image['result_image_url'], access_token=a), 'Desktop image download failed')
        self.passed('既有 Desktop API client 經可信 HTTPS 讀取帳號／偵測／圖片')

        new_password = 'P6!' + secrets.token_hex(24)
        self.request('PUT', '/api/auth/profile', a, json={'current_password':password,'password':new_password})
        self.request('GET', '/api/auth/me', a, expected=401)
        self.tokens[user_a['id']] = self.login(user_a['username'], new_password)
        self.passed('自行改密碼／舊 JWT 立即失效／新密碼登入')

    def cleanup(self):
        failures = []
        for identity, username in reversed(self.created):
            try:
                results = self.request('GET', '/api/users?search=' + username, self.admin).json()['items']
                need(any(u['id'] == identity and u['username'] == username and not u['is_admin'] for u in results), 'Cleanup ownership mismatch')
                # Avoid deleting a user still referenced by a background inference.
                deadline = time.monotonic() + 180
                while True:
                    token = self.tokens[identity]
                    active = self.request('GET', '/api/detections?status=processing&limit=200', token).json()
                    pending = self.request('GET', '/api/detections?status=pending&limit=200', token).json()
                    if not any(task['user_id'] == identity for task in active + pending):
                        break
                    need(time.monotonic() < deadline, 'Temporary inference still running')
                    time.sleep(2)
                self.request('DELETE', '/api/users/' + str(identity), self.admin)
            except Exception:
                failures.append(identity)
        self.report['cleanup_failed_user_ids'] = failures
        return not failures

    def run(self):
        try:
            self.exercise()
            self.report['success'] = True
        except Exception as exc:
            self.report['error'] = str(exc) if type(exc) is RuntimeError else type(exc).__name__
            print('FAIL: ' + self.report['error'], flush=True)
        finally:
            if not self.cleanup():
                self.report['success'] = False
            self.session.close()
        return self.report
