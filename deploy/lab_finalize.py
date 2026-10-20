"""Run Phase 6 lab verification, install daily backups, then verify one snapshot.

Run as the project user after sudo -v. Tests new backend and gateway images;
does not restart shared services, change firewall rules or touch other projects.
"""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import shlex
import subprocess
import sys
import threading
import requests

from lab_backup_verify import keep_sudo_alive, private_write
from lab_compose_apply import Batch, Failed, need
from lab_public_verify import Verify
from lab_regression import Regression
from lab_public_apply import check_gateway_config


class ResourceSample:
    """Observe shared GPU memory; never change clocks, limits or other jobs."""
    def __init__(self):
        self.stop=threading.Event()
        self.samples=[]
        self.backend=[]
        self.thread=threading.Thread(target=self.collect,daemon=True)

    def collect(self):
        while not self.stop.is_set():
            try:
                result=subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu',
                    '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10)
                if result.returncode==0:
                    for line in result.stdout.splitlines():
                        self.samples.append([int(v.strip()) for v in line.split(',')])
            except (OSError,ValueError,subprocess.TimeoutExpired):
                pass
            try:
                stats=subprocess.run(['sudo','-n','docker','stats','--no-stream','--format','{{json .}}','sam-yolo-backend'],
                    capture_output=True,text=True,timeout=10)
                if stats.returncode==0:
                    row=json.loads(stats.stdout)
                    usage=row['MemUsage'].split('/')[0].strip()
                    match=re.fullmatch(r'([0-9.]+)\s*([KMGT]?i?B)',usage)
                    units={'B':1,'kB':1000,'KB':1000,'MB':1000**2,'GB':1000**3,'TB':1000**4,
                           'KiB':1024,'MiB':1024**2,'GiB':1024**3,'TiB':1024**4}
                    if match:self.backend.append([float(match[1])*units[match[2]],float(row['CPUPerc'].rstrip('%'))])
            except (OSError,ValueError,KeyError,subprocess.TimeoutExpired):
                pass
            self.stop.wait(2)

    def finish(self):
        self.stop.set()
        self.thread.join(timeout=22)
        return {'samples':len(self.samples),'shared_gpu_peak_mib':max((x[0] for x in self.samples),default=None),
                'shared_gpu_total_mib':max((x[1] for x in self.samples),default=None),
                'backend_peak_memory_bytes':max((x[0] for x in self.backend),default=None),
                'backend_peak_cpu_percent':max((x[1] for x in self.backend),default=None),
                'note':'Shared GPU observation; not a 50-user capacity guarantee'}


class CommandFailure(Failed):
    def __init__(self, command, returncode, log_path, hint):
        self.returncode = returncode
        self.log_path = str(log_path)
        self.hint = hint
        super().__init__(f'{command} 執行失敗（exit {returncode}）：{hint}；私人紀錄：{log_path}')


