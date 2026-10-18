#!/usr/bin/env python3
"""Linux host collector. Standard library only; no shell execution or Docker socket in the web app."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import platform
import re
import socket
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4

REPOSITORY = 'LarVinchi/noc_platform'
REVISION = re.compile(r'^[0-9a-f]{40}$')


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read_json(path, default=None):
    try:
        if Path(path).stat().st_size > 256 * 1024:
            return default
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, allow_nan=False))
    temp.replace(path)


def command(args, timeout=8):
    result = subprocess.run(args, check=True, capture_output=True, timeout=timeout)
    if len(result.stdout) > 1024 * 1024:
        raise ValueError('Command output too large')
    return result.stdout.decode()


def rate(current, previous, elapsed):
    return max(0, (current-previous)/elapsed) if previous is not None and elapsed > 0 and current >= previous else None


def cpu_percent(values, previous):
    # Guest time is already included in user/nice; do not count it twice.
    total, idle = sum(values[:8]), values[3] + (values[4] if len(values) > 4 else 0)
    if previous is None or total <= previous[0] or idle < previous[1]:
        return None, (total, idle)
    return min(100, max(0, 100 * (1-(idle-previous[1])/(total-previous[0])))), (total, idle)


def host_metrics(mounts, previous, proc=Path('/proc'), sys=Path('/sys')):
    tick = time.monotonic()
    elapsed = tick-previous.get('tick', tick)
    memory = {key: int(value.split()[0])*1024 for key, value in
              (line.split(':', 1) for line in (proc/'meminfo').read_text().splitlines())}
    total, available = memory['MemTotal'], memory.get('MemAvailable', memory.get('MemFree', 0))
    cpu, counters = cpu_percent([int(v) for v in (proc/'stat').read_text().splitlines()[0].split()[1:]], previous.get('cpu'))
    filesystems, errors = [], []
    for mount in mounts:
        try:
            fs = os.statvfs(mount)
            size, free = fs.f_blocks*fs.f_frsize, fs.f_bavail*fs.f_frsize
            filesystems.append({'mount': mount, 'total_bytes': size, 'available_bytes': free,
                'used_percent': (size-free)/size*100 if size else 0,
                'inode_used_percent': (fs.f_files-fs.f_favail)/fs.f_files*100 if fs.f_files else None})
        except OSError:
            errors.append('filesystem_unavailable')
    networks, interfaces = {}, []
    for line in (proc/'net/dev').read_text().splitlines()[2:]:
        name, numbers = line.split(':', 1)
        name, values = name.strip(), [int(v) for v in numbers.split()]
        if name == 'lo':
            continue
        networks[name] = (values[0], values[8])
        old = previous.get('networks', {}).get(name, (None, None))
        try:
            state = (sys/'class/net'/name/'operstate').read_text().strip()
        except OSError:
            state = 'unknown'
        interfaces.append({'name': name, 'state': state if state in ('up', 'down') else 'unknown',
            'rx_bytes_per_second': rate(values[0], old[0], elapsed), 'tx_bytes_per_second': rate(values[8], old[1], elapsed),
            'rx_errors': values[2], 'tx_errors': values[10]})
    disks, io = {}, []
    for line in (proc/'diskstats').read_text().splitlines():
        fields = line.split()
        name = fields[2]
        # Whole devices only; show each device separately to avoid double-counting partitions.
        if not (sys/'block'/name).exists() or name.startswith(('loop', 'ram')):
            continue
        disks[name] = (int(fields[5])*512, int(fields[9])*512)
        old = previous.get('disks', {}).get(name, (None, None))
        io.append({'device': name, 'read_bytes_per_second': rate(disks[name][0], old[0], elapsed),
                   'write_bytes_per_second': rate(disks[name][1], old[1], elapsed)})
    previous.update(tick=tick, cpu=counters, networks=networks, disks=disks)
    metrics = {'cpu_percent': cpu, 'load': list(os.getloadavg()), 'memory_total_bytes': total,
        'memory_available_bytes': available, 'memory_used_percent': (total-available)/total*100,
        'swap_total_bytes': memory.get('SwapTotal', 0),
        'swap_used_bytes': memory.get('SwapTotal', 0)-memory.get('SwapFree', 0),
        'filesystems': filesystems, 'interfaces': interfaces[:64], 'disk_io': io[:64]}
    return metrics, list(set(errors))


def identity():
    release = {}
    try:
        for line in Path('/etc/os-release').read_text().splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                release[key] = value.strip('"')
    except OSError:
        pass
    model = 'Unknown'
    for line in Path('/proc/cpuinfo').read_text().splitlines():
        if line.startswith(('model name', 'Hardware')):
            model = line.split(':', 1)[-1].strip()
            break
    return {'hostname': socket.gethostname(), 'distribution': release.get('NAME', platform.system()),
        'version': release.get('VERSION_ID', 'Unknown'), 'kernel': platform.release(),
        'architecture': platform.machine(), 'cpu_model': model, 'cpu_cores': os.cpu_count() or 1,
        'uptime_seconds': float(Path('/proc/uptime').read_text().split()[0])}


def byte_size(value):
    match = re.fullmatch(r'([\d.]+)\s*([A-Za-z]*)', value.strip())
    if not match:
        return None
    units = {'B': 1, 'kB': 1000, 'KB': 1000, 'MB': 1000**2, 'GB': 1000**3, 'TB': 1000**4,
             'KiB': 1024, 'MiB': 1024**2, 'GiB': 1024**3, 'TiB': 1024**4}
    return int(float(match[1])*units[match[2]]) if match[2] in units else None


def docker_metrics(context, project):
    deadline = time.monotonic()+25
    def invoke(args, timeout=8):
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired('docker collection', 25)
        return command(args, timeout=min(timeout, remaining))
    docker = ['docker', '--context', context]
    engine = {'available': False, 'context': context}
    try:
        engine.update(json.loads(invoke(docker+['info', '--format', '{"name":{{json .Name}},"operating_system":{{json .OperatingSystem}},"cpus":{{.NCPU}},"memory_bytes":{{.MemTotal}}}'])))
        ids = invoke(docker+['ps', '-aq', '--filter', 'label=com.docker.compose.project='+project, '--filter', 'label=com.docker.compose.oneoff=False']).split()
        if len(ids) > 128 or any(not re.fullmatch('[0-9a-f]{12,64}', value) for value in ids):
            raise ValueError('Unexpected containers')
        engine['available'] = True
        if not ids:
            return engine, [], []
        template = '{"name":{{json .Name}},"status":{{json .State.Status}},"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}null{{end}},"restarts":{{.RestartCount}},"image":{{json .Image}},"service":{{index .Config.Labels "com.docker.compose.service" | json}}}'
        rows = [json.loads(line) for line in invoke(docker+['inspect', '--format', template, *ids]).splitlines()]
        rows = [row for row in rows if row.get('service') != 'migrate']
        revisions = {}
        for image in set(row['image'] for row in rows):
            revision = invoke(docker+['image', 'inspect', '--format', '{{index .Config.Labels "org.opencontainers.image.revision"}}', image]).strip()
            revisions[image] = revision if REVISION.fullmatch(revision) else None
        containers = [{'name': row['name'].lstrip('/'), 'status': row['status'], 'health': row['health'],
                       'restarts': row['restarts'], 'revision': revisions[row['image']]} for row in rows]
        errors = []
        try:
            stats = [json.loads(line) for line in invoke(docker+['stats', '--no-stream', '--format', '{{json .}}', *ids], timeout=12).splitlines()]
            for container in containers:
                stat = next((s for s in stats if s['Name'] == container['name']), None)
                if stat:
                    used, limit = stat['MemUsage'].split(' / ')
                    container.update(cpu_percent=float(stat['CPUPerc'].rstrip('%')),
                        memory_used_bytes=byte_size(used), memory_limit_bytes=byte_size(limit))
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            errors.append('docker_stats_unavailable')
        return engine, containers, errors
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        return {'available': False, 'context': context}, [], ['docker_unavailable']


def deployment_status(root):
    state = root/'.review-access/cd'
    status = read_json(state/'status.json', {})
    current = read_json(state/'current.json', {})
    if current.get('sha'):
        status.update(deployed_sha=current['sha'], deployed_at=current.get('deployed_at'))
    status['last_check_at'] = read_json(state/'heartbeat.json', {}).get('checked_at')
    try:
        active = command(['systemctl', '--user', 'show', 'noc-review-deploy.service', '-p', 'ActiveState', '--value']).strip()
        status['process_active'] = active in ('activating', 'active', 'reloading')
    except (OSError, subprocess.SubprocessError):
        status['process_active'] = None
    attempts = sorted((state/'attempts').glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:30]
    return status, [value for path in attempts if (value := read_json(path))]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_json(url, payload=None, token=None, method=None):
    headers = {'User-Agent': 'AFL-NOC-host-agent', 'Accept': 'application/vnd.github+json'}
    if token:
        headers['Authorization'] = 'Bearer '+token
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=json.dumps(payload, allow_nan=False).encode() if payload is not None else None,
                                 method=method, headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(req, timeout=8) as response:
        raw = response.read(2*1024*1024+1)
        if len(raw) > 2*1024*1024:
            raise ValueError('Response too large')
        return json.loads(raw)


def github_snapshot(token=None):
    base = 'https://api.github.com/repos/'+REPOSITORY+'/'
    main = http_json(base+'commits/main', token=token)['sha']
    runs = http_json(base+'actions/workflows/verify.yml/runs?branch=main&event=push&per_page=5', token=token)['workflow_runs']
    run = next((row for row in runs if row['head_sha'] == main), {})
    # GitHub's release list is not a publication-order guarantee. In particular,
    # an older release can precede the release that the server just installed.
    # Resolve main's immutable release by tag, as the deployer itself does.
    try:
        current_release = http_json(base+'releases/tags/review-'+main, token=token)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        current_release = {}
    if (current_release.get('tag_name') == 'review-'+main and not current_release.get('draft', True)
            and current_release.get('published_at')):
        release = main
    else:
        # Main may still be building. Show the most recently published review
        # release in the returned page rather than trusting API list position.
        releases = http_json(base+'releases?per_page=100', token=token)
        published = []
        for row in releases:
            tag = row.get('tag_name', '')
            if row.get('draft', True) or not tag.startswith('review-') or not REVISION.fullmatch(tag[7:]):
                continue
            try:
                stamp = dt.datetime.fromisoformat(row['published_at'].replace('Z', '+00:00'))
            except (KeyError, AttributeError, TypeError, ValueError):
                continue
            if stamp.tzinfo is not None:
                published.append((stamp, tag[7:]))
        release = max(published)[1] if published else None
    return {'main_sha': main, 'release_sha': release, 'build_sha': run.get('head_sha'),
        'build_status': run.get('status') if run.get('status') in ('queued', 'in_progress', 'completed') else 'unknown', 'build_result': run.get('conclusion'),
        'build_run_id': run.get('id'), 'checked_at': now(), 'error': None}


def publish_github(deployments, state, token):
    """Optional external deployment history; only canonical phases, never host metrics/logs."""
    known = read_json(state/'github-deployments.json', {})
    base = 'https://api.github.com/repos/'+REPOSITORY+'/'
    for deployment in reversed(deployments):
        key, sha = deployment.get('attempt_id'), deployment.get('target_sha')
        result = deployment.get('result')
        if not key or not sha or not REVISION.fullmatch(sha) or result not in ('running', 'success', 'failed'):
            continue
        status = {'running': 'in_progress', 'success': 'success', 'failed': 'failure'}[result]
        previous = known.get(key, {})
        if not previous.get('id'):
            row = http_json(base+'deployments', {'ref': sha, 'auto_merge': False, 'required_contexts': [],
                'environment': 'stakeholder-review', 'production_environment': False}, token)
            previous = known[key] = {'id': row['id']}
            atomic_json(state/'github-deployments.json', known)
        if previous.get('status') != status:
            http_json(base+'deployments/'+str(previous['id'])+'/statuses',
                {'state': status, 'environment': 'stakeholder-review', 'description': 'Server deployment '+status}, token)
            previous['status'] = status
            # Bound the private mapping; only the latest thirty attempts are reported.
            known = dict(list(known.items())[-100:])
            atomic_json(state/'github-deployments.json', known)


def github_worker(state, root, token_file, stop):
    next_read = 0
    while not stop.is_set():
        token = None
        try:
            if token_file:
                token = Path(token_file).read_text().strip()
            if time.monotonic() >= next_read:
                snapshot = github_snapshot(token)
                atomic_json(state/'github.json', snapshot)
                next_read = time.monotonic()+300
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
            snapshot = read_json(state/'github.json', {})
            snapshot['error'] = 'rate_limited' if isinstance(error, urllib.error.HTTPError) and error.code in (403, 429) else 'unavailable'
            atomic_json(state/'github.json', snapshot)
            next_read = time.monotonic()+300
        # A missing write permission must not invalidate successfully fetched build evidence.
        try:
            if token:
                deployment, attempts = deployment_status(root)
                publish_github(attempts or [deployment], state, token)
            atomic_json(state/'github-publishing.json', {'available':True})
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            atomic_json(state/'github-publishing.json', {'available':False})
        stop.wait(30)


def spool_report(db, report):
    payload = json.dumps(report, allow_nan=False)
    if len(payload.encode()) > 256*1024:
        raise ValueError('Agent report exceeds intake limit')
    db.execute('INSERT INTO reports(id,payload) VALUES(?,?)', (str(report['sample_id']), payload))
    db.execute('DELETE FROM reports WHERE seq NOT IN (SELECT seq FROM reports ORDER BY seq DESC LIMIT 120)')
    db.commit()


def flush_reports(db, url, token):
    # Send the latest sample first so recovery immediately restores a current heartbeat.
    for seq, payload in db.execute('SELECT seq,payload FROM reports ORDER BY seq DESC LIMIT 10').fetchall():
        try:
            http_json(url+'/api/platform-health/ingest', json.loads(payload), token)
        except urllib.error.HTTPError as error:
            if error.code in (409, 413, 422):
                db.execute('DELETE FROM reports WHERE seq=?', (seq,))
                db.commit()
                print('Host report rejected; check schema, clock and configured host ID. HTTP', error.code, flush=True)
                continue
            raise
        db.execute('DELETE FROM reports WHERE seq=?', (seq,))
        db.commit()


def validate_config(config):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', config['host_id']):
        raise ValueError('Invalid host ID')
    url = urllib.parse.urlsplit(config['api_url'])
    if url.username or url.password or url.query or url.fragment or url.path not in ('', '/') or url.scheme not in ('https', 'http'):
        raise ValueError('API URL must be an origin without credentials, query or path')
    if url.scheme != 'https' and url.hostname not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('Remote intake requires HTTPS')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', config.get('docker_context', 'desktop-linux')) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', config.get('project', 'noc-review')):
        raise ValueError('Invalid Docker context/project')
    mounts = config.get('mounts', ['/', '/home', '/var'])
    if not 1 <= len(mounts) <= 32 or any(not isinstance(m, str) or not m.startswith('/') or len(m) > 160 for m in mounts):
        raise ValueError('Invalid filesystem paths')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    if platform.system() != 'Linux':
        raise SystemExit('Install this collector on the Linux host, not inside a container or on the Windows development PC.')
    config = json.loads(args.config.read_text())
    validate_config(config)
    root = Path(config['root']).resolve()
    state = args.config.resolve().parent
    import fcntl
    lock = (state/'agent.lock').open('w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('Another host collector is already running') from None
    stop = threading.Event()
    worker = threading.Thread(target=github_worker, args=(state, root, config.get('github_token_file'), stop), daemon=True)
    worker.start()
    if args.once:
        worker.join(timeout=0.1)
    db = sqlite3.connect(str(state/'queue.sqlite3'))
    db.execute('CREATE TABLE IF NOT EXISTS reports(seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE,payload TEXT NOT NULL)')
    previous, backoff, next_send = {}, 30, 0
    try:
        while True:
            started = time.monotonic()
            observed_at = now()
            try:
                metrics, errors = host_metrics(config.get('mounts', ['/', '/home', '/var']), previous)
                engine, containers, docker_errors = docker_metrics(config.get('docker_context', 'desktop-linux'), config.get('project', 'noc-review'))
                deployment, attempts = deployment_status(root)
                url = config['api_url'].rstrip('/')
                try:
                    ready = http_json(url+'/health/ready').get('status') == 'ready'
                except (OSError, ValueError):
                    ready = False
                    errors.append('application_unavailable')
                if read_json(state/'github-publishing.json', {}).get('available') is False:
                    errors.append('github_reporting_unavailable')
                report = {'schema_version': 1, 'sample_id': str(uuid4()), 'host_id': config['host_id'], 'observed_at': observed_at,
                    'host': identity(), 'metrics': metrics, 'docker': engine, 'containers': containers,
                    'application_ready': ready, 'deployment': deployment, 'deployments': attempts,
                    'github': read_json(state/'github.json', {}), 'collection_errors': list(set(errors+docker_errors))}
                spool_report(db, report)
                if time.monotonic() >= next_send:
                    flush_reports(db, url, Path(config['token_file']).read_text().strip())
                    backoff, next_send = 30, 0
                atomic_json(state/'heartbeat.json', {'collected_at': report['observed_at'], 'queued_samples': db.execute('SELECT count(*) FROM reports').fetchone()[0]})
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
                print('Host collector cycle incomplete:', type(error).__name__, flush=True)
                next_send = time.monotonic()+backoff
                backoff = min(300, backoff*2)
            if args.once:
                return
            stop.wait(max(1, 30-(time.monotonic()-started)))
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        db.close()
        lock.close()


if __name__ == '__main__':
    main()
