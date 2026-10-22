import { useEffect, useRef, useState } from 'react';
import { Download } from 'lucide-react';
import api from '../api/client';
import CopyImageButton from './CopyImageButton';
import EnergyDatePicker from './EnergyDatePicker';
import { drawWeeklyChart, weeklyFields, weeklyImage, weeklyNumber, weeklyDate, weeklyDetails, weeklyAverage, weeklyCoverageNote } from './weeklyEnergyCharts';

const calendar = day => new Date(`${day}T12:00:00Z`);
const shift = (day, count) => { const date = calendar(day); date.setUTCDate(date.getUTCDate() + count); return date.toISOString().slice(0, 10); };
const monday = day => { const date = calendar(day); return shift(day, -((date.getUTCDay() + 6) % 7)); };
const toBlob = canvas => new Promise((resolve, reject) => canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('PNG export failed')), 'image/png'));
async function download(canvas, name) {
  const url = URL.createObjectURL(await toBlob(canvas)); const anchor = document.createElement('a');
  anchor.href = url; anchor.download = name; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 30000);
}

function WeeklyPanel({ report, site, kind, theme, onNotice }) {
  const canvas = useRef(null), field = weeklyFields(site, kind);
  useEffect(() => { drawWeeklyChart(canvas.current, report, site, kind, theme); }, [report, site, kind, theme]);
  const image = part => weeklyImage(report, site, kind, theme, part);
  const filename = part => `${site.id}-${kind}-weekly-${report.weekStart}-${part}.png`;
  const actions = part => <div className="energy-weekly-actions"><CopyImageButton key={`${report.weekStart}:${theme}:${part}`} label={`Copy ${part}`} image={() => image(part)} filename={filename(part)} onNotice={onNotice} /><button className="response-button" aria-label={`Download ${part} PNG`} onClick={() => download(image(part), filename(part)).catch(error => onNotice(error.message))}><Download size={14} />{part === 'chart' ? 'Chart PNG' : 'Table PNG'}</button></div>;
  const hasAdditions = field.measured && (site[field.addition] || 0) > 0;
  const displayedUsage = value => weeklyNumber(theme === 'excel' && value ? -value : value);
  return <article className={`energy-chart energy-chart--${theme} energy-weekly-panel`}>
    <header><div className="energy-chart-heading"><strong>{site.id}</strong><span className="energy-chart-kind">{field.name}{kind === 'gen' ? ` · ${site.fuel}` : ''}</span></div><span>{field.partial || (field.measured && field.usagePartial) ? 'Partial / review' : report.elapsed ? 'Recorded week' : 'Week to date'}</span></header>
    <canvas ref={canvas} width={1200} height={650} role="img" aria-label={`${site.id} weekly ${kind} chart`} />
    {actions('chart')}
    <section className="energy-weekly-table-section"><h3>{site.name} · {field.name}</h3><div className="energy-weekly-table-layout"><div className="energy-weekly-pivot"><table><caption>{weeklyDate(report.weekStart)} – {weeklyDate(report.weekEnd)} · Daily pivot summary</caption><thead><tr><th>Day</th><th>{kind === 'grid' ? 'EKEDC availability' : 'Generator runtime'} (hrs)</th>{field.measured && <th>{kind === 'grid' ? 'EKEDC' : 'Diesel'} {theme === 'excel' ? 'balance change' : 'used'} ({field.unit})</th>}{hasAdditions && <th>{kind === 'grid' ? 'Top-ups' : 'Refills'} ({field.unit})</th>}</tr></thead><tbody>
      {site.days.map(row => <tr key={row.date}><th scope="row">{weeklyDate(row.date)}</th><td>{weeklyNumber(row[field.hours])}</td>{field.measured && <td>{displayedUsage(row[field.usage])}{(kind === 'grid' ? row.gridPartial : row.dieselPartial) && row[field.usage] != null ? '*' : ''}</td>}{hasAdditions && <td className="energy-addition-value">{row.future ? '—' : '+' + weeklyNumber(row[field.addition] || 0)}{row[kind === 'grid' ? 'gridAdditionInferred' : 'dieselAdditionInferred'] ? '*' : ''}</td>}</tr>)}
    </tbody><tfoot><tr><th>Grand total</th><td>{weeklyNumber(site[field.hours])}</td>{field.measured && <td>{displayedUsage(site[field.usage])}{field.usagePartial ? '*' : ''}</td>}{hasAdditions && <td className="energy-addition-value">+{weeklyNumber(site[field.addition])}{field.additionInferred ? '*' : ''}</td>}</tr><tr><th>Daily average</th><td>{weeklyAverage(site, kind)}</td>{field.measured && <td>{displayedUsage(site[field.usageAverage])}</td>}{hasAdditions && <td>+{weeklyNumber(site[field.addition] / (report.averageDays || 7))}</td>}</tr></tfoot></table></div><aside className="energy-weekly-details" aria-label={`${site.id} ${kind} report details`}><dl>{weeklyDetails(report, site, kind).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>{kind === 'gen' && site.generatorCapacitySource && <small>Capacity reference: presentation template</small>}</aside></div></section>
    <p className="energy-weekly-note">{kind === 'gen' && site.fuel === 'Gas' ? 'Gas consumption not tracked. ' : ''}{weeklyCoverageNote(report, site, kind)}</p>
    {actions('table')}
  </article>;
}

export default function WeeklyEnergyReport({ source, site, defaultDay, refresh, theme, onTheme, onNotice }) {
  const [week, setWeek] = useState(() => monday(defaultDay)), [loaded, setLoaded] = useState(null), [error, setError] = useState(''), [includeGas, setIncludeGas] = useState(true);
  const report = loaded?.weekStart === week && loaded.mode === source ? loaded : null;
  const sites = report?.sites.filter(value => site === 'all' || site === value.id) || [];
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Lagos', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  useEffect(() => {
    const controller = new AbortController();
    api.get('/energy/weekly', { params: { week_start: week, source }, signal: controller.signal }).then(({ data }) => { setLoaded(data); setError(''); })
      .catch(value => { if (!controller.signal.aborted) { setLoaded(null); setError(typeof value.response?.data?.detail === 'string' ? value.response.data.detail : 'Unable to load the weekly report.'); } });
    return () => controller.abort();
  }, [week, source, refresh]);
  async function fullReport() {
    const panels = sites.flatMap(value => [{ site: value, kind: 'grid' }, ...(value.fuel === 'Diesel' || includeGas ? [{ site: value, kind: 'gen' }] : [])]);
    const canvas = document.createElement('canvas'); canvas.width = 2400; canvas.height = 140 + Math.ceil(panels.length / 2) * 1150;
    const ctx = canvas.getContext('2d'); ctx.fillStyle = theme === 'excel' ? '#000' : theme === 'dark' ? '#101e2b' : '#fff'; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = theme === 'light' ? '#203c50' : '#ecf3f7'; ctx.font = '700 39px Arial'; ctx.fillText(`AFL NOC · Weekly energy report · ${report.weekStart} to ${report.weekEnd}`, 40, 64);
    ctx.font = '23px Arial'; ctx.fillText(`${source === 'trial' ? 'ISOLATED TRIAL' : 'Workbook snapshot'} · ${report.elapsed ? 'Elapsed week' : 'Week in progress'} · Africa/Lagos`, 40, 106);
    panels.forEach((panel, index) => ctx.drawImage(weeklyImage(report, panel.site, panel.kind, theme), (index % 2) * 1200, 140 + Math.floor(index / 2) * 1150, 1200, 1150));
    await download(canvas, `AFL-weekly-energy-${week}.png`); onNotice('Weekly charts and pivot tables downloaded.');
  }
  return <section className="energy-weekly"><div className="energy-weekly-heading"><div><span className="eyebrow">WEEKLY TEAM REPORT</span><h2>Seven days. A clear operational picture.</h2><p>PowerPoint-style daily charts and pivot summaries · Monday to Sunday · Lagos time</p></div></div>
    <div className="energy-toolbar"><div><EnergyDatePicker key={week} value={week} onChange={setWeek} today={today} weekly/><p>{weeklyDate(week)} – {weeklyDate(shift(week,6))} · Monday–Sunday</p></div><label>Chart appearance<select value={theme} onChange={event => onTheme(event.target.value)}><option value="excel">Excel · template style</option><option value="light">Light · email friendly</option><option value="dark">Dark · modern</option></select></label></div>
    {error && <p role="alert" className="response-error">{error}</p>}{!report && !error && <p role="status">Loading weekly totals…</p>}
    {report && <><div className="energy-cards">{sites.map(value => <section className="noc-stat" key={value.id}><h2>{value.id}<small>{value.name} · {value.daysWithGridRecords}/7 days with EKEDC records</small></h2><strong>{weeklyAverage(value, 'grid')} <small>hrs/day EKEDC</small></strong><p>{weeklyNumber(value.gridHours)} hrs total · {weeklyNumber(value.gridAvailabilityPercent)}% EKEDC availability{value.gridPartial ? ' · partial' : ''}</p><div>{weeklyNumber(value.genHours)} logged gen hrs · {weeklyAverage(value, 'gen')} hrs/day</div><div>{weeklyNumber(value.gridUsed)} kWh{value.gridUsagePartial ? ' · partial/unavailable' : ''}</div><small>{value.fuel === 'Gas' ? 'Gas consumption not tracked' : `${weeklyNumber(value.dieselUsed)} L diesel · ${weeklyNumber(value.averageDieselUsed)} L/day · ${weeklyNumber(value.dieselLitresPerHour)} L/runtime hour`}</small></section>)}</div>
      <div className="energy-toolbar"><label><input type="checkbox" checked={includeGas} onChange={event => setIncludeGas(event.target.checked)} />Include gas-generator runtime sections</label><button className="response-button" disabled={!sites.length} onClick={() => fullReport().catch(value => onNotice(value.message))}><Download size={15} />Download weekly report</button></div>
      {!report.elapsed && <p className="response-notice">Week to date: averages use {report.averageDays} calendar days, including today. Future days are excluded; days without entries count as zero.</p>}
      <div className="energy-weekly-grid">{sites.flatMap(value => [<WeeklyPanel key={`${value.id}:grid`} report={report} site={value} kind="grid" theme={theme} onNotice={onNotice} />, ...(value.fuel === 'Diesel' || includeGas ? [<WeeklyPanel key={`${value.id}:gen`} report={report} site={value} kind="gen" theme={theme} onNotice={onNotice} />] : [])])}</div>
      <details className="energy-method"><summary>Weekly calculation and coverage notes</summary><p>Unrecorded dates count as zero under the reporting policy. Completed weeks average over seven days; current weeks average over calendar days reached, including today. Future dates are excluded. Missing readings inside an actual session remain unresolved, rather than inventing consumption. Refills/top-ups are shown separately from usage; explicit comment quantities adjust opening + addition − closing. Level increases without an amount show net additions for review. Gas consumption remains untracked. Source load errors do not become zero values.</p>{sites.map(value => <p key={value.id}>{value.id}: {value.daysWithRecords}/7 days have source records; {value.zeroDays || 0} unrecorded days counted as zero; {value.issues.length} source validation notes.</p>)}</details>
    </>}
  </section>;
}
