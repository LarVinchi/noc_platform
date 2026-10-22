import { useEffect, useState } from 'react';
import { CalendarDays, Download, Plus, RefreshCw } from 'lucide-react';
import api, { provisioningApi } from '../api/client';
import { operationError, watTime } from '../api/operations';
import { lagosDay, downloadCsv } from '../api/ftthMetrics';

const statuses = ['Planned', 'In progress', 'Completed', 'Not completed', 'Excluded'];
function monday(value) {
  const day = new Date(value + 'T12:00:00Z');
  day.setUTCDate(day.getUTCDate() - (day.getUTCDay() + 6) % 7);
  return day.toISOString().slice(0, 10);
}

export default function FtthDailyPlans({ identity }) {
  const canWrite = identity.roles.some(r => ['NOC.Admin', 'NOC.Operator'].includes(r));
  const [plans, setPlans] = useState([]), [orders, setOrders] = useState([]), [plan, setPlan] = useState(null);
  const [rows, setRows] = useState([]), [date, setDate] = useState(lagosDay()), [selected, setSelected] = useState('');
  const [error, setError] = useState(''), [notice, setNotice] = useState(''), [busy, setBusy] = useState(false);
  const [weekStart, setWeekStart] = useState(monday(lagosDay())), [week, setWeek] = useState(null), [history, setHistory] = useState(null);
  const [deliveries, setDeliveries] = useState(null);
  const dirty = plan && JSON.stringify(rows) !== JSON.stringify(plan.customers);
  function open(value) { setPlan(value); setRows(value.customers); setHistory(null); setNotice(''); }
  async function load() {
    try {
      const [a, b] = await Promise.all([api.get('/ftth/daily-plans'), provisioningApi.getOrders()]);
      setPlans(a.data.items); setOrders(b.data.filter(o => o.service_category === 'FTTH')); setError('');
    } catch (e) { setError(operationError(e)); }
  }
  useEffect(() => { load(); }, []);
  async function write(action) {
    setBusy(true); setError(''); setNotice('');
    try {
      const payload = action === 'create' ? { date, customers: [] } : { revision: plan.revision,
        ...(action === 'save' ? { customers: rows.map(c => ({ order_id: c.order_id, status: c.status, comment: c.comment })) } : {}) };
      const { data } = await api.post(action === 'create' ? '/ftth/daily-plans' : `/ftth/daily-plans/${plan.plan_id}/${action}`, payload);
      open(data); setNotice(action === 'close' ? 'Work closed. Final outcomes are retained.' : 'Saved successfully.');
      await load(); setWeek(null);
    } catch (e) { setError(operationError(e)); }
    finally { setBusy(false); }
  }
  async function choose(id) {
    setBusy(true);
    try { const { data } = await api.get(`/ftth/daily-plans/${id}`); open(data); setError(''); }
    catch (e) { setError(operationError(e)); } finally { setBusy(false); }
  }
  function add() {
    const order = orders.find(o => o.order_id === selected); if (!order) return;
    setRows([...rows, { order_id: order.order_id, customer_name: order.customer_name, fn_number: order.fn_number,
      isp: order.isp, service_area: order.coverage_zone_name, status: 'Planned', comment: '', added_after_start: plan.status !== 'planning' }]);
    setSelected('');
  }
  async function weekly() {
    setBusy(true); setError('');
    try { const { data } = await api.get('/ftth/weekly-report', { params: { start: weekStart } }); setWeek(data); }
    catch (e) { setError(operationError(e)); setWeek(null); } finally { setBusy(false); }
  }
  async function revisions() {
    try { const { data } = await api.get(`/ftth/daily-plans/${plan.plan_id}/history`); setHistory(data.items); }
    catch (e) { setError(operationError(e)); }
  }
  async function deliveryHistory() {
    try { const { data } = await api.get('/ftth/report-deliveries'); setDeliveries(data.items); }
    catch (e) { setError(operationError(e)); }
  }
  function exportWeek() {
    downloadCsv(`AFL-weekly-work-${week.week_start}.csv`, [
      ['AFL daily work entries', week.week_start, week.week_end, 'Africa/Lagos'],
      ['Missing dates', week.missing_dates.join(', ')], ['Unclosed dates', week.unclosed_dates.join(', ')],
      ['Date', 'Report status', 'FN', 'Customer', 'Provider', 'Area', 'Outcome', 'Reason', 'Added after start'],
      ...week.reports.flatMap(p => p.customers.map(c => [p.date, p.status, c.fn_number, c.customer_name, c.isp, c.service_area, c.status, c.comment, c.added_after_start ? 'Yes' : 'No'])),
    ]);
  }
  const editable = canWrite && plan?.status !== 'closed';
  return <div className="afl-ftth-page"><header className="afl-page-heading"><div><span className="afl-eyebrow">FIELD WORK / DAILY EVIDENCE</span><h1>Daily plans & closure</h1><p>Freeze the plan, record outcomes, and close the day with a clear audit trail.</p></div><button className="response-button" onClick={load} disabled={busy}><RefreshCw size={16}/>Refresh list</button></header>
    <div className="afl-notice">Daily completion records field work only. NOC acceptance and cumulative network connections are managed separately.</div>
    {error && <p role="alert" className="response-error">{error}</p>}{notice && <p role="status" className="afl-notice">{notice}</p>}
    <section className="afl-panel"><div className="afl-panel-title"><h2>Work date</h2><span className="afl-chip">Lagos / WAT</span></div><div className="afl-plan-controls">
      <label>Open a saved plan<select aria-label="Saved daily plan" value={plan?.plan_id || ''} disabled={busy || !!dirty} onChange={e => e.target.value && choose(e.target.value)}><option value="">Choose a date</option>{plans.map(p => <option key={p.plan_id} value={p.plan_id}>{p.date} · {p.status} · revision {p.revision}</option>)}</select></label>
      {canWrite && <><label>New plan date<input type="date" value={date} onChange={e => setDate(e.target.value)}/></label><button className="response-button primary" disabled={busy || !date || !!dirty} onClick={() => write('create')}><Plus size={15}/>Create plan</button></>}
    </div></section>
    {plan && <section className="afl-panel"><div className="afl-panel-title"><div><h2>{plan.date} · {plan.status}</h2><p>Revision {plan.revision} · saved {watTime(plan.updated_at)} by {plan.updated_by}</p></div><button className="response-button" disabled={busy} onClick={revisions}>Revision history</button></div>
      <div className="afl-plan-summary">{[['Planned', plan.summary.planned], ['Completed', plan.summary.completed], ['Plan not covered', plan.summary.not_covered], ['Additional completed', plan.summary.additional_completed], ['Pending', plan.summary.pending]].map(([k,v]) => <span key={k}>{k}<strong>{v}</strong></span>)}</div>
      {dirty && <p role="status" className="afl-notice">Unsaved changes. Summary figures reflect the last saved revision.</p>}
      <div className="afl-table-scroll"><table><thead><tr><th>Customer / provider</th><th>Service area</th><th>Outcome</th><th>Reason / work note</th></tr></thead><tbody>{rows.map((c,i) => <tr key={c.order_id}><td><strong>{c.customer_name}</strong><small>{c.fn_number || 'No FN'} · {c.isp}{c.added_after_start ? ' · Additional work' : ''}</small></td><td>{c.service_area || 'Unrecorded'}</td><td><select aria-label={`Outcome for ${c.customer_name}`} disabled={!editable || busy} value={c.status} onChange={e => setRows(rows.map((r,n) => n === i ? { ...r, status:e.target.value } : r))}>{(plan.status === 'planning' ? ['Planned','Excluded'] : statuses).map(v => <option key={v}>{v}</option>)}</select></td><td><input aria-label={`Work note for ${c.customer_name}`} disabled={!editable || busy} maxLength={1500} placeholder="Required for unfinished or excluded work" value={c.comment} onChange={e => setRows(rows.map((r,n) => n === i ? { ...r, comment:e.target.value } : r))}/></td></tr>)}</tbody></table></div>
      {!rows.length && <p className="afl-empty">No customers planned. An empty day can be started and closed to record that no work was scheduled.</p>}
      {editable && <div className="afl-plan-controls"><label>Add an FTTH order<select aria-label="FTTH order to add" value={selected} disabled={busy} onChange={e => setSelected(e.target.value)}><option value="">Choose an existing provisioning request</option>{orders.filter(o => !rows.some(r => r.order_id === o.order_id)).map(o => <option key={o.order_id} value={o.order_id}>{o.customer_name} · {o.fn_number || o.isp}</option>)}</select></label><button className="response-button" disabled={!selected || busy} onClick={add}><Plus size={15}/>Add customer</button></div>}
      <div className="afl-panel-footer"><span>{plan.status === 'closed' ? 'Closed reports cannot be edited.' : 'Keep saved rows; exclude with a reason instead of removing.'}</span><div className="afl-plan-actions">{editable && <><button className="response-button" disabled={busy || !dirty} onClick={() => write('save')}>Save changes</button>{plan.status === 'planning' ? <button className="response-button primary" disabled={busy || !!dirty} onClick={() => write('start')}>Start & freeze plan</button> : <button className="response-button primary" disabled={busy || !!dirty || plan.summary.pending > 0} onClick={() => write('close')}>Close work</button>}</>}</div></div>
      {history && <div className="afl-plan-history"><h3>Saved revisions</h3>{history.map(e => <p key={e.report.revision}>Revision {e.report.revision} · {e.action} · {e.actor_id} · {watTime(e.occurred_at)}</p>)}</div>}
    </section>}
    <section className="afl-panel"><div className="afl-panel-title"><div><h2>Weekly work report</h2><p>Monday–Sunday · includes missing and unclosed days</p></div><CalendarDays size={19}/></div><div className="afl-plan-controls"><label>Week beginning Monday<input type="date" value={weekStart} onChange={e => { setWeek(null); setWeekStart(e.target.value ? monday(e.target.value) : ''); }}/></label><button className="response-button" disabled={busy || !weekStart} onClick={weekly}>View week</button>{week && <button className="response-button" onClick={exportWeek}><Download size={15}/>Weekly CSV</button>}</div>
      {week && <><div className="afl-plan-summary">{[['Planned entries',week.totals.planned],['Completed entries',week.totals.completed],['Plan completion',week.totals.completion_rate == null ? '—' : `${week.totals.completion_rate}%`]].map(([k,v]) => <span key={k}>{k}<strong>{v}</strong></span>)}</div><p className="afl-notice">{week.complete ? 'Complete, closed week.' : 'Partial week.'} Missing dates: {week.missing_dates.join(', ') || 'None'}. Unclosed dates: {week.unclosed_dates.join(', ') || 'None'}.</p><p className="afl-panel-note">{week.counting_basis}</p><div className="afl-table-scroll"><table><thead><tr><th>Date</th><th>Status</th><th>Planned</th><th>Completed</th><th>Pending</th></tr></thead><tbody>{week.reports.map(p => <tr key={p.plan_id}><td>{p.date}</td><td>{p.status}</td><td>{p.summary.planned}</td><td>{p.summary.completed}</td><td>{p.summary.pending}</td></tr>)}</tbody></table></div></>}
      {identity.roles.includes('NOC.Admin') && <div className="afl-plan-controls"><button className="response-button" onClick={deliveryHistory}>View scheduled delivery history</button><span className="afl-panel-note">Delivery requires separate server configuration. No email is sent by this page.</span></div>}
      {deliveries && <div className="afl-table-scroll"><table><thead><tr><th>Week</th><th>Recipient</th><th>Result</th><th>Updated</th><th>Detail</th></tr></thead><tbody>{deliveries.map(d => <tr key={d.delivery_id}><td>{d.week_start}</td><td>{d.recipient}</td><td>{d.status}</td><td>{watTime(d.updated_at)}</td><td>{d.error_type || '—'}</td></tr>)}</tbody></table>{!deliveries.length && <p className="afl-empty">No delivery attempts recorded. The server schedule may not be enabled.</p>}</div>}
    </section>
  </div>;
}
