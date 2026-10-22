import { useState } from 'react';
import { X } from 'lucide-react';
import { provisioningApi } from '../api/client';

const fields = [
  ['customer_name', 'Customer name', true], ['service_address', 'Service address', true],
  ['bandwidth', 'Service package', true], ['phone_number', 'Contact phone', false],
  ['email', 'Email', false], ['fn_number', 'FN number', true],
  ['work_order_id', 'Work order ID', true],
];
const inputClass = 'w-full rounded-lg border border-slate-600 bg-slate-800 p-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-cyan-500';
const errorMessage = (error) => {
  const detail = error.response?.data?.detail;
  return typeof detail === 'string' ? detail : Array.isArray(detail)
    ? detail.map((entry) => `${entry.loc?.slice(-1)[0] || 'Request'}: ${entry.msg}`).join('; ')
    : 'Could not process this request. Check your connection and try again.';
};

export default function FTTHImportModal({ onClose, onImported }) {
  const [rawText, setRawText] = useState('');
  const [isp, setIsp] = useState('MTNN');
  const [order, setOrder] = useState(null);
  const [warnings, setWarnings] = useState([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function preview(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setOrder(null);
    try {
      const { data } = await provisioningApi.previewRequest({ raw_text: rawText, isp });
      setOrder(data.order);
      setWarnings(data.warnings);
    } catch (failure) { setError(errorMessage(failure)); }
    finally { setBusy(false); }
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const { data } = await provisioningApi.importRequest({
        raw_text: rawText, order: { ...order, email: order.email || null, phone_number: order.phone_number || null },
      });
      onImported(data);
    } catch (failure) { setError(errorMessage(failure)); }
    finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/70 backdrop-blur-sm p-4 flex items-start justify-center">
      <section role="dialog" aria-modal="true" aria-labelledby="intake-title" className="w-full max-w-3xl my-6 rounded-xl border border-slate-700 bg-slate-900 shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-slate-700 p-5">
          <div><h2 id="intake-title" className="text-lg font-semibold">Paste FTTH request</h2><p className="text-sm text-slate-400 mt-1">Extract the customer and order details, review them, then log the request.</p></div>
          <button type="button" aria-label="Close import" disabled={busy} onClick={onClose} className="text-slate-400 hover:text-white disabled:opacity-50"><X size={22} /></button>
        </header>
        <div className="p-5 space-y-5">
          {error && <p role="alert" className="rounded-lg border border-red-800 bg-red-950/30 p-3 text-sm text-red-200">{error}</p>}
          <form onSubmit={preview} className="space-y-3">
            <label htmlFor="intake-isp" className="block text-sm text-slate-300">ISP</label>
            <select id="intake-isp" value={isp} disabled={busy} onChange={(event) => { setIsp(event.target.value); setOrder(null); }} className={inputClass}>
              <option value="MTNN">MTNN</option><option value="METROREACH">Metroreach</option><option value="MANGONET">Mangonet</option><option value="TELEWYZ">Telewyz</option>
            </select>
            <label htmlFor="intake-text" className="block text-sm text-slate-300">Request text</label>
            <textarea id="intake-text" autoFocus required maxLength={20000} rows={9} value={rawText} disabled={busy}
              onChange={(event) => { setRawText(event.target.value); setOrder(null); setWarnings([]); }}
              placeholder={'FN NUMBER\nFN123456\nCUSTOMER NAME\nCustomer name\nSERVICE ADDRESS\nAddress\nSERVICE PACKAGE\n100Mbps\nWORK ORDER ID\nCO12345678'} className={`${inputClass} font-mono`} />
            <p className="text-xs text-slate-400">Paste one request at a time. Screenshots are a visual reference; copy the request text here.</p>
            <button disabled={busy} type="submit" className="rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 px-4 py-2 text-sm font-semibold">{busy ? 'Processing…' : 'Extract details'}</button>
          </form>
          {order && <form onSubmit={submit} className="border-t border-slate-700 pt-5 space-y-4">
            <h3 className="font-semibold">Review extracted details</h3>
            {warnings.length > 0 && <ul className="list-disc pl-5 space-y-1 text-xs text-amber-200">{warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {fields.map(([key, label, required]) => <div key={key} className={key === 'service_address' ? 'sm:col-span-2' : ''}>
                <label htmlFor={`intake-${key}`} className="block text-xs text-slate-400 mb-1">{label}{required ? ' *' : ''}</label>
                <input id={`intake-${key}`} type={key === 'email' ? 'email' : key === 'phone_number' ? 'tel' : 'text'} required={required} disabled={busy} value={order[key] || ''}
                  onChange={(event) => setOrder({ ...order, [key]: event.target.value })} className={inputClass} />
              </div>)}
            </div>
            <p className="text-xs text-slate-400">The order starts in New Requests. An existing FN/work order will be detected before another record is created.</p>
            <div className="flex justify-end gap-3"><button type="button" disabled={busy} onClick={onClose} className="px-4 py-2 text-sm text-slate-300">Cancel</button><button type="submit" disabled={busy} className="rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 px-4 py-2 text-sm font-semibold">{busy ? 'Logging…' : 'Log FTTH request'}</button></div>
          </form>}
        </div>
      </section>
    </div>
  );
}
