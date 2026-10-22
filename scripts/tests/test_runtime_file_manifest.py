import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('release_packaging',ROOT/'scripts/package-review-release.py')
packaging=importlib.util.module_from_spec(spec);spec.loader.exec_module(packaging)


def test_optional_ftth_mail_setup_is_available_in_the_installed_runtime():
    expected={'scripts/run-ftth-weekly-reports.py','docs/afl-ftth-workspace.md',
        'deploy/systemd/noc-ftth-weekly-report.service','deploy/systemd/noc-ftth-weekly-report.timer'}
    assert expected.issubset(set(packaging.RUNTIME_FILES))
    assert len(set(packaging.RUNTIME_FILES))==len(packaging.RUNTIME_FILES)
    for name in packaging.RUNTIME_FILES:
        assert (ROOT/name).is_file() and not (ROOT/name).is_symlink()
        assert not any(part.startswith('.env') or part in {'.qa','.review-access','node_modules'} for part in Path(name).parts)
