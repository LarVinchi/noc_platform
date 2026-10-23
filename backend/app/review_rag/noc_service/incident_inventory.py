"""Deterministic incident catalogue over an accepted extracted-text snapshot.

No model, embeddings, filename-based cause inference or automatic canonical version.
"""
from collections import defaultdict
import csv
import io
import re

from .store import keyword_terms


def table_fields(chunks):
    fields = []
    seen = set()
    for locator, text in chunks:
        for row in re.split(r'(?m)^Row \d+:\s*', text)[1:]:
            cells = re.findall(r'C\d+=(.*?)(?=\s*\|\s*C\d+=|\Z)', row, re.S)
            if len(cells) < 2:
                continue
            label = re.sub(r'[^a-z0-9]+', ' ', cells[0].casefold()).strip()
            value = ' | '.join(cells[1:]).strip()
            # The next table's context is not part of this cell.
            value = re.split(r'\nTable \d+;', value)[0].strip()
            key = (label, value)
            if not value or key in seen:
                continue
            seen.add(key)
            if ('root cause' in label or label in ('rca','cause','cause of incident')):
                kind = 'cause'
            elif 'incident date' in label or label == 'date of incident':
                kind = 'date'
            elif 'customer' in label or 'client' in label:
                kind = 'customer'
            else:
                continue
            fields.append({'kind':kind, 'label':cells[0].strip()[:200], 'text':value[:3000],
                           'locator':locator, 'truncated':len(value)>3000})
    return fields


class IncidentInventory:
    def __init__(self, rows, *, snapshot, files):
        self.snapshot, self.files = snapshot, files
        self.rows = [row for row in rows if row['text_only_candidate']]
        self.by_id = {row['id']:row for row in self.rows}
        self.groups = defaultdict(list)
        self.facts, self.tokens = {}, {}
        for row in self.rows:
            identifiers = row.get('incident_ids', [])
            # Same ID groups report variants, not inferred identity from filename/date.
            group = 'incident:'+identifiers[0] if len(identifiers)==1 else 'unresolved:'+row['source']['sha256']
            self.groups[group].append(row)
            self.facts[row['id']] = table_fields(row['evidence'])
            self.tokens[row['id']] = keyword_terms('\n'.join(text for _,text in row['evidence']))

    def source(self, identifier):
        row = self.by_id.get(identifier)
        if row is None:
            raise KeyError(identifier)
        return {'id':row['id'], 'path':row['path'], 'source':row['source'],
                'review_flags':row['review_flags'], 'chunks':[
                    {'locator':locator,'text':text} for locator,text in row['evidence']],
                'snapshot':self.snapshot, 'production_approved':False}

    def search(self, customer='', offset=0, limit=25):
        if not isinstance(customer,str) or len(customer)>100 or not 0<=offset<=1000 or not 1<=limit<=100:
            raise ValueError('Invalid inventory filter or page')
        terms = keyword_terms(customer.strip())
        matched = {row['id'] for row in self.rows if not terms or terms <= self.tokens[row['id']]}
        items = []
        for key, origins in sorted(self.groups.items()):
            if not any(row['id'] in matched for row in origins):
                continue
            causes, dates, customers, reports = [], set(), set(), []
            unique_hashes = {r['source']['sha256'] for r in origins}
            for row in sorted(origins,key=lambda r:r['path']):
                facts = self.facts[row['id']]
                for field in facts:
                    if field['kind']=='cause':
                        causes.append({**field,'source_id':row['id'],'source':row['source']})
                    elif field['kind']=='date': dates.add(field['text'])
                    elif field['kind']=='customer': customers.add(field['text'])
                reports.append({'id':row['id'],'path':row['path'],'source':row['source'],
                                'matches_filter':row['id'] in matched,'review_flags':row['review_flags'],
                                'facts':facts})
            cause_texts = {re.sub(r'\s+',' ',c['text']).casefold() for c in causes}
            items.append({'group_id':key, 'incident_id':key.removeprefix('incident:') if key.startswith('incident:') else None,
                          'dates':sorted(dates),'customers':sorted(customers), 'causes':causes,
                          'reports':reports, 'report_count':len(reports), 'unique_content_count':len(unique_hashes),
                          'duplicate_copies':len(reports)-len(unique_hashes),
                          'different_cause_text':len(cause_texts)>1,
                          'needs_identity_review':key.startswith('unresolved:'),
                          'missing_cause':not causes})
        summary = {'files':self.files,'scanned_reports':len(self.rows),'deferred_files':self.files-len(self.rows),
                   'matching_reports':len(matched),'matching_incident_groups':len(items),
                   'groups_needing_identity_review':sum(i['needs_identity_review'] for i in items),
                   'groups_missing_cause':sum(i['missing_cause'] for i in items),
                   'duplicate_copies':sum(i['duplicate_copies'] for i in items),
                   'scope_complete':True,'production_approved':False,'provider_calls':0,
                   'snapshot':self.snapshot,
                   'notice':'Every accepted text/table report in this snapshot was checked. Customer filtering matches mentions, '
                            'not a verified affected-service relationship. Different report versions are retained. '
                            'Images, Word notes and deferred files are outside this scope.'}
        return {'items':items[offset:offset+limit], 'summary':summary, 'offset':offset, 'limit':limit,
                'next_offset':offset+limit if offset+limit<len(items) else None}

    def export(self, customer=''):
        stream=io.StringIO(newline='')
        writer=csv.writer(stream)
        def cell(value):
            value=str(value)
            return "'"+value if value.lstrip().startswith(('=','+','-','@','\t','\r')) else value
        writer.writerow(['Incident ID','Dates as reported','Cause text as reported','Source paths','Reports','Duplicate copies','Review notes'])
        offset=0
        while True:
            page=self.search(customer,offset,100)
            for item in page['items']:
                notes=['Text/tables only; not production approval']
                if item['different_cause_text']:notes.append('Different cause text; compare versions')
                if item['needs_identity_review']:notes.append('Missing or ambiguous incident ID')
                if item['missing_cause']:notes.append('Cause not extracted; inspect evidence')
                writer.writerow([cell(v) for v in [item['incident_id'] or 'Unresolved identity',
                    '\n'.join(item['dates']), '\n\n'.join(dict.fromkeys(c['text'] for c in item['causes'])),
                    '\n'.join(r['path'] for r in item['reports']),item['report_count'],item['duplicate_copies'],'; '.join(notes)]])
            if page['next_offset'] is None:break
            offset=page['next_offset']
        return {'filename':'incident-inventory.csv','content':stream.getvalue(),'snapshot':self.snapshot}
