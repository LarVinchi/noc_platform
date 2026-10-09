import { useState } from 'react';
import { ShieldCheck, Network } from 'lucide-react';

export default function NOCLoginScreen({ configuration, error, onLogin }) {
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState('');
  const preview = configuration?.mode === 'preview';
  async function enter() {
    setBusy(true); setFailure('');
    try { await onLogin(); }
    catch (error) { setFailure(error.response?.data?.detail || error.message); }
    finally { setBusy(false); }
  }
  return <div className="min-h-screen bg-charcoal-950 text-slate-200 flex items-center justify-center p-6">
    <div className="w-full max-w-lg rounded-2xl border border-slate-700 bg-charcoal-900 p-10 shadow-2xl">
      <Network className="text-cyan-400 mb-6" size={36} />
      <p className="text-xs text-cyan-400 uppercase tracking-widest">Network operations centre</p>
      <h1 className="text-3xl font-semibold mt-3 mb-4">NOC workspace</h1>
      <p className="text-slate-400 mb-6">{preview
        ? 'Local development preview. Actions use an unverified preview identity. Use sample data here.'
        : 'Use your company Microsoft 365 account. Access depends on your assigned NOC role.'}</p>
      {(failure || error) && <p role="alert" className="text-red-300 mb-4">{failure || error}</p>}
      {configuration && !configuration.configured && <p className="text-amber-300 mb-4">Microsoft 365 registration is pending. An administrator must configure access before this environment can be used.</p>}
      <button onClick={enter} disabled={busy || !configuration?.configured}
        className="w-full rounded-lg bg-cyan-600 p-3 font-medium disabled:opacity-40 flex items-center justify-center gap-2">
        <ShieldCheck size={18} />{busy ? 'Opening workspace…' : preview ? 'Open local preview' : 'Sign in with Microsoft 365'}
      </button>
    </div>
  </div>;
}
