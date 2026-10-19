import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, ArrowRight, ArrowUpRight, Check, ChevronRight, CircleDot, Clock3, ClipboardList, Layers3, MapPin, Radio, RefreshCw, Search, ShieldAlert, SlidersHorizontal, UserRound, X } from 'lucide-react';
import { activitiesApi, incidentsApi } from '../api/client';
import { watTime } from '../api/operations';
import '../styles/control-room.css';

const activeStatuses = new Set(['open', 'investigating', 'pending']);
const severityRank = { Critical: 0, High: 1, Medium: 2, Low: 3 };
const timestamp = value => value ? Date.parse(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`) : NaN;
const age = value => {
  const start = timestamp(value);
  if (!Number.isFinite(start)) return 'Not recorded';
  const minutes = Math.max(0, Math.floor((Date.now() - start) / 60000));
  return minutes < 60 ? `${minutes}m` : minutes < 1440 ? `${Math.floor(minutes / 60)}h ${minutes % 60}m` : `${Math.floor(minutes / 1440)}d ${Math.floor(minutes % 1440 / 60)}h`;
};
const needsOwner = incident => !incident.responsible_person?.trim() && !incident.assigned_engineer_id;
const owner = incident => incident.responsible_person?.trim() || (incident.assigned_engineer_id ? 'Assigned engineer' : 'Unassigned');
function Severity({ value }) { return <span className={`control-severity severity-${value?.toLowerCase() || 'unknown'}`}><i />{value || 'Not set'}</span>; }

function IncidentFocus({ incident, stale }) {
  if (!incident) return <aside className="control-focus"><div className="control-focus-empty"><Layers3 size={30} /><h2>Room to focus</h2><p>Select an incident to see its recorded context and response milestones.</p></div></aside>;
  return <aside className="control-focus" aria-label="Selected incident details">
    <header><span className="control-eyebrow">INCIDENT FOCUS</span><span>{incident.tt_number || 'Unnumbered'}</span></header>
    <div className="control-focus-body"><div className="control-focus-badges"><Severity value={incident.severity} /><span className="control-status">{incident.status}</span></div>
      <h2>{incident.short_description || incident.incident_type || 'Incident details'}</h2>
      {stale && <p className="control-warning">Last known record. The incident feed is unavailable.</p>}
      <dl className="control-context"><div><dt><MapPin size={13} />Route / location</dt><dd>{incident.network_route || incident.network_node || 'Not recorded'}</dd></div><div><dt><UserRound size={13} />Responsible engineer</dt><dd>{owner(incident)}{incident.assigned_engineer_id && !incident.responsible_person?.trim() && <small>See response centre for engineer details</small>}</dd></div><div><dt><Layers3 size={13} />Category</dt><dd>{incident.ticket_category || incident.incident_type || 'Not recorded'}</dd></div></dl>
      <div className="control-milestones"><h3>Response milestones</h3>{[['Reported', incident.reported_at], ['Acknowledged', incident.acknowledged_at], ['Resolved', incident.resolved_at]].map(([label, value]) => <div className={value ? 'is-recorded' : ''} key={label}><span className="control-step-mark">{value ? <Check size={11} /> : <CircleDot size={11} />}</span><div><strong>{label}</strong><small>{value ? watTime(value) : 'Not recorded'}</small></div></div>)}</div>
      <Link className="control-primary" to="/response">Open response centre <ArrowUpRight size={15} /></Link><p className="control-evidence-note">Recorded facts only. Live route diagnostics are not connected to this view.</p>
    </div></aside>;
}

function ShiftNotes({ entries, error, loading }) {
  return <section className="control-handover"><header><div><span className="control-eyebrow">LEAVE CONTEXT, NOT GUESSWORK</span><h2>From the handover desk <span>{entries.length}</span></h2></div><Link to="/handover">Open activity log <ArrowUpRight size={15} /></Link></header>
    {error && <p className="control-warning">Activity feed unavailable. Previously loaded entries may be stale.</p>}
    <div className="control-note-grid">{loading ? <p className="control-empty">Loading shift activity…</p> : !entries.length ? <p className="control-empty">No activity recorded yet. Leave a handover using the activity log.</p> : [...entries].sort((a, b) => timestamp(b.created_at) - timestamp(a.created_at)).slice(0, 2).map(entry => <article key={entry.activity_id}><div className="control-note-meta"><span><ClipboardList size={13} />{entry.category || 'Activity'}</span><time>{age(entry.created_at)} ago</time></div><h3>{entry.title}</h3><p>{entry.description || 'No additional notes recorded.'}</p><footer><span className="control-avatar">{entry.person?.split(' ').map(part => part[0]).slice(0, 2).join('') || '—'}</span><span>{entry.person || 'Name not recorded'}</span><span className={entry.status === 'Completed' ? 'is-complete' : ''}>{entry.status || 'Not recorded'}</span></footer></article>)}</div>
  </section>;
}

export default function ControlRoomOverview() {
  const [incidents, setIncidents] = useState(null), [entries, setEntries] = useState(null);
  const [updated, setUpdated] = useState(null), [error, setError] = useState(''), [activityError, setActivityError] = useState(false);
  const [refreshing, setRefreshing] = useState(false), [revision, setRevision] = useState(0);
  const [filter, setFilter] = useState('all'), [search, setSearch] = useState(''), [selected, setSelected] = useState(null), [dense, setDense] = useState(false);
  useEffect(() => {
    const controller = new AbortController(); let timer;
    async function refresh() {
      setRefreshing(true);
      const [incidentResult, activityResult] = await Promise.allSettled([incidentsApi.getIncidents({}, { signal: controller.signal }), activitiesApi.list({ signal: controller.signal })]);
      if (controller.signal.aborted) return;
      if (incidentResult.status === 'fulfilled' && Array.isArray(incidentResult.value.data)) { setIncidents(incidentResult.value.data); setUpdated(new Date()); setError(''); }
      else setError('Incident feed unavailable. Displayed records may be stale.');
      if (activityResult.status === 'fulfilled' && Array.isArray(activityResult.value.data)) { setEntries(activityResult.value.data); setActivityError(false); }
      else setActivityError(true);
      setRefreshing(false); timer = setTimeout(refresh, 30000);
    }
    refresh(); return () => { controller.abort(); clearTimeout(timer); };
  }, [revision]);
  const active = (incidents || []).filter(row => activeStatuses.has(row.status));
  const critical = active.filter(row => row.severity === 'Critical'), unassigned = active.filter(needsOwner);
  const queue = [...active].sort((a, b) => (severityRank[a.severity] ?? 4) - (severityRank[b.severity] ?? 4) || (timestamp(a.reported_at) || 0) - (timestamp(b.reported_at) || 0))
    .filter(row => (filter === 'all' || (filter === 'critical' ? row.severity === 'Critical' : needsOwner(row))) && `${row.tt_number} ${row.short_description} ${row.network_route} ${row.network_node} ${row.responsible_person}`.toLowerCase().includes(search.toLowerCase()));
  const focused = queue.find(row => row.incident_id === selected) || queue[0];
  const date = new Intl.DateTimeFormat('en-GB', { timeZone: 'Africa/Lagos', weekday: 'long', day: 'numeric', month: 'long' }).format(new Date());
  return <div className="control-overview">
    <header className="control-page-heading"><div><div className="control-page-kicker"><span />OPERATIONS WORKSPACE <i>/</i> {date}</div><h1>Every incident.<br className="control-mobile-break" /> In focus<span>.</span></h1><p>Priorities, ownership and handover. One clear operational picture.</p></div><Link to="/incidents" className="control-primary"><ArrowUpRight size={16} />Incident workspace</Link></header>
    <div className={`control-feed ${error ? 'has-error' : ''}`} role="status"><span><i />{error ? 'Feed unavailable · last known records' : updated ? 'Incident feed connected' : 'Connecting to incident feed'}</span><span><Radio size={13} />Refreshes every 30s <b>/</b>{updated ? `Updated ${updated.toLocaleTimeString('en-GB', { timeZone: 'Africa/Lagos', hour: '2-digit', minute: '2-digit' })} WAT` : 'Awaiting first update'}<button onClick={() => setRevision(value => value + 1)} disabled={refreshing} aria-label="Refresh overview"><RefreshCw size={14} className={refreshing ? 'control-spin' : ''} /></button></span></div>
    <div className="control-metrics"><button onClick={() => setFilter('all')} className={filter === 'all' ? 'is-active' : ''}><div><span className="control-metric-icon"><Layers3 size={19} /></span><ArrowUpRight size={16} /></div><span>Active incidents</span><strong>{incidents ? active.length.toString().padStart(2, '0') : '—'}</strong><small>Open, investigating & pending</small></button><button onClick={() => setFilter('critical')} className={`is-critical ${filter === 'critical' ? 'is-active' : ''}`}><div><span className="control-metric-icon"><ShieldAlert size={19} /></span><span className="control-metric-hint">{critical.length ? 'Needs attention' : 'No critical records'}</span></div><span>Critical incidents</span><strong>{incidents ? critical.length.toString().padStart(2, '0') : '—'}</strong><small>Highest priority for this shift</small></button><button onClick={() => setFilter('unassigned')} className={filter === 'unassigned' ? 'is-active' : ''}><div><span className="control-metric-icon"><UserRound size={19} /></span><ArrowUpRight size={16} /></div><span>Awaiting ownership</span><strong>{incidents ? unassigned.length.toString().padStart(2, '0') : '—'}</strong><small>No assigned engineer or named owner</small></button></div>
    <div className="control-workbench"><div className="control-main-column"><section className="control-queue"><header><div><span className="control-section-mark"><Activity size={18} /></span><h2>The response queue <span>{active.length}</span></h2></div><button className="control-density" aria-label="Compact incident rows" aria-pressed={dense} onClick={() => setDense(value => !value)}><SlidersHorizontal size={14} />{dense ? 'Compact' : 'Comfortable'}</button></header>
      <div className="control-queue-toolbar"><div className="control-filters" role="group" aria-label="Filter incident queue">{[['all', 'All active', active.length], ['critical', 'Critical', critical.length], ['unassigned', 'Unassigned', unassigned.length]].map(([value, label, count]) => <button key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}<span>{count}</span></button>)}</div><label className="control-search"><Search size={15} /><input aria-label="Search response queue" placeholder="Find a ticket or route…" value={search} onChange={event => setSearch(event.target.value)} />{search && <button onClick={() => setSearch('')} aria-label="Clear incident search"><X size={13} /></button>}</label></div>
      {error && <p className="control-warning" role="alert">{error}</p>}
      <div className="control-table-scroll" role="region" aria-label="Response queue" tabIndex={0}><table className={dense ? 'is-compact' : ''}><thead><tr><th>Incident / context</th><th>Priority</th><th>Status</th><th>Age</th><th><span className="sr-only">View details</span></th></tr></thead><tbody>{queue.map(row => <tr className={focused?.incident_id === row.incident_id ? 'is-selected' : ''} key={row.incident_id}><td><button className="control-ticket" aria-label={`View ${row.tt_number || 'incident'} details`} aria-pressed={focused?.incident_id === row.incident_id} onClick={() => setSelected(row.incident_id)}><span>{row.tt_number || 'Unnumbered'}<i>{row.ticket_category || 'Incident'}</i></span><strong>{row.short_description || row.incident_type}</strong><small><MapPin size={11} />{row.network_route || row.network_node || 'Location not recorded'}</small></button></td><td><Severity value={row.severity} /></td><td><span className={`control-status status-${row.status}`}><i />{row.status}</span></td><td className="control-age">{age(row.reported_at)}</td><td><button className="control-row-open" aria-label={`Inspect ${row.tt_number || 'incident'}`} onClick={() => setSelected(row.incident_id)}><ChevronRight size={17} /></button></td></tr>)}</tbody></table></div>
      {!queue.length && <div className="control-queue-empty"><Search size={25} /><h3>{incidents === null ? error ? 'Incident data unavailable' : 'Loading the response queue' : 'A clear queue for this view'}</h3><p>{incidents === null ? 'Waiting for a successful incident feed update.' : 'Try another filter or search to find a recorded incident.'}</p></div>}
      <footer><span><CircleDot size={12} />{queue.length} matching incident{queue.length === 1 ? '' : 's'}</span><Link to="/incidents">All incidents <ArrowRight size={13} /></Link></footer>
    </section><ShiftNotes entries={entries || []} error={activityError} loading={entries === null && !activityError} /></div><IncidentFocus incident={focused} stale={!!error} /></div>
    <footer className="control-page-footer"><span><span className="control-footer-mark">A</span>AFL NOC <i>/</i> Keeping things connected.</span><span><Clock3 size={12} />Africa/Lagos · WAT</span></footer>
  </div>;
}
