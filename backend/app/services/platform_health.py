"""Evidence-based state; GitHub success alone never establishes server deployment."""
from datetime import datetime, timezone


def age(value, now):
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (now - parsed).total_seconds()


def fresh(value, now, seconds):
    elapsed = age(value, now)
    return elapsed is not None and -60 <= elapsed <= seconds


def summarize(payload, received_at, now=None, warning=80, critical=90):
    now = now or datetime.now(timezone.utc)
    host_fresh = fresh(payload['observed_at'], now, 120) and fresh(received_at, now, 120)
    gh, deployment = payload['github'], payload['deployment']
    github_fresh = fresh(gh.get('checked_at'), now, 900)
    deployer_fresh = fresh(deployment.get('last_check_at'), now, 900)
    containers = payload['containers']
    app_containers = [row for row in containers if row['name'] in ('noc-review-api-1', 'noc-review-frontend-1')]
    revisions = {row.get('revision') for row in app_containers if row.get('revision')}
    running_sha = next(iter(revisions)) if len(revisions) == 1 and len(app_containers) == 2 and all(
        row.get('revision') and row['status'] == 'running' for row in app_containers) else None
    state, reason = 'Status stale', 'Waiting for current deployment evidence'
    if not host_fresh:
        reason = 'Host-agent readings are stale'
    elif deployment['result'] == 'running':
        if deployment.get('process_active') and fresh(deployment.get('updated_at'), now, 1800):
            state, reason = 'Deploying', 'Server deployer is active'
        else:
            reason = 'Deployment has no fresh active-process confirmation'
    elif not github_fresh or gh.get('error'):
        reason = 'GitHub version/build information is unavailable or stale'
    elif not deployer_fresh:
        reason = 'Deployment checker has not reported a recent check'
    elif deployment['result'] == 'failed' and deployment.get('target_sha') == gh.get('main_sha'):
        state, reason = 'Failed', 'Server deployment failed; check rollback and application health separately'
    elif gh.get('build_sha') == gh.get('main_sha') and gh.get('build_result') in ('failure', 'cancelled', 'timed_out', 'action_required', 'startup_failure'):
        state, reason = 'Failed', 'Latest main build did not succeed'
    elif running_sha and running_sha == gh.get('main_sha') == gh.get('release_sha') == deployment.get('deployed_sha'):
        state, reason = 'Up to date', 'Running API and frontend images match the published main release'
    elif gh.get('main_sha') and gh.get('main_sha') != deployment.get('deployed_sha'):
        state, reason = 'Update pending', 'Waiting for build, release publication or server installation'
    elif gh.get('main_sha'):
        reason = 'Running images or published release identity do not confirm the installed version'
    expected = {'noc-review-api-1', 'noc-review-frontend-1', 'noc-review-db-1', 'noc-review-response-worker-1', 'noc-review-public-gateway-1'}
    bad_containers = sorted(expected - {row['name'] for row in containers}) if payload['docker']['available'] else []
    bad_containers += [row['name'] for row in containers if row['status'] != 'running' or row.get('health') == 'unhealthy']
    application = 'Unknown' if not host_fresh else 'Unhealthy' if payload.get('application_ready') is False or bad_containers else 'Healthy' if payload.get('application_ready') is True and containers and payload['docker']['available'] else 'Unknown'
    alerts = []
    metrics = payload['metrics']
    values = [('CPU', metrics.get('cpu_percent')), ('RAM', metrics['memory_used_percent'])]
    values += [(f"Storage {row['mount']}", row['used_percent']) for row in metrics['filesystems']]
    values += [(f"Inodes {row['mount']}", row.get('inode_used_percent')) for row in metrics['filesystems']]
    if host_fresh:
        for label, value in values:
            if value is not None and value >= warning:
                alerts.append({'metric': label, 'value': value, 'severity': 'critical' if value >= critical else 'warning'})
    return {'state': state, 'reason': reason, 'host_fresh': host_fresh, 'github_fresh': github_fresh,
            'deployer_fresh': deployer_fresh, 'running_sha': running_sha, 'application_health': application,
            'unhealthy_containers': bad_containers, 'alerts': alerts,
            'sample_age_seconds': age(payload['observed_at'], now),
            'thresholds': {'warning_percent': warning, 'critical_percent': critical}}
