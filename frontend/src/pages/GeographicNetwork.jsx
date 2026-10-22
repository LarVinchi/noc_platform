import { useEffect, useMemo, useRef, useState } from 'react';
import { Upload, Search, LocateFixed, PanelLeftClose, PanelLeftOpen, RefreshCw, X, Layers, ChevronRight, Cable, MapPin, AlertTriangle } from 'lucide-react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import apiClient from '../api/client';
import { COLORS, STATUS_LABEL, TYPE_LABEL, nodeSvg } from '../components/fibreMapSymbols';

const empty = { type: 'FeatureCollection', features: [], routes: [] };
const km = length => `${(Number(length || 0) / 1000).toFixed(2)} km`;
const safeRead = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } };
const nodeTypes = ['pop', 'cls', 'closure', 'handhole', 'customer', 'fault'];
function drawnLength(feature) {
  if (Number.isFinite(Number(feature.properties.length_m))) return Number(feature.properties.length_m);
  const points = feature.geometry.coordinates;
  const radians = value => value * Math.PI / 180;
  return points.slice(1).reduce((sum, point, i) => {
    const previous = points[i], a = Math.sin(radians(point[1] - previous[1]) / 2) ** 2 + Math.cos(radians(previous[1])) * Math.cos(radians(point[1])) * Math.sin(radians(point[0] - previous[0]) / 2) ** 2;
    return sum + 6371000 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a)));
  }, 0);
}

