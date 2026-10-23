#!/usr/bin/env python3
"""Pull a successful main-branch release into the isolated stakeholder stack."""
import argparse
import base64
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import urllib.error
import urllib.request
from uuid import uuid4

REPOSITORY = 'LarVinchi/noc_platform'
APPS = ['api', 'response-worker', 'frontend', 'public-gateway']
DOCKER = ['docker', '--context', 'desktop-linux']
MAX_DOWNLOAD = 4 * 1024**3


def request(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={
        'User-Agent': 'AFL-NOC-review-deployer', 'Accept': 'application/vnd.github+json'}), timeout=90)


def api(path):
    with request('https://api.github.com/repos/' + REPOSITORY + '/' + path) as response:
        return json.load(response)


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            value.update(block)
    return value.hexdigest()


def validate_manifest(value, sha):
    if value.get('schema') != 1 or value.get('repository') != REPOSITORY or value.get('sha') != sha:
        raise ValueError('Release identity mismatch')
    for key in ['verify_run_id', 'release_run_id']:
        if type(value.get(key)) is not int or value[key] <= 0:
            raise ValueError('Missing workflow provenance')
    if set(value['artifacts']) != {'backend', 'frontend', 'runtime'}:
        raise ValueError('Unexpected release artifacts')
    for name, item in value['artifacts'].items():
        if item['file'] != name + '.tar.gz' or type(item['size']) is not int or not 0 < item['size'] <= MAX_DOWNLOAD:
            raise ValueError('Invalid artifact size or filename')
        if not re.fullmatch('[0-9a-f]{64}', item['sha256']):
            raise ValueError('Invalid artifact digest')
        if name != 'runtime' and (item['image'] != f'noc-release-{name}:{sha}' or not re.fullmatch('sha256:[0-9a-f]{64}', item['image_id'])):
            raise ValueError('Unexpected image identity')
        if name != 'runtime' and 'image_config_sha256' in item and not re.fullmatch('[0-9a-f]{64}', item['image_config_sha256']):
            raise ValueError('Invalid image configuration digest')


def verify_loaded_image(path, item, image, sha):
    # Classic Docker IDs identify the config; containerd IDs identify the manifest.
    # Compare the saved config digest, runtime settings and all filesystem DiffIDs.
    with tarfile.open(path, 'r:gz') as archive:
        manifest = json.load(archive.extractfile('manifest.json'))
        if len(manifest) != 1 or item['image'] not in manifest[0]['RepoTags']:
            raise ValueError('Unexpected image archive contents')
        member = archive.getmember(manifest[0]['Config'])
        if not member.isfile() or member.size > 4 * 1024**2:
            raise ValueError('Invalid image configuration')
        raw = archive.extractfile(member).read()
    expected = item.get('image_config_sha256', item['image_id'].removeprefix('sha256:'))
    config = json.loads(raw)
    if (hashlib.sha256(raw).hexdigest() != expected or image['Config'] != config['config']
            or image['RootFS']['Layers'] != config['rootfs']['diff_ids']
            or image['Os'] != config['os'] or image['Architecture'] != config['architecture']
            or image['Config'].get('Labels', {}).get('org.opencontainers.image.revision') != sha):
        raise ValueError('Loaded image does not match the tested image')


def verify_run(run, sha, path):
    return (run.get('conclusion') == 'success' and run.get('status') == 'completed'
            and run.get('head_sha') == sha and run.get('head_branch') == 'main'
            and run.get('path') == path and run.get('head_repository', {}).get('full_name') == REPOSITORY)


