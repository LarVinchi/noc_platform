import { useEffect, useState } from 'react';
import apiClient from '../api/client';

export default function AuditHistory() {
  const [rows, setRows] = useState([]);
  const [cursor, setCursor] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function load(before) {
    setBusy(true); setError('');
    try {
      const { data } = await apiClient.get('/audit/', { params: { before, limit: 50 } });
      setRows(previous => before ? [...previous, ...data.items] : data.items);
      setCursor(data.next_before);
    } catch (error) { setError(error.response?.data?.detail || error.message); }
    finally { setBusy(false); }
  }
  useEffect(() => { load(); }, []);
  return <section className="space-y-5">
    <div className="flex justify-between"><div><h1 className="text-2xl font-semibold">Audit history</h1>
      <p className="text-slate-400 mt-2">Committed changes to service orders, customer links, incidents and infrastructure. Sensitive text is excluded from snapshots.</p></div>
      <button disabled={busy} onClick={() => load()} className="text-cyan-400">Refresh</button></div>
    {error && <p role="alert" className="text-red-300">{error}</p>}
    {rows.map(row => <article key={row.audit_id} className="border border-slate-700 rounded-lg p-4 bg-charcoal-800">
      <div className="flex flex-wrap justify-between gap-2"><strong>{row.action} · {row.entity_type}</strong>
        <time className="text-sm text-slate-400">{new Date(row.occurred_at).toLocaleString()}</time></div>
      <p className="text-xs text-slate-400 mt-2 break-all">{row.entity_id} · Actor: {row.actor_id} {row.actor_verified ? '(verified)' : '(unverified)'} · Request: {row.request_id || 'outside API'}</p>
      <details className="mt-3 text-sm"><summary className="cursor-pointer text-cyan-400">View change</summary>
        <pre className="overflow-auto mt-2 text-xs">{JSON.stringify({ before: row.before_state, after: row.after_state }, null, 2)}</pre>
      </details>
    </article>)}
    {!rows.length && !busy && !error && <p className="text-slate-400">No changes recorded since audit history was enabled.</p>}
    {cursor && <button disabled={busy} onClick={() => load(cursor)} className="text-cyan-400">Load older changes</button>}
  </section>;
}
