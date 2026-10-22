import { createElement, useEffect, useRef, useState } from 'react';
import { NavLink, Link, useLocation } from 'react-router-dom';
import { Server, LayoutDashboard, Map, Users, AlertTriangle, HardHat, History, Radio, PanelLeftClose, PanelLeftOpen, LogOut, Clock3, ChevronRight, FileText, Mail, BookOpen, Zap, Menu, X, ChevronsUpDown, ClipboardList } from 'lucide-react';
import { incidentsApi } from '../api/client';
import AssistantProvider from './AssistantProvider';
import FloatingAssistant from './FloatingAssistant';
import ThemeSelector from './ThemeSelector';
import FtthWorkspaceShell from './FtthWorkspaceShell';
import '../styles/afl-brand.css';

const pages = { '/documents/intake': 'OneDrive document intake', '/server-health': 'Server health & deployments', '/energy': 'Energy operations', '/': 'Operations overview', '/response': 'Response centre', '/documents': 'Documents', '/mail': 'Mail triage', '/knowledge': 'Knowledge assistant', '/ftth-operations': 'FTTH operations', '/topology': 'Network topology', '/crm': 'Customers & services', '/provisioning': 'FTTH provisioning', '/incidents': 'Incident response', '/monitoring': 'Monitoring intake', '/audit': 'Audit history' };
const navigation = [
  { group: 'Operations', items: [['/', LayoutDashboard, 'Overview'], ['/incidents', AlertTriangle, 'Incident response'], ['/response', Clock3, 'Response centre'], ['/handover', ClipboardList, 'Shift handover'], ['/energy', Zap, 'Energy operations']] },
  { group: 'Network', items: [['/topology', Map, 'Network topology'], ['/monitoring', Radio, 'Monitoring'], ['/crm', Users, 'Customers & services']] },
  { group: 'Knowledge', items: [['/documents', FileText, 'Documents'], ['/knowledge', BookOpen, 'Knowledge assistant']] },
  { group: 'Communications', items: [['/mail', Mail, 'Mail triage']] },
];
export default function NocAppShell(props) {
  const {pathname}=useLocation();
  const isFtth = pathname === '/ftth' || pathname.startsWith('/ftth/');
  useEffect(() => {
    const preview = document.querySelector('meta[name="robots"]')?.content.includes('noindex');
    document.title = `${preview ? 'DEMO | ' : ''}AFL Networks | ${isFtth ? 'FTTH' : 'NOC'} workspace`;
  }, [isFtth]);
  return isFtth?<FtthWorkspaceShell {...props}/>:<NocWorkspaceShell {...props}/>;
}

