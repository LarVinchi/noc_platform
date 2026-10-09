import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { activitiesApi } from '../api/client';

const statuses = ['Open', 'In Progress', 'Pending', 'Completed', 'Partially Closed', 'Aborted'];
const categories = ['Activity / Task', 'Incident', 'Customer Escalation', 'Maintenance', 'Monitoring / Alert', 'Reminder Email'];
const terminal = new Set(['Completed', 'Aborted']);
const css = 'w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm';
const nowShift = () => { const h = Number(new Intl.DateTimeFormat('en-GB', { hour: '2-digit', hourCycle: 'h23', timeZone: 'Africa/Lagos' }).format(new Date())); return h < 6 || h >= 22 ? 'Night' : h < 14 ? 'Morning' : 'Afternoon'; };
const empty = () => ({ person: '', shift: nowShift(), category: 'Activity / Task', title: '', description: '', status: 'Open', severity: 'Medium', affected_system: '', vendor_reference: '', handover: false, scheduled_at: '', due_at: '' });

export default function ShiftActivityLog() {
  const [entries, setEntries] = useState([]);
  const [form, setForm] = useState(empty);
  const [tab, setTab] = useState('All activity');
  const [search, setSearch] = useState('');
  const [person, setPerson] = useState('');
  const [shift, setShift] = useState('');
  const [status, setStatus] = useState('');
  const [handover, setHandover] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [copyMessage, setCopyMessage] = useState('');
  async function refresh() { try { const { data } = await activitiesApi.list(); setEntries(data); setError(''); } catch { setError('Activity feed unavailable. Displayed entries may be stale.'); } }
  useEffect(() => { refresh(); const timer = setInterval(refresh, 30000); return () => clearInterval(timer); }, []);
  async function submit(event) {
    event.preventDefault(); setBusy(true);
    const aware = (value) => value ? `${value}:00+01:00` : null;
    try { await activitiesApi.create({ ...form, scheduled_at: aware(form.scheduled_at), due_at: aware(form.due_at) }); setForm({ ...empty(), person: form.person }); await refresh(); }
    catch (failure) { setError(typeof failure.response?.data?.detail === 'string' ? failure.response.data.detail : 'Could not save activity. Check the fields and retry.'); }
    finally { setBusy(false); }
  }
  async function update(entry, next) { try { await activitiesApi.update(entry.activity_id, { status: next }); await refresh(); } catch { setError('Could not update activity status. Refresh and retry.'); } }
  const people = [...new Set(entries.map((e) => e.person))].sort();
  const filtered = entries.filter((e) => (!person || e.person === person) && (!shift || e.shift === shift) && (!status || e.status === status) &&
    `${e.title} ${e.description} ${e.vendor_reference || ''}`.toLowerCase().includes(search.toLowerCase()) &&
    (tab === 'All activity' || tab === 'Team summary' || (tab === 'Incidents & escalations' ? ['Incident', 'Customer Escalation'].includes(e.category) : tab === 'Maintenance' ? e.category === 'Maintenance' : e.category === 'Reminder Email')));
  const pending = entries.filter((e) => e.handover || !terminal.has(e.status));
  const summary = `SHIFT HANDOVER · ${new Date().toLocaleString('en-GB', { timeZone: 'Africa/Lagos' })} WAT\n` + (pending.length ? pending.map((e) => `[${e.status}] ${e.title} · ${e.person} (${e.shift})${e.affected_system ? ` · ${e.affected_system}` : ''}\n${e.description}`).join('\n\n') : 'No pending or flagged activities recorded.');
  const set = (key, value) => setForm({ ...form, [key]: value });
  return <section className="space-y-4">
    <div className="flex flex-wrap gap-3 items-center justify-between"><div><h2 className="text-xl font-semibold">Daily activity & shift handover</h2><p className="text-xs text-slate-400 mt-1">{nowShift()} shift · Morning 06–14 / Afternoon 14–22 / Night 22–06 · WAT</p></div><button onClick={() => setHandover(!handover)} className="text-sm border border-slate-600 rounded-lg px-3 py-2">Handover summary</button></div>
    {error && <p role="alert" className="text-sm text-red-300">{error} <button onClick={refresh} className="underline">Refresh</button></p>}
    <div className="grid grid-cols-2 md:grid-cols-6 gap-2">{statuses.map((s) => <button key={s} onClick={() => setStatus(status === s ? '' : s)} className={`text-left rounded-lg border p-3 ${status === s ? 'border-cyan-400' : 'border-slate-700'} bg-slate-800/30`}><span className="text-2xl font-mono">{entries.filter((e) => e.status === s).length}</span><span className="block text-xs text-slate-400 mt-1">{s}</span></button>)}</div>
    {handover && <div className="rounded-xl border border-slate-700 bg-slate-800/40 p-4"><pre className="text-xs whitespace-pre-wrap max-h-64 overflow-auto">{summary}</pre><button onClick={async () => { try { await navigator.clipboard.writeText(summary); setCopyMessage('Copied'); } catch { setCopyMessage('Clipboard unavailable; select the text to copy.'); } }} className="text-cyan-300 text-sm mt-3">Copy handover</button><span className="ml-3 text-xs" role="status">{copyMessage}</span></div>}
    <div className="grid grid-cols-1 xl:grid-cols-[320px_1fr] gap-5">
      <form onSubmit={submit} className="space-y-3 rounded-xl border border-slate-700 p-4 bg-slate-800/20">
        <h3 className="font-semibold">Log activity</h3>
        <label className="block text-xs text-slate-400">Logged by<input required value={form.person} onChange={(e) => set('person', e.target.value)} className={css} /></label>
        <label className="block text-xs text-slate-400">Shift<select value={form.shift} onChange={(e) => set('shift', e.target.value)} className={css}>{['Morning', 'Afternoon', 'Night'].map((s) => <option key={s}>{s}</option>)}</select></label>
        <label className="block text-xs text-slate-400">Category<select value={form.category} onChange={(e) => set('category', e.target.value)} className={css}>{categories.map((c) => <option key={c}>{c}</option>)}</select></label>
        <label className="block text-xs text-slate-400">Title<input required value={form.title} onChange={(e) => set('title', e.target.value)} className={css} /></label>
        <label className="block text-xs text-slate-400">Details<textarea rows={3} value={form.description} onChange={(e) => set('description', e.target.value)} className={css} /></label>
        <label className="block text-xs text-slate-400">Affected system / service<input value={form.affected_system} onChange={(e) => set('affected_system', e.target.value)} className={css} /></label>
        <label className="block text-xs text-slate-400">Vendor / reference<input value={form.vendor_reference} onChange={(e) => set('vendor_reference', e.target.value)} className={css} /></label>
        <label className="block text-xs text-slate-400">Severity<select value={form.severity} onChange={(e) => set('severity', e.target.value)} className={css}>{['Critical', 'High', 'Medium', 'Low'].map((s) => <option key={s}>{s}</option>)}</select></label>
        {form.category === 'Maintenance' && <label className="block text-xs text-slate-400">Scheduled for · WAT<input type="datetime-local" value={form.scheduled_at} onChange={(e) => set('scheduled_at', e.target.value)} className={css} /></label>}
        {form.category === 'Reminder Email' && <label className="block text-xs text-slate-400">Due at · WAT<input type="datetime-local" value={form.due_at} onChange={(e) => set('due_at', e.target.value)} className={css} /></label>}
        <label className="block text-xs text-slate-400">Status<select value={form.status} onChange={(e) => set('status', e.target.value)} className={css}>{statuses.map((s) => <option key={s}>{s}</option>)}</select></label>
        <label className="flex gap-2 text-sm"><input type="checkbox" checked={form.handover} onChange={(e) => set('handover', e.target.checked)} />Flag for next shift</label>
        {['Incident', 'Customer Escalation'].includes(form.category) && <p className="text-xs text-slate-400">Creates a linked incident with the existing trouble-ticket convention.</p>}
        <button disabled={busy} className="bg-cyan-700 rounded-lg w-full p-2.5 text-sm disabled:opacity-50">{busy ? 'Saving…' : 'Add to log'}</button>
      </form>
      <div className="min-w-0 space-y-3">
        <div className="flex flex-wrap border-b border-slate-700 gap-2">{['All activity', 'Incidents & escalations', 'Maintenance', 'Reminders', 'Team summary'].map((t) => <button key={t} onClick={() => setTab(t)} className={`text-sm p-2 border-b-2 ${t === tab ? 'text-cyan-300 border-cyan-400' : 'text-slate-400 border-transparent'}`}>{t}</button>)}</div>
        <div className="flex flex-wrap gap-2"><input aria-label="Search activity" placeholder="Search title or details…" value={search} onChange={(e) => setSearch(e.target.value)} className={`${css} flex-1 min-w-40`} /><select aria-label="Filter by person" value={person} onChange={(e) => setPerson(e.target.value)} className="bg-slate-800 rounded-lg p-2 text-xs"><option value="">All people</option>{people.map((p) => <option key={p}>{p}</option>)}</select><select aria-label="Filter by shift" value={shift} onChange={(e) => setShift(e.target.value)} className="bg-slate-800 rounded-lg p-2 text-xs"><option value="">All shifts</option>{['Morning', 'Afternoon', 'Night'].map((s) => <option key={s}>{s}</option>)}</select></div>
        {tab === 'Team summary' ? <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr>{['Engineer', 'Total', 'Completed', 'Pending'].map((s) => <th key={s} className="p-3 text-left text-slate-400">{s}</th>)}</tr></thead><tbody>{people.map((p) => { const own = filtered.filter((e) => e.person === p); return <tr key={p} className="border-t border-slate-700"><td className="p-3">{p}</td><td>{own.length}</td><td>{own.filter((e) => e.status === 'Completed').length}</td><td>{own.filter((e) => !terminal.has(e.status)).length}</td></tr>; })}</tbody></table></div> : filtered.map((entry) => <article key={entry.activity_id} className="rounded-lg border border-slate-700 border-l-4 border-l-cyan-700 p-4 space-y-2">
          <div className="flex flex-wrap justify-between gap-2"><p className="text-xs text-slate-400">{entry.category} · {entry.person} · {entry.shift} · {new Date(entry.created_at).toLocaleString('en-GB', { timeZone: 'Africa/Lagos' })} WAT</p><select aria-label={`Status for ${entry.title}`} value={entry.status} onChange={(e) => update(entry, e.target.value)} className="bg-slate-800 rounded p-1 text-xs">{statuses.map((s) => <option key={s}>{s}</option>)}</select></div>
          <h3 className="font-medium">{entry.title}</h3><p className="text-sm text-slate-400 whitespace-pre-wrap">{entry.description}</p>
          <p className="text-xs text-slate-400">{entry.affected_system}{entry.vendor_reference && ` · ${entry.vendor_reference}`}{entry.handover && ' · Next shift attention'}{entry.due_at && ` · Due ${new Date(entry.due_at).toLocaleString('en-GB', { timeZone: 'Africa/Lagos' })} WAT`}{entry.scheduled_at && ` · Scheduled ${new Date(entry.scheduled_at).toLocaleString('en-GB', { timeZone: 'Africa/Lagos' })} WAT`}</p>
          {entry.due_at && new Date(entry.due_at) < new Date() && !terminal.has(entry.status) && <p className="text-xs text-red-300">Overdue</p>}
          {entry.incident_id && <Link to="/incidents" className="text-xs text-cyan-300 underline">View linked incident</Link>}{entry.order_id && <Link to="/provisioning" className="text-xs text-cyan-300 underline">View FTTH orders</Link>}
        </article>)}
        {!filtered.length && <p className="text-sm text-slate-400 p-6 text-center">No activities match these filters.</p>}
      </div>
    </div>
  </section>;
}
