"""Bounded, version-pinned service contracts. User authorization belongs to NOC."""
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceVersion(Contract):
    document_id: UUID
    version_id: UUID
    sha256: Digest

    @property
    def key(self) -> str:
        return f"{self.document_id}:{self.version_id}:{self.sha256}"


class Query(Contract):
    request_id: UUID
    question: Text = Field(max_length=4000)
    allowed_versions: tuple[SourceVersion, ...] = Field(max_length=50)

    @model_validator(mode="after")
    def distinct_versions(self):
        identifiers = [version.version_id for version in self.allowed_versions]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Duplicate version scope")
        return self


class Chunk(Contract):
    chunk_id: Text = Field(max_length=128)
    source: SourceVersion
    # Created by extraction, never inferred by the answer model.
    locator: Text = Field(max_length=300)
    text: Text = Field(max_length=12000)


class GeneratedAnswer(Contract):
    status: Literal["answered", "insufficient_evidence"]
    answer: Text = Field(max_length=12000)
    cited_chunk_ids: tuple[Text, ...] = Field(max_length=8)


class Citation(Contract):
    chunk_id: str
    source: SourceVersion
    locator: str
    excerpt: str


class Answer(Contract):
    request_id: UUID
    status: Literal["answered", "insufficient_evidence"]
    answer: str
    citations: tuple[Citation, ...]
    model: str | None = Field(default=None,max_length=100)
    index_version: str = Field(default='unspecified',max_length=100)
