import { createElement, lazy, Suspense, useEffect, useRef, useState } from 'react';
import { Map, Network, Maximize2, Minimize2, Layers3 } from 'lucide-react';
import GeographicNetwork from './GeographicNetwork';
import '../styles/topology.css';
const LogicalTopology = lazy(() => import('./TopologyMap'));

export default function NetworkTopology() {
  const [view, setView] = useState('Geographic');
  const [fullscreen, setFullscreen] = useState(false);
  const [error, setError] = useState('');
  const root = useRef(null);
  useEffect(() => {
    const sync = () => setFullscreen(document.fullscreenElement === root.current);
    document.addEventListener('fullscreenchange', sync);
    return () => document.removeEventListener('fullscreenchange', sync);
  }, []);
  async function toggleFullscreen() {
    try { if (document.fullscreenElement) await document.exitFullscreen(); else await root.current.requestFullscreen(); }
    catch { setError('Full-screen mode is unavailable in this browser. Collapse the sidebar for more space.'); }
  }
  return <section ref={root} className="topology-workspace">
    <div className="topology-viewbar"><div className="topology-title"><Layers3 size={18} /><strong>NETWORK EXPLORER</strong><span>Infrastructure / Services / Impact</span></div>
      <div className="topology-view-actions"><div className="topology-tabs" role="tablist" aria-label="Topology view">{[['Geographic', Map], ['Logical', Network]].map(([name, Icon]) => <button role="tab" aria-selected={view === name} key={name} onClick={() => setView(name)} className={view === name ? 'selected' : ''}>{createElement(Icon, { size: 15 })}{name}</button>)}</div><button className="noc-icon-button" onClick={toggleFullscreen} aria-label={fullscreen ? 'Exit full screen' : 'Enter full screen'} title="Full screen">{fullscreen ? <Minimize2 size={17} /> : <Maximize2 size={17} />}</button></div>
    </div>
    {error && <p role="alert" className="topology-error">{error}</p>}
    <div className="topology-stage">{view === 'Geographic' ? <GeographicNetwork /> : <Suspense fallback={<div className="topology-loading">Loading network diagram…</div>}><LogicalTopology /></Suspense>}</div>
  </section>;
}
