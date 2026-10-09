import { useEffect, useState } from 'react';
import apiClient from '../api/client';
const css = 'w-full rounded-lg border border-slate-600 bg-slate-800 p-2 text-sm';

export default function ServiceProvisionForm({ customers, onClose, onProvisioned }) {
  const [cores, setCores] = useState([]);
  const [form, setForm] = useState({ customer_id: '', customer_name: '', customer_code: '', address: '', service_type: 'DIA', bandwidth_mbps: 100, core_id: '', backup_core_id: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { apiClient.get('/services/free-cores').then(({ data }) => setCores(data)).catch(() => setError('Could not load available cores.')); }, []);
  const available = cores.filter((c) => ['FREE', form.service_type].includes(c.usage_type));
  const set = (key, value) => setForm({ ...form, [key]: value });
  async function submit(event) {
    event.preventDefault(); setBusy(true);
    try { await apiClient.post('/services/', { ...form, customer_id: form.customer_id || null,
      backup_core_id: form.backup_core_id || null, customer_name: form.customer_id ? null : form.customer_name,
      customer_code: form.customer_id ? null : form.customer_code, bandwidth_mbps: form.service_type === 'DARKFIBER' ? null : Number(form.bandwidth_mbps) }); onProvisioned(); }
    catch (failure) { setError(typeof failure.response?.data?.detail === 'string' ? failure.response.data.detail : 'Could not provision service. Check the selected customer and cores.'); } finally { setBusy(false); }
  }
  return <div className="fixed inset-0 z-50 overflow-auto bg-black/70 p-4 flex justify-center items-start"><form onSubmit={submit} className="bg-slate-900 border border-slate-700 rounded-xl p-6 my-8 w-full max-w-xl space-y-3" role="dialog" aria-modal="true" aria-label="Provision service">
    <div className="flex justify-between"><h2 className="font-semibold text-lg">Provision enterprise service</h2><button type="button" disabled={busy} onClick={onClose} aria-label="Close">✕</button></div>
    {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
    <label className="block text-sm">Customer<select value={form.customer_id} onChange={(e) => set('customer_id', e.target.value)} className={css}><option value="">Create customer record</option>{customers.map((c) => <option key={c.customer_id} value={c.customer_id}>{c.customer_name} · {c.service_id_code}</option>)}</select></label>
    {!form.customer_id && <>{[['customer_name', 'Customer name'], ['customer_code', 'Customer reference code'], ['address', 'Address']].map(([key, label]) => <label key={key} className="block text-sm">{label}<input required={key !== 'address'} value={form[key]} onChange={(e) => set(key, e.target.value)} className={css} /></label>)}</>}
    <label className="block text-sm">Service type<select value={form.service_type} onChange={(e) => setForm({ ...form, service_type: e.target.value, core_id: '', backup_core_id: '' })} className={css}>{['DIA', 'DARKFIBER', 'LAYER2'].map((s) => <option key={s}>{s}</option>)}</select></label>
    {form.service_type !== 'DARKFIBER' && <label className="block text-sm">Bandwidth · Mbps<input type="number" min="1" required value={form.bandwidth_mbps} onChange={(e) => set('bandwidth_mbps', e.target.value)} className={css} /></label>}
    {[['core_id', 'Primary core'], ['backup_core_id', 'Backup core · optional']].map(([key, label]) => <label key={key} className="block text-sm">{label}<select required={key === 'core_id'} value={form[key]} onChange={(e) => set(key, e.target.value)} className={css}><option value="">Select core</option>{available.map((c) => <option key={c.core_id} value={c.core_id}>{c.route} → {c.cable} → core {c.number}</option>)}</select></label>)}
    <p className="text-xs text-slate-400">This records the service and its physical dependencies. It does not configure network devices or verify connectivity.</p>
    <button disabled={busy} className="bg-cyan-700 disabled:opacity-50 px-4 py-2 rounded-lg">{busy ? 'Provisioning…' : 'Provision service'}</button>
  </form></div>;
}