def download(url, path, size, expected):
    # Release URLs must belong to this repository; urllib follows GitHub's asset redirect.
    if not url.startswith(f'https://github.com/{REPOSITORY}/releases/download/'):
        raise ValueError('Unexpected asset origin')
    temporary = path.with_suffix('.partial')
    count = 0
    try:
        with request(url) as response, temporary.open('wb') as target:
            while True:
                block = response.read(1024**2)
                if not block:
                    break
                count += len(block)
                if count > size:
                    raise ValueError('Artifact exceeds declared size')
                target.write(block)
        if count != size or digest(temporary) != expected:
            raise ValueError('Artifact checksum mismatch')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def extract_runtime(path, target):
    # Python 3.9-compatible: reject traversal, links, devices and duplicate names.
    with tarfile.open(path, 'r:gz') as archive:
        seen = set()
        members = archive.getmembers()
        if sum(item.size for item in members) > 10 * 1024**2:
            raise ValueError('Runtime archive too large')
        for item in members:
            parts = Path(item.name).parts
            if not item.isfile() or not parts or Path(item.name).is_absolute() or '..' in parts or item.name in seen:
                raise ValueError('Unsafe runtime archive')
            seen.add(item.name)
        for item in members:
            destination = target / item.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(item) as source, destination.open('wb') as output:
                shutil.copyfileobj(source, output)


def run(args, **kwargs):
    # Keep configuration, credentials and container output out of public logs.
    return subprocess.run(args, check=True, stderr=subprocess.PIPE, **kwargs)


def capture(args):
    return run(args, stdout=subprocess.PIPE).stdout.decode()


