import { lazy, Suspense, useState } from 'react';
import GeographicNetwork from './GeographicNetwork';
const LogicalTopology = lazy(() => import('./TopologyMap'));

export default function NetworkTopology() {
  const [view, setView] = useState('Geographic');
  return <div className="space-y-5 h-full"><div><h1 className="text-2xl font-semibold">Network topology</h1><p className="text-sm text-slate-400 mt-1">Fibre routes, infrastructure dependencies and provisioned customer services.</p></div><div className="flex gap-2">{['Geographic', 'Logical'].map((v) => <button key={v} onClick={() => setView(v)} className={`border rounded-lg px-4 py-2 text-sm ${view === v ? 'border-cyan-500 text-cyan-300' : 'border-slate-700 text-slate-400'}`}>{v}</button>)}</div>{view === 'Geographic' ? <GeographicNetwork /> : <Suspense fallback={<p>Loading logical topology…</p>}><LogicalTopology /></Suspense>}</div>;
}