function NocWorkspaceShell({ children, identity, onLogout }) {
  const { pathname } = useLocation();
  const [collapsed, setCollapsed] = useState(false), [mobileOpen, setMobileOpen] = useState(false);
  const [now, setNow] = useState(new Date());
  const [feed, setFeed] = useState({ active: null, critical: null, unassigned: null, investigating: null, updated: null, stale: false });
  const sidebar = useRef(null), menuButton = useRef(null);
  useEffect(() => { const timer = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(timer); }, []);
  useEffect(() => {
    const controller = new AbortController(); let timer;
    async function refresh() {
      try {
        const { data } = await incidentsApi.getIncidents({}, { signal: controller.signal });
        const active = data.filter(row => ['open', 'investigating', 'pending'].includes(row.status));
        if (!controller.signal.aborted) setFeed({ active: active.length, critical: active.filter(row => row.severity === 'Critical').length, unassigned: active.filter(row => !row.assigned_engineer_id && !row.responsible_person?.trim()).length, investigating: active.filter(row => row.status === 'investigating').length, updated: new Date(), stale: false });
      } catch { if (!controller.signal.aborted) setFeed(previous => ({ ...previous, stale: true })); }
      if (!controller.signal.aborted) timer = setTimeout(refresh, 30000);
    }
    refresh(); return () => { controller.abort(); clearTimeout(timer); };
  }, []);
  useEffect(() => {
    if (!mobileOpen) return;
    const panel = sidebar.current;
    const previous = document.activeElement;
    panel.querySelector('a,button')?.focus();
    const keyboard = event => {
      if (event.key === 'Escape') setMobileOpen(false);
      if (event.key === 'Tab') {
        const items = [...panel.querySelectorAll('a,button')].filter(el => el.getClientRects().length && !el.disabled);
        if (event.shiftKey && document.activeElement === items[0]) { event.preventDefault(); items.at(-1)?.focus(); }
        else if (!event.shiftKey && document.activeElement === items.at(-1)) { event.preventDefault(); items[0]?.focus(); }
      }
    };
    document.addEventListener('keydown', keyboard);
    return () => { document.removeEventListener('keydown', keyboard); previous?.focus(); };
  }, [mobileOpen]);
  const time = now.toLocaleTimeString('en-GB', { timeZone: 'Africa/Lagos', hour: '2-digit', minute: '2-digit' });
  const hour = Number(now.toLocaleString('en-GB', { timeZone: 'Africa/Lagos', hour: '2-digit', hourCycle: 'h23' }));
  const shift = hour >= 6 && hour < 14 ? 'Morning' : hour >= 14 && hour < 22 ? 'Afternoon' : 'Night';
  const group = pathname.startsWith('/documents/') ? 'Knowledge' : pathname === '/server-health' || pathname === '/audit' ? 'Governance' : navigation.find(item => item.items.some(([path]) => path === pathname))?.group || 'Workspace';
  const pageTitle = pathname === '/handover' ? 'Shift handover' : pathname === '/design/v0' ? 'Previous overview design' : pages[pathname] || 'Workspace';
  const groups = identity.roles.includes('NOC.Admin') ? [...navigation, { group: 'Governance', items: [['/server-health', Server, 'Server health'], ['/audit', History, 'Audit history']] }] : navigation;
  return <AssistantProvider key={pathname}><div className={`noc-shell ${collapsed ? 'nav-collapsed' : ''} ${mobileOpen ? 'mobile-nav-open' : ''}`}>
    <a className="skip-link" href="#workspace-content">Skip to workspace</a>
    {mobileOpen && <button className="nav-scrim" aria-label="Close navigation" tabIndex={-1} onClick={() => setMobileOpen(false)} />}
    <aside ref={sidebar} id="workspace-navigation" className="noc-sidebar" role={mobileOpen ? 'dialog' : undefined} aria-modal={mobileOpen || undefined} aria-label="Workspace navigation">
      <Link to="/" className="noc-brand" aria-label="AFL NOC operations overview" onClick={() => setMobileOpen(false)}><img className="afl-icon-logo" src="/branding/afl-icon.png" alt=""/><span className="nav-copy afl-noc-brand"><img className="afl-full-logo" src="/branding/afl-networks-logo.png" alt="AFL Networks"/><small>NOC workspace</small></span><ChevronsUpDown size={14} className="nav-copy brand-chevron" /></Link>
      <button className="mobile-nav-close noc-icon-button" onClick={() => setMobileOpen(false)} aria-label="Close navigation"><X size={20} /></button>
      <Link to="/ftth" className="noc-ftth-entry" onClick={()=>setMobileOpen(false)}><HardHat size={17}/><span className="nav-copy"><strong>FTTH workspace</strong><small>Operations & provisioning</small></span><ChevronRight size={14} className="nav-copy"/></Link>
      <nav aria-label="Main navigation" className="noc-navigation">{groups.map(section => <div className="nav-group" key={section.group}><p className="nav-group-label nav-copy">{section.group}</p>{section.items.map(([to, Icon, label]) => <NavLink end={to === '/'} key={to} to={to} title={label} onClick={() => setMobileOpen(false)} className={({ isActive }) => `noc-nav-link ${isActive ? 'is-active' : ''}`}>{createElement(Icon, { size: 17 })}<span className="nav-copy">{label}</span>{to === '/incidents' && feed.active > 0 && <span className="nav-count nav-copy">{feed.active}</span>}</NavLink>)}</div>)}</nav>
      <div className="sidebar-bottom"><div className="sidebar-appearance nav-copy"><span>Appearance</span><ThemeSelector /></div><div className="noc-sidebar-footer"><span className="identity-avatar">{identity.verified ? 'NO' : 'DM'}</span><div className="nav-copy"><strong>{identity.verified ? 'NOC workspace' : 'Demo workspace'}</strong><small>{identity.roles.includes('NOC.Admin') ? 'Administrator' : 'NOC operator'} · {identity.verified ? 'Verified' : 'Unverified'}</small></div><button className="noc-icon-button" onClick={onLogout} title="Sign out" aria-label="Sign out"><LogOut size={16} /></button></div></div>
    </aside>
    <main className="noc-main" inert={mobileOpen || undefined}>
      <header className="noc-commandbar"><div className="noc-breadcrumb"><button ref={menuButton} className="noc-icon-button mobile-menu" onClick={() => setMobileOpen(true)} aria-label="Open navigation" aria-expanded={mobileOpen} aria-controls="workspace-navigation"><Menu size={20} /></button><button className="noc-icon-button desktop-menu" onClick={() => setCollapsed(value => !value)} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed}>{collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}</button><span className="breadcrumb-root">{group}</span><ChevronRight size={13} /><strong>{pageTitle}</strong></div><div className="noc-header-summary"><nav className={`noc-header-kpis ${feed.stale ? 'is-stale' : ''}`} aria-label="Incident queue snapshot"><Link to="/response" title={feed.stale ? 'Last known count; incident feed unavailable' : 'Active incidents awaiting an assigned engineer'}><span>Awaiting owner</span><strong>{feed.unassigned ?? '—'}</strong></Link><Link to="/incidents" title={feed.stale ? 'Last known count; incident feed unavailable' : 'Active incidents under investigation'}><span>Investigating</span><strong>{feed.investigating ?? '—'}</strong></Link>{feed.stale && <small>Last known</small>}</nav><div className="noc-clock"><Clock3 size={15} /><span>{time} <b>WAT</b><small>{shift} shift · Lagos</small></span></div></div></header>
      <div className="noc-statusbar"><span className="workspace-indicator"><span className="status-dot" />Operations workspace</span><div className="noc-command-status"><Link to="/incidents" className="command-counter"><span>Active</span><b>{feed.active ?? '—'}</b></Link><Link to="/incidents" className={`command-counter ${feed.critical > 0 ? 'has-alert' : ''}`}><span>Critical</span><b>{feed.critical ?? '—'}</b></Link><span className={`command-sync ${feed.stale ? 'feed-stale' : ''}`}><Radio size={12} />{feed.stale ? 'Feed stale' : feed.updated ? 'Feed synced · 30s' : 'Connecting'}</span></div></div>
      <div id="workspace-content" tabIndex={-1} className={`noc-content ${pathname === '/topology' ? 'noc-content-map' : ''}`}>{children}<footer className="workspace-footer"><span>AFL NOC <span> / </span> Network operations centre</span><span>Africa/Lagos · WAT</span></footer></div>
    </main>
  </div><FloatingAssistant page={pageTitle} /></AssistantProvider>;
}
