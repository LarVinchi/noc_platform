"""Fail-closed orchestration, independent of Chroma/Gemini or shared chat memory."""
from typing import Protocol

from .contracts import Answer, Chunk, Citation, GeneratedAnswer, Query, SourceVersion


class ScopeDenied(Exception):
    """A requested immutable version is not approved and ready in the registry."""


class AdapterViolation(Exception):
    """A backend violated the private adapter contract."""


class Registry(Protocol):
    def approved_and_ready(self, source: SourceVersion) -> bool:
        """Read current approval, readiness and identity for this exact version."""
        ...


class Retriever(Protocol):
    def search(self, question: str, *, where: dict, limit: int) -> list[Chunk]:
        """Apply the mandatory exact-version filter BEFORE similarity/top-k."""
        ...


class Generator(Protocol):
    def answer(self, question: str, *, evidence: tuple[Chunk, ...]) -> GeneratedAnswer:
        """Treat evidence as untrusted data, require evidence and structured output.

        Implementations must have bounded timeouts/retries and no external tools.
        """
        ...


class QueryEngine:
    def __init__(self, registry: Registry, retriever: Retriever, generator: Generator):
        self.registry = registry
        self.retriever = retriever
        self.generator = generator

    def insufficient(self, query: Query) -> Answer:
        return Answer(request_id=query.request_id, status="insufficient_evidence",
                      answer="There is insufficient approved evidence to answer this question.", citations=(),
                      model=getattr(self.generator,'model',None),index_version=getattr(self.retriever,'index_version','unspecified'))

    def check_scope(self, query: Query):
        bulk = getattr(self.registry, 'approved_scope_ready', None)
        ready = bulk(query.allowed_versions) if callable(bulk) else all(self.registry.approved_and_ready(source) for source in query.allowed_versions)
        if not ready:
            raise ScopeDenied()

    def query(self, query: Query) -> Answer:
        if not query.allowed_versions:
            return self.insufficient(query)
        self.check_scope(query)
        allowed = {source.key for source in query.allowed_versions}
        # Backends must index this composite metadata key. A global search with
        # post-filtering is not a conforming implementation of Retriever.
        where = {"source_version_key": {"$in": sorted(allowed)}}
        chunks = self.retriever.search(query.question, where=where, limit=8)
        if not isinstance(chunks, list) or len(chunks) > 8:
            raise AdapterViolation()
        if any(not isinstance(chunk, Chunk) or chunk.source.key not in allowed for chunk in chunks):
            raise AdapterViolation()
        if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
            raise AdapterViolation()
        if sum(len(chunk.text) for chunk in chunks) > 24000:
            raise AdapterViolation()
        self.check_scope(query)  # Reject revocation during retrieval before generation.
        if not chunks:
            return self.insufficient(query)
        generated = self.generator.answer(query.question, evidence=tuple(chunks))
        self.check_scope(query)  # Reject revocation during generation before releasing an answer.
        if not isinstance(generated, GeneratedAnswer):
            raise AdapterViolation()
        if generated.status == "insufficient_evidence":
            return self.insufficient(query)
        lookup = {chunk.chunk_id: chunk for chunk in chunks}
        cited = generated.cited_chunk_ids
        if not cited or len(cited) != len(set(cited)) or any(key not in lookup for key in cited):
            raise AdapterViolation()
        citations = tuple(Citation(chunk_id=key, source=lookup[key].source,
                                   locator=lookup[key].locator, excerpt=lookup[key].text[:600]) for key in cited)
        return Answer(request_id=query.request_id, status="answered", answer=generated.answer, citations=citations,
                      model=getattr(self.generator,'model',None),index_version=getattr(self.retriever,'index_version','unspecified'))
