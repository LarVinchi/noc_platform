#!/usr/bin/env python3
"""Run the installed release's optional FTTH report job; dry-run unless --send is specified."""
import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

KEYS = {'FTTH_WEEKLY_EMAIL_ENABLED', 'FTTH_WEEKLY_RECIPIENTS', 'FTTH_SMTP_HOST', 'FTTH_SMTP_PORT',
        'FTTH_SMTP_FROM', 'FTTH_SMTP_USERNAME', 'FTTH_SMTP_PASSWORD'}


def configuration(path):
    if os.name != 'nt' and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError('Mail configuration must be private: chmod 600 the configuration file')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or set(data) - KEYS or not all(isinstance(v, str) and '\0' not in v for v in data.values()):
        raise ValueError('Use only the documented FTTH mail settings with string values')
    return data


def command(root, settings, context, send, runner=subprocess.run):
    current = json.loads((root / '.review-access/cd/current.json').read_text())
    expected = current.get('sha', '')
    docker = ['docker', '--context', context]
    container = 'noc-review-api-1'
    check = runner(docker + ['inspect', '--format', '{{json .Config.Labels}}', container],
        capture_output=True, text=True, check=True)
    labels = json.loads(check.stdout)
    if not expected or labels.get('org.opencontainers.image.revision') != expected or labels.get('com.docker.compose.project') != 'noc-review' or labels.get('com.docker.compose.service') != 'api':
        raise ValueError('Running API does not match the installed release; wait for deployment to finish')
    # Pass only environment variable names on the command line; values remain in the child environment.
    args = docker + ['exec', '-i']
    for key in sorted(KEYS):
        args += ['--env', key]
    args += [container, 'python', '-m', 'app.ftth_report_worker']
    if send:
        args.append('--send')
    env = {k: v for k, v in os.environ.items() if k not in KEYS}
    env.update({key: settings.get(key, '') for key in KEYS})
    return runner(args, env=env, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--docker-context', default='desktop-linux')
    parser.add_argument('--send', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    settings = configuration(root / '.review-access/ftth-mail/config.json')
    command(root, settings, args.docker_context, args.send)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError):
        print('FTTH report job failed. Check private configuration, installed release identity and service logs; no automatic resend of uncertain deliveries.', file=sys.stderr)
        raise SystemExit(1)
