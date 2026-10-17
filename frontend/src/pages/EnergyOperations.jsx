import { useCallback, useEffect, useRef, useState } from 'react';
import { Battery, Download, RefreshCw, Upload, Zap } from 'lucide-react';
import api from '../api/client';
import { drawChart } from '../components/energyCharts';
import '../styles/energy.css';

const SITES = ['PROJN01', 'LEKKP01', 'ADEMP01'];
const number = value => value == null ? '—' : Number(value).toFixed(2);
const watDay = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Lagos', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
const watNow = () => new Date(Date.now() + 3600000).toISOString().slice(0, 16);
const errorText = error => typeof error.response?.data?.detail === 'string' ? error.response.data.detail : error.response?.status === 422 ? 'Check the supplied date, readings and workbook format.' : error.message || 'Energy operation failed.';
const chartHeight = theme => theme === 'excel' ? 552 : 680;
const chartDate = day => new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Africa/Lagos' }).format(new Date(day + 'T12:00:00+01:00'));
const syncTime = value => value ? new Date(value).toLocaleString('en-GB', { timeZone: 'Africa/Lagos' }) + ' WAT' : 'Not yet';
const pngBlob = canvas => new Promise((resolve, reject) => canvas.toBlob(value => value ? resolve(value) : reject(new Error('PNG export failed')), 'image/png'));
function exportCanvas(report, site, kind, theme) {
  const canvas = document.createElement('canvas'); canvas.width = 2400; canvas.height = chartHeight(theme) * 2;
  canvas.getContext('2d').scale(2, 2); drawChart(canvas, site, kind, theme, report); return canvas;
}
async function download(canvas, name) {
  const url = URL.createObjectURL(await pngBlob(canvas)); const anchor = document.createElement('a');
  anchor.href = url; anchor.download = name; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 30000);
}

function EnergyChart({ report, site, kind, theme, onNotice }) {
  const ref = useRef(null);
  useEffect(() => { drawChart(ref.current, site, kind, theme, report); }, [report, site, kind, theme]);
  async function copy() {
    try {
      if (!navigator.clipboard?.write || !window.ClipboardItem) throw new Error('Image clipboard unavailable');
      const canvas = exportCanvas(report, site, kind, theme);
      await navigator.clipboard.write([new ClipboardItem({ 'image/png': pngBlob(canvas) })]); onNotice('Chart copied for your email.');
    } catch {
      try { await download(exportCanvas(report, site, kind, theme), `${site.id}-${kind}-${report.date}.png`); onNotice('Image clipboard unavailable; PNG downloaded.'); }
      catch (error) { onNotice(error.message); }
    }
  }
  return <article className={`energy-chart energy-chart--${theme}`}><header><div className="energy-chart-heading"><strong>{site.id}</strong><span className="energy-chart-kind">{kind === 'grid' ? 'EKEDC availability' : `${site.fuel} generator`}</span></div><time dateTime={report.date}>{chartDate(report.date)} <span>WAT</span></time></header>
    <canvas ref={ref} width={1200} height={chartHeight(theme)} role="img" aria-label={`${site.id} ${kind} report for ${report.date}`} />
    <div><button className="response-button" onClick={copy}>Copy image</button><button className="response-button" onClick={() => download(exportCanvas(report, site, kind, theme), `${site.id}-${kind}-${report.date}.png`).catch(error => onNotice(error.message))}><Download size={14} />PNG</button></div></article>;
}

