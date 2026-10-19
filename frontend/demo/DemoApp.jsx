import { useState } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { FlaskConical, Network, LogOut } from 'lucide-react';
import NocAppShell from '../src/components/NocAppShell';
import NocRoutes from '../src/components/NocRoutes';
import ThemeSelector from '../src/components/ThemeSelector';
import { SCENARIOS, changeScenario, currentScenario, forgetOpened, openDemoSession } from './session.js';

const localRag = import.meta.env.VITE_RAG_LOCAL_PREVIEW === 'true';

function ScenarioPicker() {
  return <label className="demo-scenario">
    <span>Scenario</span>
    <select value={currentScenario()} onChange={event => changeScenario(event.target.value)} aria-label="Demo data scenario">
      {SCENARIOS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
    </select>
  </label>;
}

function DemoBanner({ onExit }) {
  return <div className="demo-banner" role="status" aria-label="Design preview notice">
    <span className="demo-badge"><FlaskConical size={13} aria-hidden="true" />{localRag ? 'LOCAL RAG TEST' : 'DEMO'}</span>
    <p>{localRag ? 'Isolated local documents are saved · approved evidence is sent to Gemini when you ask · other pages use synthetic fixtures' : 'Synthetic data · read-only design preview · nothing is saved and no backend is connected'}</p>
    <div className="demo-banner-actions">
      <ScenarioPicker />
      {onExit && <button type="button" onClick={onExit}><LogOut size={13} aria-hidden="true" />Exit preview</button>}
    </div>
  </div>;
}

function DemoGate({ onOpen }) {
  const [busy, setBusy] = useState(false), [failure, setFailure] = useState('');
  async function open() {
    setBusy(true); setFailure('');
    try { onOpen(await openDemoSession()); }
    catch (error) { setFailure(error.response?.data?.detail || error.message); setBusy(false); }
  }
  return <main className="demo-gate">
    <section className="demo-gate-card" aria-labelledby="demo-gate-title">
      <div className="demo-gate-brand"><span className="noc-brand-mark"><Network size={20} /></span>AFL NOC</div>
      <h1 id="demo-gate-title">Design preview</h1>
      <p>{localRag ? 'Test document upload, explicit approval and Gemini questions against a local SQLite catalogue. This is an unverified local administrator session. Use only approved non-sensitive test material.' : 'Explore the redesigned workspace with synthetic, contract-shaped sample data. Microsoft sign-in is not used here, and the real application is unchanged.'}</p>
      <dl className="demo-identity">
        <div><dt>Identity</dt><dd>DEMO · Synthetic NOC Admin</dd></div>
        <div><dt>Role</dt><dd>NOC.Admin</dd></div>
        <div><dt>Verification</dt><dd>Unverified · synthetic</dd></div>
        <div><dt>Writes</dt><dd>{localRag ? 'Local documents and knowledge only · no production data' : 'Rejected · read-only fixtures'}</dd></div>
      </dl>
      {failure && <p role="alert" className="response-error">{failure}</p>}
      <button type="button" className="response-button primary" onClick={open} disabled={busy}>{busy ? 'Opening preview…' : 'Open design preview'}</button>
      <ThemeSelector />
    </section>
  </main>;
}

export default function DemoApp({ initialIdentity }) {
  const [identity, setIdentity] = useState(initialIdentity);
  const exit = () => { forgetOpened(); setIdentity(null); };
  return <div className="demo-frame">
    <DemoBanner onExit={identity ? exit : null} />
    {identity
      ? <BrowserRouter><NocAppShell identity={identity} onLogout={exit}><NocRoutes identity={identity} /></NocAppShell></BrowserRouter>
      : <DemoGate onOpen={setIdentity} />}
  </div>;
}
