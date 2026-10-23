import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, Check, Download, FileText, RefreshCw, Search, ShieldCheck, Send, X } from 'lucide-react';
import api from '../api/client';
import { operationError, watTime } from '../api/operations';
import '../styles/response.css';
import '../styles/approved-knowledge.css';

export default function ApprovedKnowledge({ identity }) {
  const [status, setStatus] = useState(null), [sources, setSources] = useState([]), [selected, setSelected] = useState([]);
  const [question, setQuestion] = useState(''), [answer, setAnswer] = useState(null), [search, setSearch] = useState('');
  const [error, setError] = useState(''), [notice, setNotice] = useState(''), [busy, setBusy] = useState(false);
  const [review, setReview] = useState(null), [note, setNote] = useState('');
  const [origin, setOrigin] = useState(null);
  const request = useRef(null), epoch = useRef(0), refreshVersion = useRef(0), dialog = useRef(null);
  const admin = identity.roles.includes('NOC.Admin');
  const load = useCallback(async signal => {
    const version = ++refreshVersion.current;
    try {
      const [a,b] = await Promise.all([api.get('/knowledge/status', { signal }), api.get('/knowledge/sources', { signal })]);
      if (signal?.aborted || version !== refreshVersion.current) return;
      setStatus(a.data); setSources(b.data.items); setError('');
      setSelected(previous => previous.filter(id => b.data.items.some(s => s.document_id === id && s.approved && s.eligible !== false)));
    } catch (value) { if (!signal?.aborted && version === refreshVersion.current) setError(operationError(value)); }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal); const timer = setInterval(() => load(controller.signal), 30000);
    return () => { controller.abort(); clearInterval(timer); request.current?.abort(); };
  }, [load]);
  useEffect(() => {
    if (!review) return;
    const previous = document.activeElement, panel = dialog.current;
    panel?.querySelector('textarea')?.focus();
    const keyboard = event => {
      if (event.key === 'Escape' && !busy) setReview(null);
      if (event.key !== 'Tab') return;
      const items = [...panel.querySelectorAll('button,textarea')].filter(el => !el.disabled);
      if (!items.length) return;
      if (event.shiftKey && document.activeElement === items[0]) { event.preventDefault(); items.at(-1).focus(); }
      else if (!event.shiftKey && document.activeElement === items.at(-1)) { event.preventDefault(); items[0].focus(); }
    };
    document.addEventListener('keydown', keyboard);
    return () => { document.removeEventListener('keydown', keyboard); previous?.focus(); };
  }, [review, busy]);
  function toggle(source) {
    request.current?.abort(); epoch.current++; setBusy(false); setAnswer(null);
    setSelected(previous => previous.includes(source.document_id) ? previous.filter(id => id !== source.document_id) : [...previous, source.document_id].slice(0,10));
  }
  async function ask(event) {
    event.preventDefault(); request.current?.abort(); const controller = new AbortController(); request.current = controller;
    const version = ++epoch.current, asked = question.trim();
    setBusy(true); setError(''); setAnswer(null);
    try {
      const { data } = await api.post('/knowledge/query', { question: asked, document_ids: selected }, { signal: controller.signal, timeout: 120000 });
      if (version === epoch.current) setAnswer({ ...data, question: asked });
    } catch (value) { if (!controller.signal.aborted && version === epoch.current) setError(operationError(value)); }
    finally { if (version === epoch.current) setBusy(false); }
  }
  async function download(source) {
    try {
      const current = sources.find(s => s.document_id === source.document_id && s.version.version_id === source.version_id);
      if (current?.origin_kind === 'onedrive_link') {
        const response = await api.get(`/documents/${source.document_id}/versions/${source.version_id}/origin`);
        setOrigin(response.data); return;
      }
      const { data } = await api.get(`/documents/${source.document_id}/versions/${source.version_id}/download`, { responseType: 'blob' });
      const url = URL.createObjectURL(data), anchor = document.createElement('a');
      anchor.href = url; anchor.download = source.filename || 'approved-source.txt'; anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    } catch (value) { setError(operationError(value)); }
  }
  async function saveReview(event) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      await api.post(`/knowledge/versions/${review.source.version.version_id}/review`, { action: review.action, note: note.trim() }, { timeout: 45000 });
      setNotice(review.action === 'approve' ? 'This exact source revision is approved and indexed.' : 'Approval revoked. The source can no longer be queried.');
      setReview(null); setNote(''); setAnswer(null); await load();
    } catch (value) { setError(operationError(value)); }
    finally { setBusy(false); }
  }
  const visible = sources.filter(s => `${s.title} ${s.filename}`.toLowerCase().includes(search.toLowerCase()));
  const currentAnswer = answer && answer.citations.every(c => sources.some(s => s.approved && s.eligible !== false && s.version.version_id === c.source.version_id && s.version.sha256 === c.source.sha256));
  return <div className="response-centre approved-knowledge">
    {admin && status?.review_lab_available && <Link className="response-button" to="/knowledge/review"><FileText size={16}/>Review collection · Incident inventory and questions</Link>}
    {admin && status?.linked_intake_available && <Link className="response-button" to="/documents/intake">OneDrive intake · metadata and extraction only</Link>}
    {origin && <section className="response-panel linked-extraction"><header><h2>OneDrive source provenance</h2><button className="response-button" onClick={() => setOrigin(null)}>Close</button></header><p>{origin.notice}</p><p>{origin.path}</p><small>Original SHA-256: {origin.original_sha256}</small><small>Extraction SHA-256: {origin.extraction_sha256}</small><p>{origin.identity_evidence}</p>{origin.original_url && <a className="response-button" href={origin.original_url} target="_blank" rel="noopener noreferrer">Open current file in OneDrive</a>}</section>}
    <div className="response-page-heading"><div><span className="eyebrow">KNOWLEDGE / APPROVED EVIDENCE</span><h1>Answers you can trace.</h1><p>Choose reviewed sources. Ask one question. Inspect the exact revision behind the answer.</p></div><button className="response-button" onClick={() => load()}><RefreshCw size={15} />Refresh sources</button></div>
    <div className="approved-connection"><ShieldCheck size={20} /><div><strong>{status?.rag_connected ? 'Private knowledge worker configured' : 'Knowledge connection pending'}</strong><p>{status?.rag_connected ? 'Provider availability is verified when you ask. Answers still require source review.' : 'Configure the private worker and approve a TXT runbook, text-based PDF or linked extraction to enable questions.'}</p></div><span>{status?.approved_sources ?? '—'} approved</span></div>
    {error && <p role="alert" className="response-error">{error}</p>}{notice && <p role="status" className="response-notice">{notice}</p>}
    <div className="approved-layout"><section className="approved-conversation response-panel"><header><BookOpen size={18} /><h2>Ask approved knowledge</h2><span>{selected.length}/10 sources selected</span></header>
      <div className="approved-answer" aria-live="polite">{busy && !review ? <p role="status">Retrieving approved evidence and preparing an answer…</p> : answer && currentAnswer ? <><div className="approved-question"><small>YOUR QUESTION</small><h3>{answer.question}</h3></div><div className={`approved-answer-text ${answer.status === 'insufficient_evidence' ? 'is-insufficient' : ''}`}><strong>{answer.status === 'answered' ? 'Evidence-based answer · verify before use' : 'Insufficient approved evidence'}</strong><p>{answer.answer}</p></div>{answer.citations.length > 0 && <section className="approved-citations"><h3>Verify the evidence</h3>{answer.citations.map((c,index) => <article key={c.chunk_id}><header><strong>[{index+1}] {sources.find(s => s.document_id === c.source.document_id)?.title || 'Approved source'}</strong><span>{c.locator}</span></header><blockquote>{c.excerpt}</blockquote><small>Version {c.source.version_id} · SHA-256 {c.source.sha256}</small><button className="response-button" onClick={() => download(c.source)}><Download size={14} />Original cited revision</button></article>)}</section>}</> : <div className="approved-welcome"><BookOpen size={32} /><h2>Start with one reviewed runbook.</h2><p>{answer ? 'Source approval or revision changed. Refresh your selection and ask again.' : 'Select an approved source on the right, then ask about a procedure it actually contains. Missing evidence produces an abstention.'}</p><div><span><Check size={14} />Version-pinned citations</span><span><ShieldCheck size={14} />Your source permissions apply</span></div></div>}</div>
      {answer && currentAnswer && <div className="approved-result-meta">Model: {answer.model || 'Not reported'} · Index: {answer.index_version || 'Not reported'} · Request: {answer.request_id}</div>}<form className="approved-composer" onSubmit={ask}><label htmlFor="approved-question">Your question<textarea id="approved-question" required minLength={3} maxLength={4000} rows={3} value={question} onChange={event => setQuestion(event.target.value)} placeholder="Who receives an unresolved test incident after 15 minutes?" /></label><div><small>Single question · no shared chat memory · TXT and text-based PDF</small><button className="response-button primary" disabled={busy || !!error || !status?.query_available || !selected.length || question.trim().length < 3}><Send size={14} />{busy ? 'Working…' : 'Ask approved sources'}</button></div></form>
    </section><aside className="approved-source-panel response-panel"><header><div><h2>Source scope</h2><p>Latest accessible revisions · up to 100 sources</p></div><Link className="response-button" to="/documents">Upload / manage</Link></header><label className="approved-search"><Search size={15} /><input aria-label="Search approved source titles" placeholder="Find a runbook…" value={search} onChange={event => setSearch(event.target.value)} /></label><div className="approved-source-list">{visible.map(s => <article className={selected.includes(s.document_id) ? 'is-selected' : ''} key={s.document_id}><label><input type="checkbox" disabled={!s.approved || s.eligible === false || busy || (!selected.includes(s.document_id) && selected.length >= 10)} checked={selected.includes(s.document_id)} onChange={() => toggle(s)} /><span><strong>{s.title}</strong><small>Revision {s.revision} · {s.approved ? 'Approved' : 'Not approved'}{s.eligible === false ? ' · stale or unavailable' : !s.supported ? ' · extraction required' : ''}</small></span></label><p><FileText size={13} />{s.filename}</p><div><button className="response-button" onClick={() => download({ ...s.version, filename: s.filename })}><Download size={13} />Inspect original</button>{admin && status?.approval_available && s.approved && <button className="response-button" disabled={busy || !s.supported} onClick={() => { setReview({ source: s, action: 'approve' }); setNote(''); }}>Reindex</button>}{admin && status?.approval_available && (s.supported || s.approved) && <button className="response-button" disabled={busy} onClick={() => { setReview({ source: s, action: s.approved ? 'revoke' : 'approve' }); setNote(''); }}>{s.approved ? 'Revoke' : 'Review / approve'}</button>}</div>{s.reviewed_at && <small>Reviewed {watTime(s.reviewed_at)}</small>}</article>)}{!visible.length && <p className="approved-empty">{status ? 'No matching sources. Upload a UTF-8 TXT runbook or text-based PDF under Documents.' : 'Loading accessible sources…'}</p>}</div></aside></div>
    <p className="approved-footer">Retrieval: {status?.source_mode || 'Checking worker'}. Review every answer against its original source before use.</p>
    {review && <div className="response-modal-backdrop"><section ref={dialog} className="response-draft-editor" role="dialog" aria-modal="true" aria-labelledby="source-review-title"><header><h2 id="source-review-title">{review.action === 'approve' ? 'Approve exact source revision' : 'Revoke source approval'}</h2><button className="noc-icon-button" aria-label="Close source review" disabled={busy} onClick={() => setReview(null)}><X size={20} /></button></header><form className="response-form" onSubmit={saveReview}><p><strong>{review.source.title}</strong> · Revision {review.source.revision}</p><code>{review.source.version.sha256}</code><p>{review.action === 'approve' ? 'Inspect the source and extracted text first. Linked originals stay in OneDrive; NOC trusts the collector hash. Approval permits indexing, including sending extracted text to the approved embedding provider.' : 'New questions cannot use this source after revocation.'}</p><label>Review reason<textarea required minLength={5} maxLength={2000} value={note} onChange={event => setNote(event.target.value)} /></label><button className="response-button primary" disabled={busy || note.trim().length < 5}>{busy ? 'Saving…' : review.action === 'approve' ? 'Approve and index revision' : 'Revoke approval'}</button>{error && <p role="alert" className="response-error">{error}</p>}</form></section></div>}
  </div>;
}
