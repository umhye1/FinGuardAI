#!/usr/bin/env python3
"""Isolated local Compose lab. Python stdlib only; no external AI calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / 'infra/.ops-lab'
PROJECT = 'finguard-ops-lab'
MODEL = 'ops-synthetic-v1'
TEXT = '운영 실험 합성 문자: 검찰 사칭 계좌 이체 요구를 주의하세요.'
URL = 'http://127.0.0.1:3100'


class CheckError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise CheckError(message)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    path.chmod(0o600)


def environment():
    # Shell settings must not override the dedicated lab env file.
    return {k: v for k, v in os.environ.items() if not (
        k.startswith(('AI_', 'COMPOSE_', 'POSTGRES_', 'BACKEND_', 'FRONTEND_', 'JWT_'))
    )}


def compose(*args, timeout=180, capture=False):
    return subprocess.run([
        'docker', 'compose', '--project-name', PROJECT,
        '--env-file', str(STATE / 'lab.env'),
        '-f', str(ROOT / 'infra/compose.yml'), '-f', str(ROOT / 'infra/compose.ops.yml'),
        *args,
    ], cwd=ROOT, env=environment(), check=True, timeout=timeout,
        text=True, capture_output=capture)


def request(path, body=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(URL + path, headers=headers,
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            raw = response.read().decode()
            if path == '/':
                require('FinGuard AI' in raw and 'id="root"' in raw, 'frontend HTML mismatch')
                return raw
            result = json.loads(raw)
            require(result.get('statusCode') == 200, 'application status is not 200')
            return result['data']
    except urllib.error.HTTPError as exc:
        # Do not include response bodies, passwords or tokens in diagnostics.
        raise CheckError(f'{path}: HTTP {exc.code}') from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
        raise CheckError(f'{path}: {type(exc).__name__}') from None


def validate_analysis(data):
    require(isinstance(data, dict), 'analysis missing')
    model = data.get('modelResult') or {}
    require(model.get('status') == 'COMPLETED', 'AI classification incomplete')
    require(model.get('modelVersion') == MODEL, 'unexpected AI model')
    require(isinstance(data.get('analysisId'), int), 'analysis ID missing')


def identity():
    return json.loads((STATE / 'identity.json').read_text())


def login():
    user = identity()
    result = request('/api/auth/login', {k: user[k] for k in ('email', 'password')})
    require(bool(result.get('accessToken')), 'login token missing')
    return result['accessToken']


def smoke():
    request('/')
    token = login()  # DB read + Redis refresh-token write
    me = request('/api/auth/me', token=token)
    require(me.get('email') == identity()['email'], 'identity mismatch')
    sentinel = STATE / 'sentinel.json'
    if sentinel.exists():
        expected = json.loads(sentinel.read_text())
        actual = request('/api/analysis/' + str(expected['analysisId']), token=token)
        require(actual == expected, 'persisted analysis changed or missing')
    # HTTP 200 may contain FAILED/ABSTAIN on a broken AI connection: reject that.
    analysis = request('/api/analysis', {'text': TEXT}, token)
    validate_analysis(analysis)
    request('/api/analysis/' + str(analysis['analysisId']), token=token)
    # Keep a bounded successful smoke footprint; failed attempts remain diagnostic evidence.
    req = urllib.request.Request(URL + '/api/analysis/' + str(analysis['analysisId']),
                                 method='DELETE', headers={'Authorization': 'Bearer ' + token})
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            require(response.status == 200, 'smoke cleanup failed')
    except (urllib.error.URLError, TimeoutError, OSError):
        raise CheckError('smoke cleanup failed') from None


def wait_for(check, timeout):
    started = time.monotonic()
    attempts = 0
    last = None
    while time.monotonic() - started < timeout:
        attempts += 1
        try:
            check()
            return {'seconds': round(time.monotonic() - started, 3), 'attempts': attempts}
        except CheckError as exc:
            last = str(exc)
            time.sleep(1)
    raise CheckError(f'timeout after {timeout}s: {last}')


def seed():
    # Call once against this lab's DB. Repeated prepare does not overwrite credentials.
    user = identity()
    try:
        token = login()
    except CheckError as exc:
        if 'HTTP 401' not in str(exc):
            raise
        request('/api/auth/signup', user)
        token = login()
    analysis = request('/api/analysis', {'text': TEXT}, token)
    validate_analysis(analysis)
    detail = request('/api/analysis/' + str(analysis['analysisId']), token=token)
    require(detail.get('inputText') == TEXT, 'seed text mismatch')
    save(STATE / 'sentinel.json', detail)


def prepare():
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    (STATE / 'models').mkdir(exist_ok=True)
    env = STATE / 'lab.env'
    if not env.exists():
        env.write_text('\n'.join([
            'POSTGRES_PASSWORD=' + secrets.token_hex(24),
            'JWT_SECRET=' + secrets.token_hex(48),
            'AI_SERVICE_TOKEN=' + secrets.token_hex(32),
            'FRONTEND_PORT=3100', 'BACKEND_PORT=8180', 'POSTGRES_PORT=56432',
            'AI_CLASSIFIER_MODE=local', 'AI_ALLOW_DEMO_MODEL=true',
            'AI_PROVIDER=openai', 'AI_OPENAI_API_KEY=', 'AI_GEMINI_API_KEY=',
            'AI_GENERATION_MODEL=', '',
        ]))
        env.chmod(0o600)
    if not (STATE / 'identity.json').exists():
        save(STATE / 'identity.json', {
            'email': 'ops-' + secrets.token_hex(6) + '@example.invalid',
            'password': secrets.token_hex(24), 'name': '합성 운영 실험',
        })
    compose('build', timeout=1800)
    compose('run', '--rm', '-T', '--no-deps', '--user', '0',
            '-v', str(STATE / 'models') + ':/output',
            '-v', str(ROOT / 'ai/data/examples') + ':/training:ro',
            'ai', 'finguard-train', '--data', '/training/synthetic-train.jsonl',
            '--output', '/output/classifier.json', '--version', MODEL, '--allow-synthetic')


def metadata():
    def output(*cmd):
        return subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    return {
        'startedAt': datetime.now(timezone.utc).isoformat(),
        'commit': output('git', 'rev-parse', 'HEAD'),
        'trackedChanges': output('git', 'diff', '--stat'),
        'host': platform.system() + ' ' + platform.release() + ' ' + platform.machine(),
        'docker': output('docker', 'version', '--format', '{{.Server.Version}}'),
        'compose': output('docker', 'compose', 'version', '--short'),
        'dockerResources': output('docker', 'info', '--format', '{{.NCPU}} CPUs / {{.MemTotal}} bytes'),
        'images': [],
        'sourceSha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (ROOT / 'infra/compose.yml', ROOT / 'infra/compose.ops.yml',
                                   Path(__file__), ROOT / 'ai/data/examples/synthetic-train.jsonl')},
        'modelSha256': hashlib.sha256((STATE / 'models/classifier.json').read_bytes()).hexdigest(),
        'conditions': 'prebuilt images, existing volumes, sequential warm runs, 1s poll, 8s HTTP timeout; no RAG/provider calls',
    }


def timed_action(action, timeout):
    started = time.monotonic()
    action()
    ready = wait_for(smoke, timeout)
    return {'seconds': round(time.monotonic() - started, 3), 'attempts': ready['attempts']}


def recover(service, timeout):
    started = time.monotonic()
    try:
        compose('stop', service)
        try:
            smoke()
        except CheckError as exc:
            detected = str(exc)
        else:
            raise CheckError(f'{service} stop was not detected')
        stopped_at = time.monotonic()
        result = timed_action(lambda: compose('start', service), timeout)
        result.update(outageObserved=detected,
                      stopAndDetectionSeconds=round(stopped_at - started, 3),
                      totalSeconds=round(time.monotonic() - started, 3))
        return result
    finally:
        # Also restore the stopped service after failure/interrupt, without deleting volumes.
        compose('start', service)


def experiment(runs, timeout):
    require((STATE / 'models/classifier.json').exists(), 'run prepare first')
    report = {'environment': metadata(), 'runs': [], 'status': 'RUNNING'}
    result_path = STATE / ('result-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.json')
    save(result_path, report)
    try:
        compose('up', '-d', '--no-build')
        wait_for(lambda: request('/'), timeout)
        if not (STATE / 'sentinel.json').exists():
            # Wait for backend readiness without assuming frontend startup implies API readiness.
            def backend_ready():
                try:
                    with urllib.request.urlopen('http://127.0.0.1:8180/actuator/health', timeout=8) as r:
                        require(json.load(r).get('status') == 'UP', 'backend not UP')
                except (urllib.error.URLError, OSError, ValueError):
                    raise CheckError('backend health unavailable') from None
            wait_for(backend_ready, timeout)
            wait_for(seed, timeout)
        wait_for(smoke, timeout)
        report['environment']['images'] = json.loads(
            compose('images', '--format', 'json', capture=True).stdout)
        save(result_path, report)
        for number in range(1, runs + 1):
            row = {'run': number, 'status': 'RUNNING'}
            report['runs'].append(row)
            save(result_path, report)
            print(f'Run {number}/{runs}: recreate, backend stop/start, postgres stop/start', flush=True)
            compose('down')  # Deliberately keep volumes; no -v anywhere.
            row['startup'] = timed_action(lambda: compose('up', '-d', '--no-build'), timeout)
            save(result_path, report)
            for service in ('backend', 'postgres'):
                row[service] = recover(service, timeout)
                save(result_path, report)
            row['persistence'] = 'exact API detail equality after recreate and each recovery'
            row['status'] = 'PASSED'
            save(result_path, report)
        report['status'] = 'PASSED'
    except BaseException as exc:
        report['status'] = 'FAILED'
        if report['runs'] and report['runs'][-1]['status'] == 'RUNNING':
            report['runs'][-1]['status'] = 'FAILED'
        report['failure'] = str(exc) if isinstance(exc, CheckError) else type(exc).__name__
        raise
    finally:
        report['finishedAt'] = datetime.now(timezone.utc).isoformat()
        save(result_path, report)
        print('Result:', result_path, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run', 'smoke', 'status', 'down'])
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    require(args.runs > 0 and args.timeout > 0, 'runs and timeout must be positive')
    if args.command == 'prepare':
        prepare()
    elif args.command == 'run':
        experiment(args.runs, args.timeout)
    elif args.command == 'smoke':
        smoke()
        print('PASS: frontend → authentication/DB/Redis → local AI → persisted analysis')
    elif args.command == 'status':
        compose('ps')
    elif args.command == 'down':
        compose('down')


if __name__ == '__main__':
    main()
