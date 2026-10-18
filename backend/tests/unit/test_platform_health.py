import copy
import os
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import pytest
from pydantic import SecretStr, ValidationError
from fastapi import HTTPException
from app.schemas.platform_health import AgentReport
from app.services.platform_health import summarize
os.environ.setdefault('POSTGRES_PASSWORD', 'unit-test-unused')

SHA = 'a'*40


def report():
    now = datetime.now(timezone.utc).isoformat()
    raw = dict(sample_id=str(uuid4()), host_id='noc-review-host', observed_at=now,
        host=dict(hostname='test-host', distribution='Rocky Linux', version='9', kernel='6.test', architecture='x86_64',
                  cpu_model='Test CPU', cpu_cores=8, uptime_seconds=3600),
        metrics=dict(cpu_percent=25, memory_total_bytes=10000, memory_available_bytes=5000, memory_used_percent=50,
                     filesystems=[dict(mount='/', total_bytes=10000, available_bytes=5000, used_percent=50)]),
        docker=dict(available=True, context='desktop-linux'),
        containers=[dict(name=name, status='running', health='healthy', revision=SHA) for name in ('noc-review-api-1','noc-review-frontend-1')],
        application_ready=True, github=dict(checked_at=now, main_sha=SHA, release_sha=SHA, build_sha=SHA, build_status='completed', build_result='success'),
        deployment=dict(target_sha=SHA, deployed_sha=SHA, last_check_at=now, deployed_at=now, updated_at=now, stage='complete', result='success'))
    raw['containers'] += [dict(name=name,status='running',health='healthy') for name in ('noc-review-db-1','noc-review-response-worker-1','noc-review-public-gateway-1')]
    return AgentReport.model_validate(raw).model_dump(mode='json')


def test_version_success_requires_both_running_images_and_release():
    value = report()
    assert summarize(value, value['observed_at'])['state'] == 'Up to date'
    value['containers'][0]['revision'] = 'b'*40
    assert summarize(value, value['observed_at'])['state'] != 'Up to date'
    value = report()
    value['github']['main_sha'] = 'b'*40
    assert summarize(value, value['observed_at'])['state'] == 'Update pending'


def test_stale_samples_do_not_become_current_after_replay():
    value = report()
    value['observed_at'] = (datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()
    summary = summarize(value, datetime.now(timezone.utc))
    assert summary['state'] == 'Status stale'
    assert summary['application_health'] == 'Unknown'
    assert summary['alerts'] == []


def test_failed_update_keeps_application_health_separate():
    value = report()
    value['deployment'].update(result='failed', stage='failed', rollback='succeeded')
    summary = summarize(value, value['observed_at'])
    assert summary['state'] == 'Failed'
    assert summary['application_health'] == 'Healthy'


def test_deploying_requires_active_process_and_recent_stage():
    value = report()
    value['deployment'].update(result='running', stage='migrating', process_active=True)
    assert summarize(value, value['observed_at'])['state'] == 'Deploying'
    value['deployment']['process_active'] = False
    assert summarize(value, value['observed_at'])['state'] == 'Status stale'


def test_missing_github_or_deployer_heartbeat_is_stale():
    for field in ('github', 'deployment'):
        value = report()
        value[field]['checked_at' if field=='github' else 'last_check_at'] = None
        assert summarize(value, value['observed_at'])['state'] == 'Status stale'


@pytest.mark.parametrize('change', ['nan', 'future', 'old', 'oversized', 'unknown', 'memory', 'duplicate'])
def test_rejects_invalid_reports(change):
    value = report()
    if change == 'nan': value['metrics']['cpu_percent'] = float('nan')
    if change == 'future': value['observed_at'] = (datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()
    if change == 'old': value['observed_at'] = (datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
    if change == 'oversized': value['containers'] *= 100
    if change == 'unknown': value['secrets'] = 'forbidden'
    if change == 'memory': value['metrics']['memory_available_bytes'] = 999999
    if change == 'duplicate': value['containers'].append(copy.deepcopy(value['containers'][0]))
    with pytest.raises(ValidationError): AgentReport.model_validate(value)


def test_threshold_flags_and_unknown_container_health():
    value = report()
    value['metrics']['cpu_percent'] = 95
    assert summarize(value, value['observed_at'])['alerts'][0]['severity'] == 'critical'
    value['containers'][0]['health'] = 'unhealthy'
    assert summarize(value, value['observed_at'])['application_health'] == 'Unhealthy'


def test_agent_authentication_is_independent_and_endpoint_scoped(monkeypatch):
    from app.core import security
    monkeypatch.setattr(security.settings, 'PLATFORM_AGENT_INGEST_TOKEN', SecretStr('a'*48))
    monkeypatch.setattr(security.settings, 'ENVIRONMENT', 'production')
    monkeypatch.setattr(security.settings, 'AUTH_MODE', 'entra')
    actor = security.authenticate({'authorization':'Bearer '+'a'*48}, 'POST', '/api/platform-health/ingest')
    assert actor['roles'] == ['HostAgent']
    with pytest.raises(HTTPException) as error:
        security.authenticate({'authorization':'Bearer wrong'}, 'POST', '/api/platform-health/ingest')
    assert error.value.status_code == 401
    monkeypatch.setattr(security.settings, 'AUTH_MODE', 'preview')
    monkeypatch.setattr(security.settings, 'ENVIRONMENT', 'development')
    monkeypatch.setattr(security, 'auth_configuration', lambda: {'configured':True,'mode':'entra'})
    monkeypatch.setattr(security, 'validate_token', lambda token: {'roles':['NOC.Viewer']})
    with pytest.raises(HTTPException) as error:
        security.authenticate({'authorization':'Bearer viewer'}, 'GET', '/api/platform-health/hosts')
    assert error.value.status_code == 403
