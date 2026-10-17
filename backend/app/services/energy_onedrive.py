"""Bounded, read-only Microsoft Graph client. Never expose tokens or download URLs."""
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID
from app.services.energy_import import MAX_WORKBOOK_BYTES


class SyncFailure(Exception):
    def __init__(self, code, message, retry_after=0):
        super().__init__(message)
        self.code, self.message, self.retry_after = code, message, retry_after


def configuration_errors(config):
    errors = []
    if config.ENVIRONMENT != 'production' or config.AUTH_MODE != 'entra':
        errors.append('company_sign_in_required')
    for field in ['ENTRA_TENANT_ID', 'ENTRA_API_CLIENT_ID', 'ENTRA_SPA_CLIENT_ID',
                  'ENERGY_GRAPH_TENANT_ID', 'ENERGY_GRAPH_CLIENT_ID']:
        try:
            UUID(getattr(config, field))
        except (ValueError, TypeError, AttributeError):
            errors.append(field.lower() + '_required')
    for field in ['ENERGY_GRAPH_DRIVE_ID', 'ENERGY_GRAPH_ITEM_ID']:
        value = getattr(config, field)
        if not value or len(value) > 512 or value in {'.', '..'} or any(ord(c) < 32 for c in value):
            errors.append(field.lower() + '_required')
    return errors


def source_key(config):
    return hashlib.sha256(json.dumps([config.ENERGY_GRAPH_TENANT_ID,
                                     config.ENERGY_GRAPH_DRIVE_ID, config.ENERGY_GRAPH_ITEM_ID]).encode()).hexdigest()


