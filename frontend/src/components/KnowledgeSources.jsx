import {useCallback,useEffect,useRef,useState} from 'react';
import {Download,FileText,RefreshCw} from 'lucide-react';
import {Link} from 'react-router-dom';
import apiClient from '../api/client';
import {operationError,watTime} from '../api/operations';
import '../styles/knowledge.css';

export default function KnowledgeSources({kind,id,search='',onStatus}) {
 const [data,setData]=useState(null),[error,setError]=useState(''),[selected,setSelected]=useState(null);
 const revision=useRef(0);
 const load=useCallback(async(signal)=>{const version=++revision.current;try{const params={search,limit:20};if(kind==='incident')params.incident_id=id;if(kind==='ftth_order')params.order_id=id;
  const [a,b]=await Promise.all([apiClient.get('/documents',{params,signal}),apiClient.get('/knowledge/status',{signal})]);
  if(signal?.aborted||version!==revision.current)return;setData(a.data);onStatus?.(b.data);setError('');
 }catch(error){if(error.code!=='ERR_CANCELED'&&version===revision.current)setError(operationError(error));}},[kind,id,search,onStatus]);
 useEffect(()=>{const controller=new AbortController();const timer=setTimeout(()=>load(controller.signal),0);return()=>{clearTimeout(timer);controller.abort();};},[load]);
 async function download(record){const version=record.latest_version;if(!version)return;try{const result=await apiClient.get(`/documents/${record.document_id}/versions/${version.version_id}/download`,{responseType:'blob'});const url=URL.createObjectURL(result.data);const anchor=document.createElement('a');anchor.href=url;anchor.download=version.original_filename;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}catch(error){setError(error.response?.status===503?'Source storage or integrity verification failed.':operationError(error));}}
 const selectedRecord=data?.items.find(value=>value.document_id===selected);
 return <section className="knowledge-sources"><header><div><h2><FileText size={16}/>{id?'Linked documents':'Source catalogue'}</h2><small>{data?`${data.total} accessible ${id?'linked ':''}documents`:'Loading authorized sources…'}</small></div><button className="noc-icon-button" aria-label="Refresh knowledge sources" onClick={()=>load()}><RefreshCw size={16}/></button></header>
  <p className="knowledge-source-note">Catalogue records are unreviewed and not indexed. They are available for inspection; no answer or citation has been generated from them.</p>
  {error&&<p role="alert" className="response-error">{error}</p>}
  <div className="knowledge-source-list">{data?.items.map(record=><button key={record.document_id} className={`knowledge-source-card ${selected===record.document_id?'selected':''}`} onClick={()=>setSelected(record.document_id)}><span>{record.document_type.replaceAll('_',' ')}</span><strong>{record.title}</strong><small>Revision {record.latest_version?.revision} · {record.review_state}</small><small>{record.latest_version?.original_filename}</small></button>)}{data&&!data.items.length&&<p className="knowledge-empty">{id?'No directly linked documents are visible for this case.':'No documents match this title search. Upload and link sources under Documents.'}</p>}</div>
  {selectedRecord&&<section className="knowledge-source-detail" aria-label="Selected source version"><h3>{selectedRecord.title}</h3><p>Revision {selectedRecord.latest_version?.revision} · {watTime(selectedRecord.latest_version?.created_at)}</p><small>{selectedRecord.latest_version?.original_filename}</small><code>{selectedRecord.latest_version?.sha256}</code><p>Page, section or sheet citations will be available after extraction and retrieval are connected.</p><button className="response-button" disabled={!selectedRecord.latest_version} onClick={()=>download(selectedRecord)}><Download size={14}/>Download original revision</button></section>}
  {data&&data.total>20&&<p className="knowledge-source-note">Showing the first 20 results. Use Documents for pagination.</p>}<Link className="response-button knowledge-manage" to="/documents">Manage documents and revisions</Link>
 </section>;
}
