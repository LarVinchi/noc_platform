import { useState } from 'react';
import { ShieldCheck, Network, Activity, Clock3, LockKeyhole } from 'lucide-react';
import ThemeSelector from '../components/ThemeSelector';

export default function NOCLoginScreen({ configuration, error, onLogin }) {
  const [busy, setBusy] = useState(false), [failure, setFailure] = useState('');
  const preview = configuration?.mode === 'preview';
  async function enter() {
    setBusy(true); setFailure('');
    try { await onLogin(); }
    catch (error) { setFailure(error.response?.data?.detail || error.message); }
    finally { setBusy(false); }
  }
  return <main className="noc-login"><section className="login-intro"><div className="login-brand"><span className="noc-brand-mark"><Network size={23} /></span>AFL NOC</div><div><p className="eyebrow">NETWORK OPERATIONS CENTRE</p><h1>A clear view.<br />A coordinated response.</h1><p>Your workspace for incident response, infrastructure visibility and a connected shift handover.</p><div className="login-features"><span><Activity size={15} />Operational focus</span><span><ShieldCheck size={15} />Role-based access</span><span><Clock3 size={15} />Lagos · WAT</span></div></div><footer>AFL · Network operations workspace</footer></section>
    <section className="login-access"><div className="login-card"><LockKeyhole size={25} className="text-cyan-400" /><h2>Welcome to your workspace</h2><p>{preview ? 'Local development environment. Actions use an unverified preview identity. Use sample data only.' : 'Sign in with your company Microsoft 365 account to continue. Access is based on your assigned NOC role.'}</p>
      {(failure || error) && <p role="alert" className="response-error">{failure || error}</p>}
      {configuration && !configuration.configured && <p className="response-preview">Microsoft 365 registration is pending. An administrator must configure access.</p>}
      <button onClick={enter} disabled={busy || !configuration?.configured} className="response-button primary"><ShieldCheck size={17} />{busy ? 'Opening workspace…' : preview ? 'Open local preview' : 'Sign in with Microsoft 365'}</button>
      {import.meta.env.DEV && <a href="/demo/" className="login-demo-link">Explore the design demo · no sign-in required</a>}
      <p className="login-access-note">Authorized personnel only. Operational changes remain subject to existing permissions and audit records.</p><ThemeSelector />
    </div></section></main>;
}
