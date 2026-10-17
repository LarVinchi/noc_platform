import base64
import importlib.util
import os
from pathlib import Path
import struct
import subprocess
import sys

import pytest

spec = importlib.util.spec_from_file_location('installer', Path(__file__).parents[1] / 'install-energy-upload-key.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

PUBLIC = 'ssh-ed25519 ' + base64.b64encode(struct.pack('>I', 11) + b'ssh-ed25519' + struct.pack('>I', 32) + bytes(range(32))).decode()


def test_install_is_restricted_idempotent_and_preserves_existing_keys(tmp_path):
    ssh = tmp_path / '.ssh'
    ssh.mkdir()
    authorized = ssh / 'authorized_keys'
    original = 'ssh-rsa ORIGINAL-ADMIN-KEY admin'
    authorized.write_text(original)
    receiver = Path('/home/steve/Downloads/noc_platform/scripts/receive-energy-review-workbook.sh')
    assert 'installed' in installer.install(tmp_path, PUBLIC, receiver)
    expected = original + '\n' + installer.restricted_line(PUBLIC, receiver) + '\n'
    assert authorized.read_text() == expected
    assert authorized.stat().st_mode & 0o777 == 0o600
    assert 'already' in installer.install(tmp_path, PUBLIC, receiver)
    assert authorized.read_text() == expected


def test_existing_unrestricted_upload_key_is_not_silently_reused(tmp_path):
    ssh = tmp_path / '.ssh'
    ssh.mkdir()
    authorized = ssh / 'authorized_keys'
    authorized.write_text(PUBLIC + '\n')
    with pytest.raises(ValueError, match='different restrictions'):
        installer.install(tmp_path, PUBLIC, Path('/receiver.sh'))
    assert authorized.read_text() == PUBLIC + '\n'


@pytest.mark.parametrize('key', ['ssh-rsa abc', 'ssh-ed25519 abc', 'ssh-ed25519 !!!', 'restrict ' + PUBLIC])
def test_invalid_keys_and_options_are_rejected(key):
    with pytest.raises(ValueError):
        installer.restricted_line(key, Path('/receiver.sh'))


def test_symlinked_authorized_keys_is_not_followed(tmp_path):
    ssh = tmp_path / '.ssh'
    ssh.mkdir()
    target = tmp_path / 'other'
    target.write_text('leave this alone')
    (ssh / 'authorized_keys').symlink_to(target)
    with pytest.raises(OSError):
        installer.install(tmp_path, PUBLIC, Path('/receiver.sh'))
    assert target.read_text() == 'leave this alone'


@pytest.mark.parametrize('mode,result,expected', [
    ('--enable', 'ok', 0), ('--status', 'ok', 0),
    ('--status', 'empty', 1), ('--enable', 'failure', 1),
])
def test_bash_scheduler_passes_complete_encoded_script_and_requires_confirmation(tmp_path, mode, result, expected):
    # Exercise the actual Bash launcher on Linux with a fake Windows executable.
    # Windows task registration itself must still be verified on the workstation.
    source = (Path(__file__).parents[1] / 'setup-energy-windows.sh').read_text()
    block = source[source.index('if [[ "$MODE" == \'--enable\' || "$MODE" == \'--status\' ]]; then'):]
    fake = tmp_path / 'powershell.exe'
    fake.write_text('''#!/usr/bin/env python3
import base64, os, sys
assert '-Command' not in sys.argv
assert '-EncodedCommand' in sys.argv
script = base64.b64decode(sys.argv[sys.argv.index('-EncodedCommand')+1]).decode('utf-16le')
assert 'Register-ScheduledTask' in script and 'Get-ScheduledTaskInfo' in script
assert "'pythonw.exe'" in script and '-Execute $BackgroundPython' in script
assert 'NOC_TASK_STATUS_OK' in script
assert os.environ['NOC_UPLOAD_WORKBOOK'] == 'C:/Workbook with spaces.xlsx'
if os.environ['TEST_RESULT'] == 'ok':
    print('NOC_TASK_STATUS_OK')
elif os.environ['TEST_RESULT'] == 'failure':
    print('Access denied by Windows', file=sys.stderr)
    sys.exit(1)
''')
    fake.chmod(0o755)
    launcher = tmp_path / 'launcher.sh'
    launcher.write_text('''set -euo pipefail
PYTHON=("$TEST_PYTHON")
POWERSHELL="$TEST_POWERSHELL"
MODE="$TEST_MODE"
WORKBOOK='C:/Workbook with spaces.xlsx'
SERVER='steve@192.168.1.24'
KEY_WIN='C:/Users/NOC1/.ssh/noc-energy-upload'
SENDER_WIN='C:/NOC/send-energy-workbook.py'
''' + block)
    env = {**os.environ, 'TEST_PYTHON': sys.executable, 'TEST_POWERSHELL': str(fake),
           'TEST_MODE': mode, 'TEST_RESULT': result}
    process = subprocess.run(['bash', str(launcher)], env=env, capture_output=True, text=True, timeout=10)
    assert process.returncode == expected, process.stdout + process.stderr
    if result == 'empty':
        assert 'not verified' in process.stderr
    elif result == 'failure':
        assert 'Access denied by Windows' in process.stderr
