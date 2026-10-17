import copy
import importlib.util
import io
from pathlib import Path
import tarfile

import pytest

spec = importlib.util.spec_from_file_location('deployer', Path(__file__).parents[1] / 'deploy-review-release.py')
deployer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deployer)
SHA = 'a' * 40


def manifest():
    value = {'schema': 1, 'repository': deployer.REPOSITORY, 'sha': SHA, 'verify_run_id': 1, 'release_run_id': 2,
             'artifacts': {name: {'file': name + '.tar.gz', 'size': 10, 'sha256': 'b' * 64} for name in ['backend', 'frontend', 'runtime']}}
    for name in ['backend', 'frontend']:
        value['artifacts'][name].update(image=f'noc-release-{name}:{SHA}', image_id='sha256:' + 'c' * 64)
    return value


def test_manifest_accepts_only_expected_commit_and_images():
    deployer.validate_manifest(manifest(), SHA)
    for mutate in [lambda v: v.update(sha='d' * 40), lambda v: v.update(repository='someone/else'),
                   lambda v: v.update(verify_run_id=True),
                   lambda v: v['artifacts']['backend'].update(file='../backend.tar.gz'),
                   lambda v: v['artifacts']['frontend'].update(image='untrusted:latest'),
                   lambda v: v['artifacts']['runtime'].update(size=deployer.MAX_DOWNLOAD + 1),
                   lambda v: v['artifacts']['runtime'].update(sha256='wrong')]:
        value = copy.deepcopy(manifest())
        mutate(value)
        with pytest.raises(ValueError):
            deployer.validate_manifest(value, SHA)


@pytest.mark.parametrize('kind', ['traversal', 'symlink', 'duplicate'])
def test_runtime_rejects_unsafe_archive_before_writing(tmp_path, kind):
    archive = tmp_path / 'runtime.tar.gz'
    with tarfile.open(archive, 'w:gz') as stream:
        member = tarfile.TarInfo('../escape' if kind == 'traversal' else 'safe')
        if kind == 'symlink':
            member.type, member.linkname = tarfile.SYMTYPE, '/etc/passwd'
        else:
            member.size = 1
        stream.addfile(member, io.BytesIO(b'x'))
        if kind == 'duplicate':
            stream.addfile(member, io.BytesIO(b'x'))
    target = tmp_path / 'runtime'
    target.mkdir()
    with pytest.raises(ValueError):
        deployer.extract_runtime(archive, target)
    assert not list(target.iterdir())


def test_download_rejects_corruption_and_cleans_partial(tmp_path, monkeypatch):
    monkeypatch.setattr(deployer, 'request', lambda url: io.BytesIO(b'bad'))
    target = tmp_path / 'artifact.tar.gz'
    with pytest.raises(ValueError, match='checksum'):
        deployer.download('https://github.com/' + deployer.REPOSITORY + '/releases/download/tag/file', target, 3, 'a'*64)
    assert not target.exists()
    assert not target.with_suffix('.partial').exists()


def test_provenance_requires_successful_matching_main_run():
    value = {'conclusion': 'success', 'status': 'completed', 'head_sha': SHA, 'head_branch': 'main',
             'path': '.github/workflows/verify.yml', 'head_repository': {'full_name': deployer.REPOSITORY}}
    assert deployer.verify_run(value, SHA, value['path'])
    for field, bad in [('conclusion', 'failure'), ('head_sha', 'd'*40), ('head_branch', 'feature'), ('path', 'other.yml')]:
        invalid = {**value, field: bad}
        assert not deployer.verify_run(invalid, SHA, value['path'])


@pytest.mark.parametrize('failure', ['stop', 'migrate', 'up'])
def test_deployment_failure_restarts_previous_images_without_restoring_database(tmp_path, monkeypatch, failure):
    import json
    import subprocess
    root = tmp_path / 'server'
    access = root / '.review-access'
    state = access / 'cd'
    state.mkdir(parents=True)
    (root / '.env.review').write_text('private settings')
    (access / 'htpasswd').write_text('private hash')
    release = access / 'releases' / SHA
    release.mkdir(parents=True)
    with tarfile.open(release / 'runtime.tar.gz', 'w:gz'):
        pass
    value = manifest()
    def capture(args):
        if 'config' in args:
            return json.dumps({'services': {name: {'image': 'previous', 'build': {}} for name in deployer.APPS + ['migrate']}})
        if 'image' in args:
            return json.dumps([{'Id': 'sha256:' + 'c'*64, 'Config': {'Labels': {'org.opencontainers.image.revision': SHA}}}])
        return json.dumps([{'Image': 'sha256:' + 'd'*64}])
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        if ('stop' in args and failure == 'stop') or ('run' in args and args[-1] == 'migrate' and failure == 'migrate') or ('up' in args and failure == 'up' and str(release / 'runtime/images.json') in args):
            raise subprocess.CalledProcessError(1, args, stderr=b'simulated startup error')
        if 'pg_dump' in args:
            kwargs['stdout'].write(b'fake verified dump')
        if 'tar' in args:
            with tarfile.open(fileobj=kwargs['stdout'], mode='w:gz'):
                pass
    monkeypatch.setattr(deployer, 'capture', capture)
    monkeypatch.setattr(deployer, 'run', run)
    monkeypatch.setattr(deployer, 'verify_loaded_image', lambda *args: None)
    with pytest.raises(subprocess.CalledProcessError):
        deployer.deploy(root, state, release, value)
    rollback = [args for args in calls if 'up' in args and any(arg.endswith('previous.json') for arg in args)]
    assert len(rollback) == 1
    assert not (state / 'current.json').exists()
    assert not any('downgrade' in args or '--clean' in args for args in calls)
    if failure != 'stop':
        assert list((access / 'backups').glob('*/backup-complete'))
        assert any('pg_restore' in args and '-i' in args for args in calls)


def test_loaded_image_identity_is_portable_across_docker_stores(tmp_path):
    import hashlib
    import json
    config = {'config': {'Labels': {'org.opencontainers.image.revision': SHA}, 'User': '10001'},
              'rootfs': {'diff_ids': ['sha256:' + 'd'*64]}, 'os': 'linux', 'architecture': 'amd64'}
    raw = json.dumps(config).encode()
    checksum = hashlib.sha256(raw).hexdigest()
    item = {'image': 'noc-release-backend:' + SHA, 'image_id': 'sha256:' + checksum}
    archive = tmp_path / 'image.tar.gz'
    with tarfile.open(archive, 'w:gz') as stream:
        for name, content in [('manifest.json', json.dumps([{'Config': 'config.json', 'RepoTags': [item['image']]}]).encode()), ('config.json', raw)]:
            member = tarfile.TarInfo(name)
            member.size = len(content)
            stream.addfile(member, io.BytesIO(content))
    image = {'Id': 'sha256:' + 'e'*64, 'Config': config['config'], 'RootFS': {'Layers': config['rootfs']['diff_ids']},
             'Os': 'linux', 'Architecture': 'amd64'}
    deployer.verify_loaded_image(archive, item, image, SHA)
    # Future CI runners can also use containerd, with a separate config digest.
    item.update(image_id='sha256:' + 'f'*64, image_config_sha256=checksum)
    deployer.verify_loaded_image(archive, item, image, SHA)
    image['RootFS']['Layers'] = ['sha256:' + '0'*64]
    with pytest.raises(ValueError, match='does not match'):
        deployer.verify_loaded_image(archive, item, image, SHA)
