export const weeklyNumber = value => value == null ? '—' : Number(value).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const weeklyDate = day => new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', timeZone: 'Africa/Lagos' }).format(new Date(`${day}T12:00:00+01:00`));
export function weeklyFields(site, kind) {
  return kind === 'grid'
    ? { hours: 'gridHours', usage: 'gridUsed', average: 'averageGridHours', usageAverage: 'averageGridUsed', unit: 'kWh', name: 'EKEDC availability', partial: site.gridPartial, usagePartial: site.gridUsagePartial, measured: site.id === 'PROJN01' || site.gridUsed != null }
    : { hours: 'genHours', usage: 'dieselUsed', average: 'averageGenHours', usageAverage: 'averageDieselUsed', unit: 'L', name: 'Generator runtime', partial: site.genPartial, usagePartial: site.dieselUsagePartial, measured: site.fuel === 'Diesel' };
}

export function weeklyAverage(site, kind) {
  const field = weeklyFields(site, kind), value = site[field.average];
  return `${weeklyNumber(value)}${value != null && field.partial ? '*' : ''}`;
}

export function weeklyCoverageNote(report, site, kind) {
  const field = weeklyFields(site, kind);
  if (!report.elapsed) return 'Week in progress: full-week averages are withheld.';
  if (site[field.average] == null) return 'Hours average requires seven recorded days. Missing days are not zero.';
  const hours = field.partial
    ? '* Provisional hours average = logged total / 7; unresolved intervals are excluded.'
    : 'Hours average = logged total / 7 recorded days.';
  return hours + (field.measured && field.usagePartial ? ' Consumption average awaits complete readings.' : '');
}

export function weeklyDetails(report, site, kind) {
  const field = weeklyFields(site, kind);
  const details = kind === 'grid'
    ? [['EKEDC meter number', site.meterNumbers?.join(', ') || 'Not available in source']]
    : [[site.generatorCapacitySource ? 'Generator capacity (template)' : 'Generator capacity', site.generatorCapacity || 'Not recorded'], ['Fuel', site.fuel]];
  details.push(['Reporting period', `${weeklyDate(report.weekStart)} – ${weeklyDate(report.weekEnd)} ${report.weekEnd.slice(0, 4)}`],
    [kind === 'grid' ? 'Total availability' : 'Total runtime', `${weeklyNumber(site[field.hours])} hrs${field.partial ? ' · partial' : ''}`],
    ['Daily average (logged)', `${weeklyAverage(site, kind)} hrs/day`]);
  if (field.measured) details.push([kind === 'grid' ? 'Total EKEDC used' : 'Total diesel used', `${weeklyNumber(site[field.usage])} ${field.unit}${field.usagePartial ? ' · partial' : ''}`]);
  else if (kind === 'gen') details.push(['Consumption', 'Gas usage not tracked']);
  return details;
}

