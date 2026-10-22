import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('ftth_runner', Path(__file__).parents[1]/'run-ftth-weekly-reports.py')
runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)


def test_runner_dry_run_and_secret_values_do_not_enter_arguments(tmp_path):
    root = tmp_path; state = root/'.review-access/cd'; state.mkdir(parents=True)
    (state/'current.json').write_text(json.dumps({'sha':'synthetic-sha'}))
    calls = []
    def execute(args, **kw):
        calls.append((args, kw))
        return SimpleNamespace(stdout=json.dumps({'org.opencontainers.image.revision':'synthetic-sha',
            'com.docker.compose.project':'noc-review','com.docker.compose.service':'api'}))
    runner.command(root, {'FTTH_SMTP_PASSWORD':'synthetic-secret'}, 'desktop-linux', False, execute)
    args, options = calls[-1]
    assert '--send' not in args and 'synthetic-secret' not in ' '.join(args)
    assert options['env']['FTTH_SMTP_PASSWORD'] == 'synthetic-secret'


def test_runner_blocks_mismatched_release(tmp_path):
    import pytest
    state=tmp_path/'.review-access/cd';state.mkdir(parents=True)
    (state/'current.json').write_text('{"sha":"expected"}')
    def execute(args, **kw):
        return SimpleNamespace(stdout='{}')
    with pytest.raises(ValueError):
        runner.command(tmp_path, {}, 'desktop-linux', True, execute)