def write_json(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(path)


def compose(root, runtime=None):
    location = runtime or root
    command = DOCKER + ['compose', '-p', 'noc-review', '--env-file', str(root / '.env.review'),
                        '-f', str(location / 'compose.review.yaml'), '-f', str(location / 'compose.review.public.yaml')]
    monitoring = root / '.review-access/monitoring/compose.json'
    if monitoring.is_file() and (monitoring.parent / 'enabled').is_file():
        command += ['-f', str(monitoring)]
    knowledge = root / '.review-access/knowledge/compose.json'
    if knowledge.is_file() and (knowledge.parent / 'enabled').is_file():
        command += ['--profile', 'knowledge-review', '-f', str(knowledge)]
    return command


def report_stage(state, sha, stage, result='running', begin=False, rollback=None, error_type=None):
    """Only sanitized operational metadata; private logs and backup paths stay private."""
    state.mkdir(parents=True, exist_ok=True)
    path = state / 'status.json'
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        value = json.loads(path.read_text()) if path.exists() else {}
    except (OSError, ValueError):
        value = {}
    if begin or value.get('target_sha') != sha:
        value = {'attempt_id': str(uuid4()) if begin else None, 'target_sha': sha,
                 'started_at': stamp if begin else None, 'rollback': 'not_needed'}
    value.update(stage=stage, result=result, updated_at=stamp, error_type=error_type)
    if rollback:
        value['rollback'] = rollback
    write_json(path, value)
    if value.get('attempt_id'):
        attempts = state / 'attempts'
        attempts.mkdir(exist_ok=True)
        write_json(attempts / (value['attempt_id']+'.json'), value)
        for expired in sorted(attempts.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[100:]:
            expired.unlink()


def deploy(root, state_root, release_dir, manifest):
    apps = APPS + (['knowledge-review'] if (root / '.review-access/knowledge/enabled').is_file() else [])
    report_stage(state_root, manifest['sha'], 'loading_images')
    runtime = release_dir / 'runtime'
    runtime.mkdir()
    extract_runtime(release_dir / 'runtime.tar.gz', runtime)
    access = runtime / '.review-access'
    access.mkdir()
    (access / 'htpasswd').symlink_to(root / '.review-access/htpasswd')
    loaded_images = {}
    for name in ['backend', 'frontend']:
        item = manifest['artifacts'][name]
        run(DOCKER + ['load', '-i', str(release_dir / item['file'])], stdout=subprocess.DEVNULL)
        image = json.loads(capture(DOCKER + ['image', 'inspect', item['image']]))[0]
        verify_loaded_image(release_dir / item['file'], item, image, manifest['sha'])
        loaded_images[name] = image['Id']
    images = {name: loaded_images['backend' if name in ['api', 'response-worker', 'migrate', 'knowledge-review'] else 'frontend']
              for name in apps + ['migrate']}
    override = runtime / 'images.json'
    write_json(override, {'services': {name: {'image': image} for name, image in images.items()}})
    candidate = compose(root, runtime) + ['-f', str(override)]
    previous_state = state_root / 'current.json'
    old = json.loads(previous_state.read_text()) if previous_state.exists() else None
    previous = compose(root, Path(old['runtime'])) + ['-f', str(Path(old['runtime']) / 'images.json')] if old else compose(root)
    backup = root / '.review-access/backups' / (dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-ci-' + manifest['sha'][:12])
    backup.mkdir(parents=True)
    # Compose resolves all bind paths and volume names before serializing.
    rollback = json.loads(capture(previous + ['config', '--format', 'json']))
    for name in apps + ['migrate']:
        rollback['services'][name].pop('build', None)
        container = 'noc-review-' + ('api' if name == 'migrate' else name) + '-1'
        rollback['services'][name]['image'] = json.loads(capture(DOCKER + ['inspect', container]))[0]['Image']
    rollback_file = backup / 'previous.json'
    write_json(rollback_file, rollback)
    shutil.copyfile(root / '.env.review', backup / 'env.review')
    shutil.copyfile(root / '.review-access/htpasswd', backup / 'htpasswd')
    rollback_command = DOCKER + ['compose', '-p', 'noc-review', '-f', str(rollback_file)]
    stopped = False
    try:
        report_stage(state_root, manifest['sha'], 'backing_up')
        stopped = True
        run(previous + ['stop', *apps], stdout=subprocess.DEVNULL)
        with (backup / 'database.dump').open('wb') as stream:
            run(DOCKER + ['exec', 'noc-review-db-1', 'pg_dump', '-U', 'noc_review', '-d', 'noc_review', '-Fc'], stdout=stream)
        run(DOCKER + ['exec', '-i', 'noc-review-db-1', 'pg_restore', '--list'],
            input=(backup / 'database.dump').read_bytes(), stdout=subprocess.DEVNULL)
        for volume in ['documents', 'private_documents']:
            target = backup / (volume + '.tar.gz')
            with target.open('wb') as stream:
                run(DOCKER + ['run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                              '--entrypoint', 'tar', '-v', f'noc-review_{volume}:/backup:ro',
                              rollback['services']['api']['image'], '-czf', '-', '-C', '/backup', '.'], stdout=stream)
            with tarfile.open(target, 'r:gz') as archive:
                for member in archive:
                    if member.isfile():
                        with archive.extractfile(member) as stream:
                            while stream.read(1024**2):
                                pass
        write_json(backup / 'checksums.json', {p.name: digest(p) for p in backup.iterdir() if p.is_file()})
        (backup / 'backup-complete').write_text('Verified database dump and document archives.\n')
        report_stage(state_root, manifest['sha'], 'migrating')
        run(candidate + ['run', '--rm', '--no-deps', 'migrate'], stdout=subprocess.DEVNULL)
        report_stage(state_root, manifest['sha'], 'starting')
        run(candidate + ['up', '-d', '--no-build', '--no-deps', '--wait', '--wait-timeout', '240', *apps], stdout=subprocess.DEVNULL)
        report_stage(state_root, manifest['sha'], 'health_check')
        # Validate the anonymous public upstream stays password protected.
        try:
            urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:18080/', timeout=15)
        except urllib.error.HTTPError as error:
            if error.code != 401:
                raise
        else:
            raise ValueError('Password gate failed')
        credentials = dict(line.split(': ', 1) for line in (root / '.review-access/credentials.txt').read_text().splitlines())
        authorization = base64.b64encode((credentials['Username'] + ':' + credentials['Password']).encode()).decode()
        client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for path in ['/', '/api/energy/status']:
            probe = urllib.request.Request('http://127.0.0.1:18080' + path, headers={'Authorization': 'Basic ' + authorization})
            with client.open(probe, timeout=20) as response:
                if response.status != 200:
                    raise ValueError('Authenticated review access failed')
        write_json(previous_state, {'sha': manifest['sha'], 'runtime': str(runtime), 'backup': str(backup),
                                   'deployed_at': dt.datetime.now(dt.timezone.utc).isoformat()})
        report_stage(state_root, manifest['sha'], 'complete', 'success')
    except Exception as error:
        if stopped:
            report_stage(state_root, manifest['sha'], 'rollback', rollback='attempted')
            # Schema downgrades and destructive restores require operator review.
            try:
                run(rollback_command + ['up', '-d', '--no-build', '--no-deps', '--wait', '--wait-timeout', '240', *apps], stdout=subprocess.DEVNULL)
            except Exception as rollback_error:
                report_stage(state_root, manifest['sha'], 'failed', 'failed', rollback='failed', error_type=type(rollback_error).__name__)
                raise
            report_stage(state_root, manifest['sha'], 'failed', 'failed', rollback='succeeded', error_type=type(error).__name__)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--retry', action='store_true', help='Retry a failed main commit after resolving its error')
    args = parser.parse_args()
    os.umask(0o077)
    root = args.root.resolve()
    state = root / '.review-access/cd'
    state.mkdir(parents=True, exist_ok=True)
    with (state / 'lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Another deployment is running')
            return
        write_json(state / 'heartbeat.json', {'checked_at': dt.datetime.now(dt.timezone.utc).isoformat()})
        sha = api('commits/main')['sha']
        if not re.fullmatch('[0-9a-f]{40}', sha):
            raise ValueError('Invalid main commit')
        current = state / 'current.json'
        failed = state / 'failed.json'
        if current.exists() and json.loads(current.read_text())['sha'] == sha:
            report_stage(state, sha, 'idle', 'success')
            print('Already running tested main:', sha)
            return
        if failed.exists() and json.loads(failed.read_text())['sha'] == sha and not args.retry:
            report_stage(state, sha, 'failed', 'failed')
            print('Deployment failed previously; inspect failed.json and retry explicitly:', sha)
            return
        try:
            release = api('releases/tags/review-' + sha)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                report_stage(state, sha, 'waiting_for_release', 'waiting')
                print('Waiting for a tested main release:', sha)
                return
            raise
        assets = {item['name']: item for item in release['assets']}
        manifest_asset = assets['release.json']
        if manifest_asset['size'] > 32768:
            raise ValueError('Manifest too large')
        with request(manifest_asset['browser_download_url']) as response:
            manifest = json.loads(response.read(32769))
        validate_manifest(manifest, sha)
        for key, path, event in [('verify_run_id', '.github/workflows/verify.yml', 'push'),
                                 ('release_run_id', '.github/workflows/review-release.yml', 'workflow_run')]:
            workflow = api('actions/runs/' + str(manifest[key]))
            # workflow_run itself can report the current default-branch SHA;
            # require the publishing run to be completed and successful as well.
            if key == 'release_run_id':
                valid = (workflow.get('conclusion') == 'success' and workflow.get('status') == 'completed'
                         and workflow.get('path') == path and workflow.get('event') == event
                         and workflow.get('head_repository', {}).get('full_name') == REPOSITORY)
            else:
                valid = verify_run(workflow, sha, path) and workflow.get('event') == event
            if not valid:
                report_stage(state, sha, 'waiting_for_build', 'waiting')
                print('Waiting for successful release provenance:', key)
                return
        release_dir = root / '.review-access/releases' / sha
        if release_dir.exists():
            # Only this locked service writes its private download directory.
            shutil.rmtree(release_dir)
        release_dir.mkdir(parents=True)
        try:
            report_stage(state, sha, 'downloading', begin=True)
            for item in manifest['artifacts'].values():
                download(assets[item['file']]['browser_download_url'], release_dir / item['file'], item['size'], item['sha256'])
            report_stage(state, sha, 'verifying')
            if api('commits/main')['sha'] != sha:
                report_stage(state, sha, 'waiting_for_release', 'waiting')
                print('Main advanced while downloading; wait for its next release')
                return
            deploy(root, state, release_dir, manifest)
        except Exception as error:
            report_stage(state, sha, 'failed', 'failed', error_type=type(error).__name__)
            write_json(failed, {'sha': sha, 'error_type': type(error).__name__,
                                'detail': error.stderr.decode(errors='replace')[-4000:] if isinstance(error, subprocess.CalledProcessError) and error.stderr else str(error),
                                'notice': 'Inspect private deployment journal and backup. Application rollback attempted; database not downgraded.'})
            raise
        failed.unlink(missing_ok=True)
        print('Deployed tested main:', sha)


if __name__ == '__main__':
    main()
