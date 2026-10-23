"""Chroma is a derived index. SQLite atomically activates complete generations."""
import hashlib
import math
from pathlib import Path
from uuid import uuid4
from .contracts import Chunk, SourceVersion
from .extraction import extract
from .store import SourceStore


class VectorStore(SourceStore):
    def __init__(self, path, embeddings, *, chroma_path=None, collection=None, max_distance=0.45):
        super().__init__(path)
        self.embeddings = embeddings
        self.fingerprint = hashlib.sha256(f'{embeddings.model}:{embeddings.dimensions}:cosine:extract-v1'.encode()).hexdigest()[:16]
        self.index_version = f'chroma-v1-{self.fingerprint}'
        if not math.isfinite(max_distance) or not 0 <= max_distance <= 2:
            raise ValueError('Invalid cosine distance threshold')
        self.max_distance = max_distance
        self.chroma_path=Path(chroma_path).resolve() if chroma_path else None
        if collection is None:
            import chromadb
            from chromadb.config import Settings
            if not chroma_path:
                raise ValueError('Configure a persistent Chroma directory')
            client = chromadb.PersistentClient(path=str(chroma_path), settings=Settings(anonymized_telemetry=False))
            collection = client.get_or_create_collection(name='noc-'+self.fingerprint,
                embedding_function=None, metadata={'hnsw:space': 'cosine'})
        self.collection = collection
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS vector_active (source_key TEXT, fingerprint TEXT, generation TEXT NOT NULL, PRIMARY KEY(source_key,fingerprint))')

    def approved_and_ready(self, source):
        with self.connect() as db:
            return db.execute('''SELECT 1 FROM sources s JOIN vector_active v ON s.key=v.source_key
                WHERE s.key=? AND s.approved=1 AND v.fingerprint=?''', (source.key,self.fingerprint)).fetchone() is not None

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
                found.update(row[0] for row in db.execute(f'''SELECT s.key FROM sources s
                    JOIN vector_active v ON s.key=v.source_key WHERE s.approved=1 AND v.fingerprint=?
                    AND s.key IN ({','.join('?' for _ in batch)})''', [self.fingerprint,*batch]))
        return found

    def publish(self, value):
        return self.publish_chunks(value.source, extract(value))

    def publish_chunks(self, source, chunks):
        self.ensure_capacity(chunks)
        if self.chroma_path:
            self.ensure_capacity(chunks,self.chroma_path)
        vectors = self.embeddings.embed([text for _,text in chunks])
        generation = uuid4().hex
        ids = [generation+':'+str(i) for i in range(len(chunks))]
        # Inactive vectors never enter queries; partial writes cannot replace a live generation.
        self.collection.add(ids=ids, embeddings=vectors,
            metadatas=[{'source_version_key':source.key, 'generation':generation} for _ in chunks])
        with self.connect() as db:
            self.write_chunks(db, source, chunks)
            db.execute('INSERT OR REPLACE INTO vector_active VALUES (?,?,?)', (source.key,self.fingerprint,generation))
        return {'indexed':True, 'chunks':len(chunks), 'source':source.model_dump(mode='json'), 'index_kind':self.index_version}

    def search(self, question, *, where, limit):
        keys = where['source_version_key']['$in']
        if not keys or len(keys) > 50 or not 1 <= limit <= 8:
            return []
        vector = self.embeddings.embed([question], query=True)
        return [chunk for _, chunk in self.ranked_search(vector, keys=keys, limit=limit)]

    def ranked_search(self, query_vectors, *, keys, limit):
        """Bounded scope, reusable query embedding, scores for corpus-wide merging."""
        if not keys or len(keys) > 50 or not 1 <= limit <= 8:
            return []
        with self.connect() as db:
            active = db.execute(f'''SELECT v.source_key,v.generation FROM vector_active v JOIN sources s ON s.key=v.source_key
                WHERE s.approved=1 AND v.fingerprint=? AND s.key IN ({','.join('?' for _ in keys)})''', [self.fingerprint,*keys]).fetchall()
        if not active:
            return []
        scopes = [{'$and':[{'source_version_key':key},{'generation':generation}]} for key,generation in active]
        result = self.collection.query(query_embeddings=query_vectors,
            where=scopes[0] if len(scopes)==1 else {'$or':scopes}, n_results=limit, include=['metadatas','distances'])
        found = []
        active_map = dict(active)
        for item_id, metadata, distance in zip(result['ids'][0], result['metadatas'][0], result['distances'][0], strict=True):
            key, generation = metadata['source_version_key'], metadata['generation']
            if active_map.get(key) != generation or not item_id.startswith(generation+':'):
                raise ValueError('Vector scope mismatch')
            if not math.isfinite(distance) or distance > self.max_distance:
                continue
            # Resolve evidence from the authoritative local generation, not vector-returned text.
            with self.connect() as db:
                current = db.execute('SELECT generation FROM vector_active WHERE source_key=? AND fingerprint=?', (key,self.fingerprint)).fetchone()
                if not current or current[0] != generation:
                    raise ValueError('Source generation changed during retrieval')
                # Insertion order is stable within the atomic source replacement.
                rows = db.execute('SELECT id,document_id,version_id,sha256,locator,content FROM chunks WHERE source_key=? ORDER BY rowid', (key,)).fetchall()
            row = rows[int(item_id.split(':')[1])]
            found.append((distance, Chunk(chunk_id=row[0], source=SourceVersion(document_id=row[1],version_id=row[2],sha256=row[3]), locator=row[4],text=row[5])))
        return found
