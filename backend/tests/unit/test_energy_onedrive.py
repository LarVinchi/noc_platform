import datetime as dt
from io import BytesIO
import json
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import parse_qs
from uuid import uuid4
import pytest
from app.services.energy_onedrive import GraphWorkbookClient, SyncFailure, configuration_errors, retry_seconds
from app.services.energy_import import MAX_WORKBOOK_BYTES


@pytest.fixture
def config():
    return SimpleNamespace(ENVIRONMENT='production', AUTH_MODE='entra',
                           **{name: str(uuid4()) for name in ['ENTRA_TENANT_ID', 'ENTRA_API_CLIENT_ID',
                               'ENTRA_SPA_CLIENT_ID', 'ENERGY_GRAPH_TENANT_ID', 'ENERGY_GRAPH_CLIENT_ID']},
                           ENERGY_GRAPH_DRIVE_ID='b!test-drive', ENERGY_GRAPH_ITEM_ID='test-item')


class Reply(BytesIO):
    def __init__(self, body, status=200, headers=None):
        super().__init__(json.dumps(body).encode() if isinstance(body, dict) else body)
        self.status, self.headers = status, headers or {}


class Transport:
    def __init__(self, *replies):
        self.replies, self.requests = list(replies), []

    def open(self, request, timeout):
        self.requests.append(request)
        assert timeout == 20
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def token(value='test-token'):
    return Reply({'access_token': value, 'expires_in': 3600})


def metadata(**changes):
    return Reply({'id': 'test-item', 'name': 'tracker.xlsx', 'size': 100, 'eTag': 'version-1',
                  'lastModifiedDateTime': '2026-10-17T12:00:00Z', 'file': {}, **changes})


def failure(status, headers=None):
    return HTTPError('https://graph.microsoft.com/source?secret=must-not-leak', status,
                     'secret response must not leak', headers or {}, BytesIO(b'secret body'))


def test_download_redirect_does_not_forward_credentials(config):
    transport = Transport(token(), metadata(), failure(302, {'Location': 'https://ankersupport.sharepoint.com/download?temporary=secret'}),
                          Reply(b'xlsx bytes'), metadata())
    client = GraphWorkbookClient(config, 'app-secret', transport)
    result = client.fetch()
    assert result.content == b'xlsx bytes' and result.etag == 'version-1'
    assert result.modified_at == dt.datetime(2026, 10, 17, 12, tzinfo=dt.timezone.utc)
    download = transport.requests[3]
    assert download.get_header('Authorization') is None and download.data is None
    assert transport.requests[1].get_header('Authorization') == 'Bearer test-token'
    body = parse_qs(transport.requests[0].data.decode())
    assert body['grant_type'] == ['client_credentials']
    assert body['scope'] == ['https://graph.microsoft.com/.default']


def test_unchanged_version_uses_conditional_metadata_only_and_cached_token(config):
    transport = Transport(token(), failure(304), failure(304))
    client = GraphWorkbookClient(config, 'app-secret', transport)
    assert client.fetch('etag') is None
    assert client.fetch('etag') is None
    assert len(transport.requests) == 3
    assert transport.requests[1].get_header('If-none-match') == 'etag'


@pytest.mark.parametrize('url', ['http://ankersupport.sharepoint.com/file', 'https://127.0.0.1/file',
                               'https://sharepoint.com.evil.example/file', 'https://evil.example/file',
                               'https://user:pass@ankersupport.sharepoint.com/file', 'https://ankersupport.sharepoint.com:444/file'])
def test_rejects_untrusted_redirect_without_following_it(config, url):
    transport = Transport(token(), metadata(), failure(302, {'Location': url}))
    with pytest.raises(SyncFailure) as caught:
        GraphWorkbookClient(config, 'app-secret', transport).fetch()
    assert caught.value.code == 'invalid_download_location'
    assert len(transport.requests) == 3


@pytest.mark.parametrize('status,code', [(429, 'microsoft_throttled'), (503, 'microsoft_throttled'),
                                      (403, 'source_access_denied'), (404, 'source_not_found'),
                                      (500, 'microsoft_unavailable')])
def test_http_failure_is_sanitized_and_honors_retry_after(config, status, code):
    transport = Transport(token(), failure(status, {'Retry-After': '180'}))
    with pytest.raises(SyncFailure) as caught:
        GraphWorkbookClient(config, 'app-secret', transport).fetch()
    assert caught.value.code == code
    assert 'secret' not in str(caught.value)
    if status in (429, 503):
        assert caught.value.retry_after == 180


def test_expired_token_is_refreshed_once(config):
    transport = Transport(token('old'), failure(401), token('new'), metadata(), Reply(b'xlsx'), metadata())
    assert GraphWorkbookClient(config, 'app-secret', transport).fetch().content == b'xlsx'
    assert transport.requests[3].get_header('Authorization') == 'Bearer new'


def test_workbook_changed_mid_download_is_not_published(config):
    transport = Transport(token(), metadata(), Reply(b'xlsx'), metadata(eTag='version-2'))
    with pytest.raises(SyncFailure) as caught:
        GraphWorkbookClient(config, 'app-secret', transport).fetch()
    assert caught.value.code == 'source_changed_during_download'


def test_empty_malware_facet_is_accepted(config):
    transport = Transport(token(), metadata(malware=None), Reply(b'xlsx'), metadata(malware=None))
    assert GraphWorkbookClient(config, 'app-secret', transport).fetch().content == b'xlsx'


@pytest.mark.parametrize('changes', [{'name': 'not-a-workbook.csv'}, {'malware': {}},
                                    {'size': MAX_WORKBOOK_BYTES + 1}, {'file': None}, {'id': 'different-item'}])
def test_invalid_source_is_rejected_before_content_download(config, changes):
    transport = Transport(token(), metadata(**changes))
    with pytest.raises(SyncFailure) as caught:
        GraphWorkbookClient(config, 'app-secret', transport).fetch()
    assert caught.value.code == 'invalid_source' and len(transport.requests) == 2


def test_streaming_download_is_bounded(config):
    transport = Transport(token(), metadata(), Reply(b'x' * (MAX_WORKBOOK_BYTES + 1)))
    with pytest.raises(SyncFailure) as caught:
        GraphWorkbookClient(config, 'app-secret', transport).fetch()
    assert caught.value.code == 'response_too_large'


def test_live_sync_requires_company_identity_and_safe_configuration(config):
    assert configuration_errors(config) == []
    config.ENVIRONMENT, config.AUTH_MODE = 'development', 'preview'
    assert 'company_sign_in_required' in configuration_errors(config)
    config.ENERGY_GRAPH_TENANT_ID = 'other-tenant/path'
    assert 'energy_graph_tenant_id_required' in configuration_errors(config)
    assert retry_seconds('120') == 120 and retry_seconds('not-a-date') == 0
