import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import ReactFlow, { MiniMap, Controls, Background, BackgroundVariant } from 'reactflow';
import dagre from 'dagre';
import { Search, LocateFixed, RefreshCw, Expand, Minus, Plus, X, Route, Network, ArrowDownUp, ChevronRight, Info, AlertTriangle } from 'lucide-react';
import 'reactflow/dist/style.css';
import apiClient from '../api/client';
import { NetworkNode } from '../components/TopologyNodes';
import CableEdge from '../components/CableEdge';

const nodeTypes = Object.fromEntries(['core', 'cable', 'primary_splitter', 'secondary_splitter', 'access_point', 'cpe_outlet', 'dia_endpoint', 'dark_fiber_endpoint', 'layer2_endpoint'].map(type => [type, NetworkNode]));
const edgeTypes = { fibre: CableEdge };
const colors = { core: '#59c7ff', cable: '#7d9cff', primary_splitter: '#bba1ff', secondary_splitter: '#be8ef5', access_point: '#55d5ce', cpe_outlet: '#efbd77' };
function related(id, edges, direction) {
  const found = new Set([id]), queue = [id];
  while (queue.length) { const current = queue.shift(); for (const edge of edges) { const next = direction === 'up' ? edge.target === current && edge.source : edge.source === current && edge.target; if (next && !found.has(next)) { found.add(next); queue.push(next); } } }
  return found;
}
function mergeGraph(previous, next) {
  const nodes = new Map(previous.nodes.map(node => [node.id, node])); const edges = new Map(previous.edges.map(edge => [edge.id, edge]));
  next.nodes.forEach(node => nodes.set(node.id, node)); next.edges.forEach(edge => edges.set(edge.id, edge));
  return { nodes: [...nodes.values()], edges: [...edges.values()] };
}

