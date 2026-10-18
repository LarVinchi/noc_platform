import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import urllib.error
from uuid import uuid4
import pytest


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1]/filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


agent = module('host_agent', 'noc-host-agent.py')
installer = module('host_install', 'install-host-monitoring.py')


def test_cpu_ignores_guest_double_count_and_rates_reset():
    percent, first = agent.cpu_percent([100,0,0,900,0,0,0,0,500,500], None)
    assert percent is None
    percent, _ = agent.cpu_percent([200,0,0,1000,0,0,0,0,999,999], first)
    assert percent == 50
    assert agent.rate(50,100,30) is None
    assert agent.rate(200,100,2) == 50
    assert agent.byte_size('1.5GiB') == int(1.5*1024**3)
    assert agent.byte_size('1.5GB') == 1500000000


@pytest.mark.parametrize('url', ['http://remote.example', 'https://user:pass@example.com', 'https://example.com/?token=secret'])
def test_rejects_unencrypted_remote_intake_and_credentials_in_url(url):
    with pytest.raises(ValueError):
        agent.validate_config({'host_id':'noc-review-host','api_url':url})


def test_queue_is_bounded_and_sends_newest_first(tmp_path, monkeypatch):
    db = sqlite3.connect(tmp_path/'queue.sqlite3')
    db.execute('CREATE TABLE reports(seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE,payload TEXT NOT NULL)')
    for index in range(130): agent.spool_report(db, {'sample_id':str(uuid4()),'index':index})
    assert db.execute('SELECT count(*) FROM reports').fetchone()[0] == 120
    sent = []
    monkeypatch.setattr(agent,'http_json',lambda url,payload,token: sent.append(payload['index']))
    agent.flush_reports(db,'http://127.0.0.1:18001','private-test-token')
    assert sent == list(range(129,119,-1))
    assert db.execute('SELECT count(*) FROM reports').fetchone()[0] == 110


def test_docker_failure_is_not_zero_utilization(monkeypatch):
    monkeypatch.setattr(agent,'command',lambda *args,**kwargs: (_ for _ in ()).throw(subprocess.TimeoutExpired('docker',8)))
    engine, containers, errors = agent.docker_metrics('desktop-linux','noc-review')
    assert not engine['available'] and containers == []
    assert errors == ['docker_unavailable']


def test_preparation_reuses_secret_and_does_not_activate_controller(tmp_path,monkeypatch):
    monkeypatch.setattr(installer.Path,'home',lambda:tmp_path/'home')
    controller=tmp_path/'.review-access/cd/deploy-review-release.py'
    controller.parent.mkdir(parents=True)
    controller.write_text('previous controller')
    config,state=installer.prepare(tmp_path,'test-host',18001)
    token=(state/'ingest.token').read_text()
    installer.prepare(tmp_path,'test-host',18001)
    assert (state/'ingest.token').read_text()==token
    assert controller.read_text()=='previous controller'
    assert not (state/'enabled').exists()
    assert config['api_url']=='http://127.0.0.1:18001'
    assert json.loads((state/'compose.json').read_text())['services']['api']['ports']==['127.0.0.1:18001:8000']
    assert token not in (tmp_path/'home/.config/systemd/user/noc-host-agent.service').read_text()


def test_redirects_never_forward_bearer_credentials():
    assert agent.NoRedirect().redirect_request(None,None,302,'Moved',{},'https://different.example') is None


def test_optional_status_upload_failure_keeps_build_evidence(tmp_path,monkeypatch):
    token=tmp_path/'github.token'
    token.write_text('test-only-token')
    monkeypatch.setattr(agent,'github_snapshot',lambda token:{'main_sha':'a'*40,'error':None})
    monkeypatch.setattr(agent,'deployment_status',lambda root:({},[]))
    monkeypatch.setattr(agent,'publish_github',lambda *args:(_ for _ in ()).throw(OSError('unavailable')))
    class Stop:
        done=False
        def is_set(self):return self.done
        def wait(self,seconds):self.done=True
    agent.github_worker(tmp_path,tmp_path,str(token),Stop())
    assert agent.read_json(tmp_path/'github.json')['error'] is None
    assert agent.read_json(tmp_path/'github-publishing.json')['available'] is False


def test_main_release_is_resolved_by_exact_tag_not_list_order(monkeypatch):
    sha = 'a'*40
    calls = []

    def request(url, **kwargs):
        calls.append(url)
        if url.endswith('commits/main'):
            return {'sha': sha}
        if '/actions/' in url:
            return {'workflow_runs': [{'head_sha': sha, 'status': 'completed', 'conclusion': 'success', 'id': 42}]}
        if url.endswith('releases/tags/review-'+sha):
            return {'tag_name': 'review-'+sha, 'draft': False, 'published_at': '2026-10-18T22:09:01Z'}
        pytest.fail('The exact published main release must not depend on release-list ordering')

    monkeypatch.setattr(agent, 'http_json', request)
    value = agent.github_snapshot()
    assert value['main_sha'] == value['release_sha'] == value['build_sha'] == sha
    assert value['build_result'] == 'success'
    assert len(calls) == 3


@pytest.mark.parametrize('state', ['not_found', 'draft', 'unpublished'])
def test_pending_main_fallback_uses_publication_time_not_list_order(monkeypatch, state):
    sha, old, recent = 'a'*40, 'b'*40, 'c'*40

    def request(url, **kwargs):
        if url.endswith('commits/main'):
            return {'sha': sha}
        if '/actions/' in url:
            return {'workflow_runs': []}
        if '/releases/tags/' in url:
            if state == 'not_found':
                raise urllib.error.HTTPError(url, 404, 'Not found', {}, None)
            return {'tag_name': 'review-'+sha, 'draft': state == 'draft',
                    'published_at': None if state == 'unpublished' else '2026-10-18T23:00:00Z'}
        assert url.endswith('releases?per_page=100')
        return [
            {'tag_name': 'review-'+old, 'draft': False, 'published_at': '2026-10-18T20:00:00Z'},
            {'tag_name': 'review-'+recent, 'draft': False, 'published_at': '2026-10-18T22:00:00Z'},
            {'tag_name': 'review-'+sha, 'draft': True, 'published_at': '2026-10-19T00:00:00Z'},
            {'tag_name': 'unrelated', 'draft': False, 'published_at': '2026-10-19T00:00:00Z'},
            {'tag_name': 'review-'+'d'*40, 'draft': False, 'published_at': 'invalid'},
        ]

    monkeypatch.setattr(agent, 'http_json', request)
    value = agent.github_snapshot()
    assert value['release_sha'] == recent and value['main_sha'] == sha
    assert value['build_status'] == 'unknown'


@pytest.mark.parametrize('status', [403, 429, 500])
def test_release_lookup_errors_are_not_disguised_as_a_missing_release(monkeypatch, status):
    def request(url, **kwargs):
        if url.endswith('commits/main'):
            return {'sha': 'a'*40}
        if '/actions/' in url:
            return {'workflow_runs': []}
        raise urllib.error.HTTPError(url, status, 'Unavailable', {}, None)

    monkeypatch.setattr(agent, 'http_json', request)
    with pytest.raises(urllib.error.HTTPError):
        agent.github_snapshot()
