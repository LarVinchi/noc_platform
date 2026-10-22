import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, Copy, FolderOpen, RefreshCw, Upload, X } from 'lucide-react';
import api from '../api/client';
import { operationError, watTime } from '../api/operations';
import '../styles/linked-intake.css';

const mb = value => !value || value < 1000 ? `${value || 0} B` : value < 1000000 ? `${(value / 1000).toFixed(1)} KB` : `${(value / 1000000).toFixed(2)} MB`;

function ScanIssues({ scan }) {
  if (!scan) return null;
  return <details className="linked-scan-issues"><summary>{scan.complete ? 'Complete inventory' : 'Partial inventory'} · {scan.issue_count || 0} files without complete extraction</summary>{scan.issues?.map(i => <p key={i.path}><strong>{i.path}</strong><br />{i.status.replaceAll('_', ' ')}</p>)}{scan.issue_count > 100 && <p>Showing the first 100 issues. Inspect the private collector report for the rest.</p>}</details>;
}

export default function LinkedDocumentIntake({ identity }) {
  const [data, setData] = useState(null), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [title, setTitle] = useState(''), [busy, setBusy] = useState(false), [offset, setOffset] = useState(0);
  const [preview, setPreview] = useState(null), [copied, setCopied] = useState('');
  const timer = useRef(null), sequence = useRef(0);
  const admin = identity.roles.includes('NOC.Admin');
  const load = useCallback(async signal => {
    const current = ++sequence.current;
    try {
      const response = await api.get('/document-intake', { params: { offset, limit: 50 }, signal });
      if (signal?.aborted || current !== sequence.current) return;
      setData(response.data); setError('');
    } catch (value) { if (!signal?.aborted && current === sequence.current) setError(operationError(value)); }
  }, [offset]);
  useEffect(() => {
    if (!admin) return;
    const controller = new AbortController(); load(controller.signal);
    return () => { controller.abort(); clearTimeout(timer.current); };
  }, [load, admin]);
  async function action(work) {
    setBusy(true); setError('');
    try { await work(); await load(); }
    catch (value) { setError(operationError(value)); }
    finally { setBusy(false); }
  }
  async function create(event) {
    event.preventDefault();
    await action(async () => {
      await api.post('/document-intake/collections', { title: title.trim() });
      setTitle(''); setNotice('Collection created. Copy its ID to configure the collector on the sync PC.');
    });
  }
  async function importReport(event) {
    const file = event.target.files?.[0]; event.target.value = '';
    if (!file) return;
    if (file.size > 5000000) { setError('Choose a collector report smaller than 5 MB.'); return; }
    await action(async () => {
      const report = await file.text(); JSON.parse(report);
      const response = await api.post('/document-intake/import', report, { headers: { 'Content-Type': 'application/json' }, timeout: 60000 });
      const result = response.data;
      setPreview(null);
      setNotice(`${result.replayed ? 'Report already accepted. ' : ''}${result.created_revisions} new revisions; ${result.unchanged} unchanged; ${result.skipped} skipped. ${result.complete ? 'Complete inventory.' : 'Partial inventory; absent sources were not marked missing.'} Review new revisions in Knowledge.`);
    });
  }
  async function copy(id) {
    try { await navigator.clipboard.writeText(id); setCopied(id); clearTimeout(timer.current); timer.current = setTimeout(() => setCopied(''), 1000); }
    catch { setError('Clipboard unavailable. Select and copy the collection ID manually.'); }
  }
  async function inspect(item) {
    setError('');
    try {
      const response = await api.get(`/document-intake/versions/${item.version_id}/preview`);
      setPreview({ ...item, ...response.data });
    } catch (value) { setError(operationError(value)); }
  }
  if (!admin) return <div className="response-centre"><h1>OneDrive intake</h1><p>Administrator access is required. Approved shared sources remain available in Knowledge.</p><Link to="/knowledge">Open Knowledge</Link></div>;
  return <div className="response-centre linked-intake">
    <div className="response-page-heading"><div><span className="eyebrow">DOCUMENTS / ONEDRIVE INTAKE</span><h1>Catalogue once. Keep originals in OneDrive.</h1><p>Import metadata and extracted text from the approved sync PC, then review exact revisions in Knowledge.</p></div><Link className="response-button" to="/knowledge">Review in Knowledge</Link></div>
    <div className="response-notice"><FolderOpen size={18} /> No original-file copies are retained by this intake. Extracted text, metadata and search vectors still use private storage. Folder access is not automatic permission to share its contents with NOC users.</div>
    {error && <p className="response-error" role="alert">{error}</p>}{notice && <p className="response-notice" role="status">{notice}</p>}
    <div className="linked-intake-controls response-panel"><form onSubmit={create}><label>Approved collection name<input required minLength={3} maxLength={200} value={title} onChange={e => setTitle(e.target.value)} placeholder="Approved NOC runbooks" /></label><button className="response-button primary" disabled={busy || title.trim().length < 3}>Create collection</button></form><div><label className="response-button"><Upload size={15} />Import collector report<input className="linked-file-input" type="file" accept=".json,application/json" onChange={importReport} disabled={busy} /></label><button className="response-button" disabled={busy} onClick={() => load()}><RefreshCw size={15} />Refresh</button></div></div>
    <div className="linked-collections">{data?.collections.map(c => <section className="response-panel" key={c.collection_id}><h2>{c.title}</h2><p>{c.enabled ? 'Active' : 'Paused'} · Observation expires after {Math.round(c.freshness_seconds / 3600)} hours</p><code>{c.collection_id}</code><div className="linked-card-actions"><button className="response-button" onClick={() => copy(c.collection_id)}>{copied === c.collection_id ? <Check size={14} /> : <Copy size={14} />}{copied === c.collection_id ? 'Copied' : 'Copy ID'}</button><button className="response-button" disabled={busy} onClick={() => action(async () => { await api.patch(`/document-intake/collections/${c.collection_id}`, { enabled: !c.enabled }); setNotice(c.enabled ? 'Collection paused. Its sources are blocked from new answers.' : 'Collection resumed. Only fresh, approved revisions can be queried.'); })}>{c.enabled ? 'Pause collection' : 'Resume'}</button></div><p>Derived text: {mb(c.derived_bytes)} / {mb(c.derived_limit_bytes)}</p><small>{c.last_observed_at ? `Last observation ${watTime(c.last_observed_at)}` : 'No collector report received'}</small><ScanIssues scan={c.last_scan} /></section>)}</div>
    {!data?.collections.length && !error && <p className="response-notice">Create a collection first. Run export-linked-folder.py on the sync PC with its collection ID, then import that private JSON report here.</p>}
    <section className="response-panel linked-table-panel"><h2>Latest linked revisions <small>{data?.total ?? 0} sources</small></h2><div className="linked-table-scroll"><table><thead><tr><th>Source</th><th>Revision / readiness</th><th>Storage / audience</th><th>Review</th></tr></thead><tbody>{data?.items.map(item => <tr key={item.version_id}><td><strong>{item.title}</strong><small>{item.path}</small>{item.duplicate_content && <span>Identical bytes elsewhere · origins kept separate</span>}</td><td>Revision {item.revision}<small>{item.fresh ? 'Fresh extraction' : 'Stale, unavailable or extraction required'} · {item.chunk_count} chunks</small></td><td>{mb(item.derived_bytes)} derived<small>{mb(item.original_bytes)} original stays in OneDrive</small><span>{item.visibility === 'noc' ? 'Shared with NOC roles' : 'Private to collection owner and administrators'}</span></td><td><button className="response-button" onClick={() => inspect(item)}>Inspect extraction</button></td></tr>)}</tbody></table></div><div className="linked-pagination"><button className="response-button" disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</button><span>{data?.total ? `${offset + 1}–${Math.min(offset + 50, data.total)} of ${data.total}` : 'No linked sources yet'}</span><button className="response-button" disabled={!data || offset + 50 >= data.total} onClick={() => setOffset(offset + 50)}>Next</button></div></section>
    {preview && <section className="response-panel linked-extraction"><header><h2>{preview.title} · Revision {preview.revision}</h2><button className="response-button" onClick={() => setPreview(null)}><X size={15} />Close preview</button></header><p>{preview.notice}</p><small>Original SHA-256: {preview.sha256}</small><small>Extraction SHA-256: {preview.extraction_sha256}</small>{preview.chunks.map(c => <article key={c.locator}><strong>{c.locator}</strong><pre>{c.text}</pre></article>)}{!preview.chunks.length && <p>No complete supported extraction. Review the collector result before approving.</p>}<div className="linked-card-actions"><Link className="response-button primary" to="/knowledge">Review / approve in Knowledge</Link><button className="response-button" disabled={busy || preview.visibility === 'noc'} onClick={() => action(async () => { await api.patch(`/documents/${preview.document_id}/sharing`, { visibility: 'noc' }); setPreview(p => ({ ...p, visibility: 'noc' })); setNotice('Audience explicitly expanded to all NOC roles. Source revision approval is still required.'); })}>Allow all NOC roles to access this source</button><button className="response-button" disabled={busy || preview.visibility === 'private'} onClick={() => action(async () => { await api.patch(`/documents/${preview.document_id}/sharing`, { visibility: 'private' }); setPreview(p => ({ ...p, visibility: 'private' })); setNotice('Source restricted to its owner and administrators.'); })}>Restrict to owner / administrators</button></div><p>Sharing grants access to extracted content, regardless of the reader’s Microsoft 365 permissions. Confirm the intended audience before expanding access.</p></section>}
  </div>;
}
