import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, AlertTriangle, ArrowUpRight, Clock3, UserRound, Search, Radio } from 'lucide-react';
import { incidentsApi } from '../api/client';
import ShiftActivityLog from '../components/ShiftActivityLog';
import { PageHeader, RefreshButton, MetricPanel, StateBadge, EmptyState, LoadingRows, TableRegion, FilterTabs } from '../components/WorkspaceUI';

const activeStatuses = new Set(['open', 'investigating', 'pending']);
const severityRank = { Critical: 0, High: 1, Medium: 2, Low: 3 };
const severityTone = { Critical: 'danger', High: 'warning', Medium: 'warning', Low: 'accent' };
const timestamp = value => value ? Date.parse(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`) : NaN;
const age = value => {
  const start = timestamp(value);
  if (!Number.isFinite(start)) return 'Unknown';
  const minutes = Math.max(0, Math.floor((Date.now() - start) / 60000));
  return minutes < 60 ? `${minutes}m` : minutes < 1440 ? `${Math.floor(minutes / 60)}h ${minutes % 60}m` : `${Math.floor(minutes / 1440)}d ${Math.floor(minutes % 1440 / 60)}h`;
};
export default function OperationsDashboard() {
  const [incidents, setIncidents] = useState(null), [lastUpdated, setLastUpdated] = useState(null);
  const [error, setError] = useState(''), [refreshing, setRefreshing] = useState(false), [revision, setRevision] = useState(0);
  const [filter, setFilter] = useState('all'), [search, setSearch] = useState('');
  useEffect(() => {
    const controller = new AbortController(); let timer;
    async function refresh() {
      setRefreshing(true);
      try {
        const response = await incidentsApi.getIncidents({}, { signal: controller.signal });
        if (controller.signal.aborted) return;
        if (!Array.isArray(response.data)) throw new Error('Invalid incident response');
        setIncidents(response.data); setLastUpdated(new Date()); setError('');
      } catch { if (!controller.signal.aborted) setError('Incident feed unavailable. Check connectivity or retry. Previously loaded records may be stale.'); }
      finally { if (!controller.signal.aborted) { setRefreshing(false); timer = setTimeout(refresh, 30000); } }
    }
    refresh(); return () => { controller.abort(); clearTimeout(timer); };
  }, [revision]);
  const active = (incidents || []).filter(row => activeStatuses.has(row.status));
  const critical = active.filter(row => row.severity === 'Critical');
  const unassigned = active.filter(row => !row.responsible_person?.trim());
  const queue = [...active].sort((a, b) => (severityRank[a.severity] ?? 4) - (severityRank[b.severity] ?? 4) || (timestamp(a.reported_at) || 0) - (timestamp(b.reported_at) || 0))
    .filter(row => (filter === 'all' || (filter === 'critical' ? row.severity === 'Critical' : !row.responsible_person?.trim())) && `${row.tt_number} ${row.short_description} ${row.network_route} ${row.responsible_person}`.toLowerCase().includes(search.toLowerCase()));
  return <div className="overview-page">
    <PageHeader eyebrow="YOUR SHIFT, AT A GLANCE" title="Operations overview" description="Prioritize what matters. Keep the next response moving."><RefreshButton busy={refreshing} onClick={() => setRevision(value => value + 1)} /></PageHeader>
    <div className="feed-strip" role="status"><span><Radio size={14} />{error ? 'Incident feed unavailable · readings may be stale' : lastUpdated ? 'Incident feed connected' : 'Connecting to incident feed'}</span><span>{lastUpdated ? `Last updated ${lastUpdated.toLocaleTimeString('en-GB', { timeZone: 'Africa/Lagos' })} WAT` : 'Awaiting first successful update'}<i />Auto-refresh 30s</span></div>
    {error && <p className="response-error" role="alert">{error}</p>}
    <div className="overview-metrics"><MetricPanel label="Active incidents" value={incidents ? active.length : '—'} description="Open, investigating or pending" icon={Activity} /><MetricPanel label="Critical incidents" value={incidents ? critical.length : '—'} description="Highest priority for this shift" icon={AlertTriangle} tone="danger" /><MetricPanel label="Awaiting ownership" value={incidents ? unassigned.length : '—'} description="No responsible engineer recorded" icon={UserRound} tone="warning" /></div>
    <section className="queue-panel"><header><div className="section-title"><span className="section-icon"><Activity size={19} /></span><div><h2>Priority incident queue <span className="count-chip">{incidents ? active.length : '—'}</span></h2><p>Highest severity first, then oldest reported.</p></div></div><Link to="/incidents">View all incidents <ArrowUpRight size={15} /></Link></header>
      <div className="queue-filters"><FilterTabs label="Incident queue filter" value={filter} onChange={setFilter} options={[{ value: 'all', label: 'All active' }, { value: 'critical', label: 'Critical' }, { value: 'unassigned', label: 'Unassigned' }]} /><label className="search-control"><Search size={15} /><input aria-label="Search priority incidents" placeholder="Search incidents…" value={search} onChange={event => setSearch(event.target.value)} /></label></div>
      {incidents === null && !error ? <LoadingRows /> : !queue.length ? <EmptyState title={error && !incidents ? 'Incident data unavailable' : 'No incidents in this view'}>{error && !incidents ? 'Retry the feed to load the priority queue.' : 'Change the filters or check back after the next refresh.'}</EmptyState> : <TableRegion label="Priority incidents"><table className="queue-table"><thead><tr>{['Incident / context', 'Severity', 'Status', 'Responsible engineer', 'Age'].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>{queue.slice(0, 12).map(row => <tr key={row.incident_id}><td><Link to="/incidents" className="ticket-ref">{row.tt_number || 'Unnumbered'}</Link><strong>{row.short_description || row.incident_type}</strong><small>{row.network_route || 'Route not recorded'}</small></td><td><StateBadge tone={severityTone[row.severity]}>{row.severity || 'Not set'}</StateBadge></td><td><span className="incident-status"><i data-status={row.status} />{row.status}</span></td><td><span className={`engineer-cell ${row.responsible_person?.trim() ? '' : 'unassigned'}`}><span className="engineer-avatar">{row.responsible_person?.trim() ? row.responsible_person.split(' ').map(name => name[0]).slice(0, 2).join('') : <UserRound size={13} />}</span>{row.responsible_person?.trim() || 'Unassigned'}</span></td><td><span className="incident-age"><Clock3 size={13} />{age(row.reported_at)}</span></td></tr>)}</tbody></table></TableRegion>}
      <footer><span>{Math.min(queue.length, 12)} of {queue.length} matching incidents</span><span>Age from recorded report time · WAT</span></footer>
    </section>
    <div className="overview-log"><ShiftActivityLog /></div>
  </div>;
}
