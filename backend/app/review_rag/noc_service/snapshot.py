"""Pure accepted-extraction snapshot validation and stable source identities."""
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from uuid import UUID, uuid5

NAMESPACE = UUID('c198d8f1-a5be-4a01-b424-42d9adf74d5d')
POLICY = 'demo-extracted-text-only-v1'

def read_json(path, limit):
    if path.stat().st_size > limit:
        raise ValueError('Review input exceeds size limit')
    return json.loads(path.read_text(encoding='utf-8'))

def load_review(directory):
    directory = Path(directory).resolve(strict=True)
    report_path = directory / 'assessment.json'
    report = read_json(report_path, 5_000_000)
    items = report['items']
    if len(items) > 1000:
        raise ValueError('Review is limited to 1000 origins')
    records = []
    total = 0
    for item in items:
        row = {key: item.get(key) for key in (
            'path', 'sha256', 'bytes', 'status', 'review_flags',
            'same_content_as', 'transfer_hash_matches')}
        row['review_flags'] = row.get('review_flags') or []
        row['chunks'] = []
        row['extraction_sha256'] = None
        reference = item.get('extraction_file')
        if reference:
            relative = PurePosixPath(reference)
            if (relative.is_absolute() or len(relative.parts) != 2
                    or relative.parts[0] != 'extractions' or '\\' in reference
                    or relative.suffix != '.json'):
                raise ValueError('Invalid extraction reference')
            path = (directory / reference).resolve(strict=True)
            if not path.is_relative_to(directory / 'extractions'):
                raise ValueError('Extraction reference escapes its directory')
            data = read_json(path, 1_250_000)
            if data.get('original_sha256') != item['sha256'] or data.get('original_size') != item['bytes']:
                raise ValueError('Extraction does not match the assessed original')
            if data.get('status') != item['status'] or sorted(data.get('review_flags', [])) != sorted(row['review_flags']):
                raise ValueError('Extraction status or warnings changed since assessment')
            chunks = data.get('chunks', [])
            if len(chunks) != item.get('chunks') or len(chunks) > 100:
                raise ValueError('Extraction chunk count differs from assessment')
            characters = 0
            for chunk in chunks:
                locator, text = chunk['locator'], chunk['text']
                if not isinstance(locator, str) or not isinstance(text, str) or len(locator) > 300 or len(text) > 2800:
                    raise ValueError('Invalid extracted evidence')
                characters += len(text)
            if characters > 200_000:
                raise ValueError('Document text exceeds assessment limits')
            row['chunks'] = chunks
            row['extraction_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            total += characters
        if total > 50_000_000:
            raise ValueError('Review bundle is too large; split the batch')
        row['eligible'] = bool(row['status'] == 'extracted_for_review' and row['chunks']
                               and not row['review_flags'] and row['transfer_hash_matches'] is True)
        records.append(row)
    return {
        'assessment_sha256': hashlib.sha256(report_path.read_bytes()).hexdigest(),
        'summary': report['summary'], 'records': records,
        'approved': False, 'indexed': False, 'provider_calls': 0,
    }

def audit(directory):
    bundle = load_review(directory)
    records = []
    allowances = {'docx_image_content_not_transcribed', 'pdf_image_content_not_transcribed', 'docx_notes_require_review'}
    for source in bundle['records']:
        chunks = source['chunks']
        text = '\n'.join(chunk['text'] for chunk in chunks)
        issues = []
        if not chunks:
            issues.append('no_extracted_evidence')
        if text and len(text.strip()) < 200:
            issues.append('very_little_extracted_text')
        cid_count = len(re.findall(r'\(cid:\d+\)', text))
        replacement_count = text.count('\ufffd')
        if cid_count or replacement_count:
            issues.append('unresolved_pdf_character_mapping')
        if text and any(ord(c) < 32 and c not in '\n\r\t' for c in text):
            issues.append('unexpected_control_characters')
        locators = [chunk['locator'] for chunk in chunks]
        if len(locators) != len(set(locators)):
            issues.append('duplicate_evidence_locators')
        hard_flags = sorted(set(source['review_flags']) - allowances)
        incident_ids = sorted({re.sub(r'[_ -]', '', value.upper()) for value in
                               re.findall(r'\b[A-Z]{2,8}[_ -]IM[_ -]\d{6,8}[_ -]\d{2,5}\b', text, re.I)})
        # User has accepted an extracted-text demo, not verification of omitted images/notes.
        candidate = bool(chunks and source['transfer_hash_matches'] is True
                         and source['status'] in ('needs_review', 'extracted_for_review')
                         and not hard_flags and not issues)
        records.append({
            'path': source['path'], 'source_sha256': source['sha256'],
            'extraction_sha256': source['extraction_sha256'], 'bytes': source['bytes'],
            'extension': Path(source['path']).suffix.lower(), 'status': source['status'],
            'review_flags': source['review_flags'], 'hard_flags': hard_flags,
            'quality_issues': issues, 'chunks': len(chunks), 'characters': len(text),
            'table_chunks': sum('table' in c['locator'].lower() for c in chunks),
            'cid_tokens': cid_count, 'replacement_characters': replacement_count,
            'duplicate_origin': source['same_content_as'],
            'incident_ids': incident_ids,
            'confidential_label_present': bool(re.search(r'\bconfidential\b', text, re.I)),
            'incident_sections': sum(bool(re.search(term, text, re.I)) for term in
                                     ('root cause', 'restoration', 'incident date', 'outage duration')),
            'text_only_candidate': candidate,
            'omitted_content_verified': False, 'approved': False,
        })
    candidates = [r for r in records if r['text_only_candidate'] and not r['duplicate_origin']]
    incident_groups = Counter(identifier for r in candidates for identifier in r['incident_ids'])
    for r in records:
        r['incident_variant_group'] = any(incident_groups[i] > 1 for i in r['incident_ids'])
    ranked = sorted(candidates, key=lambda r: (-r['incident_sections'], -min(r['table_chunks'], 4),
                                              abs(r['characters'] - 6500), r['path']))
    # Prefer substantive incident documents, with some format diversity if available.
    selected = []
    # First pilot avoids multi-origin incidents whose authoritative revision is unknown.
    pilot_pool = [r for r in ranked if not r['incident_variant_group'] and len(r['incident_ids']) <= 1]
    for extension, count in (('.docx', 8), ('.pdf', 2)):
        selected.extend([r for r in pilot_pool if r['extension'] == extension][:count])
    chosen = {r['path'] for r in selected}
    selected.extend(r for r in pilot_pool if r['path'] not in chosen)
    selected = selected[:10]
    for index, record in enumerate(selected, 1):
        record['pilot_order'] = index
    summary = {
        'origins_audited': len(records), 'origins_with_evidence': sum(bool(r['chunks']) for r in records),
        'extracted_chunks_across_origins': sum(r['chunks'] for r in records),
        'text_only_candidate_origins': sum(r['text_only_candidate'] for r in records),
        'unique_content_candidate_origins': len(candidates),
        'quality_issues': dict(Counter(issue for r in records for issue in r['quality_issues'])),
        'hard_flags': dict(Counter(flag for r in records for flag in r['hard_flags'])),
        'flagged_word_notes_require_original_inspection': sum('docx_notes_require_review' in r['review_flags'] for r in records),
        'candidate_incident_ids_with_multiple_origins': sum(n > 1 for n in incident_groups.values()),
        'candidate_origins_in_incident_variant_groups': sum(r['incident_variant_group'] for r in candidates),
        'origins_with_confidential_label': sum(r['confidential_label_present'] for r in records),
        'pilot_proposals': len(selected), 'pilot_chunks': sum(r['chunks'] for r in selected),
        'pilot_characters': sum(r['characters'] for r in selected),
        'indexed': False, 'approved': False, 'provider_calls': 0,
    }
    return {'schema': 1, 'assessment_sha256': bundle['assessment_sha256'], 'summary': summary,
            'scope': 'Extracted text and tables only. Images and Word notes are unverified and excluded from evidence. '
                     'Candidate classification is not a completeness certification or authenticated NOC approval.',
            'items': records, 'pilot_paths': [r['path'] for r in selected]}

def source_record(row):
    path = row['path']
    doc_id = uuid5(NAMESPACE, path)
    version_id = uuid5(doc_id, row['sha256'] + row['extraction_sha256'] + POLICY)
    label = ('Text-only: images and Word notes are unverified and excluded. '
             'Do not infer omitted content.\nSource: ' + Path(path).name[:70] + '\n')
    if len(label) > 200:
        raise ValueError('Evidence context exceeds retrieval budget')
    return {'path': path, 'source': {'document_id': str(doc_id), 'version_id': str(version_id),
            'sha256': row['sha256']}, 'extraction_sha256': row['extraction_sha256'],
            'review_flags': row['review_flags'], 'chunks': [(c['locator'], label+c['text']) for c in row['chunks']]}
