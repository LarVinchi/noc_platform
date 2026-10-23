"""Loopback-only full-corpus demo. Uses reviewed extraction, never original uploads."""
from collections import Counter
import json
import os
from pathlib import Path
import re
import secrets
import threading
import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import Field
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .contracts import Query, SourceVersion
from .engine import QueryEngine
from .gemini import GeminiGenerator
from .snapshot import audit as audit_snapshot, load_review, source_record

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'preview_web'


class IndexCancelled(Exception):
    pass


class CorpusQuery(Query):
    # Production's public 50-version contract remains unchanged.
    allowed_versions: tuple[SourceVersion, ...] = Field(max_length=1000)


class CorpusRetriever:
    """One query embedding; permission-scoped batches merged by global distance."""
    def __init__(self, store, timing):
        self.store, self.timing = store, timing
        self.index_version = store.index_version

    def search(self, question, *, where, limit):
        keys = where['source_version_key']['$in']
        if not keys or len(keys) > 1000:
            return []
        vector = self.timing('query_embedding', lambda: self.store.embeddings.embed([question], query=True))
        def search_batches():
            ranked = []
            for offset in range(0, len(keys), 50):
                ranked.extend(self.store.ranked_search(vector, keys=keys[offset:offset+50], limit=limit))
            ranked.sort(key=lambda pair: (pair[0], pair[1].chunk_id))
            found, size, seen = [], 0, set()
            for _, chunk in ranked:
                if chunk.chunk_id in seen:
                    continue
                seen.add(chunk.chunk_id)
                if size + len(chunk.text) > 9000:
                    continue
                found.append(chunk)
                size += len(chunk.text)
                if len(found) >= min(limit, 6):
                    break
            return found
        return self.timing('semantic_search', search_batches)


class KeywordRetriever:
    """Local lexical retrieval only; never calls the embedding adapter."""
    index_version = 'demo-keyword-v2'

    def __init__(self, store, timing):
        self.store, self.timing = store, timing
        self.coverage = {}

    def search(self, question, *, where, limit):
        keys = where['source_version_key']['$in']
        if not keys or len(keys) > 1000:
            return []
        def search_batches():
            ranked, matching_keys = [], set()
            for offset in range(0, len(keys), 50):
                batch = keys[offset:offset+50]
                matching_keys.update(self.store.lexical_match_keys(question, keys=batch))
                ranked.extend(self.store.ranked_lexical_search(question, keys=batch, limit=limit, per_source_limit=1))
            ranked.sort(key=lambda pair: (-pair[0], pair[1].chunk_id))
            found, size, seen = [], 0, set()
            for _, chunk in ranked:
                if chunk.chunk_id in seen or size + len(chunk.text) > 9000:
                    continue
                seen.add(chunk.chunk_id)
                found.append(chunk)
                size += len(chunk.text)
                if len(found) >= min(limit, 6):
                    break
            self.coverage = {'matching_reports': len(matching_keys), 'retrieved_passages': len(found),
                             'retrieved_reports': len({c.source.document_id for c in found}),
                             'exhaustive': False,
                             'note': 'Top matching passages only. This is not a complete incident inventory.'}
            return found
        return self.timing('keyword_search', search_batches)


class TimedGenerator:
    def __init__(self, backend, timing):
        self.backend, self.model, self.timing = backend, backend.model, timing

    def answer(self, question, *, evidence):
        return self.timing('generation', lambda: self.backend.answer(question, evidence=evidence))