export default function EnergyOperations({ identity }) {
  const [status, setStatus] = useState(null), [loadedReport, setReport] = useState(null);
  const [day, setDay] = useState(watDay), [source, setSource] = useState('workbook'), [site, setSite] = useState('all'), [theme, setTheme] = useState('excel');
  const [error, setError] = useState(''), [notice, setNotice] = useState(''), [busy, setBusy] = useState(false), [refresh, setRefresh] = useState(0);
  const [tab, setTab] = useState('reports');
  const [trialSite, setTrialSite] = useState('PROJN01'), [trial, setTrial] = useState(null);
  const [form, setForm] = useState(null);
  const report = loadedReport?.mode === source && loadedReport.date === day ? loadedReport : null;
  const fileRef = useRef(null), initialDate = useRef(false), pendingRequest = useRef(null);
  const canWrite = identity.roles.some(role => ['NOC.Operator', 'NOC.Admin'].includes(role));
  const admin = identity.roles.includes('NOC.Admin');
  const synchronization = status?.sync;
  const fileDelivery = synchronization?.transport === 'ssh_push';
  const waitingForSource = fileDelivery && synchronization?.pending && synchronization.request_state !== 'delayed';
  const sourceHeading = fileDelivery && synchronization.pending ? synchronization.request_state === 'delayed' ? 'Sync delayed · showing the last valid report' : 'Sync requested · waiting for source workbook' : fileDelivery ? !synchronization.configured ? 'Workbook delivery setup required' : synchronization.connected ? 'Workbook up to date' : synchronization.last_success_at ? 'Workbook delivery delayed · showing last valid report' : 'Waiting for first workbook delivery'
    : !synchronization?.enabled ? synchronization?.active_revision_id ? 'OneDrive synchronization paused · cached workbook' : 'OneDrive synchronization not enabled'
    : !synchronization.configured ? 'OneDrive setup required'
      : synchronization.connected ? 'OneDrive synchronization active'
        : synchronization.last_success_at ? 'OneDrive synchronization delayed · showing last valid report'
          : 'OneDrive configured · waiting for first successful sync';

  useEffect(() => {
    const timer = setInterval(() => setRefresh(value => value + 1), waitingForSource ? 5000 : 30000);
    return () => clearInterval(timer);
  }, [waitingForSource]);

  useEffect(() => {
    const controller = new AbortController();
    api.get('/energy/status', { signal: controller.signal }).then(({ data }) => {
      setStatus(data);
      if (data.sync?.pending) {
        pendingRequest.current = data.sync.requested_at;
      } else if (pendingRequest.current && data.sync?.last_success_at && new Date(data.sync.last_success_at) >= new Date(pendingRequest.current)) {
        pendingRequest.current = null;
        setNotice('Workbook updated. Reports now show the latest copy received from the source computer.');
      }
      if (!initialDate.current && data.metadata) { initialDate.current = true; setDay(data.metadata.defaultDate); }
    }).catch(value => { if (!controller.signal.aborted) setError(errorText(value)); });
    return () => controller.abort();
  }, [refresh]);
  useEffect(() => {
    const controller = new AbortController();
    api.get('/energy/report', { params: { day, source }, signal: controller.signal }).then(({ data }) => { setReport(data); setError(''); })
      .catch(value => { if (!controller.signal.aborted) { setReport(null); if (value.response?.status !== 404) setError(errorText(value)); } });
    return () => controller.abort();
  }, [day, source, refresh]);
  const loadTrial = useCallback(async (signal) => {
    const { data } = await api.get(`/energy/trial/${trialSite}`, { signal });
    if (signal?.aborted) return;
    setTrial(data);
    const previous = data.events[0]?.observation;
    setForm({ request_key: crypto.randomUUID(), expected_revision: data.revision, effective_at: watNow(),
      grid: previous?.grid || 'unknown', gen: previous?.gen || 'unknown', grid_balance: '', diesel_litres: '', comment: '' });
  }, [trialSite]);
  useEffect(() => {
    const controller = new AbortController();
    if (tab === 'collector' && status?.trial_enabled) loadTrial(controller.signal).catch(value => { if (!controller.signal.aborted) setError(errorText(value)); });
    return () => controller.abort();
  }, [tab, status?.trial_enabled, loadTrial]);

  async function importFile(event) {
    const input = event.target, file = input.files[0]; if (!file) return;
    setError(''); setNotice('');
    if (!file.name.toLowerCase().endsWith('.xlsx') || file.size > 10 * 1024 * 1024 || !file.size) {
      setError('Choose the main XLSX tracker, no larger than 10 MB.'); input.value = ''; return;
    }
    setBusy(true);
    try {
      const data = new FormData(); data.append('file', file);
      if (fileDelivery) data.append('modified_at', new Date(file.lastModified).toISOString());
      const result = await api.post(fileDelivery ? '/energy/deliveries' : '/energy/imports', data,
        { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60000 });
      setNotice(fileDelivery ? result.data.notice : result.data.outcome === 'already_imported'
        ? 'This workbook revision was already imported. The latest revision remains active.'
        : 'Workbook imported. Operational Excel is unchanged.');
      setSource('workbook'); setTab('reports'); setRefresh(value => value + 1);
    } catch (value) { setError(errorText(value)); }
    finally { setBusy(false); input.value = ''; }
  }
  async function synchronize() {
    setBusy(true); setError('');
    try {
      const { data } = await api.post('/energy/sync');
      if (data.requested_at) pendingRequest.current = data.requested_at;
      setNotice(data.notice); setRefresh(value => value + 1);
    } catch (value) { setError(errorText(value)); }
    finally { setBusy(false); }
  }
  async function observe(event) {
    event.preventDefault(); setBusy(true); setError('');
    try { await api.post(`/energy/trial/${trialSite}`, { ...form, effective_at: `${form.effective_at}+01:00`,
      grid_balance: form.grid_balance === '' ? null : Number(form.grid_balance), diesel_litres: trialSite === 'PROJN01' && form.diesel_litres !== '' ? Number(form.diesel_litres) : null });
      setNotice('Trial observation saved once. Previous intervals close automatically; Excel is unchanged.'); await loadTrial(); setRefresh(value => value + 1);
    } catch (value) { setError(errorText(value)); } finally { setBusy(false); }
  }
  const sites = report?.sites.filter(value => site === 'all' || site === value.id) || [];
  async function exportAll() {
    const h = chartHeight(theme), canvas = document.createElement('canvas'); canvas.width = 2400; canvas.height = 160 + sites.length * h;
    const ctx = canvas.getContext('2d'); ctx.fillStyle = theme === 'excel' ? '#000' : theme === 'dark' ? '#101820' : '#fff'; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = theme === 'light' ? '#223e50' : '#fff'; ctx.font = '600 40px Arial'; ctx.fillText(`AFL · Daily Energy Report · ${report.date}`, 50, 72);
    ctx.font = '24px Arial'; ctx.fillText(`${source === 'trial' ? 'ISOLATED COLLECTOR TRIAL' : 'Imported workbook snapshot'} · Lagos / WAT`, 50, 120);
    sites.forEach((value, index) => ['grid', 'gen'].forEach((kind, column) => ctx.drawImage(exportCanvas(report, value, kind, theme), column * 1200, 160 + index * h, 1200, h)));
    await download(canvas, `AFL-energy-${source}-${report.date}.png`);
  }

  return <div className="response-centre energy-page"><div className="response-page-heading"><div><span className="eyebrow">OPERATIONS / ENERGY / AFRICA-LAGOS</span><h1>Energy operations</h1><p>Daily EKEDC availability, generator runtime and source records for all three sites.</p></div><div className="response-inline"><button className="response-button" disabled={fileDelivery && admin && (busy || waitingForSource || !synchronization.configured)} onClick={fileDelivery && admin ? synchronize : () => setRefresh(value => value + 1)}><RefreshCw size={15} />{fileDelivery && admin ? waitingForSource ? 'Sync requested…' : synchronization.request_state === 'delayed' ? 'Retry sync' : 'Sync now' : 'Refresh'}</button>{admin && synchronization?.enabled && !fileDelivery && <button className="response-button" disabled={busy || !synchronization.configured || synchronization.pending} onClick={synchronize}><RefreshCw size={15} />{synchronization.pending ? 'Sync queued' : 'Sync now'}</button>}{admin && status && (!synchronization?.enabled || fileDelivery) && <><input ref={fileRef} type="file" accept=".xlsx" aria-label="Choose saved RawData workbook" hidden onChange={importFile} /><button className="response-button" disabled={busy || (fileDelivery && !synchronization.configured)} onClick={() => fileRef.current.click()}><Upload size={15} />{busy ? 'Updating workbook…' : fileDelivery ? 'Update from this computer' : 'Import RawData tracker'}</button></>}</div></div>
    <div className="energy-source"><Zap size={20} /><div><strong>{sourceHeading}</strong><p>{status?.last_import ? `Latest valid workbook: ${status.last_import.source} · ${status.last_import.record_count} records · imported ${syncTime(status.last_import.entered_at)}` : synchronization?.enabled ? 'Waiting for a validated copy of the configured RawData workbook.' : 'An administrator can import the main RawData XLSX tracker to preview reports.'}</p>{synchronization?.enabled && <><p>Last checked: {syncTime(synchronization.last_checked_at)} · Last successful check: {syncTime(synchronization.last_success_at)} · Workbook saved: {syncTime(synchronization.source_modified_at)}</p><p>{fileDelivery ? 'The source machine sends the saved workbook' : 'Saved workbook changes are checked'} every {synchronization.interval_seconds}s. This page refreshes every 30s.</p>{fileDelivery && admin && <p>Sync now requests the latest OneDrive workbook from the designated source computer, normally within one minute. You can use this button from any computer; no upload tools are needed on the computer viewing this page.</p>}{!synchronization.configured && <p>{fileDelivery ? 'Configure one file delivery source and disable Graph synchronization.' : 'Company sign-in and the OneDrive source must be configured by an administrator.'}</p>}{synchronization.last_error_message && <p role="status">{synchronization.last_error_message} · Next check: {syncTime(synchronization.next_attempt_at)}</p>}{fileDelivery && synchronization.pending && <p role="status">{synchronization.request_state === 'delayed' ? 'The source computer has not completed this request yet. Your last valid report is still available. You can retry, or it will update when the source computer reconnects.' : 'Your request is queued. Waiting for the source computer to send the latest workbook.'}</p>}{fileDelivery && !synchronization.agent_online && <p>{synchronization.agent_last_seen_at ? 'The source uploader is currently unavailable.' : 'The source uploader has not connected yet.'}{admin && ' Check that NOC1 is signed in and its updated uploader task is enabled.'}</p>}{synchronization.configured && !fileDelivery && !synchronization.worker_healthy && <p>The sync worker has not reported a recent heartbeat.</p>}</>}</div><span>{synchronization?.enabled ? fileDelivery && synchronization.request_state === 'delayed' ? 'SYNC DELAYED' : synchronization.pending ? 'SYNC REQUESTED' : synchronization.connected ? 'SYNC HEALTHY' : 'SYNC PENDING' : synchronization?.active_revision_id ? 'CACHED WORKBOOK' : 'MANUAL IMPORT'}</span></div>
    {error && <p className="response-error" role="alert">{error}</p>}{notice && <p className="response-notice" role="status">{notice}</p>}
    <div className="energy-toolbar"><div className="response-inline"><button className={`response-button ${tab === 'reports' ? 'primary' : ''}`} onClick={() => setTab('reports')}>Daily reports</button><button className={`response-button ${tab === 'records' ? 'primary' : ''}`} onClick={() => setTab('records')}>Source records</button>{status?.trial_enabled && <button className={`response-button ${tab === 'collector' ? 'primary' : ''}`} onClick={() => setTab('collector')}>Collector trial</button>}</div><div className="response-inline"><label>Day (WAT)<input type="date" required min="2000-01-02" max={watDay()} value={day} onChange={event => { if (event.target.value) setDay(event.target.value); }} /></label><label>Site<select value={site} onChange={event => setSite(event.target.value)}><option value="all">All three sites</option>{SITES.map(value => <option key={value}>{value}</option>)}</select></label><label>Dataset<select value={source} onChange={event => setSource(event.target.value)}><option value="workbook">Imported workbook</option>{status?.trial_enabled && <option value="trial">Isolated collector trial</option>}</select></label></div></div>
    <p className="energy-battery"><Battery size={16} />All sites have batteries; no grid/generator supply does not establish downtime. No telemetry is connected.</p>
    {tab !== 'collector' && !report && <div className="response-panel energy-empty">{status?.last_import || source === 'trial' ? 'Loading report, or check the error above.' : synchronization?.enabled ? fileDelivery ? 'Choose your saved workbook to generate reports now, or wait for the first scheduled delivery.' : 'A report will appear after the first successful OneDrive sync.' : 'Import the main tracker to see your actual reporting data. Site summary workbooks are not the source.'}</div>}
    {tab === 'reports' && report && <><div className="energy-cards">{sites.map(value => <section className="noc-stat" key={value.id}><h2>{value.id}<small>{value.name}</small></h2><strong>{number(value.gridHours)} <small>hrs EKEDC</small></strong><p>{number(value.gridUsed)} kWh{value.gridPartial ? ' · incomplete readings' : ''}</p><div>{number(value.genHours)} hrs generator · {value.fuel === 'Gas' ? 'Gas consumption not tracked' : `${number(value.dieselUsed)} L diesel${value.dieselPartial ? ' · partial' : ''}`}</div><small>{number(value.unaccountedHours)} hrs unaccounted · {value.issues.length} validation notes</small>{report.trial_coverage?.[value.id] && <small>{number(report.trial_coverage[value.id].confirmedNoGridOrGenHours)} hrs confirmed without grid/gen · load power unknown</small>}</section>)}</div><div className="energy-toolbar"><label>Chart appearance<select value={theme} onChange={event => setTheme(event.target.value)}><option value="excel">Excel · original report style</option><option value="light">Light · email friendly</option><option value="dark">Dark · modern</option></select></label><button className="response-button" disabled={!sites.length} onClick={() => exportAll().catch(value => setError(value.message))}><Download size={15} />Download full report</button></div><div className="energy-charts">{sites.flatMap(value => ['grid', 'gen'].map(kind => <EnergyChart key={`${value.id}:${kind}`} site={value} kind={kind} theme={theme} report={report} onNotice={setNotice} />))}</div></>}
    {tab === 'records' && report && <><section className="response-panel energy-records"><h2>Source records · {report.start} → {report.end} WAT</h2><div className="energy-table"><table><thead><tr><th>Row / site</th><th>Source</th><th>Start → stop (WAT)</th><th>Hours</th><th>Balance</th><th>Used</th><th>Operator / comment</th></tr></thead><tbody>{sites.flatMap(value => value.records.map((row, index) => <tr key={`${value.id}:${row.row}:${row.kind}:${index}`}><td>{row.row} · {value.id}</td><td>{row.kind} · {row.status}</td><td>{row.start}<br />{row.stop || 'Open · excluded'}</td><td>{number(row.hours)}{row.meterHours != null && <small>Meter: {number(row.meterHours)} h</small>}</td><td>{number(row.opening)} → {number(row.closing)}</td><td>{number(row.used)} {row.kind === 'grid' ? 'kWh' : value.fuel === 'Gas' ? '(not tracked)' : 'L'}</td><td>{row.operator}<small>{row.comment}</small></td></tr>))}</tbody></table></div></section><section className="response-panel energy-notes"><h2>Validation notes</h2>{sites.flatMap(value => value.issues.map((issue, index) => <p key={`${value.id}:${index}`}>{value.id} · {issue.row || 'Summary'} · {issue.message}</p>))}<h2>Top-ups / balance increases</h2>{report.events.filter(value => site === 'all' || value.site === site).map((value, index) => <p key={index}>{value.site} · {value.time} · +{number(value.amount)} {value.kind === 'grid' ? 'kWh' : 'L'} · {value.evidence}</p>)}</section></>}
    {tab === 'collector' && status?.trial_enabled && <section className="response-panel energy-collector"><h2>Collector trial · separate from workbook reporting</h2><p>One observation closes the previous interval. Keep readings blank when unavailable. Last open states are excluded from totals until the next observation. Top-ups, refills, late corrections and operational cutover need the next workflow milestone.</p><label>Trial site<select value={trialSite} disabled={busy} onChange={event => { setForm(null); setTrial(null); setTrialSite(event.target.value); }}>{SITES.map(value => <option key={value}>{value}</option>)}</select></label>{form && <form className="response-form" onSubmit={observe}><div className="energy-form-grid"><label>Observation time (Lagos)<input required type="datetime-local" value={form.effective_at} onChange={event => setForm({ ...form, effective_at: event.target.value })} /></label>{['grid', 'gen'].map(field => <label key={field}>{field === 'grid' ? 'EKEDC available' : 'Generator running'}<select value={form[field]} onChange={event => setForm({ ...form, [field]: event.target.value })}><option value="unknown">Unknown / not observed</option><option value="on">Yes</option><option value="off">No</option></select></label>)}<label>EKEDC units remaining (kWh)<input type="number" min="0" step="any" value={form.grid_balance} onChange={event => setForm({ ...form, grid_balance: event.target.value })} placeholder="Not measured" /></label>{trialSite === 'PROJN01' && <label>Diesel remaining (litres)<input type="number" min="0" step="any" value={form.diesel_litres} onChange={event => setForm({ ...form, diesel_litres: event.target.value })} placeholder="Not measured" /></label>}</div><label>Notes<textarea maxLength={1000} value={form.comment} onChange={event => setForm({ ...form, comment: event.target.value })} /></label>{canWrite && <button className="response-button primary" disabled={busy}>{busy ? 'Saving…' : 'Record trial observation'}</button>}</form>}<p>Revision {trial?.revision ?? '—'} · States are inherited for convenience; readings require a new measurement.</p>{trial?.events.map(value => <p key={value.id}>#{value.revision} · {new Date(value.effective_at).toLocaleString('en-GB', { timeZone: 'Africa/Lagos' })} WAT · EKEDC {value.observation.grid} · Gen {value.observation.gen} · {value.entered_by}</p>)}</section>}
    <details className="energy-method"><summary>Calculation rules and current limits</summary><p>Daily window: previous day 23:59:59 to selected day 23:59:59 Lagos. Hours use elapsed timestamps and merge overlaps. Open intervals are excluded. Usage is opening minus closing; increases require top-up/refill review. Boundary usage is prorated by time. Excel-style charts show negative balance change and round each session like the workbook; overview totals keep full precision. Gas consumption is not tracked at Lekki or Ademola. Synchronization reads saved workbook copies; changes that have not reached the source machine or server are unavailable. It never writes to Excel or sends email. It does not detect physical power state or establish a production collector cutover.</p></details>
  </div>;
}
