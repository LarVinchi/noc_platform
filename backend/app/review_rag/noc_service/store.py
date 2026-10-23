"""Small durable lexical index; approved scope is applied before ranking."""
import hashlib
import re
import sqlite3
import os
import shutil
from contextlib import contextmanager
from pathlib import Path

from .contracts import Chunk, Contract, SourceVersion
from pydantic import Field, model_validator
from .extraction import extract


def keyword_terms(text):
    """Normalize the documented customer alias and simple plural query terms."""
    words = re.findall(r'\w{3,}', text.casefold())
    return {'mtn' if word == 'mtnn' else word[:-1] if len(word)>4 and word.endswith('s') else word for word in words}


KEYWORD_STOP = {'the','what','how','are','does','for','and','with','from','this','that',
                'were','was','their','which','please','show','list','all','tell','about','affected'}


class IndexSource(Contract):
    source: SourceVersion
    content: str | None = Field(default=None, min_length=1, max_length=200000)
    pdf_base64: str | None = Field(default=None, min_length=1, max_length=6666668)

    @model_validator(mode='after')
    def one_format(self):
        if (self.content is None) == (self.pdf_base64 is None):
            raise ValueError('Supply exactly one supported format')
        return self


class SourceStore:
    index_version = 'lexical-v1'

    def __init__(self, path):
        self.path = str(Path(path).resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS sources (key TEXT PRIMARY KEY, approved INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS chunks (id TEXT PRIMARY KEY, source_key TEXT NOT NULL,
                    document_id TEXT NOT NULL, version_id TEXT NOT NULL, sha256 TEXT NOT NULL,
                    locator TEXT NOT NULL, content TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS chunk_scope ON chunks(source_key);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def approved_and_ready(self, source):
        with self.connect() as db:
            row = db.execute('SELECT approved FROM sources WHERE key=?', (source.key,)).fetchone()
            return bool(row and row[0])

    def approved_scope_ready(self, sources):
        return self.ready_source_keys(sources) == {source.key for source in sources}

    def ready_source_keys(self, sources):
        keys = {source.key for source in sources}
        if len(keys) > 1000: return set()
        found = set()
        values = sorted(keys)
        with self.connect() as db:
            for offset in range(0,len(values),50):
                batch = values[offset:offset+50]
                found.update(row[0] for row in db.execute(
                    f"SELECT key FROM sources WHERE approved=1 AND key IN ({','.join('?' for _ in batch)})", batch))
        return found

    def publish(self, value: IndexSource):
        # This first slice indexes exact UTF-8 text bytes, with original line locators.
        # Do not apply strip/normalization before checking the original source hash.
        chunks = extract(value)
        return self.publish_chunks(value.source, chunks)

    def publish_extracted(self, value):
        return self.publish_chunks(value.source, [(c.locator,c.text) for c in value.chunks])

    def publish_chunks(self, source, chunks):
        self.ensure_capacity(chunks)
        with self.connect() as db:
            self.write_chunks(db, source, chunks)
        return {'indexed': True, 'chunks': len(chunks), 'source': source.model_dump(mode='json'), 'index_kind': self.index_version}

    def ensure_capacity(self, chunks, location=None):
        minimum=int(os.environ.get('RAG_MIN_FREE_BYTES','536870912'))
        if minimum<0 or shutil.disk_usage(location or Path(self.path).parent).free < minimum+sum(len(text.encode()) for _,text in chunks)*4+2000000:
            raise RuntimeError('Private index storage reserve reached')

    @staticmethod
    def write_chunks(db, source, chunks):
        db.execute('DELETE FROM chunks WHERE source_key=?', (source.key,))
        for locator, content in chunks:
            chunk_id = hashlib.sha256(f'{source.key}:{locator}'.encode()).hexdigest()
            db.execute('INSERT INTO chunks VALUES (?,?,?,?,?,?,?)',
                (chunk_id, source.key, str(source.document_id), str(source.version_id), source.sha256, locator, content))
        db.execute('INSERT OR REPLACE INTO sources VALUES (?,1)', (source.key,))

    def revoke(self, source):
        with self.connect() as db:
            db.execute('UPDATE sources SET approved=0 WHERE key=?', (source.key,))

    def search(self, question, *, where, limit):
        keys = where['source_version_key']['$in']
        if not keys or len(keys) > 50 or not 1 <= limit <= 8:
            return []
        return [chunk for _, chunk in self.ranked_lexical_search(question, keys=keys, limit=limit)]

    def _lexical_candidates(self, question, keys):
        if not keys or len(keys) > 50:
            return []
        terms = keyword_terms(question) - KEYWORD_STOP
        anchors = terms & {'mtn'}
        if not terms:
            return []
        with self.connect() as db:
            rows = db.execute(f'''SELECT c.id,c.document_id,c.version_id,c.sha256,c.locator,c.content,c.source_key
                FROM chunks c JOIN sources s ON c.source_key=s.key
                WHERE s.approved=1 AND c.source_key IN ({','.join('?' for _ in keys)})''', keys).fetchall()
        tokenized = [(row, keyword_terms(row[5])) for row in rows]
        # A customer's name may be in its report header while the RCA is in another table.
        anchored_keys = {row[6] for row,tokens in tokenized if anchors & tokens} if anchors else set(keys)
        ranked = []
        for row,tokens in tokenized:
            if row[6] not in anchored_keys:
                continue
            matches = terms & tokens
            score = sum(1 if term in anchors else 2 for term in matches)
            if score:
                ranked.append((score,row))
        return sorted(ranked, key=lambda value: (-value[0], value[1][0]))

    def lexical_match_keys(self, question, *, keys):
        return {row[6] for _,row in self._lexical_candidates(question, keys)}

    def ranked_lexical_search(self, question, *, keys, limit, per_source_limit=None):
        """Scores allow global merging without favouring the first scope batch."""
        if not keys or len(keys) > 50 or not 1 <= limit <= 8:
            return []
        ranked, counts, chosen = self._lexical_candidates(question, keys), {}, []
        for score,row in ranked:
            if per_source_limit is not None and counts.get(row[6],0) >= per_source_limit:
                continue
            counts[row[6]] = counts.get(row[6],0)+1
            chosen.append((score,row))
            if len(chosen) >= limit:
                break
        return [(score, Chunk(chunk_id=r[0], source=SourceVersion(document_id=r[1], version_id=r[2], sha256=r[3]),
                      locator=r[4], text=r[5])) for score,r in chosen]