def checked(args, *, timeout=180, show=False, log_path=None):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        if log_path is None:
            folder = Path.home() / '.config/yolo-system/reports'
            folder.mkdir(parents=True, mode=0o700, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            log_path = folder / f'command-{stamp}-{os.getpid()}.json'
        private_write(log_path, json.dumps({'exit_code': result.returncode,
                                           'stdout': result.stdout, 'stderr': result.stderr},
                                          ensure_ascii=False, indent=2))
        error = result.stderr.lower()
        if 'bind source path does not exist' in error:
            hint = 'Docker 無法存取 bind mount 的來源路徑'
        elif 'sudo:' in error and ('password' in error or 'terminal' in error):
            hint = 'sudo 驗證無法供非互動指令使用，請先 sudo -v'
        elif 'operation not permitted' in error or 'permission denied' in error:
            hint = '容器或檔案權限被拒絕，需檢查私人紀錄'
        else:
            hint = '子程序錯誤已保存，請檢查私人紀錄'
        command = 'Docker' if args[:3] == ['sudo', '-n', 'docker'] else Path(args[0]).name
        raise CommandFailure(command, result.returncode, log_path, hint)
    if show and result.stdout:
        print(result.stdout[-7000:], flush=True)
    return result.stdout


SEED_IMAGES = '''from pathlib import Path
from PIL import Image
samples = Path('static/detections/originals')
samples.mkdir(parents=True, exist_ok=True)
for index, color in enumerate(('white', 'blue', 'red')):
    Image.new('RGB', (640, 640), color).save(samples / f'{index}.png')
'''


def container_tests(batch, state, log_path=None):
    # Docker Snap sees its own /tmp, so never bind a host temporary directory.
    # Seed only synthetic media in this disposable container's bounded tmpfs.
    command = ['sudo','-n','docker','run','--rm','--network','none','--runtime=nvidia','--gpus','all',
        '--user',state['user'],'--cpus','4','--memory','8g','--shm-size','256m',
        '--workdir','/opt/yolo/backend',
        '--tmpfs','/opt/yolo/backend/static:rw,nosuid,nodev,noexec,size=16m,mode=1777',
        '-e','APP_ENV=development','-e','PYTHONDONTWRITEBYTECODE=1']
    for source, target in ((batch.repo/'backend/tests','/opt/yolo/backend/tests'),
                           (batch.repo/'backend/scripts','/opt/yolo/backend/scripts'),
                           (batch.repo/'backend/pytest.ini','/opt/yolo/backend/pytest.ini'),
                           (batch.repo/'backend/pt','/opt/yolo/backend/pt')):
        command += ['--mount', f'type=bind,source={source},target={target},readonly']
    command += [state['image'], 'sh','-c',
                'python -m pip check && python -c ' + shlex.quote(SEED_IMAGES) +
                ' && python -m pytest -q -p no:cacheprovider && python /opt/yolo/deploy/backend_smoke.py --gpu']
    output = checked(command, timeout=600, show=True, log_path=log_path)
    need('Container custom YOLO GPU smoke test: PASS' in output, '容器回歸未完整通過')
    return output.splitlines()[-15:]


def build_backend(batch):
    """Build from tracked sources; leave the running backend untouched."""
    tag = 'sam-yolo-backend:phase6-' + batch.stamp.lower()
    print('建置修正版 backend image；正式服務持續運行…', flush=True)
    checked(['sudo','-n','docker','build','--pull=false','--platform','linux/amd64',
             '-f',str(batch.repo/'deploy/backend.Dockerfile'),'-t',tag,str(batch.repo)],
            timeout=1800,show=True)
    image = batch.docker('image','inspect','--format','{{.Id}}',tag).strip()
    need(re.fullmatch('sha256:[0-9a-f]{64}',image), 'New backend image ID invalid')
    return image


def update_backend(batch, previous, image, work):
    """Switch the tested backend only, restoring the previous image on failure."""
    env_path = batch.config/'compose.env'
    before = env_path.read_text()
    pattern = r'^YOLO_PUBLIC_BACKEND_IMAGE=.+$'
    need(len(re.findall(pattern,before,re.M)) == 1, 'Backend image setting missing/duplicated')
    need(re.search(pattern,before,re.M).group().split('=',1)[1] == previous['image'],
         'Private backend image differs from running image; refusing replacement')
    current = batch.inspect('sam-yolo-backend')
    need(current['id'] == previous['id'] and current['image'] == previous['image']
         and current['mounts'] == previous['mounts'] and current['running']
         and current['project'] == 'sam-yolo' and current['service'] == 'backend',
         'Backend identity changed; refusing replacement')
    if image == previous['image']:
        return {'previous_image': image, 'image': image, 'changed': False}
    # Read-only query inside the existing backend; credentials never leave it.
    idle = batch.docker('exec',previous['id'],'python','-c',
        'from app.db.session import SessionLocal; from app.models import DetectionTask, DetectionBatch; '
        'db=SessionLocal(); '
        'print(db.query(DetectionTask).filter(DetectionTask.status.in_(("pending","processing"))).count()+'
        'db.query(DetectionBatch).filter(DetectionBatch.status.in_(("pending","processing"))).count()); db.close()')
    need(idle.strip() == '0', '仍有進行中／中斷偵測，未切換 backend，請先完成或受控復原')
    private_write(work/'backend.compose.before.env', before)
    after = re.sub(pattern, lambda _: 'YOLO_PUBLIC_BACKEND_IMAGE='+image, before, flags=re.M)
    need(env_path.read_text() == before, 'Private Compose settings changed')
    temporary = work/'backend.compose.next.env'
    private_write(temporary, after)
    os.replace(temporary, env_path)
    compose = ['compose','--env-file',str(env_path),'-f',str(batch.repo/'deploy/compose.lab.yaml'),
               '-f',str(batch.repo/'deploy/compose.public.yaml')]
    try:
        batch.docker(*compose,'config','--quiet')
        batch.docker(*compose,'up','-d','--no-deps','--no-build','--pull','never','backend')
        batch.wait_backend()
        need(batch.inspect('sam-yolo-backend')['image'] == image, 'Backend did not adopt tested image')
        need(batch.request('/api/auth/config',port=8000).json() == {'registration_enabled':False},
             'New backend registration policy changed')
    except Exception:
        need(env_path.read_text() == after, 'Private configuration changed; refusing automatic rollback')
        rollback = work/'backend.compose.rollback.env'
        private_write(rollback, before)
        os.replace(rollback, env_path)
        batch.docker(*compose,'up','-d','--no-deps','--no-build','--pull','never','backend')
        batch.wait_backend()
        raise
    print('PASS: 已測試 backend 更新／DB health／關閉註冊；資料掛載與其他服務保留',flush=True)
    return {'previous_image':previous['image'],'image':image,'changed':True}


def update_gateway(batch, previous, work):
    """Build stateless frontend, then switch only gateway with guarded rollback."""
    env_path=batch.config/'compose.env'
    before=env_path.read_text()
    need(len(re.findall(r'^YOLO_PUBLIC_GATEWAY_IMAGE=.+$',before,re.M))==1,'Gateway image setting missing/duplicated')
    need(re.search(r'^YOLO_GATEWAY_NNP=false$',before,re.M),'請先保留已驗證的 Snap NNP 相容設定')
    private_write(work/'compose.before.env',before)
    tag='sam-yolo-gateway:phase6-'+batch.stamp.lower()
    print('建置 Vite 8／Caddy 前端 image；此時正式服務持續運行…',flush=True)
    checked(['sudo','-n','docker','build','--pull=false','-f',str(batch.repo/'deploy/public.Dockerfile'),
             '-t',tag,str(batch.repo)],timeout=1800,show=True)
    image=batch.docker('image','inspect','--format','{{.Id}}',tag).strip()
    need(re.fullmatch('sha256:[0-9a-f]{64}',image),'New gateway image ID invalid')
    adapted=batch.docker('run','--rm','--network','none','--read-only','--cap-drop','ALL',
                         '--cap-add','NET_BIND_SERVICE','--security-opt','no-new-privileges=false',
                         '-e','YOLO_PUBLIC_IP=140.113.135.113',image,
                         'caddy','adapt','--config','/etc/caddy/Caddyfile','--adapter','caddyfile')
    check_gateway_config(json.loads(adapted),'140.113.135.113')
    after=re.sub(r'^YOLO_PUBLIC_GATEWAY_IMAGE=.+$',lambda _: 'YOLO_PUBLIC_GATEWAY_IMAGE='+image,before,flags=re.M)
    need(env_path.read_text()==before,'Private Compose settings changed during build')
    temporary=work/'compose.next.env'
    private_write(temporary,after)
    os.replace(temporary,env_path)
    compose=['compose','--env-file',str(env_path),'-f',str(batch.repo/'deploy/compose.lab.yaml'),
             '-f',str(batch.repo/'deploy/compose.public.yaml')]
    try:
        batch.docker(*compose,'config','--quiet')
        batch.docker(*compose,'up','-d','--no-deps','--no-build','--pull','never','gateway')
        import time
        deadline=time.monotonic()+120
        while True:
            try:
                response=batch.session.get('https://140.113.135.113/api/health',timeout=10)
                if response.status_code==200 and response.json().get('database')=='connected':break
            except requests.exceptions.RequestException:
                pass
            need(time.monotonic()<deadline,'New gateway HTTPS health timeout')
            time.sleep(2)
        need(batch.inspect('sam-yolo-gateway')['image']==image,'Gateway did not adopt new image')
        print('PASS: 新 Vite 8／Caddy gateway 已切換；backend／MySQL／Ollama 不變',flush=True)
        return {'previous_image':previous['image'],'image':image}
    except Exception:
        need(env_path.read_text()==after,'Private configuration changed; refusing automatic rollback')
        rollback=work/'compose.rollback.env'
        private_write(rollback,before)
        os.replace(rollback,env_path)
        batch.docker(*compose,'up','-d','--no-deps','--no-build','--pull','never','gateway')
        raise


def main():
    need(sys.platform == 'linux' and os.getuid() != 0, '請在 Ubuntu 使用自己的帳號執行，先 sudo -v')
    os.umask(0o077)
    batch = Batch()
    stop = threading.Event()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    report = {'success':False, 'stage':'preflight', 'schedule':'23:30 Asia/Taipei'}
    output = batch.config / 'reports' / ('finalize-' + stamp + '.json')
    output.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    work=batch.config/'releases'/('finalize-'+batch.stamp)
    work.mkdir(mode=0o700)
    lock = os.open(batch.config/'compose-apply.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    verification = None
    resources=ResourceSample()
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        checked(['sudo','-n','-v'])
        refresh=threading.Thread(target=keep_sudo_alive,args=(stop,),daemon=True)
        refresh.start()
        original = {name:batch.inspect(name) for name in ('sam-yolo-backend','sam-yolo-web','sam-yolo-gateway','sam-yolo-mysql')}
        resources.thread.start()
        need(all(state['running'] for state in original.values()),'服務尚未全部啟動')
        database=original['sam-yolo-mysql']
        need(any(m.get('Name')=='sam-yolo-mysql-data' for m in database['mounts']),'MySQL 歸屬不符')
        report['stage']='backend-build'
        image=build_backend(batch)
        report['candidate_backend_image']=image
        report['stage']='container-regression'
        candidate={**original['sam-yolo-backend'],'image':image}
        report['container_tests']=container_tests(batch,candidate,work/'container-regression.json')
        print('PASS: 候選 backend 全套測試／合成影像／自訂模型 GPU；正式資料未掛入測試容器',flush=True)
        report['stage']='backend-update'
        report['backend_update']=update_backend(batch,original['sam-yolo-backend'],image,work)
        report['stage']='frontend-gateway'
        report['gateway_update']=update_gateway(batch,original['sam-yolo-gateway'],work)
        report['stage']='https-regression'
        regression=Regression('https://140.113.135.113',batch.repo)
        report['regression']=regression.run()
        need(report['regression']['success'],'HTTPS 跨帳號／圖片／頭像／批次／影片／Desktop 回歸失敗')
        verification=Verify(batch.repo,'140.113.135.113')
        verification.preflight()
        for path,expected in (('/',200),('/agent?mode=explain_detection&detection_id=1',200),
                              ('/api/not-a-route',404),('/docs',404),('/assets/not-a-file.js',404)):
            response=verification.request(path,expected=expected,headers={'Authorization':None})
            if expected==200:
                need('text/html' in response.headers.get('Content-Type','')
                     and response.headers.get('Cache-Control')=='no-store','新 gateway SPA 路由不符')
        verification.session.headers['Authorization']='Bearer '+regression.admin
        verification.database=verification.protected['sam-yolo-mysql']
        verification.baseline=json.loads((batch.config/'releases/20261020T084747Z-2562377/report.json').read_text())['baseline_fingerprints']
        verification.verify_existing()
        verification.stream_check()
        verification.stream_check(agent=True)
        verification.unchanged()
        report['existing_data_and_sse']=True
        report['stage']='restart-policy'
        if database['restart'] != 'unless-stopped':
            batch.docker('update','--restart','unless-stopped',database['id'])
        need(batch.inspect('sam-yolo-mysql')['restart']=='unless-stopped','MySQL restart policy 未生效')
        checked(['systemctl','is-enabled','ollama'])
        checked(['systemctl','is-active','ollama'])
        report['ollama_models']=batch.session.get('http://127.0.0.1:11434/api/tags',timeout=15).json()
        report['stage']='install-backup'
        installer=['sudo','-n','/usr/bin/python3','-I',str(batch.repo/'deploy/install_lab_maintenance.py'),
                   '--repo',str(batch.repo),'--account',pwd.getpwuid(os.getuid()).pw_name,'--at','23:30']
        checked(installer,show=True)
        # Release the shared deployment lock while the installed worker takes it.
        fcntl.flock(lock,fcntl.LOCK_UN)
        report['stage']='initial-managed-backup'
        print('建立目前部署備份與一次性 image 快取、隔離還原；擷取時 backend 短暫暫停，請稍候…',flush=True)
        checked(['sudo','-n','systemctl','start','sam-yolo-backup.service'],timeout=2800)
        report['backup_root']='/var/lib/sam-yolo-backups'
        snapshots=sorted(Path(report['backup_root']).glob('*/manifest.json'),reverse=True)
        need(snapshots,'找不到新備份報告')
        manifest=json.loads(snapshots[0].read_text())
        need(manifest.get('success') is True and manifest.get('restore_verified') is True,'新備份隔離還原未通過')
        report['verified_backup']=str(snapshots[0].parent)
        checked(installer+['--enable'],show=True)
        need(checked(['systemctl','is-enabled','sam-yolo-backup.timer']).strip()=='enabled','timer 未啟用')
        report['next_timer']=checked(['systemctl','show','sam-yolo-backup.timer','--property=NextElapseUSecRealtime','--value']).strip()
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        batch.health(8000)
        batch.health()
        verification.verify_existing()
        verification.unchanged()
        report['stage']='complete'
        report['success']=True
        print('PASS: 每日 23:30 備份／7 份成功版本輪替／當前完整 SQL 與檔案隔離還原／服務恢復／舊資料一致',flush=True)
    except (Exception,KeyboardInterrupt) as exc:
        report['error']=str(exc) if isinstance(exc,(Failed,RuntimeError)) else type(exc).__name__
        if isinstance(exc, CommandFailure):
            report['command_failure']={'exit_code':exc.returncode,'log':exc.log_path,'hint':exc.hint}
        print('FAIL ['+report['stage']+']: '+report['error'],flush=True)
        if report['stage']=='initial-managed-backup':
            print('診斷：sudo journalctl -u sam-yolo-backup.service -n 20 --no-pager',flush=True)
    finally:
        if resources.thread.ident is not None:
            report['resources']=resources.finish()
        if verification:
            verification.session.close()
        batch.session.close()
        stop.set()
        os.close(lock)
        private_write(output,json.dumps(report,ensure_ascii=False,indent=2))
        print('批次報告：'+str(output),flush=True)
    if report['success']:
        print('Phase 6 lab finalization: PASS',flush=True)
        print('新備份：'+report['verified_backup'],flush=True)
    return 0 if report['success'] else 1


if __name__=='__main__':
    raise SystemExit(main())
