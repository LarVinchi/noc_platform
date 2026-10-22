// Synthetic only. Writes still return 403 in the isolated design preview.
export const ftthPlan = {
  plan_id: 'demo-daily-plan', date: '2026-10-20', revision: 4, status: 'closed',
  created_by: 'Synthetic Operator', updated_by: 'Synthetic Operator', updated_at: '2026-10-20T16:30:00Z',
  planned_ids: ['demo-ord-1', 'demo-ord-2'], started_at: '2026-10-20T07:00:00Z', closed_at: '2026-10-20T16:30:00Z',
  customers: [
    { order_id: 'demo-ord-1', customer_name: 'Synthetic Customer 301', fn_number: 'FN-DEMO-0301', isp: 'MTNN', service_area: 'Synthetic Oniru', status: 'Completed', comment: 'Synthetic installation verified', added_after_start: false },
    { order_id: 'demo-ord-2', customer_name: 'Synthetic Customer 302', fn_number: 'FN-DEMO-0302', isp: 'METROREACH', service_area: 'Synthetic Oniru', status: 'Not completed', comment: 'Synthetic: customer requested another date', added_after_start: false },
  ],
  summary: { planned: 2, completed: 1, planned_completed: 1, not_covered: 1, additional_completed: 0, pending: 0, not_completed: 1, excluded: 0, completion_rate: 50 },
};
export function ftthWeek(start, empty) {
  const days = Array.from({ length:7 }, (_,i) => { const date = new Date(start+'T12:00:00Z'); date.setUTCDate(date.getUTCDate()+i); return date.toISOString().slice(0,10); });
  const reports = !empty && days.includes(ftthPlan.date) ? [ftthPlan] : [];
  return { week_start:start, week_end:days[6], timezone:'Africa/Lagos', reports,
    missing_dates:days.filter(day=>!reports.some(p=>p.date===day)), unclosed_dates:[], complete:false, elapsed:new Date(days[6]+'T23:00:00Z')<new Date(),
    totals:reports.length?ftthPlan.summary:{planned:0,completed:0,planned_completed:0,not_covered:0,additional_completed:0,pending:0,not_completed:0,excluded:0,completion_rate:null},
    counting_basis:'Synthetic daily work entries; repeat customers are not cumulative connections.' };
}
