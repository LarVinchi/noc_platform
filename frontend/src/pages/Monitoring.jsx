import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import apiClient from '../api/client';

export default function Monitoring({ identity }) {
  const [mappings, setMappings] = useState([]);
  const [events, setEvents] = useState([]);
  const [targets, setTargets] = useState({ cables: [], routes: [], services: [] });
  const [sensor, setSensor] = useState('');
  const [kind, setKind] = useState('cables');
  const [target, setTarget] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const admin = identity.roles.includes('NOC.Admin');
  const operator = admin || identity.roles.includes('NOC.Operator');
  async function refresh() {
    try {
      const [mappingResult, eventResult, targetResult] = await Promise.all([
        apiClient.get('/monitoring/mappings'), apiClient.get('/monitoring/events'), apiClient.get('/monitoring/targets'),
      ]);
      setMappings(mappingResult.data); setEvents(eventResult.data); setTargets(targetResult.data); setError('');
    } catch (error) { setError(error.response?.data?.detail || error.message); }
  }
  useEffect(() => {
    refresh(); const timer = setInterval(refresh, 30000); return () => clearInterval(timer);
  }, []);
  async function addMapping(event) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      const field = { cables: 'cable_id', routes: 'route_id', services: 'service_id' }[kind];
      await apiClient.post('/monitoring/mappings', { sensor_id: sensor.trim(), [field]: target });
      setSensor(''); setTarget(''); setNotice('Sensor linked to inventory. New events will use this mapping.'); await refresh();
    } catch (error) { setError(error.response?.data?.detail || error.message); }
    finally { setBusy(false); }
  }
  async function simulate(sensorId, state) {
    setBusy(true); setError(''); setNotice('');
    try {
      const { data } = await apiClient.post('/monitoring/simulate', {
        event_id: `preview:${crypto.randomUUID()}`, sensor_id: sensorId, state, observed_at: new Date().toISOString(),
      });
      setNotice(data.event.incident_id ? 'Observation recorded. Review the linked incident and verify affected services.' : 'Observation recorded.'); await refresh();
    } catch (error) { setError(error.response?.data?.detail || error.message); }
    finally { setBusy(false); }
  }
  const targetName = row => {
    const category = row.cable_id ? 'cables' : row.route_id ? 'routes' : 'services';
    const id = row.cable_id || row.route_id || row.service_id;
    return targets[category].find(item => item.id === id)?.name || id;
  };
  return <section className="space-y-6">
    <div><h1 className="text-2xl font-semibold">Monitoring intake</h1>
      <p className="text-slate-400 mt-2">Link PRTG sensor IDs to inventory. Infrastructure alarms identify potentially affected customers; service restoration needs verification.</p>
      {!identity.verified && <p className="text-amber-300 text-sm mt-2">Local preview: use Down and Up to exercise the incident workflow. Live PRTG connection is pending.</p>}</div>
    {error && <p role="alert" className="text-red-300">{error}</p>}
    {notice && <p role="status" className="text-cyan-300">{notice}</p>}
    {admin && <form onSubmit={addMapping} className="flex flex-wrap gap-3 p-4 rounded-lg border border-slate-700 bg-charcoal-800">
      <input aria-label="PRTG sensor ID" required maxLength={100} value={sensor} onChange={e => setSensor(e.target.value)} placeholder="PRTG sensor ID" className="bg-charcoal-900 border border-slate-600 rounded p-2" />
      <select aria-label="Target type" value={kind} onChange={e => { setKind(e.target.value); setTarget(''); }} className="bg-charcoal-900 border border-slate-600 rounded p-2">
        <option value="cables">Cable</option><option value="routes">Route</option><option value="services">Service</option>
      </select>
      <select aria-label="Inventory target" required value={target} onChange={e => setTarget(e.target.value)} className="bg-charcoal-900 border border-slate-600 rounded p-2 max-w-md">
        <option value="">Choose inventory target</option>{targets[kind].map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
      </select>
      <button disabled={busy} className="bg-cyan-700 rounded px-4 disabled:opacity-40">Link sensor</button>
    </form>}
    <div className="flex justify-between"><h2 className="text-lg font-medium">Sensor mappings</h2><button onClick={refresh} className="text-cyan-400">Refresh</button></div>
    <div className="grid gap-3 lg:grid-cols-2">{mappings.map(row => <article key={row.sensor_id} className="p-4 border border-slate-700 rounded-lg bg-charcoal-800">
      <div className="flex justify-between gap-3"><strong>Sensor {row.sensor_id}</strong><span className={row.last_state === 'down' ? 'text-red-300' : 'text-slate-400'}>{row.last_state || 'Awaiting observation'}</span></div>
      <p className="mt-2 text-sm text-slate-400">{targetName(row)}</p>
      <p className="mt-2 text-xs text-slate-500">{row.last_observed_at ? `Observed ${new Date(row.last_observed_at).toLocaleString()}` : 'No monitoring data received'}</p>
      {row.incident_id && <Link to="/incidents" className="text-cyan-400 text-sm mt-3 block">Review incidents</Link>}
      {!identity.verified && operator && <div className="flex gap-3 mt-3"><button disabled={busy} onClick={() => simulate(row.sensor_id, 'down')} className="text-red-300 border border-red-900 px-3 py-1 rounded">Preview Down</button>
        <button disabled={busy} onClick={() => simulate(row.sensor_id, 'up')} className="text-cyan-300 border border-cyan-900 px-3 py-1 rounded">Preview Up</button></div>}
    </article>)}</div>
    {!mappings.length && <p className="text-slate-400">No sensors mapped yet.</p>}
    <h2 className="text-lg font-medium">Recent observations</h2>
    <div className="overflow-auto border border-slate-700 rounded-lg"><table className="w-full text-sm"><thead className="bg-charcoal-800 text-slate-400"><tr>
      {['Observed', 'Sensor', 'State', 'Processing', 'Incident'].map(label => <th key={label} className="p-3 text-left">{label}</th>)}</tr></thead>
      <tbody>{events.map(row => <tr key={row.event_id} className="border-t border-slate-700"><td className="p-3">{new Date(row.observed_at).toLocaleString()}</td><td className="p-3">{row.sensor_id}</td>
        <td className="p-3">{row.state}</td><td className="p-3">{row.disposition}</td><td className="p-3">{row.incident_id ? <Link to="/incidents" className="text-cyan-400">Review</Link> : '—'}</td></tr>)}</tbody>
    </table></div>
  </section>;
}
