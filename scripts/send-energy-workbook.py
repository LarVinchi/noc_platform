#!/usr/bin/env python3
"""Send a OneDrive-synced workbook using Python 3.9+ and OpenSSH; no Graph login."""
import argparse
import datetime as dt
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

MAX_BYTES = 10 * 1024 * 1024


def snapshot(path):
    before = path.stat()
    if not 0 < before.st_size <= MAX_BYTES:
        raise ValueError('Expected a nonempty XLSX workbook no larger than 10 MB')
    with path.open('rb') as stream:
        content = stream.read(MAX_BYTES + 1)
    # Allow OneDrive/Excel replacement or writing to finish before a later run.
    time.sleep(2)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino) or len(content) != before.st_size:
        raise ValueError('Workbook is changing; wait for Excel save and OneDrive synchronization to finish')
    if not content.startswith(b'PK'):
        raise ValueError('Source is not an XLSX workbook')
    return content, {'size': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
                     'modified_at': dt.datetime.fromtimestamp(after.st_mtime, dt.timezone.utc).isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook', required=True, type=Path)
    parser.add_argument('--server', required=True, help='SSH account@hostname or account@IPv4')
    parser.add_argument('--identity', required=True, type=Path, help='Dedicated private SSH key')
    parser.add_argument('--port', type=int, default=22)
    parser.add_argument('--log-file', type=Path, help='Optional rotating acknowledgement/error log')
    parser.add_argument('--agent-check', action='store_true', help='Check for a web refresh request or an hourly upload due')
    parser.add_argument('--check-only', action='store_true', help='Check the local snapshot without uploading')
    args = parser.parse_args()
    handler = None
    logger = logging.getLogger('noc.energy_upload')
    logger.setLevel(logging.INFO)
    logger.propagate = False

    def emit(message, error=False):
        stream = sys.stderr if error else sys.stdout
        if stream is not None:  # pythonw.exe has no console streams.
            print(message, file=stream)
        if handler:
            logger.info(message)

    try:
        if args.log_file:
            args.log_file.parent.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(args.log_file, maxBytes=1024 * 1024, backupCount=3, encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
            logger.addHandler(handler)
        if not re.fullmatch(r'[a-zA-Z0-9_][a-zA-Z0-9_.-]*@[a-zA-Z0-9][a-zA-Z0-9.-]*', args.server) or not 1 <= args.port <= 65535:
            raise ValueError('Invalid SSH destination or port')
        if args.workbook.suffix.lower() != '.xlsx':
            raise ValueError('Select the main XLSX tracker, not an Excel temporary file')
        if args.check_only:
            content, header = snapshot(args.workbook)
            emit(json.dumps({'outcome': 'local_snapshot_checked', **header}))
            return 0
        native_ssh = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'System32/OpenSSH/ssh.exe'
        ssh = str(native_ssh) if sys.platform == 'win32' and native_ssh.is_file() else shutil.which('ssh')
        if not ssh or not args.identity.is_file():
            raise ValueError('Install OpenSSH and configure a dedicated SSH key first')
        # The server key is pinned in known_hosts during setup. No interactive prompts.
        # No shell and no remote command: authorized_keys selects the fixed receiver.
        command = [ssh, '-T', '-p', str(args.port), '-i', str(args.identity.resolve()),
                   '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
                   '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=20',
                   '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3', args.server]
        def exchange(payload):
            for attempt in range(3):
                options = {'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}
                result = subprocess.run(command, input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180, **options)
                if result.returncode == 0:
                    return json.loads(result.stdout)
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))
            emit(result.stderr.decode(errors='replace')[-2000:], error=True)
            raise ValueError('SSH receiver failed; check access and receiver configuration. Last valid server data is retained.')

        token = None
        if args.agent_check:
            decision = exchange(b'{"operation":"poll"}\n')
            if decision.get('outcome') != 'poll' or type(decision.get('upload_required')) is not bool:
                raise ValueError('Receiver returned an invalid agent response; update the Linux receiver')
            if not decision['upload_required']:
                emit(json.dumps({'outcome': 'idle', 'notice': 'No refresh requested; hourly upload is not due'}))
                return 0
            token = decision.get('request_token')
        content, header = snapshot(args.workbook)
        if token is not None:
            header['request_token'] = token
        acknowledgement = exchange(json.dumps(header).encode() + b'\n' + content)
        if acknowledgement.get('sha256') != header['sha256'] or acknowledgement.get('outcome') not in ('updated', 'unchanged'):
            raise ValueError('Receiver returned an invalid acknowledgement')
        emit(json.dumps(acknowledgement))
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        emit(f'Energy upload failed: {error}', error=True)
        return 1
    finally:
        if handler:
            logger.removeHandler(handler)
            handler.close()


if __name__ == '__main__':
    sys.exit(main())
