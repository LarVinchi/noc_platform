import { createElement, useEffect, useState } from 'react';
import { NavLink, Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Map, Users, AlertTriangle, HardHat, History, Radio, PanelLeftClose, PanelLeftOpen, Network, LogOut, Clock3, ChevronRight } from 'lucide-react';
import { incidentsApi } from '../api/client';

const pages = { '/': 'Operations overview', '/topology': 'Network topology', '/crm': 'Customers & services', '/provisioning': 'FTTH provisioning', '/incidents': 'Incident response', '/monitoring': 'Monitoring intake', '/audit': 'Audit history' };
const navigation = [
  { group: 'OPERATIONS', items: [['/', LayoutDashboard, 'Overview'], ['/incidents', AlertTriangle, 'Incident response'], ['/provisioning', HardHat, 'Provisioning']] },
  { group: 'NETWORK', items: [['/topology', Map, 'Network topology'], ['/monitoring', Radio, 'Monitoring'], ['/crm', Users, 'Customers & services']] },
];

export default function NocAppShell({ children, identity, onLogout }) {
  const { pathname } = useLocation();
  const [collapsed, setCollapsed] = useState(() => { try { return localStorage.getItem('noc.sidebar') === 'collapsed' || window.innerWidth < 900; } catch { return false; } });
  const [now, setNow] = useState(new Date());
  const [feed, setFeed] = useState({ active: null, critical: null, updated: null, stale: false });
  useEffect(() => { const timer = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(timer); }, []);
  useEffect(() => {
    const controller = new AbortController(); let timer;
    async function refresh() {
      try {
        const { data } = await incidentsApi.getIncidents({}, { signal: controller.signal });
        const active = data.filter(row => ['open', 'investigating', 'pending'].includes(row.status));
        if (!controller.signal.aborted) setFeed({ active: active.length, critical: active.filter(row => row.severity === 'Critical').length, updated: new Date(), stale: false });
      } catch { if (!controller.signal.aborted) setFeed(previous => ({ ...previous, stale: true })); }
      if (!controller.signal.aborted) timer = setTimeout(refresh, 30000);
    }
    refresh(); return () => { controller.abort(); clearTimeout(timer); };
  }, []);
  function toggle() { setCollapsed(previous => { const next = !previous; try { localStorage.setItem('noc.sidebar', next ? 'collapsed' : 'expanded'); } catch { /* optional preference */ } return next; }); }
  const time = now.toLocaleTimeString('en-GB', { timeZone: 'Africa/Lagos' });
  const hour = Number(now.toLocaleString('en-GB', { timeZone: 'Africa/Lagos', hour: '2-digit', hourCycle: 'h23' }));
  const shift = hour >= 6 && hour < 14 ? 'Morning' : hour >= 14 && hour < 22 ? 'Afternoon' : 'Night';
  return <div className={`noc-shell ${collapsed ? 'nav-collapsed' : ''}`}>
    <aside className="noc-sidebar">
      <Link to="/" className="noc-brand" aria-label="NOC operations overview"><span className="noc-brand-mark"><Network size={23} /></span><span className="nav-copy"><strong>AFL<span>NOC</span></strong><small>NETWORK OPERATIONS</small></span></Link>
      <nav aria-label="Main navigation" className="noc-navigation">
        {navigation.map(group => <div className="nav-group" key={group.group}><p className="nav-group-label nav-copy">{group.group}</p>{group.items.map(([to, Icon, label]) => <NavLink end={to === '/'} key={to} to={to} title={label} className={({ isActive }) => `noc-nav-link ${isActive ? 'is-active' : ''}`}>{createElement(Icon, { size: 19 })}<span className="nav-copy">{label}</span>{to === '/incidents' && feed.active > 0 && <span className="nav-count nav-copy">{feed.active}</span>}</NavLink>)}</div>)}
        {identity.roles.includes('NOC.Admin') && <div className="nav-group"><p className="nav-group-label nav-copy">GOVERNANCE</p><NavLink to="/audit" title="Audit history" className={({ isActive }) => `noc-nav-link ${isActive ? 'is-active' : ''}`}><History size={19} /><span className="nav-copy">Audit history</span></NavLink></div>}
      </nav>
      <div className="noc-sidebar-footer"><span className={`identity-dot ${identity.verified ? 'verified' : ''}`} /><div className="nav-copy"><strong>{identity.verified ? 'Company workspace' : 'LOCAL PREVIEW'}</strong><small>{identity.verified ? identity.roles.join(' · ') : 'Unverified development identity'}</small></div></div>
    </aside>
    <main className="noc-main">
      <header className="noc-commandbar">
        <div className="noc-breadcrumb"><button className="noc-icon-button" onClick={toggle} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed}>{collapsed ? <PanelLeftOpen size={19} /> : <PanelLeftClose size={19} />}</button><span className="breadcrumb-root">Control centre</span><ChevronRight size={13} /><strong>{pages[pathname] || 'Workspace'}</strong></div>
        <div className="noc-command-status"><Link to="/incidents" className="command-counter"><i className={feed.stale ? 'stale' : 'accent'} /><span>ACTIVE</span><b>{feed.active ?? '—'}</b></Link><Link to="/incidents" className={`command-counter critical ${feed.critical > 0 ? 'has-alert' : ''}`}><span>CRITICAL</span><b>{feed.critical ?? '—'}</b></Link><span className="command-sync">{feed.stale ? 'FEED STALE' : feed.updated ? 'SYNC 30s' : 'CONNECTING'}</span><div className="noc-clock"><Clock3 size={14} /><span>{time}<small> WAT · {shift} shift</small></span></div><button className="noc-icon-button" onClick={onLogout} title="Sign out" aria-label="Sign out"><LogOut size={17} /></button></div>
      </header>
      <div className={`noc-content ${pathname === '/topology' ? 'noc-content-map' : ''}`}>{children}</div>
    </main>
  </div>;
}
