import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import apiClient from '../api/client';

const colors = { live: '#35e0a1', down: '#ff5c5c', planned: '#7aa2ff', unknown: '#e8b84a' };

export default function GeographicNetwork() {
  const container = useRef(null);
  const map = useRef(null);
  const clickHandler = useRef(null);
  const [inventory, setInventory] = useState({ type: 'FeatureCollection', features: [], routes: [] });
  const [imports, setImports] = useState([]);
  const [importId, setImportId] = useState('');
  const [layer, setLayer] = useState(null);
  const [selected, setSelected] = useState(null);
  const [impact, setImpact] = useState(null);
  const [routeId, setRouteId] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState('all');
  const [impactError, setImpactError] = useState('');
  useEffect(() => {
    const instance = L.map(container.current).setView([6.4468, 3.4725], 13);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© OpenStreetMap contributors' }).addTo(instance);
    L.control.scale({ imperial: false }).addTo(instance);
    map.current = instance;
    return () => { instance.remove(); map.current = null; };
  }, []);
  async function refresh() {
    try { const [geo, list] = await Promise.all([apiClient.get('/topology/geography'), apiClient.get('/topology/maps')]); setInventory(geo.data); setImports(list.data); setError(''); }
    catch { setError('Network inventory unavailable. Check the API connection.'); }
  }
  useEffect(() => { refresh(); const timer = setInterval(refresh, 30000); return () => clearInterval(timer); }, []);
  useEffect(() => {
    if (!importId) return;
    const controller = new AbortController();
    apiClient.get(importId === 'demo' ? '/topology/maps/demo' : `/topology/maps/${importId}`, { signal: controller.signal })
      .then(({ data }) => { setLayer(data); setSelected(null); setImpact(null); }).catch(() => { if (!controller.signal.aborted) setError('Could not load this map.'); });
    return () => controller.abort();
  }, [importId]);
  clickHandler.current = async (feature, source) => {
    setSelected({ ...feature.properties, source }); setRouteId(feature.properties.inventory_route_id || ''); setImpact(null); setImpactError('');
    if (feature.properties.inventory_route_id) {
      try { const { data } = await apiClient.get(`/topology/impact/${feature.properties.inventory_route_id}`); setImpact(data); }
      catch { setImpactError('Could not load customer impact.'); }
    }
  };
  useEffect(() => {
    if (!map.current) return;
    const group = L.featureGroup().addTo(map.current);
    for (const [geo, source] of [[inventory, 'inventory'], [layer, 'import']]) {
      if (!geo) continue;
      L.geoJSON(geo, {
        filter: (feature) => filter === 'all' || (feature.properties.monitoring_alarms?.length ? 'down' : feature.properties.status) === filter || feature.geometry.type === 'Point',
        style: (feature) => ({ color: feature.properties.monitoring_alarms?.length ? colors.down : colors[feature.properties.status] || colors.unknown, weight: 5, opacity: 0.9, dashArray: feature.properties.monitoring_alarms?.length || ['down', 'planned'].includes(feature.properties.status) ? '8 6' : undefined }),
        pointToLayer: (feature, latlng) => L.circleMarker(latlng, { radius: feature.properties.node_type === 'customer' ? 7 : 5, color: feature.properties.node_type === 'customer' ? '#b69cff' : '#5cc8ff', fillOpacity: 0.8 }),
        onEachFeature: (feature, leafletLayer) => {
          const label = document.createElement('span'); label.textContent = feature.properties.name || 'Network feature';
          leafletLayer.bindTooltip(label);
          leafletLayer.on('click', () => clickHandler.current(feature, source));
        },
      }).addTo(group);
    }
    if (group.getLayers().some((entry) => entry.getLayers().length)) map.current.fitBounds(group.getBounds(), { padding: [40, 40], maxZoom: 16 });
    return () => { group.remove(); };
  }, [inventory, layer, filter]);
  async function upload(event) {
    const file = event.target.files[0]; if (!file) return;
    setBusy(true); const body = new FormData(); body.append('file', file);
    try { const { data } = await apiClient.post('/topology/maps', body, { headers: { 'Content-Type': 'multipart/form-data' } }); await refresh(); setImportId(data.import_id); }
    catch (failure) { setError(typeof failure.response?.data?.detail === 'string' ? failure.response.data.detail : 'Map import failed.'); }
    finally { setBusy(false); event.target.value = ''; }
  }
  async function link() {
    setBusy(true);
    try { await apiClient.post(`/topology/maps/${importId}/link`, { route_id: routeId, feature_index: selected.feature_index }); await refresh(); const { data } = await apiClient.get(`/topology/maps/${importId}`); setLayer(data); setSelected(null); setImpact(null); }
    catch (failure) { setError(typeof failure.response?.data?.detail === 'string' ? failure.response.data.detail : 'Could not link route.'); }
    finally { setBusy(false); }
  }
  return <div className="space-y-4">
    <div className="flex flex-wrap gap-3 items-center"><label className="border border-cyan-700 text-cyan-300 rounded-lg px-3 py-2 text-sm cursor-pointer">{busy ? 'Processing…' : 'Import KMZ / KML'}<input type="file" accept=".kmz,.kml" disabled={busy} onChange={upload} className="sr-only" /></label><select aria-label="Map layer" value={importId} onChange={(e) => { setImportId(e.target.value); if (!e.target.value) { setLayer(null); setSelected(null); setImpact(null); } }} className="bg-slate-800 p-2 rounded-lg text-sm"><option value="">Inventory only</option><option value="demo">Lekki demo · approximate</option>{imports.map((row) => <option key={row.import_id} value={row.import_id}>{row.name}</option>)}</select><select aria-label="Route status filter" value={filter} onChange={(e) => setFilter(e.target.value)} className="bg-slate-800 p-2 rounded-lg text-sm">{['all', 'live', 'down', 'planned', 'unknown'].map((s) => <option key={s}>{s}</option>)}</select><button onClick={refresh} className="text-sm underline text-cyan-300">Refresh</button></div>
    <p className="text-xs text-slate-400">Red inventory routes have a last-observed down alarm on the route or a cable. Imported colors reflect file metadata. Customer pins are serving-NAP/route anchors; service health needs verification.</p>
    {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-4">
      <div ref={container} className="h-[600px] min-w-0 rounded-xl border border-slate-700 z-0" aria-label="Fibre network geographic map" />
      <aside className="rounded-xl border border-slate-700 p-4 space-y-4 text-sm">
        <h2 className="font-semibold">Customer impact & infrastructure</h2>
        {!selected ? <p className="text-slate-400">Select a route or customer to inspect its linked inventory and services.</p> : <>
          {selected.monitoring_alarms?.map(alarm => <p key={alarm.sensor_id} className="text-xs text-red-300">Sensor {alarm.sensor_id}: last observed down at {new Date(alarm.observed_at).toLocaleString()}. Confirm current conditions.</p>)}
          <h3 className="font-medium">{selected.name}</h3><p className="text-xs text-slate-400">{selected.location_source || selected.status || 'Status unknown'}</p>
          {selected.source === 'import' && selected.kind === 'route' && importId !== 'demo' && !selected.inventory_route_id && <div className="space-y-2"><label className="block text-xs">Link this line to an inventory route<select value={routeId} onChange={(e) => setRouteId(e.target.value)} className="bg-slate-800 p-2 w-full rounded-lg"><option value="">Select route</option>{inventory.routes.map((r) => <option key={r.route_id} value={r.route_id}>{r.name}</option>)}</select></label><button disabled={!routeId || busy} onClick={link} className="bg-cyan-700 p-2 rounded-lg disabled:opacity-50 text-xs">Use this line as inventory geometry</button></div>}
          {impactError && <p role="alert" className="text-red-300">{impactError}</p>}
          {impact && <><p>{impact.customer_count} customers · {impact.service_count} potentially affected services</p><p className="text-xs text-amber-200">Dependency analysis; monitoring must confirm service downtime.</p>{impact.services.map((s) => <article key={s.service_id} className="border-t border-slate-700 pt-3"><p>{s.customer} · {s.service_type}</p><p className="text-xs text-slate-400">{s.alternate_path_recorded ? 'Alternate path recorded; health unverified' : 'No alternate path recorded'}</p>{s.affected_paths.map((p, i) => <div key={i} className="text-xs text-slate-400 mt-2"><p>{p.route} → {p.cable} → core {p.core}{p.nap && ` → ${p.pfp} → ${p.pfs} → ${p.nap} → port ${p.port} → ${p.drop}`}</p><button onClick={async () => { try { const { data } = await apiClient.get(`/topology/cable-impact/${p.cable_id}`); setImpact(data); } catch { setImpactError('Could not load cable impact.'); } }} className="text-cyan-300 underline mt-1">Inspect this cable’s impact</button></div>)}</article>)}</>}
        </>}
      </aside>
    </div>
  </div>;
}
