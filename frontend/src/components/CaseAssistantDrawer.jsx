import {useEffect,useState} from 'react';
import {Sparkles,X,Unplug} from 'lucide-react';
import KnowledgeSources from './KnowledgeSources';
import {watTime} from '../api/operations';
import '../styles/knowledge.css';

export default function CaseAssistantDrawer({kind,record,onClose}) {
 const [question,setQuestion]=useState('');
 const id=kind==='incident'?record.incident_id:record.order_id;
 const title=kind==='incident'?(record.tt_number||'Unnumbered incident'):(record.fn_number||record.customer_name||'FTTH case');
 useEffect(()=>{const escape=event=>{if(event.key==='Escape'){event.preventDefault();event.stopPropagation();onClose();}};document.addEventListener('keydown',escape,true);return()=>document.removeEventListener('keydown',escape,true);},[onClose]);
 const facts=kind==='incident'?[['Status',record.status],['Severity',record.severity||'Unset'],['Engineer',record.responsible_person||'Unassigned'],['Reported',watTime(record.reported_at)]]:
  [['Customer',record.customer_name],['Provider',record.isp],['Stage',record.status],['Work order',record.work_order_id||'Not recorded'],['Activated service',record.activated_service_id?'Recorded':'Not activated']];
 const prompts=kind==='incident'?['Find approved RCAs related to this incident.','What evidence is missing before closure?']:['What is missing before NOC acceptance?','Find the approved customer handover for this FN.'];
 return <aside className="case-assistant-drawer" role="dialog" aria-modal="false" aria-label="Case knowledge assistant"><header><div><span className="eyebrow">CONTEXTUAL KNOWLEDGE ASSISTANT</span><h2><Sparkles size={18}/>{title}</h2></div><button className="noc-icon-button" aria-label="Close case assistant" onClick={onClose}><X size={20}/></button></header><div className="case-assistant-body"><p className="knowledge-offline"><Unplug size={16}/>RAG not connected. Case facts and linked files are available.</p><section className="knowledge-case-facts"><h3>Record facts</h3><dl>{facts.map(([name,value])=><div key={name}><dt>{name}</dt><dd>{value}</dd></div>)}</dl><small>These fields come from the platform record, not a generated answer.</small></section><div className="knowledge-prompts">{prompts.map(prompt=><button key={prompt} onClick={()=>setQuestion(prompt)}>{prompt}</button>)}</div><label className="knowledge-question">Draft a question<textarea aria-label="Case assistant question" maxLength={4000} rows={3} value={question} onChange={event=>setQuestion(event.target.value)} placeholder="Ask about this case when the knowledge engine is connected…"/></label><button className="response-button primary" disabled>Ask — RAG connection pending</button><p className="knowledge-source-note">Your question stays in this open drawer. It is not submitted, saved or sent to a model. Switching cases clears the draft.</p><KnowledgeSources kind={kind} id={id}/></div></aside>;
}
