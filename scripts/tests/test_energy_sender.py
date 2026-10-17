import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location('sender', Path(__file__).parents[1] / 'send-energy-workbook.py')
sender = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sender)


def test_binary_snapshot_and_ssh_acknowledgement(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'Tracker with spaces.xlsx'
    content = b'PK\x00\xff\r\n\x1a' * 100
    path.write_bytes(content)
    key = tmp_path / 'upload key'
    key.write_text('test placeholder')
    monkeypatch.setattr(sender.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(sender.shutil, 'which', lambda name: '/test/ssh')
    monkeypatch.setattr(sender.sys, 'argv', ['sender', '--workbook', str(path), '--server', 'steve@192.168.1.24', '--identity', str(key)])
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        header, body = kwargs['input'].split(b'\n', 1)
        assert body == content
        assert json.loads(header)['sha256'] == hashlib.sha256(content).hexdigest()
        assert 'StrictHostKeyChecking=yes' in command and command[-1] == 'steve@192.168.1.24'
        assert str(key) in command  # Paths with spaces remain a single argument.
        if len(calls) == 1:
            return SimpleNamespace(returncode=255, stderr=b'connection lost', stdout=b'')
        return SimpleNamespace(returncode=0, stdout=json.dumps({'outcome': 'unchanged', 'sha256': hashlib.sha256(content).hexdigest()}).encode())

    monkeypatch.setattr(sender.subprocess, 'run', run)
    assert sender.main() == 0
    assert len(calls) == 2
    assert json.loads(capsys.readouterr().out)['outcome'] == 'unchanged'


def test_source_changing_during_snapshot_is_rejected(tmp_path, monkeypatch):
    path = tmp_path / 'tracker.xlsx'
    path.write_bytes(b'PK first')
    monkeypatch.setattr(sender.time, 'sleep', lambda seconds: path.write_bytes(b'PK second version'))
    with pytest.raises(ValueError, match='changing'):
        sender.snapshot(path)


def test_bad_acknowledgement_does_not_report_success(tmp_path, monkeypatch):
    path = tmp_path / 'tracker.xlsx'
    path.write_bytes(b'PK content')
    monkeypatch.setattr(sender.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(sender.shutil, 'which', lambda name: '/test/ssh')
    monkeypatch.setattr(sender.sys, 'argv', ['sender', '--workbook', str(path), '--server', 'steve@192.168.1.24', '--identity', str(path)])
    monkeypatch.setattr(sender.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=b'{"outcome":"updated","sha256":"wrong"}'))
    assert sender.main() == 1


def test_local_check_writes_a_status_log_without_workbook_content(tmp_path, monkeypatch):
    path = tmp_path / 'tracker.xlsx'
    path.write_bytes(b'PK private-workbook-bytes')
    log = tmp_path / 'logs' / 'delivery.log'
    monkeypatch.setattr(sender.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(sender.sys, 'argv', ['sender', '--workbook', str(path), '--server', 'steve@192.168.1.24', '--identity', str(path), '--check-only', '--log-file', str(log)])
    assert sender.main() == 0
    assert 'local_snapshot_checked' in log.read_text()
    assert 'private-workbook-bytes' not in log.read_text()


@pytest.mark.parametrize('required', [False, True])
def test_agent_reads_workbook_only_when_due_and_acknowledges_web_request(tmp_path, monkeypatch, required):
    path, key = tmp_path / 'tracker.xlsx', tmp_path / 'upload-key'
    key.write_text('placeholder')
    content = b'PK workbook'
    if required:
        path.write_bytes(content)
    monkeypatch.setattr(sender.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(sender.shutil, 'which', lambda name: '/test/ssh')
    monkeypatch.setattr(sender.sys, 'argv', ['sender', '--workbook', str(path), '--server', 'steve@192.168.1.24', '--identity', str(key), '--agent-check'])
    calls = []
    token = '2026-07-04T12:00:00+00:00'
    def run(command, **kwargs):
        calls.append(kwargs['input'])
        if len(calls) == 1:
            assert json.loads(kwargs['input']) == {'operation': 'poll'}
            response = {'outcome': 'poll', 'upload_required': required, 'request_token': token}
        else:
            header, body = kwargs['input'].split(b'\n', 1)
            assert json.loads(header)['request_token'] == token
            assert body == content
            response = {'outcome': 'unchanged', 'sha256': hashlib.sha256(content).hexdigest()}
        return SimpleNamespace(returncode=0, stdout=json.dumps(response).encode())
    monkeypatch.setattr(sender.subprocess, 'run', run)
    assert sender.main() == 0
    assert len(calls) == (2 if required else 1)
