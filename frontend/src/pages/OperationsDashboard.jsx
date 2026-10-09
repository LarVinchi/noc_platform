import { createElement, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, AlertTriangle, ArrowUpRight, Clock, RefreshCw, UserRound } from 'lucide-react';
import { incidentsApi } from '../api/client';
import ShiftActivityLog from '../components/ShiftActivityLog';

const activeStatuses = new Set(['open', 'investigating', 'pending']);
const severityRank = { Critical: 0, High: 1, Medium: 2, Low: 3 };
const severityStyles = {
  Critical: 'text-red-300 bg-red-950/40 border-red-800',
  High: 'text-orange-300 bg-orange-950/40 border-orange-800',
  Medium: 'text-amber-300 bg-amber-950/40 border-amber-800',
  Low: 'text-sky-300 bg-sky-950/40 border-sky-800',
};
const timestamp = (value) => {
  if (!value) return NaN;
  // Legacy API timestamps are naive UTC, not the operator's local time.
  return Date.parse(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`);
};
const age = (value) => {
  const start = timestamp(value);
  if (!Number.isFinite(start)) return 'Unknown';
  const minutes = Math.max(0, Math.floor((Date.now() - start) / 60000));
  return minutes < 60 ? `${minutes}m` : minutes < 1440 ? `${Math.floor(minutes / 60)}h ${minutes % 60}m` : `${Math.floor(minutes / 1440)}d ${Math.floor(minutes % 1440 / 60)}h`;
};

export default function OperationsDashboard() {
  const [incidents, setIncidents] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let timer;
    async function refresh() {
      setRefreshing(true);
      try {
        const response = await incidentsApi.getIncidents({}, { signal: controller.signal });
        if (controller.signal.aborted) return;
        if (!Array.isArray(response.data)) throw new Error('Invalid incident response');
        setIncidents(response.data);
        setLastUpdated(new Date());
        setError('');
      } catch {
        if (!controller.signal.aborted) setError('Incident feed unavailable. Check connectivity or retry.');
      } finally {
        if (!controller.signal.aborted) {
          setRefreshing(false);
          timer = setTimeout(refresh, 30000);
        }
      }
    }
    refresh();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [revision]);

  const active = (incidents || []).filter((incident) => activeStatuses.has(incident.status));
  const critical = active.filter((incident) => incident.severity === 'Critical');
  const unassigned = active.filter((incident) => !incident.responsible_person?.trim());
  const queue = [...active].sort((a, b) =>
    (severityRank[a.severity] ?? 4) - (severityRank[b.severity] ?? 4) ||
    (timestamp(a.reported_at) || 0) - (timestamp(b.reported_at) || 0));
  const cards = [
    { title: 'Active incidents', value: active.length, description: 'Open, investigating or pending', icon: Activity, color: 'text-cyan-300' },
    { title: 'Critical incidents', value: critical.length, description: 'Active incidents marked critical', icon: AlertTriangle, color: 'text-red-300' },
    { title: 'Awaiting ownership', value: unassigned.length, description: 'No responsible engineer recorded', icon: UserRound, color: 'text-amber-300' },
  ];

  return (
    <div className="space-y-6 max-w-screen-2xl mx-auto">
      <ShiftActivityLog />
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-widest text-cyan-400 mb-2">Network operations centre</p>
          <h1 className="text-3xl font-semibold tracking-tight">Operations overview</h1>
          <p className="text-sm text-slate-400 mt-2">Prioritize active incidents and coordinate the next response.</p>
        </div>
        <button onClick={() => setRevision((value) => value + 1)} disabled={refreshing}
          className="flex items-center gap-2 rounded-lg border border-slate-600 px-4 py-2 text-sm hover:bg-slate-800 disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400">
          <RefreshCw size={16} />{refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      <div role="status" aria-live="polite" className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400 border-y border-slate-800 py-3">
        <span className={error ? 'text-amber-300' : ''}>{error ? 'Feed unavailable · displayed data may be stale' : lastUpdated ? 'Incident feed connected' : 'Connecting to incident feed…'}</span>
        <span>{lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString('en-GB', { timeZone: 'Africa/Lagos' })} WAT` : 'Awaiting first update'} · Refreshes every 30 seconds</span>
      </div>
      {error && <p role="alert" className="rounded-lg border border-amber-800 bg-amber-950/30 p-4 text-sm text-amber-200">{error}</p>}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {cards.map(({ title, value, description, icon: Icon, color }) => (
          <section key={title} className="rounded-xl border border-slate-700/70 bg-slate-800/40 p-5">
            <div className="flex items-center justify-between text-sm text-slate-300"><h2>{title}</h2>{createElement(Icon, { size: 18, className: color })}</div>
            <p className={`text-4xl font-semibold tabular-nums mt-4 ${color}`}>{incidents === null ? '—' : value}</p>
            <p className="text-xs text-slate-400 mt-3">{description}</p>
          </section>
        ))}
      </div>

      <section className="rounded-xl border border-slate-700/70 bg-slate-800/20 overflow-hidden">
        <div className="p-5 border-b border-slate-700/70 flex flex-wrap items-center justify-between gap-3">
          <div><h2 className="font-semibold">Incident work queue</h2><p className="text-xs text-slate-400 mt-1">Highest severity first, then oldest reported incident</p></div>
          <Link to="/incidents" className="flex items-center gap-1 text-sm text-cyan-300 hover:underline">Manage incidents <ArrowUpRight size={16} /></Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Active incidents ordered by severity and reported time</caption>
            <thead className="text-xs text-slate-400 bg-slate-900/40"><tr>{['Incident', 'Severity', 'Status', 'Engineer', 'Elapsed'].map((label) => <th key={label} scope="col" className="px-5 py-3 font-medium">{label}</th>)}</tr></thead>
            <tbody className="divide-y divide-slate-800">
              {queue.slice(0, 12).map((incident) => (
                <tr key={incident.incident_id} className="hover:bg-slate-800/60">
                  <td className="px-5 py-4"><Link to="/incidents" className="text-cyan-300 hover:underline font-mono text-xs">{incident.tt_number || 'Unnumbered'}</Link><p className="mt-1 text-slate-300">{incident.short_description || incident.incident_type}</p><p className="text-xs text-slate-500 mt-1">{incident.network_route || 'Route not recorded'}</p></td>
                  <td className="px-5 py-4"><span className={`inline-block rounded border px-2 py-1 text-xs ${severityStyles[incident.severity] || 'border-slate-600 text-slate-400'}`}>{incident.severity || 'Not set'}</span></td>
                  <td className="px-5 py-4 text-slate-300 capitalize">{incident.status === 'investigating' ? 'Investigating' : incident.status}</td>
                  <td className="px-5 py-4 text-slate-300">{incident.responsible_person?.trim() || <span className="text-amber-300">Unassigned</span>}</td>
                  <td className="px-5 py-4 text-slate-300 whitespace-nowrap"><span className="inline-flex items-center gap-2"><Clock size={14} />{age(incident.reported_at)}</span></td>
                </tr>
              ))}
              {!queue.length && <tr><td colSpan={5} className="p-10 text-center text-slate-400">{incidents === null ? error ? 'Incident data unavailable.' : 'Loading incidents…' : 'No active incidents recorded.'}</td></tr>}
            </tbody>
          </table>
        </div>
        <p className="px-5 py-3 text-xs text-slate-500 border-t border-slate-800">Elapsed time starts at the recorded report time. Service availability and SLA measurements will appear once monitoring and service policies are connected.</p>
      </section>
    </div>
  );
}