export default function GeographicNetwork() {
  const container = useRef(null), map = useRef(null), layers = useRef(new Map()), bounds = useRef(null), viewportKey = useRef(null), callbacks = useRef({});
  const [inventory, setInventory] = useState(empty), [imports, setImports] = useState([]);
  const [importId, setImportId] = useState(() => safeRead('noc.fiberviz.layer', ''));
  const [layer, setLayer] = useState(null), [selectedKey, setSelectedKey] = useState(null);
  const [annotations, setAnnotations] = useState(() => { const saved = safeRead('noc.fiberviz.annotations', {}); return saved && typeof saved === 'object' && !Array.isArray(saved) ? saved : {}; });
  const [panel, setPanel] = useState(true), [legend, setLegend] = useState(true), [filter, setFilter] = useState('all'), [search, setSearch] = useState('');
  const [impact, setImpact] = useState(null), [impactError, setImpactError] = useState(''), [routeId, setRouteId] = useState('');
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [updated, setUpdated] = useState(null), [dragging, setDragging] = useState(false);
  const dragDepth = useRef(0);
  const impactRequest = useRef(null);

  async function refresh(signal) {
    try {
      const [geo, list] = await Promise.all([apiClient.get('/topology/geography', { signal }), apiClient.get('/topology/maps', { signal })]);
      if (!signal?.aborted) { setInventory(geo.data); setImports(list.data); setUpdated(new Date()); setError(''); }
    } catch { if (!signal?.aborted) setError('Inventory feed unavailable. Displayed data may be stale.'); }
  }
  useEffect(() => {
    const controller = new AbortController(); let timer;
    async function poll() { await refresh(controller.signal); if (!controller.signal.aborted) timer = setTimeout(poll, 30000); }
    poll(); return () => { controller.abort(); clearTimeout(timer); };
  }, []);
  useEffect(() => {
    if (!importId) return;
    const controller = new AbortController();
    apiClient.get(importId === 'demo' ? '/topology/maps/demo' : `/topology/maps/${importId}`, { signal: controller.signal })
      .then(({ data }) => { if (!controller.signal.aborted) { setLayer(data); setSelectedKey(null); setError(''); } })
      .catch(() => { if (!controller.signal.aborted) setError('This map could not be loaded. Select another layer or import a file.'); });
    return () => controller.abort();
  }, [importId]);
  function changeLayer(id) { setImportId(id); setLayer(null); setSelectedKey(null); try { localStorage.setItem('noc.fiberviz.layer', JSON.stringify(id)); } catch { /* optional preference */ } }

  const features = useMemo(() => {
    const routeAlarms = new Map(inventory.features.filter(f => f.properties.kind === 'route').map(f => [f.properties.inventory_route_id, f.properties.monitoring_alarms || []]));
    const linked = new Set((layer?.features || []).map(f => f.properties.inventory_route_id).filter(Boolean));
    const entries = [];
    for (const [geo, source] of [[inventory, 'inventory'], [layer, 'import']]) {
      (geo?.features || []).forEach((original, index) => {
        if (source === 'inventory' && original.geometry.type === 'LineString' && linked.has(original.properties.inventory_route_id)) return;
        const key = source === 'import' ? `import:${importId}:${index}` : `inventory:${original.properties.service_id || original.properties.inventory_route_id || index}:${original.geometry.type}`;
        const alarms = routeAlarms.get(original.properties.inventory_route_id) || original.properties.monitoring_alarms || [];
        const annotation = source === 'import' && Object.hasOwn(STATUS_LABEL, annotations[key]) ? annotations[key] : null;
        const status = alarms.length && original.geometry.type === 'LineString' ? 'down' : annotation || (Object.hasOwn(STATUS_LABEL, original.properties.status) ? original.properties.status : 'unknown');
        entries.push({ ...original, key, source, properties: { ...original.properties, feature_index: index, status, monitoring_alarms: alarms, annotation,
          length_m: original.geometry.type === 'LineString' ? drawnLength(original) : 0 } });
      });
    }
    return entries;
  }, [inventory, layer, importId, annotations]);
  const routes = features.filter(f => f.geometry.type === 'LineString');
  const visibleRoutes = routes.filter(f => (filter === 'all' || f.properties.status === filter) && (!search.trim() || `${f.properties.name} ${f.properties.data?.cable_type || ''}`.toLowerCase().includes(search.toLowerCase().trim())));
  const mapKey = `${importId}:${layer ? 'loaded' : 'inventory'}`;
  const selected = features.find(f => f.key === selectedKey);
  const lengths = { live: 0, down: 0, planned: 0, unknown: 0 };
  routes.forEach(f => { lengths[f.properties.status in lengths ? f.properties.status : 'unknown'] += f.properties.length_m; });
  const total = Object.values(lengths).reduce((a, b) => a + b, 0), built = total - lengths.planned;
  const alarms = routes.filter(f => f.properties.monitoring_alarms.length).length;

  useEffect(() => {
    const instance = L.map(container.current, { zoomControl: false }).setView([6.4468, 3.4725], 13);
    const streets = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, className: 'tiles-dark', attribution: '&copy; OpenStreetMap contributors' });
    const satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19, attribution: 'Imagery &copy; Esri, Maxar, Earthstar Geographics' });
    streets.addTo(instance); L.control.layers({ 'Streets': streets, Satellite: satellite }, null, { position: 'topright' }).addTo(instance);
    L.control.zoom({ position: 'bottomright' }).addTo(instance); L.control.scale({ imperial: false, position: 'bottomleft' }).addTo(instance);
    const zoomLabels = () => { const element = instance.getContainer(); element.classList.toggle('z-far', instance.getZoom() < 16); element.classList.toggle('z-mid', instance.getZoom() < 17); };
    instance.on('zoomend', zoomLabels); zoomLabels(); map.current = instance;
    const observer = new ResizeObserver(() => instance.invalidateSize({ pan: false })); observer.observe(container.current);
    return () => { observer.disconnect(); instance.remove(); map.current = null; };
  }, []);

  callbacks.current.select = (feature, zoom) => {
    setSelectedKey(feature.key); setPanel(true); setRouteId(feature.properties.inventory_route_id || '');
    const entry = layers.current.get(feature.key);
    if (zoom && entry?.getBounds) map.current.fitBounds(entry.getBounds(), { paddingTopLeft: [map.current.getSize().x > 800 ? 350 : 30, 80], paddingBottomRight: [70, 80], maxZoom: 17 });
    else if (zoom && entry?.getLatLng) map.current.panTo(entry.getLatLng());
    if (zoom && entry?.openPopup) entry.openPopup(entry.getBounds ? entry.getBounds().getCenter() : entry.getLatLng());
  };
  callbacks.current.annotate = (key, status) => {
    setAnnotations(previous => {
      const next = { ...previous }; if (status) next[key] = status; else delete next[key];
      try { localStorage.setItem('noc.fiberviz.annotations', JSON.stringify(next)); } catch { setError('Annotation applied for this session; browser storage is unavailable.'); }
      return next;
    });
  };
  useEffect(() => {
    if (!map.current) return;
    const group = L.featureGroup().addTo(map.current); layers.current = new Map();
    const visibleKeys = new Set(features.filter(f => f.geometry.type === 'LineString' && (filter === 'all' || f.properties.status === filter) && (!search.trim() || `${f.properties.name} ${f.properties.data?.cable_type || ''}`.toLowerCase().includes(search.toLowerCase().trim()))).map(f => f.key));
    for (const feature of features) {
      const p = feature.properties, color = COLORS[p.status] || COLORS.unknown;
      if (feature.geometry.type === 'LineString') {
        if (!visibleKeys.has(feature.key)) continue;
        const points = feature.geometry.coordinates.map(c => [c[1], c[0]]), count = Number(p.data?.fibre_count) || 0;
        const width = count >= 96 ? 7 : count >= 48 ? 5 : 3.5;
        L.polyline(points, { color, weight: width + 12, opacity: .14, interactive: false }).addTo(group);
        L.polyline(points, { color: '#050d13', weight: width + 4, opacity: .95, interactive: false }).addTo(group);
        const core = L.polyline(points, { color, weight: width, className: `route-${p.status}` }).addTo(group);
        if (p.status === 'live') L.polyline(points, { color: '#eafff6', weight: Math.max(2, width * .38), opacity: .85, interactive: false, className: 'route-flow' }).addTo(group);
        const label = document.createElement('div'); label.textContent = `${p.name} · ${STATUS_LABEL[p.status]} · ${km(p.length_m)}${count ? ` · ${count} fibres` : ''}`;
        core.bindTooltip(label, { sticky: true, className: 'fv-tip' });
        const popup = document.createElement('div'); popup.className = 'fv-map-popup';
        const badge = document.createElement('span'); badge.className = `fv-badge ${p.status}`; badge.textContent = STATUS_LABEL[p.status]; popup.append(badge);
        const title = document.createElement('h3'); title.textContent = p.name; popup.append(title);
        const description = document.createElement('p'); description.textContent = `Drawn length ${km(p.length_m)}${count ? ` · ${count} fibres` : ''}${p.data?.cable_type ? ` · ${p.data.cable_type}` : ''}`; popup.append(description);
        if (p.recorded_km != null) { const recorded = document.createElement('p'); recorded.textContent = `Recorded in file: ${Number(p.recorded_km).toFixed(2)} km`; popup.append(recorded); }
        const note = document.createElement('p'); note.textContent = p.monitoring_alarms.length ? 'Last-observed monitoring alarm; verify service impact.' : p.status_source === 'inferred' ? 'Status inferred from the file; confirm the map annotation.' : 'Map status; customer availability requires verification.'; popup.append(note);
        if (feature.source === 'import') {
          const controls = document.createElement('div'); controls.className = 'fv-popup-status'; controls.setAttribute('aria-label', 'Manual route annotation');
          for (const status of ['live', 'down', 'planned']) { const button = document.createElement('button'); button.className = `fv-badge ${status}`; button.textContent = STATUS_LABEL[status]; button.addEventListener('click', () => callbacks.current.annotate(feature.key, status)); controls.append(button); }
          popup.append(controls);
          const caption = document.createElement('small'); caption.textContent = 'Annotations saved in this browser'; popup.append(caption);
        }
        core.bindPopup(popup, { maxWidth: 280, autoPanPaddingTopLeft: [map.current.getSize().x > 800 ? 350 : 20, 70] });
        core.on('mouseover', () => core.setStyle({ weight: width + 2 })); core.on('mouseout', () => core.setStyle({ weight: width }));
        core.on('click', () => callbacks.current.select(feature, false)); layers.current.set(feature.key, core);
      } else if (feature.geometry.type === 'Point') {
        const type = (p.node_type || p.data?.type || '').toLowerCase(), size = { cls: 40, pop: 40, closure: 24, handhole: 16, customer: 28, fault: 30 }[type] || 20;
        const marker = L.marker([feature.geometry.coordinates[1], feature.geometry.coordinates[0]], { icon: L.divIcon({ className: `fv-node fv-node-${type || 'other'}`, html: nodeSvg(type, p.status), iconSize: [size, size], iconAnchor: [size / 2, size / 2] }), title: p.name, zIndexOffset: ['pop', 'fault'].includes(type) ? 1000 : 500 }).addTo(group);
        const label = document.createElement('span'); label.textContent = p.name;
        marker.bindTooltip(label, { permanent: true, direction: type === 'customer' ? 'left' : 'right', offset: [(type === 'customer' ? -1 : 1) * (size / 2 + 2), 0], className: `fv-label lbl-${type || 'other'}` });
        const popup = document.createElement('div'); popup.className = 'fv-map-popup';
        const title = document.createElement('h3'); title.textContent = p.name; popup.append(title);
        const detail = document.createElement('p'); detail.textContent = TYPE_LABEL[type] || 'Network site'; popup.append(detail);
        if (p.description || p.location_source) { const note = document.createElement('p'); note.textContent = p.description || `Location: ${p.location_source}; premises unverified.`; popup.append(note); }
        marker.bindPopup(popup, { maxWidth: 280, autoPanPaddingTopLeft: [map.current.getSize().x > 800 ? 350 : 20, 70] });
        marker.on('click', () => callbacks.current.select(feature, false)); layers.current.set(feature.key, marker);
      }
    }
    if (group.getLayers().length) {
      bounds.current = group.getBounds();
      if (viewportKey.current !== mapKey) { map.current.fitBounds(bounds.current, { paddingTopLeft: [map.current.getSize().x > 800 ? 350 : 30, 80], paddingBottomRight: [80, 80], maxZoom: 16 }); viewportKey.current = mapKey; }
    }
    return () => group.remove();
    // Selection uses a ref; filtering/refreshing preserves the operator's camera.
  }, [features, filter, search, mapKey]);

  useEffect(() => {
    const route = features.find(f => f.key === selectedKey)?.properties.inventory_route_id;
    impactRequest.current?.abort();
    setImpact(null); setImpactError('');
    if (!route) return;
    const controller = new AbortController();
    impactRequest.current = controller;
    apiClient.get(`/topology/impact/${route}`, { signal: controller.signal }).then(({ data }) => { if (!controller.signal.aborted) setImpact(data); }).catch(() => { if (!controller.signal.aborted) setImpactError('Customer impact could not be loaded.'); });
    return () => controller.abort();
  }, [selectedKey, features]);

  async function inspectCable(cableId) {
    impactRequest.current?.abort(); const controller = new AbortController(); impactRequest.current = controller;
    try { const { data } = await apiClient.get(`/topology/cable-impact/${cableId}`, { signal: controller.signal }); if (!controller.signal.aborted) setImpact(data); }
    catch { if (!controller.signal.aborted) setImpactError('Cable impact unavailable.'); }
  }

  async function upload(file) {
    if (!file || busy) return;
    if (!/\.(kmz|kml)$/i.test(file.name)) { setError('Select a KMZ or KML file.'); return; }
    setBusy(true); setError(''); const body = new FormData(); body.append('file', file);
    try { const { data } = await apiClient.post('/topology/maps', body, { headers: { 'Content-Type': 'multipart/form-data' } }); await refresh(); changeLayer(data.import_id); }
    catch (failure) { setError(typeof failure.response?.data?.detail === 'string' ? failure.response.data.detail : 'Map import failed.'); }
    finally { setBusy(false); }
  }
  function annotate(status) {
    callbacks.current.annotate(selectedKey, status);
  }
  async function linkRoute() {
    setBusy(true);
    try { await apiClient.post(`/topology/maps/${importId}/link`, { route_id: routeId, feature_index: selected.properties.feature_index }); await refresh(); setLayer((await apiClient.get(`/topology/maps/${importId}`)).data); }
    catch (failure) { setError(typeof failure.response?.data?.detail === 'string' ? failure.response.data.detail : 'Route link failed.'); }
    finally { setBusy(false); }
  }
  function fitNetwork() { if (bounds.current?.isValid()) map.current.fitBounds(bounds.current, { paddingTopLeft: [panel && map.current.getSize().x > 800 ? 350 : 30, 80], paddingBottomRight: [60, 80] }); }
  return <div className={`fibre-workspace ${panel ? '' : 'fibre-panel-hidden'}`} onDragEnter={event => { if (event.dataTransfer.types.includes('Files')) { event.preventDefault(); dragDepth.current++; setDragging(true); } }} onDragOver={event => { if (event.dataTransfer.types.includes('Files')) event.preventDefault(); }} onDragLeave={event => { event.preventDefault(); dragDepth.current = Math.max(0, dragDepth.current - 1); if (!dragDepth.current) setDragging(false); }} onDrop={event => { event.preventDefault(); dragDepth.current = 0; setDragging(false); upload(event.dataTransfer.files[0]); }}>
    <div ref={container} className="fibre-canvas" aria-label="Fibre network geographic map" />
    <aside className="fibre-panel" aria-label="FibreViz route explorer" hidden={!panel}>
      <div className="fibre-panel-heading"><div><span className="eyebrow">GEOGRAPHIC INTELLIGENCE</span><h1>Fibre Route Viewer</h1><p>{layer?.name || 'Inventory & customer services'}</p></div><button className="noc-icon-button" onClick={() => setPanel(false)} aria-label="Hide route explorer"><PanelLeftClose size={18} /></button></div>
      <div className="fibre-actions"><label className="fv-button primary"><Upload size={15} />{busy ? 'Processing…' : 'Open KMZ / KML'}<input aria-label="Open KMZ or KML file" type="file" accept=".kmz,.kml" disabled={busy} onChange={e => { upload(e.target.files[0]); e.target.value = ''; }} /></label><button className="fv-button" onClick={() => changeLayer('demo')}>Lekki demo</button></div>
      <select className="fv-select" aria-label="Map layer" value={importId} onChange={e => changeLayer(e.target.value)}><option value="">Inventory only</option><option value="demo">Lekki demo · approximate</option>{imports.map(row => <option key={row.import_id} value={row.import_id}>{row.name}</option>)}</select>
      {error && <p role="alert" className="fv-error">{error}</p>}
      <section className="fibre-health" aria-label="Mapped route statistics"><div className="fibre-health-top"><strong>{built ? `${Math.round(lengths.live / built * 100)}%` : '—'}</strong><span>of built mapped length<br />marked live</span></div><div className="fibre-health-bar">{Object.keys(lengths).map(status => <i key={status} style={{ width: `${total ? lengths[status] / total * 100 : 0}%`, background: COLORS[status] }} />)}</div><dl>{['live', 'down', 'planned', 'total'].map(status => <div key={status}><dt>{status === 'total' ? 'Total' : STATUS_LABEL[status]}</dt><dd style={{ color: COLORS[status] }}>{km(status === 'total' ? total : lengths[status])}</dd></div>)}</dl><p>Map status and annotations · not a customer SLA measurement</p></section>
      <div className="fibre-filters" role="group" aria-label="Filter routes">{['all', ...Object.keys(STATUS_LABEL)].map(status => <button key={status} aria-pressed={filter === status} onClick={() => setFilter(status)} className={filter === status ? 'on' : ''}>{status === 'all' ? 'All' : STATUS_LABEL[status]}</button>)}</div>
      <label className="fibre-search"><Search size={15} /><input aria-label="Search routes" value={search} onChange={e => setSearch(e.target.value)} placeholder="Find a route or cable…" /></label>
      {selected ? <section className="fibre-details"><div className="fibre-details-heading"><span className="eyebrow">SELECTED {selected.geometry.type === 'Point' ? 'SITE' : 'ROUTE'}</span><button onClick={() => setSelectedKey(null)} className="noc-icon-button" aria-label="Close route details"><X size={16} /></button></div><h2>{selected.properties.name}</h2><span className={`fv-badge ${selected.properties.status}`}>{STATUS_LABEL[selected.properties.status] || 'Not set'}</span>
        <p>{selected.geometry.type === 'Point' ? TYPE_LABEL[selected.properties.node_type] || 'Network site' : `Drawn length ${km(selected.properties.length_m)}`}</p>
        {selected.properties.recorded_km != null && <p>Recorded in file: {Number(selected.properties.recorded_km).toFixed(2)} km{Math.abs(Number(selected.properties.recorded_km) * 1000 - selected.properties.length_m) > Number(selected.properties.recorded_km) * 100 ? ' · differs from drawn line' : ''}</p>}
        {selected.properties.data?.fibre_count && <p>{selected.properties.data.cable_type} · {selected.properties.data.fibre_count} fibres</p>}
        {selected.properties.location_source && <p className="fv-note">Location: {selected.properties.location_source}; customer premises unverified.</p>}
        {selected.properties.description && <p>{selected.properties.description}</p>}
        {selected.properties.monitoring_alarms?.map(alarm => <p key={alarm.sensor_id} className="fv-alarm"><AlertTriangle size={13} />Sensor {alarm.sensor_id} last observed down · {new Date(alarm.observed_at).toLocaleString('en-GB', { timeZone: 'Africa/Lagos' })} WAT</p>)}
        {selected.source === 'import' && selected.geometry.type === 'LineString' && <div className="fibre-annotations"><span>Manual map annotation</span><div>{['live', 'down', 'planned', 'unknown'].map(status => <button key={status} className={`fv-badge ${status} ${selected.properties.annotation === status ? 'active' : ''}`} onClick={() => annotate(status)}>{STATUS_LABEL[status]}</button>)}</div><button className="fv-text-button" onClick={() => annotate(null)}>Reset to file status</button><p>Saved in this browser. Monitoring alarms take precedence.</p></div>}
        {selected.source === 'import' && selected.geometry.type === 'LineString' && importId !== 'demo' && !selected.properties.inventory_route_id && <div className="fibre-link"><label>Link to inventory<select aria-label="Link route to inventory" className="fv-select" value={routeId} onChange={e => setRouteId(e.target.value)}><option value="">Select network route</option>{inventory.routes.map(row => <option key={row.route_id} value={row.route_id}>{row.name}</option>)}</select></label><button disabled={!routeId || busy} className="fv-button primary" onClick={linkRoute}>Use this line as route geometry</button></div>}
        {impactError && <p role="alert" className="fv-error">{impactError}</p>}
        {impact && <div className="fibre-impact"><h3>Customer dependency analysis</h3><div className="fibre-impact-counts"><strong>{impact.customer_count}<span>customers</span></strong><strong>{impact.service_count}<span>services</span></strong></div><p className="fv-note">Potential impact; verify service downtime and alternate paths.</p>{impact.services.map(service => <article key={service.service_id}><h4>{service.customer}<small>{service.service_type}</small></h4><p>{service.alternate_path_recorded ? 'Alternate path recorded · health unverified' : 'No alternate path recorded'}</p>{service.affected_paths.map((path, i) => <div className="fibre-service-path" key={i}><span>{path.route} <ChevronRight size={10} /> {path.cable} <ChevronRight size={10} /> Core {path.core}</span>{path.nap && <span>{path.pfp} → {path.pfs} → {path.nap} → Port {path.port} → {path.drop}</span>}<button className="fv-text-button" onClick={() => inspectCable(path.cable_id)}>Inspect cable impact</button></div>)}</article>)}</div>}
      </section> : <><div className="fibre-list-title"><span>ROUTE INVENTORY</span><b>{visibleRoutes.length}</b></div><ul className="fibre-route-list">{visibleRoutes.map(feature => <li key={feature.key}><button onClick={() => callbacks.current.select(feature, true)}><i style={{ background: COLORS[feature.properties.status] }} /><span><strong>{feature.properties.name}</strong><small>{feature.properties.data?.cable_type || STATUS_LABEL[feature.properties.status]}{feature.properties.data?.fibre_count ? ` · ${feature.properties.data.fibre_count} fibres` : ''}</small></span><em>{km(feature.properties.length_m)}</em></button></li>)}</ul>{!visibleRoutes.length && <div className="fibre-empty"><Cable size={25} /><p>{routes.length ? 'No routes match this filter.' : 'Import your network file or load the Lekki demo to explore fibre routes.'}</p></div>}</>}
      <div className="fibre-panel-footer"><i className={error ? 'stale' : ''} />{updated ? `Inventory sync ${updated.toLocaleTimeString('en-GB', { timeZone: 'Africa/Lagos' })} WAT` : 'Connecting to inventory…'}<button onClick={() => refresh()} aria-label="Refresh topology"><RefreshCw size={13} /></button></div>
    </aside>
    <div className="fibre-hud">{!panel && <button className="noc-icon-button" onClick={() => setPanel(true)} title="Show route explorer" aria-label="Show route explorer"><PanelLeftOpen size={18} /></button>}<strong>{layer?.name || 'Fibre network'}</strong><span className={`fv-badge ${alarms ? 'down' : 'unknown'}`}>{alarms ? `${alarms} mapped route alarm${alarms > 1 ? 's' : ''}` : `${routes.length} mapped routes`}</span></div>
    <div className="fibre-map-tools"><button className="fv-button" onClick={fitNetwork} aria-label="Fit network"><LocateFixed size={16} />Fit network</button><button className="fv-button" onClick={() => setLegend(v => !v)} aria-expanded={legend}><Layers size={16} />Legend</button></div>
    {legend && <div className="fibre-legend"><strong>FIBREVIZ · NETWORK KEY</strong><div className="fibre-legend-columns"><div>{Object.keys(STATUS_LABEL).map(status => <div key={status}><i className={`legend-line ${status}`} />{STATUS_LABEL[status]}</div>)}<hr />{[[7, 'Trunk · 96 fibres'], [5, 'Distribution · 48'], [3, 'Access · 24']].map(([width, label]) => <div key={label}><i className="legend-width" style={{ height: width }} />{label}</div>)}</div><div>{nodeTypes.map(type => <div key={type}><span className="legend-node" dangerouslySetInnerHTML={{ __html: nodeSvg(type, 'unknown') }} />{TYPE_LABEL[type]}</div>)}</div></div><small><MapPin size={11} />Customer markers are serving-network anchors</small></div>}
    {dragging && <div className="fibre-drop"><Upload size={36} /><strong>Drop a KMZ or KML file to plot your network</strong></div>}
  </div>;
}