class CorpusController:
    def __init__(self, assessment, state, *, key='', configured_model='', store_factory=None, generator_factory=None):
        self.assessment, self.state = Path(assessment).resolve(strict=True), Path(state).resolve()
        if self.state == self.assessment or self.state.is_relative_to(self.assessment) or self.assessment.is_relative_to(self.state):
            raise ValueError('Keep preview index separate from source extraction')
        self._key = key
        self.configured_model = configured_model if re.fullmatch(r'gemini-[a-z0-9.-]{1,80}',configured_model) else ''
        self.store_factory, self.generator_factory = store_factory, generator_factory
        self.lock, self.query_slot = threading.RLock(), threading.Semaphore(1)
        self.stop = threading.Event()
        self.job = {'state': 'idle', 'completed': 0, 'total': 0, 'reused': 0}
        job_path = self.state/'job.json'
        if job_path.is_file() and job_path.stat().st_size < 20000:
            try:
                previous_job = json.loads(job_path.read_text(encoding='utf-8'))
                if isinstance(previous_job,dict) and isinstance(previous_job.get('completed'),int):
                    self.job.update(previous_job)
                    if self.job['state']=='indexing': self.job['state']='interrupted'
                    self.job.pop('provider_wait_until',None)
                    self.job['provider_wait_seconds']=0
            except (ValueError,OSError): pass
        self.query_phase = 'idle'
        self.store = None
        self._load()

    def _load(self):
        audit = audit_snapshot(self.assessment)
        evidence = load_review(self.assessment)
        lookup = {r['path']: r for r in evidence['records']}
        prepare = source_record
        self.audit = audit
        self.rows = []
        for row in audit['items']:
            metadata = dict(row)
            metadata['id'] = str(uuid4())  # Excluded formats have no source/version identity.
            if row['text_only_candidate']:
                source = prepare(lookup[row['path']])
                metadata.update(source=source['source'], id=source['source']['document_id'], evidence=source['chunks'])
            text = '\n'.join(c['text'] for c in lookup[row['path']]['chunks'])
            metadata['incident_dates'] = list(dict.fromkeys(re.findall(
                r'Incident Date(?:\s*\|\s*C\d+=|\s*[:=]|\s+)([^\n|]{1,80})', text, re.I)))[:3]
            self.rows.append(metadata)
        self.candidates = [r for r in self.rows if r['text_only_candidate']]
        self.expected = {r['source']['document_id']: r['source'] for r in self.candidates}
        from .incident_inventory import IncidentInventory
        self.inventory = IncidentInventory(self.rows, snapshot=self.audit['assessment_sha256'], files=len(self.rows))

    def _get_store(self):
        with self.lock:
            if self.store is None:
                self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
                if self.store_factory:
                    self.store = self.store_factory(self.state)
                else:
                    from .embeddings import GeminiEmbeddings
                    from .vector_store import VectorStore
                    def pause(seconds):
                        if self.stop.wait(seconds): raise IndexCancelled()
                    def retry(event):
                        with self.lock:
                            self.job['provider_wait_seconds'] = event['delay_seconds']
                            self.job['provider_wait_until'] = time.monotonic()+event['delay_seconds']
                    self.store = VectorStore(self.state/'corpus.sqlite3', GeminiEmbeddings(self._key, 'gemini-embedding-001', 768,
                                             max_retries=3,on_retry=retry,sleep=pause),
                                             chroma_path=self.state/'chroma')
            return self.store

    def _receipt(self):
        path = self.state/'corpus.json'
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding='utf-8'))
        return value

    def ready(self):
        receipt = self._receipt()
        return bool(receipt and receipt.get('complete') and receipt['assessment_sha256'] == self.audit['assessment_sha256']
                    and receipt['sources'] == self.expected)

    def available_sources(self):
        if not self._key and not self.store_factory and self.store is None:
            return []  # Metadata browsing still works when private credentials are absent.
        receipt = self._receipt()
        if not receipt or receipt.get('assessment_sha256') != self.audit['assessment_sha256'] or receipt.get('sources') != self.expected:
            return []
        store = self._get_store()
        # Exact current revisions only, including active vector fingerprint where applicable.
        # These checks are local registry reads, never embedding/provider requests.
        keys = store.ready_source_keys([SourceVersion.model_validate(row['source']) for row in self.candidates])
        return [row for row in self.candidates if SourceVersion.model_validate(row['source']).key in keys]

    def status(self):
        with self.lock:
            job = dict(self.job)
            available = self.available_sources()
            indexed = len(available)
            if 'provider_wait_until' in job:
                job['provider_wait_seconds'] = max(0,round(job.pop('provider_wait_until')-time.monotonic()))
            return {'files': len(self.rows), 'candidates': len(self.candidates),
                'deferred': len(self.rows)-len(self.candidates), 'chunks': sum(r['chunks'] for r in self.candidates),
                'configured': bool(self._key or self.store_factory), 'configured_model': self.configured_model,
                'models': list(dict.fromkeys(['gemini-3.5-flash-lite', self.configured_model] if self.configured_model else ['gemini-3.5-flash-lite'])),
                'index_ready': self.ready(), 'keyword_ready': indexed > 0, 'indexed_sources': indexed,
                'indexed_ids': [row['id'] for row in available],
                'job': job, 'query_phase': self.query_phase,
                'langsmith_content_tracing': False, 'production_approved': False}

    def sources(self):
        return [{k: v for k, v in row.items() if k not in ('evidence',)} for row in self.rows]

    def _save(self, value):
        temporary = self.state/'corpus.tmp'
        with temporary.open('w', encoding='utf-8') as stream:
            os.chmod(temporary, 0o600)
            json.dump(value, stream, ensure_ascii=False)
        temporary.replace(self.state/'corpus.json')

    def _save_job(self):
        with self.lock:
            value = {k:v for k,v in self.job.items() if k!='provider_wait_until'}
        temporary = self.state/'job.tmp'
        try:
            with temporary.open('w',encoding='utf-8') as stream:
                os.chmod(temporary,0o600)
                json.dump(value,stream)
            temporary.replace(self.state/'job.json')
        except OSError:
            pass  # The authoritative source generations still determine safe resume.

    def start_index(self):
        with self.lock:
            if self.job['state'] == 'indexing' or self.query_phase != 'idle':
                raise HTTPException(409, 'An index or query job is already running')
            if not self._key and not self.store_factory:
                raise HTTPException(409, 'Configure the private Gemini key before indexing')
            self.stop.clear()
            self.job = {'state': 'indexing', 'completed': 0, 'total': len(self.candidates), 'reused': 0}
            self.thread = threading.Thread(target=self._index, daemon=True)
            self.thread.start()

    def _index(self):
        try:
            store = self._get_store()
            previous = self._receipt()
            receipt = {'assessment_sha256': self.audit['assessment_sha256'], 'sources': self.expected,
                       'complete': False, 'production_approved': False}
            self._save(receipt)
            self._save_job()
            # Changed/removed versions are revoked before any new query is allowed.
            for source in (previous or {}).get('sources', {}).values():
                if source not in self.expected.values():
                    store.revoke(SourceVersion.model_validate(source))
            for row in self.candidates:
                if self.stop.is_set():
                    with self.lock:
                        self.job['state'] = 'cancelled'
                    self._save_job()
                    return
                source = SourceVersion.model_validate(row['source'])
                if store.approved_and_ready(source):
                    with self.lock:
                        self.job['reused'] += 1
                else:
                    store.publish_chunks(source, row['evidence'])
                with self.lock:
                    self.job['completed'] += 1
                self._save_job()
            receipt['complete'] = True
            self._save(receipt)
            with self.lock:
                self.job['state'] = 'complete'
            self._save_job()
        except Exception as error:
            with self.lock:
                self.job.update(state='cancelled' if isinstance(error,IndexCancelled) else 'failed',
                                category=type(error).__name__, http_status=getattr(error, 'code', None),
                                quota_kind=getattr(error,'quota_kind',None),
                                retry_after_seconds=getattr(error,'retry_after_seconds',None))
            self._save_job()

    def query(self, question, selected, model, retrieval_mode='semantic'):
        if retrieval_mode not in ('semantic', 'keyword'):
            raise HTTPException(422, 'Choose keyword or semantic retrieval')
        if model not in self.status()['models']:
            raise HTTPException(422, 'Choose an available preview model')
        if not question.strip() or len(question) > 4000:
            raise HTTPException(422, 'Enter a question up to 4000 characters')
        if not self.query_slot.acquire(blocking=False):
            raise HTTPException(409, 'Another question is still running')
        started = time.monotonic()
        timings, usage, retries = {}, {}, []
        def timed(stage, operation):
            with self.lock:
                self.query_phase = stage
            before = time.monotonic()
            value = operation()
            timings[stage] = round(time.monotonic()-before, 3)
            return value
        try:
            with self.lock:
                if self.job['state'] == 'indexing' or (retrieval_mode == 'semantic' and not self.ready()):
                    raise HTTPException(409, 'Complete or resume indexing before asking')
                self.query_phase = 'checking_scope'
            available = self.available_sources()
            if not available:
                raise HTTPException(409, 'No current indexed sources are available to search')
            allowed = {r['id']: r for r in available}
            if selected is not None and (not selected or len(selected) > 1000 or any(i not in allowed for i in selected)):
                raise HTTPException(422, 'Selected scope contains an unavailable source')
            scoped = [allowed[i] for i in dict.fromkeys(selected)] if selected is not None else available
            store = self._get_store()
            options = {'max_retries': 1, 'max_output_tokens': 1024,
                       'thinking_level': 'MINIMAL' if model == 'gemini-3.5-flash-lite' else 'LOW',
                       'on_usage': usage.update, 'on_retry': retries.append}
            backend = self.generator_factory(model, options) if self.generator_factory else GeminiGenerator(self._key, model, **options)
            retriever = KeywordRetriever(store, timed) if retrieval_mode == 'keyword' else CorpusRetriever(store, timed)
            result = QueryEngine(store, retriever, TimedGenerator(backend, timed)).query(
                CorpusQuery(request_id=uuid4(), question=question, allowed_versions=tuple(SourceVersion.model_validate(r['source']) for r in scoped)))
            response = result.model_dump(mode='json')
            lookup = {r['source']['version_id']: r for r in scoped}
            for citation in response['citations']:
                row = lookup[citation['source']['version_id']]
                citation.update(filename=Path(row['path']).name, path=row['path'], incident_dates=row['incident_dates'],
                                report_variants=row['incident_variant_group'], review_flags=row['review_flags'])
                with store.connect() as db:
                    evidence = db.execute('SELECT content FROM chunks WHERE id=? AND source_key=?',
                        (citation['chunk_id'], SourceVersion.model_validate(row['source']).key)).fetchone()
                citation['full_evidence'] = evidence[0] if evidence else citation['excerpt']
            return {'result': response, 'timings': dict(timings, total=round(time.monotonic()-started, 3)),
                    'usage': usage, 'retry_count': len(retries), 'searched_sources': len(scoped),
                    'retrieval_mode': retrieval_mode, 'indexed_sources': len(available),
                    'retrieval_coverage': getattr(retriever, 'coverage', {'exhaustive':False,
                        'note':'Top matching passages only. This is not a complete incident inventory.'}),
                    'candidate_sources': len(self.candidates), 'partial_collection': len(available) < len(self.candidates),
                    'scope': 'Accepted demo text and tables. Images and Word notes are not verified.',
                    'production_approved': False}
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(502, {'stage': self.query_phase, 'category': type(error).__name__,
                                      'http_status': getattr(error, 'code', None), 'answer_released': False}) from None
        finally:
            with self.lock:
                self.query_phase = 'idle'
            self.query_slot.release()


