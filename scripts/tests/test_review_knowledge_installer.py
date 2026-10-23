import importlib.util
import json
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('review_installer',Path(__file__).parents[1]/'install-review-knowledge.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)


def test_installer_prepares_private_readonly_input_and_reuses_token_without_printing_it(tmp_path,capsys):
    root=tmp_path/'app';root.mkdir()
    assessment=tmp_path/'extraction';assessment.mkdir();(assessment/'extractions').mkdir();(assessment/'assessment.json').write_text('{}')
    settings=tmp_path/'provider.env';settings.write_text('GEMINI_API_KEY="PRIVATE_SYNTHETIC_KEY"\nRAG_GEMINI_MODEL=gemini-3.8-flash\nUNRELATED=ignored\n')
    state=installer.prepare(root,assessment,settings,'sha256:'+'a'*64,1000,1000)
    config=json.loads((state/'compose.json').read_text())
    service=config['services']['knowledge-review']
    assert service['user']=='1000:1000'
    assert str(assessment)+':/assessment:ro' in service['volumes']
    assert 'ports' not in service and 'PRIVATE_SYNTHETIC_KEY' not in json.dumps(config)
    token=(state/'worker.token').read_text()
    installer.prepare(root,assessment,settings,'sha256:'+'b'*64,1000,1000)
    assert (state/'worker.token').read_text()==token
    assert 'UNRELATED' not in (state/'worker.env').read_text()
    assert not (state/'enabled').exists()
    assert capsys.readouterr().out==''


def test_installer_rejects_wrong_input_invalid_image_or_multiline_credential(tmp_path):
    root=tmp_path/'app';root.mkdir()
    with pytest.raises(ValueError):installer.prepare(root,tmp_path,None,'mutable:latest',1000,1000)
    with pytest.raises(ValueError):installer.prepare(root,tmp_path,None,'sha256:'+'a'*64,1000,1000)
    provider=tmp_path/'provider.env';provider.write_text('GEMINI_API_KEY=invalid key with spaces\n')
    with pytest.raises(ValueError):installer.provider_settings(provider)


@pytest.mark.parametrize('key', ['synthetic.key_123456789', 'synthetic/key+123456789='])
def test_provider_settings_preserves_credential_punctuation(tmp_path,key):
    provider=tmp_path/'provider.env'
    provider.write_text('GEMINI_API_KEY='+key+'\n')
    assert installer.provider_settings(provider)[0]==key


@pytest.mark.parametrize('suffix', ['${OTHER}', ' # comment', '\\escape', '\ttext', '\x00'])
def test_provider_settings_rejects_env_interpolation_and_control_characters(tmp_path,suffix):
    provider=tmp_path/'provider.env'
    provider.write_text('GEMINI_API_KEY=synthetic_key_123'+suffix+'\n')
    with pytest.raises(ValueError):installer.provider_settings(provider)


def test_monitoring_refresh_preserves_enabled_knowledge_overlay(tmp_path):
    spec=importlib.util.spec_from_file_location('monitoring_installer',Path(__file__).parents[1]/'install-host-monitoring.py')
    monitoring=importlib.util.module_from_spec(spec);spec.loader.exec_module(monitoring)
    state=tmp_path/'.review-access/monitoring'
    state.mkdir(parents=True)
    knowledge=tmp_path/'.review-access/knowledge'
    knowledge.mkdir()
    (knowledge/'compose.json').write_text('{}')
    runtime=tmp_path/'runtime'
    assert str(knowledge/'compose.json') not in monitoring.compose_command(['docker'],tmp_path,runtime,state)
    (knowledge/'enabled').write_text('enabled')
    command=monitoring.compose_command(['docker'],tmp_path,runtime,state)
    assert str(knowledge/'compose.json') in command and 'knowledge-review' in command
    assert str(state/'compose.json') in command
    assert command[-1]==str(runtime/'images.json')
