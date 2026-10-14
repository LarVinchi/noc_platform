import { useEffect, useState } from 'react';
import { provisioningApi } from '../api/client';

const css = 'w-full bg-slate-800 border border-slate-600 rounded-lg p-2.5 text-sm';
const message = (failure) => typeof failure.response?.data?.detail === 'string' ? failure.response.data.detail : 'Could not save. Check the assignment fields and connection.';

export default function FTTHAssignmentModal({ order, onClose, onAssigned }) {
  const [options, setOptions] = useState({ naps: [], splitters: [] });
  const [assignment, setAssignment] = useState({ nap_id: '', port_number: '', drop_cable_id: '', new_drop_cable_code: '', installer: '', planned_install_date: '' });
  const [newNap, setNewNap] = useState({ nap_code: '', pfs_id: '', total_ports: 8 });
  const [showNewNap, setShowNewNap] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const selected = options.naps.find((nap) => nap.nap_id === assignment.nap_id);
  async function refresh() {
    try { const { data } = await provisioningApi.assignmentOptions(); setOptions(data); }
    catch (failure) { setError(message(failure)); }
  }
  useEffect(() => { refresh(); }, []);
  async function createNap(event) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const { data } = await provisioningApi.createNap({ ...newNap, total_ports: Number(newNap.total_ports) });
      await refresh(); setAssignment({ ...assignment, nap_id: data.nap_id, port_number: '', drop_cable_id: '' }); setShowNewNap(false);
    } catch (failure) { setError(message(failure)); } finally { setBusy(false); }
  }
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      // datetime-local is explicitly interpreted as Lagos/WAT, independent of browser zone.
      await provisioningApi.allocateOrder(order.order_id, { ...assignment,
        port_number: Number(assignment.port_number), drop_cable_id: assignment.drop_cable_id || null,
        new_drop_cable_code: assignment.drop_cable_id ? null : assignment.new_drop_cable_code,
        planned_install_date: `${assignment.planned_install_date}:00+01:00`,
      }); onAssigned();
    } catch (failure) { setError(message(failure)); await refresh(); } finally { setBusy(false); }
  }
  return <div className="fixed inset-0 z-50 bg-black/70 overflow-y-auto p-4 flex justify-center items-start">
    <section role="dialog" aria-modal="true" aria-labelledby="assign-title" className="my-8 p-6 w-full max-w-xl bg-slate-900 border border-slate-700 rounded-xl space-y-4">
      <div className="flex justify-between gap-3"><h2 id="assign-title" className="font-semibold text-lg">Assign & schedule · {order.customer_name}</h2><button disabled={busy} onClick={onClose} aria-label="Close assignment">✕</button></div>
      {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
      <button onClick={() => setShowNewNap(!showNewNap)} className="text-cyan-300 text-sm underline">{showNewNap ? 'Use existing NAP' : 'Create a NAP'}</button>
      {showNewNap ? <form onSubmit={createNap} className="space-y-3">
        <label className="block text-sm">NAP code<input required className={css} value={newNap.nap_code} onChange={(e) => setNewNap({ ...newNap, nap_code: e.target.value })} /></label>
        <label className="block text-sm">Upstream splitter<select required className={css} value={newNap.pfs_id} onChange={(e) => setNewNap({ ...newNap, pfs_id: e.target.value })}><option value="">Select splitter</option>{options.splitters.map((p) => <option key={p.pfs_id} value={p.pfs_id}>{p.pfp} → {p.name}</option>)}</select></label>
        <label className="block text-sm">Number of ports<input type="number" min="1" max="128" required className={css} value={newNap.total_ports} onChange={(e) => setNewNap({ ...newNap, total_ports: e.target.value })} /></label>
        <button disabled={busy} className="bg-cyan-700 px-4 py-2 rounded-lg">Create NAP</button>
      </form> : <form onSubmit={submit} className="space-y-3">
        <label className="block text-sm">NAP<select required className={css} value={assignment.nap_id} onChange={(e) => setAssignment({ ...assignment, nap_id: e.target.value, port_number: '', drop_cable_id: '' })}><option value="">Select NAP</option>{options.naps.map((n) => <option key={n.nap_id} value={n.nap_id}>{n.nap_code} · {n.available_ports.length} ports available</option>)}</select></label>
        {selected && <p className="text-xs text-slate-400">{selected.pfp} → {selected.pfs} → {selected.nap_code}</p>}
        <label className="block text-sm">Available port<select required className={css} value={assignment.port_number} onChange={(e) => setAssignment({ ...assignment, port_number: e.target.value })}><option value="">Select port</option>{selected?.available_ports.map((p) => <option key={p} value={p}>{p}</option>)}</select></label>
        <label className="block text-sm">Drop cable<select className={css} value={assignment.drop_cable_id} onChange={(e) => setAssignment({ ...assignment, drop_cable_id: e.target.value })}><option value="">Register a new drop cable</option>{selected?.drop_cables.map((d) => <option key={d.drop_cable_id} value={d.drop_cable_id}>{d.code}</option>)}</select></label>
        {!assignment.drop_cable_id && <label className="block text-sm">New drop cable code<input required placeholder="DROP-FN123456" className={css} value={assignment.new_drop_cable_code} onChange={(e) => setAssignment({ ...assignment, new_drop_cable_code: e.target.value })} /></label>}
        <label className="block text-sm">Assigned installer<input required className={css} value={assignment.installer} onChange={(e) => setAssignment({ ...assignment, installer: e.target.value })} /></label>
        <label className="block text-sm">Planned installation · Lagos/WAT<input type="datetime-local" required className={css} value={assignment.planned_install_date} onChange={(e) => setAssignment({ ...assignment, planned_install_date: e.target.value })} /></label>
        <button disabled={busy || !selected?.available_ports.length} className="bg-cyan-700 disabled:opacity-50 px-4 py-2 rounded-lg">{busy ? 'Saving…' : 'Reserve & schedule'}</button>
      </form>}
    </section>
  </div>;
}
