import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, Download, FileSearch, Search, Send } from 'lucide-react';
import api from '../api/client';
import { operationError } from '../api/operations';
import '../styles/response.css';
import '../styles/review-knowledge.css';

const base='/knowledge-review';
const unique=values=>[...new Set(values)];

export default function ReviewKnowledge({ identity }) {
  const [status,setStatus]=useState(null),[tab,setTab]=useState('inventory'),[error,setError]=useState('');
  const [customer,setCustomer]=useState('MTN'),[offset,setOffset]=useState(0),[page,setPage]=useState(null),[loading,setLoading]=useState(false);
  const [sources,setSources]=useState([]),[filter,setFilter]=useState(''),[selected,setSelected]=useState([]);
  const [question,setQuestion]=useState(''),[model,setModel]=useState('gemini-3.5-flash-lite'),[answer,setAnswer]=useState(null);
  const [busy,setBusy]=useState(false),[elapsed,setElapsed]=useState(0),[evidence,setEvidence]=useState(null),[exporting,setExporting]=useState(false);
  const requests=useRef(new Set()),dialog=useRef(null),sourceRequest=useRef(null);
  const admin=identity.roles.includes('NOC.Admin');
  useEffect(()=>{
    if(!admin)return;
    const controller=new AbortController();
    api.get(base+'/status',{signal:controller.signal,timeout:30000}).then(({data})=>setStatus(data))
      .catch(value=>{if(!controller.signal.aborted)setError(operationError(value));});
    const pending=requests.current;
    return()=>{controller.abort();for(const request of pending)request.abort();sourceRequest.current?.abort();};
  },[admin]);
  useEffect(()=>{
    if(!status?.enabled)return;
    const controller=new AbortController();
    api.get(base+'/sources',{signal:controller.signal}).then(({data})=>setSources(data.sources.filter(row=>row.text_only_candidate)))
      .catch(value=>{if(!controller.signal.aborted)setError(operationError(value));});
    return()=>controller.abort();
  },[status?.enabled]);
  useEffect(()=>{
    if(!status?.enabled||tab!=='inventory')return;
    const controller=new AbortController();setLoading(true);setPage(null);
    const timer=setTimeout(()=>{
      api.get(base+'/incidents',{params:{customer:customer.trim(),offset,limit:25},signal:controller.signal,timeout:30000})
        .then(({data})=>{if(!controller.signal.aborted){setPage(data);setError('');}})
        .catch(value=>{if(!controller.signal.aborted)setError(operationError(value));})
        .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    },250);
    return()=>{clearTimeout(timer);controller.abort();};
  },[customer,offset,status?.enabled,tab]);
  useEffect(()=>{
    if(!busy)return;
    const started=Date.now();setElapsed(0);
    const timer=setInterval(()=>setElapsed(Math.floor((Date.now()-started)/1000)),1000);
    return()=>clearInterval(timer);
  },[busy]);
  useEffect(()=>{if(evidence)dialog.current?.showModal();},[evidence]);
  function closeEvidence(){dialog.current?.close();setEvidence(null);}
  async function inspect(id,expected){
    sourceRequest.current?.abort();const controller=new AbortController();sourceRequest.current=controller;
    try{const {data}=await api.get(base+'/sources/'+id,{signal:controller.signal,timeout:30000});
      if(expected&&(data.source.version_id!==expected.version_id||data.source.sha256!==expected.sha256))throw new Error('Source snapshot changed. Refresh the inventory or ask again before comparing evidence.');
      if(!controller.signal.aborted)setEvidence(data);}
    catch(value){if(!controller.signal.aborted)setError(operationError(value));}
  }
  async function exportCsv(){
    setExporting(true);setError('');const controller=new AbortController();requests.current.add(controller);
    try{
      const {data}=await api.get(base+'/incidents/export',{params:{customer:customer.trim()},signal:controller.signal,timeout:30000});
      const url=URL.createObjectURL(new Blob(['\uFEFF'+data.content],{type:'text/csv;charset=utf-8'}));
      const anchor=document.createElement('a');anchor.href=url;anchor.download='incident-inventory.csv';anchor.click();
      setTimeout(()=>URL.revokeObjectURL(url),30000);
    }catch(value){if(!controller.signal.aborted)setError(operationError(value));}
    finally{requests.current.delete(controller);setExporting(false);}
  }
  async function ask(event){
    event.preventDefault();if(busy)return;
    const controller=new AbortController();requests.current.add(controller);setBusy(true);setError('');setAnswer(null);
    try{
      const {data}=await api.post(base+'/query',{question:question.trim(),model,...(selected.length?{source_ids:selected}:{})},
        {signal:controller.signal,timeout:150000});
      if(!controller.signal.aborted)setAnswer(data);
    }catch(value){if(!controller.signal.aborted)setError(operationError(value));}
    finally{requests.current.delete(controller);setBusy(false);}
  }
  if(!admin)return <section className="response-panel"><h1>Administrator access required</h1></section>;
  const summary=page?.summary,coverage=answer?.retrieval_coverage;
  const visible=sources.filter(row=>row.path.toLowerCase().includes(filter.toLowerCase()));
  return <main className="response-centre review-knowledge">
    <div className="response-page-heading"><div><span className="eyebrow">KNOWLEDGE / REVIEW COLLECTION</span><h1>Every report. A traceable incident picture.</h1><p>Explore the accepted extracted snapshot, then ask a focused question.</p></div><Link className="response-button" to="/knowledge">Approved knowledge</Link></div>
    <p className="response-notice">Accepted demo text and tables · Images and Word notes are unverified · Production approval is separate · Content tracing is off</p>
    {error&&<p role="alert" className="response-error">{error}</p>}
    {!status&&!error&&<p role="status">Connecting to the private review collection…</p>}
    {status&&!status.enabled&&<section className="response-panel"><h2>Review collection is not connected</h2><p>An administrator needs to activate the private snapshot worker on the review server.</p></section>}
    {status?.enabled&&<>
      <div className="response-inline review-tabs"><button className={'response-button '+(tab==='inventory'?'primary':'')} aria-pressed={tab==='inventory'} onClick={()=>setTab('inventory')}><FileSearch size={16}/>Incident inventory</button><button className={'response-button '+(tab==='ask'?'primary':'')} aria-pressed={tab==='ask'} onClick={()=>setTab('ask')}><BookOpen size={16}/>Ask the collection</button></div>
      {tab==='inventory'?<>
        <section className="response-panel review-filters"><label>Customer mentioned in reports<input aria-label="Inventory customer" maxLength={100} placeholder="MTN / MTNN, or leave blank for all" value={customer} onChange={event=>{setCustomer(event.target.value);setOffset(0);}}/></label><button className="response-button" disabled={!page||exporting||loading} onClick={exportCsv}><Download size={15}/>{exporting?'Preparing CSV…':'Export all matching groups'}</button></section>
        {summary&&<><div className="review-metrics"><article className="noc-stat"><span>Reports checked</span><strong>{summary.scanned_reports}</strong><small>Every accepted report · no provider calls</small></article><article className="noc-stat"><span>Matching reports</span><strong>{summary.matching_reports}</strong><small>{summary.duplicate_copies} duplicate copies retained</small></article><article className="noc-stat"><span>Incident groups</span><strong>{summary.matching_incident_groups}</strong><small>{summary.groups_needing_identity_review} need identity review</small></article></div><p className="review-scope">{summary.notice} {summary.deferred_files} files deferred. {summary.groups_missing_cause} groups have no extracted cause. Snapshot: <code>{summary.snapshot.slice(0,12)}</code></p></>}
        {loading&&<p role="status">Checking the complete accepted snapshot…</p>}
        <div className="review-inventory">{page?.items.map(item=><article className="response-panel review-incident" key={item.group_id}>
          <header><div><span className="eyebrow">{item.needs_identity_review?'IDENTITY NEEDS REVIEW':'INCIDENT GROUP'}</span><h2>{item.incident_id||'No single incident ID extracted'}</h2></div><span>{item.report_count} reports · {item.unique_content_count} distinct files</span></header>
          <p><strong>Dates as reported:</strong> {item.dates.join(' / ')||'Not extracted'}</p>
          {item.different_cause_text&&<p className="response-notice">Different cause text is reported. Compare the versions before choosing an operational conclusion.</p>}
          <h3>Reported causes</h3>{item.missing_cause?<p>Cause not extracted. Inspect the source evidence; no cause was inferred from the filename.</p>:unique(item.causes.map(c=>c.text)).map((text,index)=><blockquote key={index}>{text}</blockquote>)}
          <details><summary>Compare {item.report_count} source reports and extraction warnings</summary>{item.reports.map(report=><section key={report.id} className="review-report"><strong>{report.path}</strong><small>{report.matches_filter?'Matches customer filter':'Related incident variant'} · SHA-256 {report.source.sha256}</small><p>{report.review_flags.join(' · ')||'No recorded extraction flags'}</p><button className="response-button" onClick={()=>inspect(report.id,report.source)}>Inspect extracted evidence</button></section>)}</details>
        </article>)}</div>
        {page&&!page.items.length&&<p>No reports match this customer mention in the accepted snapshot.</p>}
        {page&&page.items.length>0&&<div className="response-inline"><button className="response-button" disabled={loading||offset===0} onClick={()=>setOffset(Math.max(0,offset-25))}>Previous</button><span>Groups {offset+1}–{offset+page.items.length} of {page.summary.matching_incident_groups}</span><button className="response-button" disabled={loading||page.next_offset===null} onClick={()=>setOffset(page.next_offset)}>Next</button></div>}
      </>:<div className="review-ask-layout"><section className="response-panel">
        <h2>Ask the collection</h2><p>{selected.length?`${selected.length} selected reports`:`All ${status.indexed_sources} accepted reports by default`} · Keyword retrieval · No embedding calls</p>
        <p className="review-scope">Answers use top matching passages. Use Incident inventory to check all matching reports and compare versions.</p>
        <form className="response-form" onSubmit={ask}><label>Your question<textarea required minLength={3} maxLength={4000} rows={3} value={question} onChange={event=>setQuestion(event.target.value)} placeholder="What were the incidents that affected MTN and their causes?"/></label><label>Generation model<select value={model} onChange={event=>setModel(event.target.value)}>{status.models.map(value=><option key={value}>{value}</option>)}</select></label><button className="response-button primary" disabled={busy||!status.generation_available||question.trim().length<3}><Send size={15}/>{busy?`Preparing cited answer · ${elapsed}s`:'Ask knowledge'}</button></form>
        {!status.generation_available&&<p>Gemini generation is not configured. Incident inventory remains available.</p>}
        {answer&&<section className="review-answer" aria-live="polite"><h3>{answer.result.status==='answered'?'Answer with source evidence':'Insufficient evidence'}</h3><p>{answer.result.answer}</p><small>{answer.searched_sources} reports searched · {coverage?.matching_reports??'—'} matching reports · {coverage?.retrieved_reports??'—'} supplied to model · {answer.timings.total}s · {answer.result.model}</small><p>Top matching evidence; this answer is not a complete incident inventory.</p>{answer.result.citations.map(c=><details key={c.chunk_id}><summary>{c.filename} · {c.locator}</summary><pre>{c.full_evidence}</pre><button className="response-button" onClick={()=>inspect(c.source.document_id,c.source)}>Inspect source snapshot</button></details>)}</section>}
      </section><aside className="response-panel review-source-list"><header><h2>Optional source filter</h2><button className="response-button" disabled={busy} onClick={()=>{setSelected([]);setAnswer(null);}}>Clear</button></header><label><Search size={14}/>Find a report<input value={filter} onChange={event=>setFilter(event.target.value)} placeholder="Filename or folder"/></label><div>{visible.map(row=><label key={row.id}><input type="checkbox" disabled={busy} checked={selected.includes(row.id)} onChange={event=>{setSelected(previous=>event.target.checked?[...previous,row.id]:previous.filter(id=>id!==row.id));setAnswer(null);}}/><span>{row.path}<small>{row.chunks} chunks{row.incident_variant_group?' · Report variant':''}</small></span></label>)}</div></aside></div>}
    </>}
    <dialog ref={dialog} className="review-evidence" onCancel={()=>setEvidence(null)}><header><h2>Extracted source evidence</h2><button className="response-button" onClick={closeEvidence}>Close</button></header>{evidence&&<><p>{evidence.path}</p><small>Original SHA-256: {evidence.source.sha256}</small><p>Exact accepted text snapshot. Images and Word notes are not verified.</p>{evidence.chunks.map((chunk,index)=><section key={index}><h3>{chunk.locator}</h3><pre>{chunk.text}</pre></section>)}</>}</dialog>
  </main>;
}
