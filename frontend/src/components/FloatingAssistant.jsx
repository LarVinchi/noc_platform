import {useEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {Link} from 'react-router-dom';
import {Bot,MessageSquare,Minus,Send,BookOpen,Unplug,ChevronRight} from 'lucide-react';
import {useAssistant} from './AssistantContext';
import KnowledgeSources from './KnowledgeSources';
import {watTime} from '../api/operations';
import '../styles/knowledge.css';
import '../styles/assistant.css';

function AssistantConversation({activeCase,page}) {
 const [question,setQuestion]=useState(''),[tab,setTab]=useState('chat');
 const record=activeCase?.record,kind=activeCase?.kind;
 const title=record?(kind==='incident'?(record.tt_number||'Unnumbered incident'):(record.fn_number||record.customer_name||'FTTH case')):page;
 const id=kind==='incident'?record?.incident_id:record?.order_id;
 const facts=record?(kind==='incident'?[['Status',record.status],['Severity',record.severity||'Unset'],['Engineer',record.responsible_person||'Unassigned'],['Reported',watTime(record.reported_at)]]:[['Customer',record.customer_name],['Provider',record.isp],['Stage',record.status],['Work order',record.work_order_id||'Not recorded']]):[];
 const prompts=kind==='incident'?['Find approved RCAs related to this incident.','What evidence is missing before closure?']:kind==='ftth_order'?['What is missing before NOC acceptance?','Find the approved customer handover for this FN.']:['Find RCAs for recurring fibre faults.','Find an approved customer handover by FN number.'];
 return <><div className="assistant-context"><span>{record?'ACTIVE CASE':'CURRENT PAGE'}</span><strong>{title}</strong><small>{record?'Case facts and directly linked documents':'Browse authorized sources across the workspace'}</small></div>
  <div className="assistant-tabs" role="tablist" aria-label="Assistant panels"><button id="assistant-chat-tab" role="tab" aria-controls="assistant-chat-panel" aria-selected={tab==='chat'} onClick={()=>setTab('chat')}><MessageSquare size={14}/>Chat</button><button id="assistant-sources-tab" role="tab" aria-controls="assistant-sources-panel" aria-selected={tab==='sources'} onClick={()=>setTab('sources')}><BookOpen size={14}/>Sources</button></div>
  {tab==='chat'?<div id="assistant-chat-panel" role="tabpanel" aria-labelledby="assistant-chat-tab" className="assistant-chat"><div className="assistant-chat-scroll"><div className="assistant-message"><span><Bot size={16}/>NOC assistant · preview</span><p>{record?'I can show the record facts and linked documents for this case.':'Open a case to bring its details into this panel, or browse the source catalogue.'}</p><p>Case-aware generation is not connected. Open the Knowledge workspace to ask about explicitly approved runbooks.</p></div>{record&&<details className="assistant-record"><summary>View record facts</summary><dl>{facts.map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl><small>Platform data, not a generated answer.</small></details>}<div className="knowledge-prompts">{prompts.map(prompt=><button key={prompt} onClick={()=>setQuestion(prompt)}>{prompt}</button>)}</div></div><form className="assistant-composer" onSubmit={event=>event.preventDefault()}><label className="knowledge-question">Draft a question<textarea aria-label="Assistant question" maxLength={4000} rows={3} value={question} onChange={event=>setQuestion(event.target.value)} placeholder="Ask about your NOC operations…"/></label><div><small>Local draft · not saved or sent</small><button type="submit" aria-label="Send question — case integration pending" disabled><Send size={17}/></button></div></form></div>:<div id="assistant-sources-panel" role="tabpanel" aria-labelledby="assistant-sources-tab" className="assistant-source-panel"><KnowledgeSources kind={kind} id={id}/></div>}
 </>;
}

export default function FloatingAssistant({page}) {
 const {open,setOpen,activeCase}=useAssistant();
 const [mobile,setMobile]=useState(()=>window.matchMedia('(max-width:600px)').matches);
 const [portalHost,setPortalHost]=useState(document.body);
 const panel=useRef(null),returnFocus=useRef(null);
 function show(){returnFocus.current=document.activeElement;setOpen(true);}
 useEffect(()=>{const media=window.matchMedia('(max-width:600px)');const changed=event=>setMobile(event.matches);media.addEventListener('change',changed);return()=>media.removeEventListener('change',changed);},[]);
 useEffect(()=>{const changed=()=>setPortalHost(document.fullscreenElement||document.body);document.addEventListener('fullscreenchange',changed);return()=>document.removeEventListener('fullscreenchange',changed);},[]);
 useEffect(()=>{
  if(!open)return;
  if(!panel.current?.contains(document.activeElement))returnFocus.current=document.activeElement;
  panel.current?.focus();
  const escape=event=>{
   if(event.key==='Escape'){event.preventDefault();event.stopPropagation();setOpen(false);}
   if(event.key==='Tab'&&window.matchMedia('(max-width:600px)').matches){
    const controls=[...panel.current.querySelectorAll('button:not(:disabled),a[href],textarea,summary,[tabindex="0"]')];
    const first=controls[0],last=controls.at(-1);
    if(event.shiftKey&&(document.activeElement===first||document.activeElement===panel.current)){event.preventDefault();last?.focus();}
    else if(!event.shiftKey&&(document.activeElement===last||document.activeElement===panel.current)){event.preventDefault();first?.focus();}
   }
  };
  document.addEventListener('keydown',escape,true);
  return ()=>{document.removeEventListener('keydown',escape,true);if(returnFocus.current?.isConnected)returnFocus.current.focus();};
 },[open,setOpen]);
 const key=activeCase?`${activeCase.kind}:${activeCase.record.incident_id||activeCase.record.order_id}`:page;
 return createPortal(<div className="assistant-widget">{open&&<section ref={panel} tabIndex={-1} id="noc-assistant-panel" role="dialog" aria-modal={mobile} aria-label="NOC AI assistant" className="assistant-floating-panel"><header><div className="assistant-avatar"><Bot size={23}/></div><div><h2>NOC assistant</h2><span><Unplug size={11}/>Case integration pending</span></div><button className="noc-icon-button" onClick={()=>setOpen(false)} aria-label="Minimize assistant"><Minus size={20}/></button></header><AssistantConversation key={key} activeCase={activeCase} page={page}/><footer><Link to="/knowledge" onClick={()=>setOpen(false)}>Open Knowledge workspace<ChevronRight size={13}/></Link></footer></section>}<button className="assistant-launcher" onClick={()=>open?setOpen(false):show()} aria-label={open?'Minimize NOC assistant':'Open NOC assistant'} aria-expanded={open} aria-controls="noc-assistant-panel"><Bot size={24}/><span>AI assistant</span><i aria-hidden="true"/></button></div>,portalHost);
}
