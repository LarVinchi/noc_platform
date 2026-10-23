"""Explicit Gemini text embeddings, bounded batches and no credential in URLs."""
import json
import math
import re
import threading
import urllib.request
from urllib.error import HTTPError
import time


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class GeminiEmbeddings:
    def __init__(self, key, model, dimensions=768, *, opener=None, max_retries=0, on_retry=None, sleep=time.sleep):
        if model != 'gemini-embedding-001':
            raise ValueError('This adapter supports the explicitly configured gemini-embedding-001 text model')
        if dimensions not in (768, 1536, 3072):
            raise ValueError('Unsupported embedding dimensions')
        if type(max_retries) is not int or not 0 <= max_retries <= 3:
            raise ValueError('Embedding retries must be between zero and three')
        if not key or not key.isascii() or re.search(r'\s', key):
            raise ValueError('Configure a private embedding credential')
        self.model, self.dimensions, self._key = model, dimensions, key
        self._open = opener or urllib.request.build_opener(NoRedirect()).open
        self._slots = threading.BoundedSemaphore(2)
        self.max_retries, self.on_retry, self._sleep = max_retries, on_retry, sleep

    def request(self, request, *, query):
        attempts = 0 if query else self.max_retries
        for attempt in range(attempts + 1):
            try:
                with self._open(request, timeout=30) as response:
                    return response.read(4_000_001)
            except HTTPError as error:
                if error.code not in (429,503) or attempt >= attempts:
                    raise
                # Parse bounded provider retry hints; never log the response body or quota identifiers.
                delay = 60 if error.code == 429 else 2 ** attempt
                raw = error.read(65537)
                hints = []
                daily = False
                if len(raw) <= 65536:
                    try:
                        details = json.loads(raw).get('error', {}).get('details', [])
                        for detail in details:
                            if isinstance(detail.get('retryDelay'), str):
                                value = re.fullmatch(r'(\d+(?:\.\d+)?)s', detail['retryDelay'])
                                if value: hints.append(float(value[1]))
                            for violation in detail.get('violations', []):
                                identifier = str(violation.get('quotaId','')).lower()
                                daily = daily or 'perday' in identifier or 'per_day' in identifier
                    except (ValueError,TypeError,AttributeError): pass
                header = error.headers.get('Retry-After') if error.headers else None
                if header and re.fullmatch(r'\d+', header): hints.append(float(header))
                if hints: delay = max(hints) + 1
                error.quota_kind = 'daily' if daily else 'rate_or_availability'
                error.retry_after_seconds = delay
                if daily or delay > 90:
                    raise
                error.close()
                if self.on_retry:
                    self.on_retry({'http_status':error.code, 'delay_seconds':delay,
                                   'next_attempt':attempt+2,'max_attempts':attempts+1})
                self._sleep(delay)

    def embed(self, texts, *, query=False):
        if not 1 <= len(texts) <= 100 or sum(len(t) for t in texts) > 280000:
            raise ValueError('Embedding batch exceeds limits')
        if any(not t.strip() or len(t) > 4000 for t in texts):
            raise ValueError('Embedding input exceeds limits')
        if query and len(texts) != 1:
            raise ValueError('Only one query per request')
        if not self._slots.acquire(blocking=False):
            raise RuntimeError('Embedding worker busy')
        try:
            body = {'requests': [{'model': 'models/'+self.model, 'content': {'parts': [{'text': t}]},
                'taskType': 'RETRIEVAL_QUERY' if query else 'RETRIEVAL_DOCUMENT',
                'outputDimensionality': self.dimensions} for t in texts]}
            request = urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models/'+self.model+':batchEmbedContents',
                data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'x-goog-api-key': self._key})
            raw = self.request(request, query=query)
            if len(raw) > 4_000_000:
                raise ValueError('Embedding response exceeds limits')
            values = [item['values'] for item in json.loads(raw)['embeddings']]
            if len(values) != len(texts):
                raise ValueError('Embedding count mismatch')
            normalized = []
            for vector in values:
                if len(vector) != self.dimensions or any(type(v) not in (int, float) or not math.isfinite(v) for v in vector):
                    raise ValueError('Invalid embedding vector')
                norm = math.sqrt(sum(v*v for v in vector))
                if not math.isfinite(norm) or norm <= 0:
                    raise ValueError('Invalid embedding norm')
                normalized.append([v/norm for v in vector])
            return normalized
        finally:
            self._slots.release()