export function drawWeeklyChart(canvas, report, site, kind, theme) {
  const ctx = canvas.getContext('2d'), W = 1200, H = 650;
  const dark = theme !== 'light', signed = theme === 'excel';
  const color = { background: signed ? '#000' : dark ? '#101e2b' : '#fff', ink: dark ? '#ecf3f7' : '#203c50', muted: dark ? '#a8bccb' : '#6b8091', line: dark ? '#2b4050' : '#e0e8ee', bar: '#5b9bd5', usage: '#ed7d31' };
  const field = weeklyFields(site, kind);
  const text = (value, x, y, size = 17, ink = color.ink, weight = 400, align = 'left') => { ctx.font = `${weight} ${size}px Arial,sans-serif`; ctx.fillStyle = ink; ctx.textAlign = align; ctx.fillText(String(value), x, y); };
  ctx.fillStyle = color.background; ctx.fillRect(0, 0, W, H);
  const title = `${site.id} - ${field.name.toUpperCase()}${field.measured ? ` & ${kind === 'grid' ? 'kWh' : 'DIESEL'} USAGE` : ''}`;
  ctx.font = '700 27px Arial'; text(title, 40, 43, Math.min(27, 27 * 1120 / ctx.measureText(title).width), color.ink, 700);
  text(`${weeklyDate(report.weekStart)} – ${weeklyDate(report.weekEnd)} ${report.weekEnd.slice(0, 4)} · Lagos / WAT`, 40, 76, 17, color.muted);
  ctx.fillStyle = color.bar; ctx.fillRect(40, 100, 12, 12); text(`${field.name} (hrs)`, 61, 112, 15, color.muted);
  if (field.measured) { ctx.fillStyle = color.usage; ctx.fillRect(405, 100, 12, 12); text(`${kind === 'grid' ? 'EKEDC usage' : 'Diesel usage'} (${field.unit})${signed ? ' · balance change' : ''}`, 426, 112, 15, color.muted); }
  const x = 85, y = 160, w = 1030, h = 330;
  const hourMax = Math.max(2, Math.ceil(Math.max(0, ...site.days.map(row => row[field.hours] || 0)) / 2) * 2);
  const usageMax = Math.max(5, Math.ceil(Math.max(0, ...site.days.map(row => row[field.usage] || 0)) / 5) * 5);
  text('HOURS', x, y - 18, 13, color.muted, 700);
  if (field.measured) text(field.unit, x + w + 10, y - 18, 13, color.muted, 700, 'right');
  for (let i = 0; i <= 4; i++) {
    const yy = y + h - h * i / 4;
    ctx.strokeStyle = color.line; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x, yy); ctx.lineTo(x + w, yy); ctx.stroke();
    text((hourMax * i / 4).toFixed(1), x - 13, yy + 5, 14, color.muted, 400, 'right');
    if (field.measured) text((signed ? -usageMax * (1 - i / 4) : usageMax * i / 4).toFixed(0), x + w + 13, yy + 5, 14, color.muted);
  }
  const step = w / 7;
  site.days.forEach((row, i) => {
    const cx = x + step * (i + .5), value = row[field.hours];
    if (value != null) { const height = value / hourMax * h; ctx.fillStyle = color.bar; ctx.fillRect(cx - 31, y + h - height, 62, height); text(weeklyNumber(value), cx, y + h - height - 10, 16, color.ink, 700, 'center'); }
    else text('No data', cx, y + h - 12, 14, color.muted, 400, 'center');
    text(weeklyDate(row.date), cx, y + h + 29, 15, color.muted, 400, 'center');
  });
  if (field.measured) {
    ctx.strokeStyle = color.usage; ctx.lineWidth = 3;
    let prior = null;
    site.days.forEach((row, i) => {
      const value = row[field.usage];
      if (value == null) { prior = null; return; }
      const point = { x: x + step * (i + .5), y: signed ? y + value / usageMax * h : y + h - value / usageMax * h };
      if (prior) { ctx.beginPath(); ctx.moveTo(prior.x, prior.y); ctx.lineTo(point.x, point.y); ctx.stroke(); }
      ctx.fillStyle = color.usage; ctx.beginPath(); ctx.arc(point.x, point.y, 5, 0, Math.PI * 2); ctx.fill();
      const hours = row[field.hours];
      const barLabelY = hours == null ? null : y + h - hours / hourMax * h - 10;
      let labelY = point.y + (signed ? 23 : -14);
      if (barLabelY != null && Math.abs(labelY - barLabelY) < 24) labelY = point.y + 25;
      text(weeklyNumber(signed && value ? -value : value), point.x, labelY, 14, color.usage, 700, 'center');
      prior = point;
    });
  }
  const total = weeklyNumber(site[field.hours]), average = weeklyAverage(site, kind);
  text(`Logged total: ${total} hrs    Daily average: ${average} hrs`, 40, 562, 18, color.ink, 600);
  if (field.measured) text(`Usage: ${weeklyNumber(site[field.usage])} ${field.unit}${field.usagePartial ? ' · partial measured total' : ''}`, 40, 592, 16, color.muted);
  else if (kind === 'gen') text('Gas consumption is not tracked.', 40, 592, 16, color.muted);
  ctx.font = '400 13px Arial'; ctx.fillStyle = color.muted; ctx.textAlign = 'left';
  ctx.fillText(weeklyCoverageNote(report, site, kind), 40, 626, 1120);
}

