"""Bounded private-worker client. No provider credentials ever reach browsers."""
import json
import urllib.request
from urllib.parse import urlsplit
from uuid import UUID
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.core.config import settings


class Source(BaseModel):
    model_config = ConfigDict(extra='forbid')
    document_id: UUID
    version_id: UUID
    sha256: str = Field(pattern='^[0-9a-f]{64}$')


class Citation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    chunk_id: str = Field(min_length=1,max_length=128)
    source: Source
    locator: str = Field(min_length=1,max_length=300)
    excerpt: str = Field(min_length=1,max_length=600)


class WorkerAnswer(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    status: Literal['answered','insufficient_evidence']
    answer: str = Field(min_length=1,max_length=12000)
    citations: list[Citation] = Field(max_length=8)
    model: str | None = Field(default=None,max_length=100)
    index_version: str = Field(default='unspecified',max_length=100)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def configured():
    url = urlsplit(settings.KNOWLEDGE_SERVICE_URL)
    token = settings.KNOWLEDGE_SERVICE_TOKEN.get_secret_value()
    return bool(settings.KNOWLEDGE_ENABLED and url.scheme in ('http','https') and url.hostname
                and not url.username and not url.password and not url.query and not url.fragment
                and 32 <= len(token) <= 512 and token.isascii() and not any(c.isspace() for c in token))


def request(path, payload=None):
    if not configured():
        raise RuntimeError('Knowledge service is not configured')
    req = urllib.request.Request(settings.KNOWLEDGE_SERVICE_URL.rstrip('/')+path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Authorization': 'Bearer '+settings.KNOWLEDGE_SERVICE_TOKEN.get_secret_value(),
                 'Content-Type': 'application/json'})
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=5 if path.startswith('/health/') else 40) as response:
        data = response.read(131073)
    if len(data) > 131072:
        raise ValueError('Worker response exceeds limits')
    return json.loads(data)


def validate_answer(payload, request_id, sources):
    value = WorkerAnswer.model_validate(payload)
    allowed = {(s['document_id'],s['version_id'],s['sha256']) for s in sources}
    if value.request_id != request_id:
        raise ValueError('Request identity mismatch')
    if value.status == 'answered' and not value.citations:
        raise ValueError('Missing evidence')
    if value.status == 'insufficient_evidence' and value.citations:
        raise ValueError('Unexpected evidence')
    if len({c.chunk_id for c in value.citations}) != len(value.citations):
        raise ValueError('Duplicate citations')
    for c in value.citations:
        if (str(c.source.document_id),str(c.source.version_id),c.source.sha256) not in allowed:
            raise ValueError('Out of scope citation')
    return value
