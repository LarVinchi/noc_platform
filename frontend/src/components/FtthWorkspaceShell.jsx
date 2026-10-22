import { createElement, useEffect, useRef, useState } from 'react';
import { NavLink, Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Cable, MapPinned, CalendarDays, FileText, History, Menu, X, ArrowLeft, LogOut } from 'lucide-react';
import AssistantProvider from './AssistantProvider';
import FloatingAssistant from './FloatingAssistant';
import ThemeSelector from './ThemeSelector';
import '../styles/ftth-workspace.css';

const navigation=[['/ftth',LayoutDashboard,'Overview'],['/ftth/provisioning',Cable,'Provisioning'],['/ftth/service-areas',MapPinned,'Service areas'],['/ftth/daily-plans',CalendarDays,'Daily plans & closure'],['/ftth/activity',CalendarDays,'Recorded activity'],['/ftth/network-reports',FileText,'Network reports'],['/ftth/history',History,'Lifecycle & faults']];

export default function FtthWorkspaceShell({children,identity,onLogout}) {
  const {pathname}=useLocation(),[mobile,setMobile]=useState(false);
  const panel=useRef(null),trigger=useRef(null);
  const title=navigation.find(([path])=>path===pathname)?.[2]||'FTTH workspace';
  useEffect(()=>{
    if(!mobile)return;
    const previous=document.activeElement;panel.current?.querySelector('a,button')?.focus();
    function keyboard(event){
      if(event.key==='Escape')setMobile(false);
      if(event.key!=='Tab')return;
      const items=[...panel.current.querySelectorAll('a,button')].filter(n=>n.getClientRects().length&&!n.disabled);
      if(event.shiftKey&&document.activeElement===items[0]){event.preventDefault();items.at(-1)?.focus();}
      else if(!event.shiftKey&&document.activeElement===items.at(-1)){event.preventDefault();items[0]?.focus();}
    }
    document.addEventListener('keydown',keyboard);
    return()=>{document.removeEventListener('keydown',keyboard);previous?.focus();};
  },[mobile]);
  return <AssistantProvider key={pathname}><div className={`ftth-shell ${mobile?'ftth-mobile-open':''}`}>
    <a className="skip-link" href="#workspace-content">Skip to FTTH workspace</a>
    {mobile&&<button className="ftth-scrim" aria-label="Close FTTH navigation" tabIndex={-1} onClick={()=>setMobile(false)}/>}
    <aside ref={panel} id="ftth-workspace-navigation" className="ftth-sidebar" role={mobile?'dialog':undefined} aria-modal={mobile||undefined} aria-label="FTTH workspace navigation">
      <Link to="/ftth" className="ftth-brand" onClick={()=>setMobile(false)}><img src="/branding/afl-networks-logo.png" alt="AFL Networks"/><span>FIBER OPERATIONS</span></Link>
      <button className="ftth-mobile-close" aria-label="Close FTTH navigation" onClick={()=>setMobile(false)}><X size={20}/></button>
      <div className="ftth-workspace-switch"><span className="ftth-live-dot"/><div><strong>FTTH workspace</strong><small>Operations & provisioning</small></div></div>
      <nav aria-label="FTTH navigation"><span className="ftth-nav-label">WORKSPACE</span>{navigation.map(([to,Icon,label])=><NavLink key={to} end to={to} className={({isActive})=>isActive?'is-active':''} onClick={()=>setMobile(false)}>{createElement(Icon,{size:18})}{label}</NavLink>)}</nav>
      <div className="ftth-sidebar-bottom"><Link to="/" className="ftth-return"><ArrowLeft size={16}/>Return to NOC workspace</Link><div className="ftth-appearance"><span>Appearance</span><ThemeSelector/></div><div className="ftth-identity"><div><strong>{identity.verified?'AFL workspace':'Design preview'}</strong><small>{identity.roles.includes('NOC.Admin')?'Administrator':'NOC operator'} · {identity.verified?'Verified':'Unverified'}</small></div><button aria-label="Sign out" onClick={onLogout}><LogOut size={17}/></button></div></div>
    </aside>
    <main className="ftth-shell-main" inert={mobile||undefined}><header className="ftth-commandbar"><div><button ref={trigger} className="ftth-mobile-trigger" aria-label="Open FTTH navigation" aria-expanded={mobile} aria-controls="ftth-workspace-navigation" onClick={()=>setMobile(true)}><Menu size={21}/></button><span>FTTH workspace</span><b>/</b><strong>{title}</strong></div><span className="ftth-zone">Lagos · WAT</span></header><div id="workspace-content" tabIndex={-1} className="noc-content ftth-shell-content">{children}</div><footer className="ftth-shell-footer"><span>AFL Networks · Every connection counts.</span><span>Shared NOC identity and provisioning records</span></footer></main>
  </div><FloatingAssistant page={'FTTH · '+title}/></AssistantProvider>;
}