export default function TopologyMap() {
  const [graph, setGraph] = useState({ nodes: [], edges: [] }), [collapsed, setCollapsed] = useState(new Set());
  const [selectedId, setSelectedId] = useState(null), [traceId, setTraceId] = useState(null), [query, setQuery] = useState('');
  const [direction, setDirection] = useState('TB'), [error, setError] = useState(''), [loading, setLoading] = useState(true), [pending, setPending] = useState(new Set());
  const [revision, setRevision] = useState(0), [impact, setImpact] = useState(null), [menu, setMenu] = useState(null), [focusId, setFocusId] = useState(null);
  const flow = useRef(null), root = useRef(null), loaded = useRef(new Set()), inFlight = useRef(new Map());
  const impactRequest = useRef(null);
  const selected = graph.nodes.find(node => node.id === selectedId);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError('');
    const requests = inFlight.current;
    apiClient.get('/topology/', { signal: controller.signal }).then(({ data }) => {
      if (!controller.signal.aborted) { setGraph(data); setCollapsed(new Set()); loaded.current = new Set(); setSelectedId(null); setTraceId(null); }
    }).catch(() => { if (!controller.signal.aborted) setError('Logical inventory could not be loaded. Retry the inventory feed.'); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => { controller.abort(); requests.forEach(controller => controller.abort()); requests.clear(); };
  }, [revision]);

  async function expandCable(node) {
    if (loaded.current.has(node.id) || inFlight.current.has(node.id)) return;
    const controller = new AbortController(); inFlight.current.set(node.id, controller); setPending(previous => new Set([...previous, node.id]));
    try {
      const { data } = await apiClient.get(`/topology/expand/${node.id}`, { signal: controller.signal });
      if (!controller.signal.aborted) { setGraph(previous => mergeGraph(previous, data)); loaded.current.add(node.id); setCollapsed(previous => { const next = new Set(previous); next.delete(node.id); return next; }); }
    } catch { if (!controller.signal.aborted) setError(`Could not expand ${node.data.label}. Retry this cable.`); }
    finally { inFlight.current.delete(node.id); setPending(previous => { const next = new Set(previous); next.delete(node.id); return next; }); }
  }
  async function toggleBranch(node) {
    setMenu(null);
    if (node.type === 'cable' && !loaded.current.has(node.id)) { await expandCable(node); return; }
    if (!graph.edges.some(edge => edge.source === node.id)) return;
    setCollapsed(previous => { const next = new Set(previous); if (next.has(node.id)) next.delete(node.id); else next.add(node.id); return next; });
  }
  async function expandAll() { setError(''); setCollapsed(new Set()); await Promise.all(graph.nodes.filter(node => node.type === 'cable').map(expandCable)); }
  const layout = useMemo(() => {
    // Traverse from roots instead of hiding all descendants: a shared endpoint
    // remains visible when another uncollapsed branch still reaches it.
    const targets = new Set(graph.edges.map(edge => edge.target)), visible = new Set(), queue = graph.nodes.filter(node => !targets.has(node.id)).map(node => node.id);
    while (queue.length) { const id = queue.shift(); if (visible.has(id)) continue; visible.add(id); if (!collapsed.has(id)) graph.edges.filter(edge => edge.source === id).forEach(edge => queue.push(edge.target)); }
    const nodes = graph.nodes.filter(node => visible.has(node.id)), edges = graph.edges.filter(edge => visible.has(edge.source) && visible.has(edge.target) && !collapsed.has(edge.source));
    const traced = traceId ? new Set([...related(traceId, graph.edges, 'up'), ...related(traceId, graph.edges, 'down')]) : null;
    const engine = new dagre.graphlib.Graph(); engine.setDefaultEdgeLabel(() => ({})); engine.setGraph({ rankdir: direction, ranksep: direction === 'TB' ? 95 : 230, nodesep: 60, marginx: 50, marginy: 65 });
    nodes.forEach(node => engine.setNode(node.id, { width: 276, height: 128 })); edges.forEach(edge => engine.setEdge(edge.source, edge.target)); dagre.layout(engine);
    return {
      nodes: nodes.map(node => ({ ...node, selected: node.id === selectedId, draggable: false, data: { ...node.data, direction }, position: { x: engine.node(node.id).x - 138, y: engine.node(node.id).y - 64 }, style: { opacity: traced && !traced.has(node.id) ? .16 : 1 } })),
      edges: edges.map(edge => ({ ...edge, type: 'fibre', animated: false, style: { ...edge.style, stroke: edge.style?.stroke || '#7186a6', opacity: traced && !(traced.has(edge.source) && traced.has(edge.target)) ? .08 : 1 } })),
    };
  }, [graph, collapsed, direction, traceId, selectedId]);

  useEffect(() => {
    if (!focusId || !flow.current) return;
    const node = layout.nodes.find(node => node.id === focusId);
    if (node) { flow.current.setCenter(node.position.x + 138, node.position.y + 64, { zoom: 1, duration: 500 }); setFocusId(null); }
  }, [focusId, layout]);
  useEffect(() => { setImpact(null); impactRequest.current?.abort(); return () => impactRequest.current?.abort(); }, [selectedId]);
  const matches = query.trim() ? graph.nodes.filter(node => `${node.data.label} ${node.data.type} ${node.id}`.toLowerCase().includes(query.toLowerCase().trim())).slice(0, 10) : [];
  function focusNode(node) {
    const ancestors = related(node.id, graph.edges, 'up'); setCollapsed(previous => new Set([...previous].filter(id => !ancestors.has(id))));
    setSelectedId(node.id); setTraceId(node.id); setFocusId(node.id); setQuery('');
  }
  function fit() { flow.current?.fitView({ padding: .18, duration: 500 }); }
  async function loadImpact() {
    impactRequest.current?.abort(); const controller = new AbortController(); impactRequest.current = controller;
    try { const { data } = await apiClient.get(selected.type === 'cable' ? `/topology/cable-impact/${selected.id}` : `/topology/impact/${selected.id}`, { signal: controller.signal }); if (!controller.signal.aborted) setImpact(data); }
    catch { if (!controller.signal.aborted) setError('Customer dependency analysis is unavailable.'); }
  }
  return <div className="logical-workspace" ref={root}>
    <div className="logical-toolbar"><div className="logical-search"><Search size={16} /><input aria-label="Search logical network" placeholder="Find a route, cable or loaded customer…" value={query} onChange={event => setQuery(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && matches[0]) focusNode(matches[0]); if (event.key === 'Escape') setQuery(''); }} />{query && <button onClick={() => setQuery('')} aria-label="Clear network search"><X size={14} /></button>}
      {query && <div className="logical-search-results">{matches.map(node => <button key={node.id} onClick={() => focusNode(node)}><span style={{ color: colors[node.type] || '#efbd77' }}>{node.data.type}</span><strong>{node.data.label}</strong></button>)}{!matches.length && <p>No loaded nodes match. Expand cables to search their customers.</p>}</div>}</div>
      <button className="fv-button" onClick={fit}><LocateFixed size={15} />Fit network</button><button className="fv-button" disabled={pending.size > 0 || loading} onClick={expandAll}><Expand size={15} />{pending.size ? `Loading ${pending.size}…` : 'Expand cables'}</button><button className="fv-button" onClick={() => setDirection(value => value === 'LR' ? 'TB' : 'LR')}><ArrowDownUp size={15} />{direction === 'LR' ? 'Vertical layout' : 'Horizontal layout'}</button><button className="noc-icon-button" onClick={() => setRevision(value => value + 1)} aria-label="Refresh logical inventory"><RefreshCw size={16} /></button>
    </div>
    {error && <div className="logical-error" role="alert"><AlertTriangle size={15} />{error}<button onClick={() => setError('')} aria-label="Dismiss error"><X size={14} /></button></div>}
    {loading && <div className="logical-loading">Loading infrastructure…</div>}
    {!loading && !graph.nodes.length && !error && <div className="logical-loading">No active routes or cables are recorded yet.</div>}
    <ReactFlow nodes={layout.nodes} edges={layout.edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} onInit={instance => { flow.current = instance; }} onNodeClick={(_, node) => { setSelectedId(node.id); setMenu(null); }} onNodeDoubleClick={(_, node) => toggleBranch(node)} onPaneClick={() => { setSelectedId(null); setMenu(null); }}
      onNodeContextMenu={(event, node) => { event.preventDefault(); setSelectedId(node.id); const rect = root.current.getBoundingClientRect(); setMenu({ x: Math.min(event.clientX - rect.left, rect.width - 220), y: Math.min(event.clientY - rect.top, rect.height - 160), node }); }}
      nodesConnectable={false} edgesUpdatable={false} deleteKeyCode={null} fitView minZoom={.08} maxZoom={2} zoomOnDoubleClick={false} proOptions={{ hideAttribution: true }}>
      <Background variant={BackgroundVariant.Dots} color="#26394c" gap={24} size={1} /><Controls showInteractive={false} /><MiniMap pannable zoomable nodeColor={node => colors[node.type] || '#efbd77'} maskColor="rgba(5,13,22,.75)" />
    </ReactFlow>
    <div className="logical-network-summary"><span><Network size={13} />{layout.nodes.length} nodes</span><span>{layout.edges.length} links</span><span>Inventory relationships · health unverified</span></div>
    {traceId && <div className="logical-trace-banner"><Route size={15} />Tracing {graph.nodes.find(node => node.id === traceId)?.data.label}<button onClick={() => setTraceId(null)}>Clear trace <X size={13} /></button></div>}
    <div className="logical-legend"><strong>NETWORK ELEMENTS</strong>{[['core', 'Route'], ['cable', 'Fibre cable'], ['primary_splitter', 'PFP cabinet'], ['secondary_splitter', 'PFS splitter'], ['access_point', 'NAP terminal'], ['cpe_outlet', 'Customer / ONT']].map(([type, label]) => <span key={type}><i style={{ background: colors[type] }} />{label}</span>)}<small>Double-click a cable to expand its infrastructure</small></div>
    {selected && <aside className="logical-inspector"><div className="fibre-details-heading"><span className="eyebrow">ELEMENT INSPECTOR</span><button className="noc-icon-button" onClick={() => setSelectedId(null)} aria-label="Close element inspector"><X size={17} /></button></div><h2>{selected.data.label}</h2><span className="fv-badge unknown">{selected.data.type}</span><dl><div><dt>Capacity / allocation</dt><dd>{selected.data.badge || 'Unrecorded'}</dd></div>{selected.data.total_cores != null && <div><dt>Physical cable capacity</dt><dd>{selected.data.total_cores} cores · {selected.data.recorded_cores} core records</dd></div>}<div><dt>Service health</dt><dd>Unverified · inventory is not a health check</dd></div><div><dt>Inventory ID</dt><dd className="inspector-id">{selected.id}</dd></div></dl>
      <div className="logical-inspector-actions"><button className="fv-button primary" onClick={() => setTraceId(selected.id)}><Route size={15} />Trace dependencies</button>{(selected.type === 'cable' || graph.edges.some(edge => edge.source === selected.id)) && <button className="fv-button" disabled={pending.has(selected.id)} onClick={() => toggleBranch(selected)}>{collapsed.has(selected.id) || (selected.type === 'cable' && !loaded.current.has(selected.id)) ? <Plus size={15} /> : <Minus size={15} />}{pending.has(selected.id) ? 'Loading…' : collapsed.has(selected.id) || !graph.edges.some(edge => edge.source === selected.id) ? 'Expand branch' : 'Collapse branch'}</button>}{['core', 'cable'].includes(selected.type) && <button className="fv-button" onClick={loadImpact}><Info size={15} />Inspect customer impact</button>}<Link to="/incidents" className="fv-text-button">Open incident response <ChevronRight size={13} /></Link></div>
      {impact && <div className="fibre-impact"><h3>{impact.customer_count} customers · {impact.service_count} services</h3><p className="fv-note">Potential impact · restoration needs verification</p>{impact.services.map(service => <article key={service.service_id}><h4>{service.customer}<small>{service.service_type}</small></h4><p>{service.alternate_path_recorded ? 'Alternate path recorded' : 'No alternate path recorded'}</p></article>)}</div>}
    </aside>}
    {menu && <div className="logical-context" style={{ left: Math.max(8, menu.x), top: Math.max(70, menu.y) }}><strong>{menu.node.data.label}</strong><button onClick={() => { setTraceId(menu.node.id); setMenu(null); }}><Route size={14} />Trace dependencies</button><button onClick={() => toggleBranch(menu.node)}><Expand size={14} />Expand / collapse branch</button><Link to="/incidents">Open incident response</Link></div>}
  </div>;
}