export function drawWeeklyTable(ctx, report, site, kind, theme, top = 650) {
  const field = weeklyFields(site, kind), dark = theme !== 'light';
  const ink = dark ? '#e8f2f8' : '#223c50', muted = dark ? '#adc1ce' : '#6b8091';
  const text = (value, x, y, bold = false, align = 'left') => { ctx.font = `${bold ? 700 : 400} 19px Arial`; ctx.fillStyle = ink; ctx.textAlign = align; ctx.fillText(String(value), x, y); };
  ctx.fillStyle = theme === 'excel' ? '#000' : dark ? '#101e2b' : '#fff'; ctx.fillRect(0, top, 1200, 500);
  text(`${site.id} · ${field.name.toUpperCase()} · DAILY SUMMARY`, 40, top + 30, true);
  const headerY = top + 48;
  ctx.fillStyle = dark ? '#253d50' : '#d8e4eb'; ctx.fillRect(40, headerY, 720, 40);
  text('Day (WAT)', 58, headerY + 27, true); text('Hours', field.measured ? 460 : 738, headerY + 27, true, 'right');
  if (field.measured) text(`${field.unit}${theme === 'excel' ? ' change' : ' used'}`, 738, headerY + 27, true, 'right');
  const rows = [...site.days.map(row => [weeklyDate(row.date), row[field.hours], row[field.usage]]),
    ['Grand total', site[field.hours], site[field.usage]], ['Daily average', site[field.average], site[field.usageAverage]]];
  rows.forEach(([label, hours, used], i) => {
    const yy = headerY + 40 + i * 36;
    if (i >= 7) { ctx.fillStyle = dark ? '#1b3040' : '#eaf0f4'; ctx.fillRect(40, yy, 720, 36); }
    text(label, 58, yy + 25, i >= 7); text(i === 8 ? weeklyAverage(site, kind) : weeklyNumber(hours), field.measured ? 460 : 738, yy + 25, i >= 7, 'right');
    if (field.measured) text(weeklyNumber(theme === 'excel' && used ? -used : used), 738, yy + 25, i >= 7, 'right');
    ctx.strokeStyle = dark ? '#304655' : '#dce6eb'; ctx.beginPath(); ctx.moveTo(40, yy + 36); ctx.lineTo(760, yy + 36); ctx.stroke();
  });
  ctx.fillStyle = dark ? '#192e3d' : '#eef4f7'; ctx.fillRect(790, headerY, 370, 364);
  weeklyDetails(report, site, kind).forEach(([label, value], i) => {
    const yy = headerY + 24 + i * 54;
    ctx.font = '400 14px Arial'; ctx.fillStyle = muted; ctx.textAlign = 'left'; ctx.fillText(label.toUpperCase(), 810, yy);
    ctx.font = '700 19px Arial'; ctx.fillStyle = ink; ctx.fillText(value, 810, yy + 23, 330);
  });
  ctx.fillStyle = muted; ctx.font = '14px Arial'; ctx.textAlign = 'left';
  ctx.fillText(`Source: ${report.source} · ${report.mode === 'trial' ? 'COLLECTOR TRIAL' : 'Workbook copy'} · missing values are not zero`, 40, top + 449);
  ctx.fillText(weeklyCoverageNote(report, site, kind), 40, top + 477, 1120);
}

export function weeklyImage(report, site, kind, theme, part = 'combined') {
  const height = part === 'chart' ? 650 : part === 'table' ? 500 : 1150;
  const canvas = document.createElement('canvas'); canvas.width = 2400; canvas.height = height * 2;
  const ctx = canvas.getContext('2d'); ctx.scale(2, 2);
  if (part !== 'table') drawWeeklyChart(canvas, report, site, kind, theme);
  if (part !== 'chart') drawWeeklyTable(ctx, report, site, kind, theme, part === 'table' ? 0 : 650);
  return canvas;
}
