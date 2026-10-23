#!/usr/bin/env python3
"""Prepare the Linux host collector; --activate applies the loopback intake and starts it."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import subprocess
import sys


def write_private(path, content, executable=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(content)
    temporary.chmod(0o700 if executable else 0o600)
    temporary.replace(path)


def prepare(root, host_id, port):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', host_id) or not 1024 <= port <= 65535:
        raise ValueError('Invalid host ID or loopback port')
    state = root/'.review-access/monitoring'
    state.mkdir(parents=True, exist_ok=True)
    state.chmod(0o700)
    token_file = state/'ingest.token'
    if not token_file.exists():
        write_private(token_file, secrets.token_urlsafe(48))
    token = token_file.read_text().strip()
    if not 32 <= len(token) <= 512:
        raise ValueError('Existing agent token is invalid; rotate it explicitly')
    config_file = state/'agent.json'
    config = json.loads(config_file.read_text()) if config_file.exists() else {}
    config.update(root=str(root), host_id=host_id, api_url='http://127.0.0.1:'+str(port), token_file=str(token_file))
    config.setdefault('docker_context', 'desktop-linux')
    config.setdefault('project', 'noc-review')
    config.setdefault('mounts', ['/', '/home', '/var'])
    write_private(config_file, json.dumps(config, indent=2)+'\n')
    # No token is printed or put on a command line. This overlay remains private.
    overlay = {'services': {'api': {'ports': ['127.0.0.1:'+str(port)+':8000'],
        'environment': {'PLATFORM_AGENT_INGEST_TOKEN': token, 'PLATFORM_AGENT_HOST_ID': host_id}}}}
    write_private(state/'compose.json', json.dumps(overlay, indent=2)+'\n')
    source = Path(__file__).resolve().parent
    write_private(state/'noc-host-agent.py', (source/'noc-host-agent.py').read_text(), executable=True)
    write_private(state/'deploy-review-release.py', (source/'deploy-review-release.py').read_text(), executable=True)
    unit = '\n'.join([
        '[Unit]', 'Description=AFL NOC host health and deployment collector', 'After=network-online.target docker-desktop.service',
        '', '[Service]', 'Type=simple', 'WorkingDirectory='+str(root),
        'ExecStart='+json.dumps(sys.executable)+' '+json.dumps(str(state/'noc-host-agent.py'))+' --config '+json.dumps(str(config_file)),
        'Restart=on-failure', 'RestartSec=15', 'UMask=0077', 'NoNewPrivileges=true', 'PrivateTmp=true',
        'ProtectSystem=strict', 'ReadWritePaths='+json.dumps(str(state)), 'RestrictSUIDSGID=true',
        'RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6', 'MemoryMax=256M', 'CPUQuota=10%',
        'StandardOutput=journal', 'StandardError=journal', '', '[Install]', 'WantedBy=default.target', '',
    ])
    unit_file = Path.home()/'.config/systemd/user/noc-host-agent.service'
    write_private(unit_file, unit)
    return config, state


def compose_command(docker, root, runtime, state):
    command = docker+['compose', '-p', 'noc-review', '--env-file', str(root/'.env.review'),
        '-f', str(runtime/'compose.review.yaml'), '-f', str(runtime/'compose.review.public.yaml'),
        '-f', str(state/'compose.json')]
    knowledge = root/'.review-access/knowledge/compose.json'
    if knowledge.is_file() and (knowledge.parent/'enabled').is_file():
        command += ['--profile', 'knowledge-review', '-f', str(knowledge)]
    return command+['-f', str(runtime/'images.json')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--host-id', default='noc-review-host')
    parser.add_argument('--port', type=int, default=18001)
    parser.add_argument('--activate', action='store_true')
    args = parser.parse_args()
    if platform.system() != 'Linux' or os.geteuid() == 0:
        raise SystemExit('Run on the Linux review server as its Docker Desktop user, not root.')
    os.umask(0o077)
    root = args.root.resolve()
    if root != Path('/home/steve/Downloads/noc_platform') or any(c in str(root) for c in ('\n', '\r', '%')):
        raise SystemExit('This installer targets /home/steve/Downloads/noc_platform. Review paths for another host.')
    current = root/'.review-access/cd/current.json'
    if not current.is_file():
        raise SystemExit('Install the existing tested-release deployer and deploy this feature before activation.')
    # Do not race the deployment controller while applying its private overlay.
    import fcntl
    with (root/'.review-access/cd/lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        config, state = prepare(root, args.host_id, args.port)
        if args.activate:
            docker = ['docker', '--context', config['docker_context']]
            subprocess.run(docker+['exec', 'noc-review-api-1', 'python', '-c',
                "import importlib.util; assert importlib.util.find_spec('app.api.routers.platform_health')"], check=True)
            runtime = Path(json.loads(current.read_text())['runtime']).resolve()
            if not runtime.is_relative_to(root/'.review-access/releases'):
                raise SystemExit('Current runtime path is outside the release directory')
            controller = root/'.review-access/cd/deploy-review-release.py'
            if controller.exists() and not controller.with_suffix('.before-monitoring').exists():
                shutil.copyfile(controller, controller.with_suffix('.before-monitoring'))
                controller.with_suffix('.before-monitoring').chmod(0o700)
            write_private(controller, (state/'deploy-review-release.py').read_text(), executable=True)
            write_private(state/'enabled', 'Host monitoring enabled\n')
            command = compose_command(docker, root, runtime, state)
            subprocess.run(command+['up', '-d', '--no-build', '--no-deps', '--wait', 'api'], check=True)
            subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
            subprocess.run(['systemctl', '--user', 'enable', '--now', 'noc-host-agent.service'], check=True)
            subprocess.run(['systemctl', '--user', 'restart', 'noc-host-agent.service'], check=True)
            print('Host collector activated. Open Governance > Server health after the first sample.')
        else:
            print('Host collector prepared; not started. Re-run with --activate after the monitoring release is deployed.')
    print('Check: systemctl --user status noc-host-agent.service')
    print('Logs: journalctl --user -u noc-host-agent.service -f')


if __name__ == '__main__':
    main()
