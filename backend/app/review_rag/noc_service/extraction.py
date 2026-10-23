"""Bounded extraction; original bytes determine identity, locators come from parsers."""
import base64
import hashlib

MAX_PDF_BYTES = 5_000_000


def extract(value):
    if value.content is not None:
        raw = value.content.encode('utf-8')
        sections = [('Lines', value.content)]
    else:
        try:
            raw = base64.b64decode(value.pdf_base64, validate=True)
        except (ValueError, TypeError):
            raise ValueError('Invalid PDF encoding') from None
        if len(raw) > MAX_PDF_BYTES or not raw.startswith(b'%PDF-'):
            raise ValueError('Invalid or oversized PDF')
        # Lazy import keeps the existing TXT-only installation usable.
        if hashlib.sha256(raw).hexdigest() != value.source.sha256:
            raise ValueError('Source integrity mismatch')
        from .loaders import load_document
        return load_document(raw,'.pdf')
    if hashlib.sha256(raw).hexdigest() != value.source.sha256:
        raise ValueError('Source integrity mismatch')
    result = []
    for label, text in sections:
        lines = text.splitlines()
        buffer, first = [], 1
        for number, line in enumerate(lines, 1):
            if len(line) > 2800:
                raise ValueError('Source lines must be at most 2800 characters')
            if buffer and sum(len(item)+1 for item in buffer) + len(line) > 2800:
                locator = f'Lines {first}-{number-1}' if label == 'Lines' else f'{label}, lines {first}-{number-1}'
                result.append((locator, '\n'.join(buffer)))
                buffer, first = [], number
            buffer.append(line)
        if buffer:
            locator = f'Lines {first}-{len(lines)}' if label == 'Lines' else f'{label}, lines {first}-{len(lines)}'
            result.append((locator, '\n'.join(buffer)))
    result = [(locator, text) for locator, text in result if text.strip()]
    if not result or len(result) > 100:
        raise ValueError('Source exceeds extraction limits or has no text')
    return result
