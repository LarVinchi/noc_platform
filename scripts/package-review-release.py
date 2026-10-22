#!/usr/bin/env python3
"""Package the exact CI-tested images and an explicit list of public runtime files."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile

RUNTIME_FILES = [
    'compose.review.yaml', 'compose.review.public.yaml',
    'deploy/review-gateway.nginx.conf',
    *[f'db/init-scripts/0{i}_{name}.sql' for i, name in enumerate([
        'infrastructure', 'customers_services', 'incidents_tickets', 'optimized_view', 'seed_data'], 1)],
    'scripts/send-energy-workbook.py', 'scripts/setup-energy-windows.sh',
    'scripts/energy-upload-windows.ps1', 'docs/energy-windows-noc1.md',
    'scripts/noc-host-agent.py', 'scripts/install-host-monitoring.py',
    'scripts/deploy-review-release.py', 'docs/server-health.md',
    'docs/linked-onedrive-intake.md',
]


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sha', required=True)
    parser.add_argument('--verify-run-id', required=True, type=int)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', args.sha) or args.verify_run_id <= 0:
        raise ValueError('Expected a commit SHA and verification run ID')
    args.output.mkdir(parents=True, exist_ok=True)
    result = {'schema': 1, 'repository': args.repository, 'sha': args.sha,
              'verify_run_id': args.verify_run_id, 'artifacts': {}}
    for name in ['backend', 'frontend']:
        image = f'noc-release-{name}:{args.sha}'
        data = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image], text=True))[0]
        assert data['Config']['Labels']['org.opencontainers.image.revision'] == args.sha
        path = args.output / (name + '.tar.gz')
        # CI creates these from the same image IDs that passed its runtime checks.
        assert path.is_file(), f'Missing image archive: {path.name}'
        with tarfile.open(path, 'r:gz') as archive:
            manifest = json.load(archive.extractfile('manifest.json'))
            assert len(manifest) == 1 and image in manifest[0]['RepoTags']
            config_digest = hashlib.sha256(archive.extractfile(manifest[0]['Config']).read()).hexdigest()
        result['artifacts'][name] = {'file': path.name, 'size': path.stat().st_size,
                                     'sha256': digest(path), 'image': image, 'image_id': data['Id'],
                                     'image_config_sha256': config_digest}
    path = args.output / 'runtime.tar.gz'
    root = Path(__file__).resolve().parents[1]
    with tarfile.open(path, 'w:gz') as archive:
        for relative in RUNTIME_FILES:
            source = root / relative
            assert source.is_file() and not source.is_symlink()
            archive.add(source, arcname=relative, recursive=False)
    result['artifacts']['runtime'] = {'file': path.name, 'size': path.stat().st_size, 'sha256': digest(path)}
    (args.output / 'release.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Packaged tested review release:', args.sha)


if __name__ == '__main__':
    main()
