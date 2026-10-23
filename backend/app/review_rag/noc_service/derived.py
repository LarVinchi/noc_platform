"""Trusted collector extraction contract; never claims to verify absent originals."""
import hashlib
import json
from pydantic import Field, model_validator
from .contracts import Contract, SourceVersion, Text, Digest


class ExtractedChunk(Contract):
    locator: Text = Field(max_length=300)
    text: Text = Field(max_length=2800)


def extraction_hash(chunks):
    values = [c.model_dump() if hasattr(c,'model_dump') else c for c in chunks]
    return hashlib.sha256(json.dumps(values,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


class IndexExtraction(Contract):
    source: SourceVersion
    extraction_sha256: Digest
    chunks: tuple[ExtractedChunk,...] = Field(min_length=1,max_length=100)

    @model_validator(mode='after')
    def integrity(self):
        if sum(len(c.text) for c in self.chunks)>200000 or len({c.locator for c in self.chunks})!=len(self.chunks):
            raise ValueError('Extraction exceeds limits or has duplicate locators')
        if extraction_hash(self.chunks)!=self.extraction_sha256:
            raise ValueError('Extraction integrity mismatch')
        return self