def retry_seconds(value):
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        try:
            return max(1, int((parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()))
        except (TypeError, ValueError, OverflowError):
            return 0


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass
class WorkbookVersion:
    etag: str
    name: str
    modified_at: datetime
    content: bytes


class GraphWorkbookClient:
    def __init__(self, config, secret, opener=None):
        self.tenant = str(UUID(config.ENERGY_GRAPH_TENANT_ID))
        self.client_id = str(UUID(config.ENERGY_GRAPH_CLIENT_ID))
        self.secret = secret
        self.item_id = config.ENERGY_GRAPH_ITEM_ID
        self.item_url = ('https://graph.microsoft.com/v1.0/drives/' + quote(config.ENERGY_GRAPH_DRIVE_ID, safe='')
                         + '/items/' + quote(self.item_id, safe=''))
        self.opener = opener or build_opener(NoRedirect())
        self._token, self._expires = None, 0

    def _request(self, url, headers=None, data=None, limit=128 * 1024):
        request = Request(url, data=data, headers={'User-Agent': 'AFL-NOC-EnergySync/1.0', **(headers or {})})
        try:
            response = self.opener.open(request, timeout=20)
        except HTTPError as response:
            # A controlled redirect must not carry Graph Authorization downstream.
            status, response_headers = response.code, response.headers
            response.close()
            return status, response_headers, b''
        except (URLError, TimeoutError, OSError):
            raise SyncFailure('network_unavailable', 'Microsoft connection failed; the last valid report is retained') from None
        try:
            with response:
                body = bytearray()
                deadline = time.monotonic() + 20
                while True:
                    block = response.read(min(65536, limit + 1 - len(body)))
                    body.extend(block)
                    if len(body) > limit:
                        raise SyncFailure('response_too_large', 'Microsoft response exceeds the configured size limit')
                    if time.monotonic() > deadline:
                        raise SyncFailure('network_timeout', 'Microsoft download timed out')
                    if not block:
                        break
                return response.status, response.headers, bytes(body)
        except (TimeoutError, OSError):
            raise SyncFailure('network_unavailable', 'Microsoft response could not be read') from None

    @staticmethod
    def _check(status, headers, token=False):
        if status in (429, 503):
            raise SyncFailure('microsoft_throttled', 'Microsoft requested a retry; the last valid report is retained',
                              retry_seconds(headers.get('Retry-After')))
        if status in (400, 401) and token:
            raise SyncFailure('credential_rejected', 'Microsoft rejected the configured application credential')
        if status in (401, 403):
            raise SyncFailure('source_access_denied', 'Read permission to the configured workbook was denied')
        if status == 404:
            raise SyncFailure('source_not_found', 'The configured workbook was not found')
        if status != 200:
            raise SyncFailure('microsoft_unavailable', 'Microsoft did not return a usable response')

    def _access_token(self):
        if self._token and time.monotonic() < self._expires:
            return self._token
        status, headers, body = self._request(
            f'https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/token',
            {'Content-Type': 'application/x-www-form-urlencoded'},
            urlencode({'client_id': self.client_id, 'client_secret': self.secret,
                       'scope': 'https://graph.microsoft.com/.default', 'grant_type': 'client_credentials'}).encode())
        self._check(status, headers, token=True)
        try:
            value = json.loads(body)
            token, lifetime = value['access_token'], int(value['expires_in'])
            if not isinstance(token, str) or not token or lifetime <= 0:
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise SyncFailure('invalid_token_response', 'Microsoft returned an invalid token response') from None
        self._token, self._expires = token, time.monotonic() + max(0, lifetime - 60)
        return token

    def _graph(self, url, extra_headers=None, limit=128 * 1024):
        for attempt in range(2):
            result = self._request(url, {'Authorization': 'Bearer ' + self._access_token(), **(extra_headers or {})}, limit=limit)
            if result[0] != 401 or attempt:
                return result
            self._token = None

    def _metadata(self, etag=None):
        query = urlencode({'$select': 'id,name,size,eTag,lastModifiedDateTime,file,malware'})
        status, headers, body = self._graph(self.item_url + '?' + query, {'If-None-Match': etag} if etag else {})
        if status == 304 and etag:
            return None
        self._check(status, headers)
        try:
            value = json.loads(body)
            modified = datetime.fromisoformat(value['lastModifiedDateTime'].replace('Z', '+00:00'))
            tag, name, size = value['eTag'], value['name'], value['size']
            if (value['id'] != self.item_id or not isinstance(value.get('file'), dict) or value.get('malware') is not None
                    or not isinstance(tag, str) or not 1 <= len(tag) <= 1024 or any(ord(c) < 32 for c in tag)
                    or not isinstance(name, str) or not name.lower().endswith('.xlsx') or modified.tzinfo is None
                    or not isinstance(size, int) or not 0 < size <= MAX_WORKBOOK_BYTES):
                raise ValueError()
        except (KeyError, TypeError, ValueError, AttributeError):
            raise SyncFailure('invalid_source', 'Source must be a readable XLSX file within the workbook size limit') from None
        return {'etag': tag, 'name': name.replace('\\', '/').split('/')[-1][:200], 'modified': modified}

    @staticmethod
    def _download_url(url):
        try:
            parts = urlsplit(url)
            host = (parts.hostname or '').lower()
            valid = (parts.scheme == 'https' and parts.port in (None, 443) and not parts.username and not parts.password
                     and any(host.endswith(suffix) for suffix in ('.sharepoint.com', '.sharepointonline.com', '.1drv.com')))
        except ValueError:
            valid = False
        if not valid:
            raise SyncFailure('invalid_download_location', 'Microsoft returned an unsupported download location')
        return url

    def fetch(self, previous_etag=None):
        before = self._metadata(previous_etag)
        if before is None:
            return None
        status, headers, content = self._graph(self.item_url + '/content', limit=MAX_WORKBOOK_BYTES)
        for _ in range(3):
            if status not in (301, 302, 303, 307, 308):
                break
            url = self._download_url(headers.get('Location', ''))
            # Presigned URLs must never receive the bearer token or client secret.
            status, headers, content = self._request(url, limit=MAX_WORKBOOK_BYTES)
        self._check(status, headers)
        after = self._metadata()
        if before['etag'] != after['etag']:
            raise SyncFailure('source_changed_during_download', 'Workbook changed during download; retrying the saved version', 15)
        return WorkbookVersion(before['etag'], before['name'], before['modified'], content)