def create_preview(controller):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost'])
    token = secrets.token_urlsafe(40)

    @app.middleware('http')
    async def guard(request: Request, call_next):
        if request.url.path.startswith('/api/'):
            cookie = request.cookies.get('rag_preview', '')
            if not cookie.isascii() or not secrets.compare_digest(cookie, token):
                return JSONResponse({'detail':'Open the local preview page first'}, status_code=401)
            if request.method != 'GET' and request.headers.get('origin') != str(request.base_url).rstrip('/'):
                return JSONResponse({'detail':'Same-origin preview request required'}, status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        return response

    @app.get('/')
    def page():
        response = FileResponse(ASSETS/'index.html')
        response.set_cookie('rag_preview', token, httponly=True, samesite='strict')
        return response

    @app.get('/assets/{name}')
    def asset(name: str):
        if name not in ('app.js', 'style.css'):
            raise HTTPException(404)
        return FileResponse(ASSETS/name)

    @app.get('/api/status')
    def status():
        return controller.status()

    @app.get('/api/sources')
    def sources():
        return {'sources': controller.sources()}

    @app.get('/api/incidents')
    def incidents(customer: str='', offset: int=0, limit: int=25):
        try:
            return controller.inventory.search(customer, offset, limit)
        except ValueError:
            raise HTTPException(422, 'Invalid inventory filter or page') from None

    @app.get('/api/incidents/export')
    def incident_export(customer: str=''):
        try:
            return controller.inventory.export(customer)
        except ValueError:
            raise HTTPException(422, 'Invalid inventory filter') from None

    @app.get('/api/incidents/sources/{identifier}')
    def incident_source(identifier: str):
        try:
            return controller.inventory.source(identifier)
        except KeyError:
            raise HTTPException(404, 'Source is not in this accepted snapshot') from None

    @app.post('/api/index')
    def index():
        controller.start_index()
        return {'started': True}

    @app.post('/api/index/cancel')
    def cancel():
        controller.stop.set()
        return {'stopping_after_current_document': True}

    @app.post('/api/query')
    async def query(request: Request):
        raw = await request.body()
        if len(raw) > 60000:
            raise HTTPException(413)
        try:
            value = json.loads(raw)
            question = value['question']
            selected = value.get('source_ids')
            model = value.get('model', 'gemini-3.5-flash-lite')
            retrieval_mode = value.get('retrieval_mode', 'semantic')
            if not isinstance(question, str) or not isinstance(model, str) or not isinstance(retrieval_mode, str) or (selected is not None and
                    (not isinstance(selected, list) or any(not isinstance(i, str) for i in selected))):
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise HTTPException(422, 'Invalid preview question') from None
        return await run_in_threadpool(controller.query, question, selected, model, retrieval_mode)

    return app
