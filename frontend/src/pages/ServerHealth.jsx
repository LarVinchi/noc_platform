import { createElement, useEffect, useState } from 'react';
import { Activity, Cpu, Database, HardDrive, MemoryStick, RefreshCw, Server, GitBranch, ExternalLink, ShieldCheck } from 'lucide-react';
import api from '../api/client';
import '../styles/response.css';
import '../styles/server-health.css';

const REPO = 'https://github.com/LarVinchi/noc_platform';
const number = value => value == null ? '—' : Number(value).toLocaleString('en-GB', { maximumFractionDigits: 1 });
const percent = value => value == null ? '—' : `${number(value)}%`;
const bytes = value => { if (value == null) return '—'; const unit = value >= 1024 ** 3 ? 3 : value >= 1024 ** 2 ? 2 : value >= 1024 ? 1 : 0; return `${number(value / 1024 ** unit)} ${['B', 'KiB', 'MiB', 'GiB'][unit]}`; };
const date = value => value ? new Date(value).toLocaleString('en-GB', { timeZone: 'Africa/Lagos' }) + ' WAT' : 'Not reported';
const duration = value => value == null ? '—' : `${Math.floor(value / 86400)}d ${Math.floor(value % 86400 / 3600)}h ${Math.floor(value % 3600 / 60)}m`;
const title = value => value?.replaceAll('_', ' ') || 'Unknown';
function Revision({ sha }) { return sha ? <a href={`${REPO}/commit/${sha}`} target="_blank" rel="noreferrer"><code title={sha} aria-label={`Commit ${sha}`}>{sha.slice(0, 8)}</code><ExternalLink size={11} /></a> : <span>Not confirmed</span>; }
function Badge({ value }) { return <span className={`host-badge host-badge--${value.toLowerCase().replaceAll(' ', '-')}`}>{title(value)}</span>; }
function Metric({ icon, label, value, detail, stale }) { return <article className={`host-metric ${stale ? 'host-muted' : ''}`}><div>{createElement(icon, { size: 18 })}<span>{label}</span></div><strong>{value}</strong><small>{detail}</small></article>; }
function Table({ columns, children }) { return <div className="host-table" role="region" aria-label={`${columns[0]} details`} tabIndex={0}><table><thead><tr>{columns.map(value => <th key={value}>{value}</th>)}</tr></thead><tbody>{children}</tbody></table></div>; }
function Facts({ rows }) { return <dl className="host-facts">{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>; }

function Trend({ points, field, label, bucket }) {
  const width = 720, height = 150, left = 40, right = 12, top = 15, bottom = 30;
  const start = points.length ? new Date(points[0].time).getTime() : 0, end = points.length ? new Date(points[points.length - 1].time).getTime() : 1;
  const x = value => left + (new Date(value.time).getTime() - start) / Math.max(1, end - start) * (width - left - right);
  const y = value => top + (100 - value) / 100 * (height - top - bottom);
  const segments = []; let segment = [], last;
  points.forEach(point => { if (point[field] == null || (last && new Date(point.time) - new Date(last.time) > bucket * 2000)) { if (segment.length) segments.push(segment); segment = []; } if (point[field] != null) segment.push(point); last = point; });
  if (segment.length) segments.push(segment);
  return <section className="host-trend"><h3>{label}</h3>{points.length ? <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${label} percentage history; gaps indicate missing samples`}>
    {[0, 50, 100].map(value => <g key={value}><line x1={left} x2={width - right} y1={y(value)} y2={y(value)} stroke="#2b4051" /><text x={left - 8} y={y(value) + 4} textAnchor="end">{value}</text></g>)}
    {segments.map((values, i) => <polyline data-series={field} key={i} points={values.map(value => `${x(value)},${y(value[field])}`).join(' ')} fill="none" stroke={field === 'cpu_percent' ? '#38bdf8' : field === 'memory_percent' ? '#a78bfa' : '#fbbf24'} strokeWidth="2" />)}
    {points.filter(value => value[field] != null).map(value => <circle key={value.time} cx={x(value)} cy={y(value[field])} r="3" fill="#b8d5e4" tabIndex={0}><title>{date(value.time)} · {percent(value[field])} · {value.samples} samples</title></circle>)}
    <text x={left} y={height - 7}>{date(start || null)}</text><text x={width - right} y={height - 7} textAnchor="end">{date(end)}</text>
  </svg> : <p className="host-empty">No samples in this period.</p>}</section>;
}

function DeploymentTimeline({ report, summary }) {
  const gh = report.github, deployment = report.deployment;
  const statuses = [
    ['Build passed', gh.main_sha && gh.build_sha === gh.main_sha && gh.build_result === 'success' ? 'success' : gh.build_result === 'failure' ? 'failed' : 'pending'],
    ['Release published', gh.release_sha && gh.release_sha === gh.main_sha ? 'success' : 'pending'],
    ['Server deploying', deployment.target_sha === gh.main_sha && deployment.result === 'running' ? 'running' : gh.main_sha && summary.running_sha === gh.main_sha && deployment.result === 'success' ? 'success' : 'pending'],
    [deployment.target_sha === gh.main_sha && deployment.result === 'failed' ? 'Deployment failed' : 'Deployment succeeded', summary.state === 'Up to date' ? 'success' : deployment.target_sha === gh.main_sha && deployment.result === 'failed' ? 'failed' : 'pending'],
  ];
  return <ol className="host-pipeline" aria-label="Deployment pipeline">{statuses.map(([label, state], index) => <li key={index} className={`host-pipeline--${summary.state === 'Status stale' ? 'unknown' : state}`}><span>{index + 1}</span><div>{label}<small>{summary.state === 'Status stale' ? 'Evidence stale / unavailable' : title(state)}</small></div></li>)}</ol>;
}

export default function ServerHealth({ identity }) {
  const [data, setData] = useState(null), [selected, setSelected] = useState(''), [error, setError] = useState('');
  const [hours, setHours] = useState(24), [history, setHistory] = useState(null), [historyError, setHistoryError] = useState('');
  const [refresh, setRefresh] = useState(0), [clock, setClock] = useState(Date.now);
  const admin = identity.roles.includes('NOC.Admin');
  useEffect(() => {
    if (!admin) return;
    const controller = new AbortController(); let timer;
    async function load() {
      try { const { data: result } = await api.get('/platform-health/hosts', { signal: controller.signal }); if (!controller.signal.aborted) { setData(result); setError(''); } }
      catch { if (!controller.signal.aborted) setError('Unable to refresh server status. Displayed readings are last known values.'); }
      if (!controller.signal.aborted) timer = setTimeout(load, 15000);
    }
    load(); return () => { controller.abort(); clearTimeout(timer); };
  }, [admin, refresh]);
  useEffect(() => { const timer = setInterval(() => setClock(Date.now()), 5000); return () => clearInterval(timer); }, []);
  const host = data?.hosts.find(value => value.host_id === selected) || data?.hosts[0], hostId = host?.host_id;
  useEffect(() => {
    if (!admin || !hostId) return;
    const controller = new AbortController(); let timer;
    async function load() {
      try { const { data: result } = await api.get(`/platform-health/hosts/${encodeURIComponent(hostId)}/history`, { params: { hours }, signal: controller.signal }); if (!controller.signal.aborted) { setHistory({ ...result, hostId, hours }); setHistoryError(''); } }
      catch { if (!controller.signal.aborted) setHistoryError('Trend history is unavailable.'); }
      if (!controller.signal.aborted) timer = setTimeout(load, 30000);
    }
    load(); return () => { controller.abort(); clearTimeout(timer); };
  }, [admin, hostId, hours, refresh]);
  if (!admin) return <section className="response-panel host-empty"><ShieldCheck size={24} /><h1>Administrator access required</h1><p>Server details and deployment history are restricted to NOC administrators.</p></section>;
  const report = host?.report, original = host?.summary;
  const stale = !!error || !original?.host_fresh || clock - new Date(report?.observed_at).getTime() > 120000 || clock - new Date(host?.received_at).getTime() > 120000;
  const summary = original ? { ...original, state: stale ? 'Status stale' : original.state, application_health: stale ? 'Unknown' : original.application_health, reason: stale ? 'Current server evidence unavailable; displaying last known values.' : original.reason } : null;
  const currentHistory = history && history.hostId === hostId && history.hours === hours ? history : null;
  const metrics = report?.metrics, deployment = report?.deployment, github = report?.github;
  return <div className="response-centre host-page"><div className="response-page-heading"><div><span className="eyebrow">PLATFORM / SERVER HEALTH / DEPLOYMENTS</span><h1>Server health & deployments</h1><p>Host resources, application health and the release actually running on your server.</p></div><button className="response-button" onClick={() => setRefresh(value => value + 1)}><RefreshCw size={15} />Refresh</button></div>
    {error && <p className="response-error" role="alert">{error}</p>}{!data && !error && <p role="status">Loading server reports…</p>}
    {data && !host && <section className="response-panel host-empty"><Server size={36} /><h2>No server reports received</h2><p>Activate the host collector on the server to see real readings, deployment progress and version comparisons.</p><small>No host metrics are inferred from this browser or the API container.</small></section>}
    {host && <><div className="host-summary-bar"><div><Server size={22} /><strong>{report.host.hostname}</strong><span>{report.host.distribution} {report.host.version}</span></div><label>Host<select value={hostId} onChange={event => setSelected(event.target.value)}>{data.hosts.map(value => <option key={value.host_id} value={value.host_id}>{value.host_id}</option>)}</select></label><Badge value={summary.state} /><span className="host-application-state">Application <Badge value={summary.application_health} /></span></div>
      <p className={`host-freshness ${stale ? 'host-freshness--stale' : ''}`}><Activity size={14} />{stale ? 'Stale readings — current resource use and application health are unknown.' : 'Host readings current'} · Last sample: {date(report.observed_at)} · Received: {date(host.received_at)}</p>
      <div className="host-metrics"><Metric icon={Cpu} label="Host CPU" value={percent(metrics.cpu_percent)} detail={`${report.host.cpu_cores} cores · load ${metrics.load.map(number).join(' / ')}`} stale={stale} /><Metric icon={MemoryStick} label="Host RAM" value={percent(metrics.memory_used_percent)} detail={`${bytes(metrics.memory_total_bytes != null && metrics.memory_available_bytes != null ? metrics.memory_total_bytes - metrics.memory_available_bytes : null)} used / ${bytes(metrics.memory_total_bytes)} total`} stale={stale} /><Metric icon={HardDrive} label="Busiest filesystem" value={metrics.filesystems.some(row => row.used_percent != null) ? percent(Math.max(...metrics.filesystems.filter(row => row.used_percent != null).map(row => row.used_percent))) : '—'} detail="Capacity used · inspect each mount below" stale={stale} /><Metric icon={Database} label="Application readiness" value={summary.application_health} detail={stale ? 'Last known probe; current status unknown' : report.application_ready ? 'API readiness and database probe passed' : 'API/database probe failed or unavailable'} stale={stale} /></div>
      {!stale && summary.alerts.length > 0 && <div className="host-alerts" role="status">{summary.alerts.map(row => <span key={row.metric} className={`host-alert--${row.severity}`}>{row.metric}: {percent(row.value)} · {row.severity} threshold</span>)}</div>}
      <section className="response-panel"><div className="host-section-heading"><div><h2><GitBranch size={18} />Deployment status</h2><p>{summary.reason}</p></div>{github.build_run_id && <a href={`${REPO}/actions/runs/${github.build_run_id}`} target="_blank" rel="noreferrer">GitHub build <ExternalLink size={13} /></a>}</div><DeploymentTimeline report={report} summary={summary} />
        <div className="host-versions">{[['Latest main', github.main_sha], ['Published release', github.release_sha], ['Running API + frontend', summary.running_sha], ['Last successful installation', deployment.deployed_sha]].map(([label, sha]) => <div key={label}><small>{label}</small><Revision sha={sha} /></div>)}</div>
        <Facts rows={[
          ['Current stage', <span>{title(deployment.stage)} <Badge value={deployment.result} /></span>], ['Last successful deployment', date(deployment.deployed_at)],
          ['Deployment checker', `${date(deployment.last_check_at)}${summary.deployer_fresh ? '' : ' · stale / unavailable'}`], ['GitHub last checked', `${date(github.checked_at)}${summary.github_fresh && !github.error ? '' : ' · stale / unavailable'}`],
          ['Rollback outcome', title(deployment.rollback)], ['Started', date(deployment.started_at)],
        ]} />{deployment.error_type && <p className="response-error">Last deployment error: {deployment.error_type}. Inspect the protected server log for details.</p>}
      </section>
      <section className="response-panel"><div className="host-section-heading"><div><h2>Resource history</h2><p>CPU/RAM: bucket averages. Storage: busiest filesystem peak. Gaps remain visible.</p></div><label>Period<select value={hours} onChange={event => setHours(Number(event.target.value))}><option value={1}>Last hour</option><option value={24}>Last 24 hours</option><option value={168}>Last 7 days</option></select></label></div>{historyError && <p className="response-error">{historyError}</p>}{currentHistory ? <div className="host-trends">{[['cpu_percent', 'CPU utilization'], ['memory_percent', 'RAM utilization'], ['storage_percent', 'Storage capacity used']].map(([field, label]) => <Trend key={field} field={field} label={label} points={currentHistory.points} bucket={currentHistory.bucket_seconds} />)}</div> : <p>Loading metric history…</p>}</section>
      <div className="host-detail-grid"><section className="response-panel"><h2>Linux host</h2><Facts rows={[
        ['Distribution', `${report.host.distribution} ${report.host.version}`], ['Kernel / architecture', `${report.host.kernel} · ${report.host.architecture}`], ['CPU', report.host.cpu_model],
        ['Host uptime', duration(report.host.uptime_seconds)], ['Swap used / total', `${bytes(metrics.swap_used_bytes)} / ${bytes(metrics.swap_total_bytes)}`], ['Host-agent heartbeat', date(host.received_at)],
      ]} /></section><section className="response-panel"><h2>Docker engine / VM allocation</h2><p>{report.docker.available ? report.docker.operating_system : 'Docker engine unavailable'}</p><Facts rows={[
        ['Context / engine', `${report.docker.context} · ${report.docker.name || 'Not reported'}`], ['Allocated CPU / RAM', `${number(report.docker.cpus)} CPUs · ${bytes(report.docker.memory_bytes)}`],
      ]} /><p>Engine allocation and container consumption are separate from Linux host utilization.</p></section></div>
      <section className="response-panel"><h2>Application containers</h2><Table columns={['Container', 'Status', 'Health check', 'Restarts', 'CPU', 'RAM used / limit', 'Image version']}>{report.containers.map(row => <tr key={row.name}><th scope="row">{row.name}</th><td><Badge value={stale ? 'Unknown' : row.status} /></td><td>{row.health || 'No health check'}</td><td>{row.restarts}</td><td>{percent(row.cpu_percent)}</td><td>{bytes(row.memory_used_bytes)} / {bytes(row.memory_limit_bytes)}</td><td><Revision sha={row.revision} /></td></tr>)}</Table>{!report.containers.length && <p>No container readings available.</p>}<p>Docker CPU can exceed 100% across multiple cores. Container figures are last known values when the host report is stale.</p></section>
      <section className="response-panel"><h2>Filesystem capacity</h2><Table columns={['Mount', 'Capacity used', 'Used / total', 'Available', 'Inodes used']}>{metrics.filesystems.map(row => <tr key={row.mount}><th scope="row">{row.mount}</th><td>{percent(row.used_percent)}</td><td>{bytes(row.total_bytes != null && row.used_percent != null ? row.total_bytes * row.used_percent / 100 : null)} / {bytes(row.total_bytes)}</td><td>{bytes(row.available_bytes)}</td><td>{percent(row.inode_used_percent)}</td></tr>)}</Table></section>
      <div className="host-detail-grid"><section className="response-panel"><h2>Network interfaces</h2><Table columns={['Interface', 'Link', 'Receive / sec', 'Transmit / sec', 'RX / TX errors']}>{metrics.interfaces.map(row => <tr key={row.name}><th scope="row">{row.name}</th><td>{row.state}</td><td>{bytes(row.rx_bytes_per_second)}</td><td>{bytes(row.tx_bytes_per_second)}</td><td>{row.rx_errors} / {row.tx_errors}</td></tr>)}</Table></section><section className="response-panel"><h2>Disk I/O by device</h2><Table columns={['Device', 'Read / sec', 'Write / sec']}>{metrics.disk_io.map(row => <tr key={row.device}><th scope="row">{row.device}</th><td>{bytes(row.read_bytes_per_second)}</td><td>{bytes(row.write_bytes_per_second)}</td></tr>)}</Table></section></div>
      <section className="response-panel"><h2>Recent deployment attempts</h2><Table columns={['Version', 'Started (Lagos)', 'Last stage', 'Result', 'Duration', 'Rollback']}>{report.deployments.map((row, i) => <tr key={row.attempt_id || i}><td><Revision sha={row.target_sha} /></td><td>{date(row.started_at)}</td><td>{title(row.stage)}</td><td><Badge value={row.result} /></td><td>{row.started_at && row.updated_at ? duration(Math.max(0, (new Date(row.updated_at) - new Date(row.started_at)) / 1000)) : '—'}</td><td>{title(row.rollback)}</td></tr>)}</Table>{!report.deployments.length && <p>No instrumented deployment attempts received yet.</p>}</section>
      {report.collection_errors.length > 0 && <p className="response-error">Collector observations: {report.collection_errors.map(title).join(' · ')}. Unavailable measurements are not replaced with zeros.</p>}
      <p className="host-footnote">Host sampling: about 30 seconds · Dashboard refresh: 15 seconds · Metric retention: 7 days · Timezone: Africa/Lagos. Threshold flags describe the latest sample and do not establish a sustained incident. This page is read-only.</p>
    </>}
  </div>;
}
