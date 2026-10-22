import { renderWeeklyPlot } from './weeklyEnergyPlot.js';
export const weeklyNumber = value => value == null ? '—' : Number(value).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const weeklyDate = day => new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', timeZone: 'Africa/Lagos' }).format(new Date(`${day}T12:00:00+01:00`));
export function weeklyFields(site, kind) {
  return kind === 'grid'
    ? { hours: 'gridHours', usage: 'gridUsed', addition:'gridAdded', additionInferred:site.gridAdditionInferred, average: 'averageGridHours', usageAverage: 'averageGridUsed', unit: 'kWh', name: 'EKEDC availability', partial: site.gridPartial, usagePartial: site.gridUsagePartial, measured: site.id === 'PROJN01' || site.gridUsed != null }
    : { hours: 'genHours', usage: 'dieselUsed', addition:'dieselAdded', additionInferred:site.dieselAdditionInferred, average: 'averageGenHours', usageAverage: 'averageDieselUsed', unit: 'L', name: 'Generator runtime', partial: site.genPartial, usagePartial: site.dieselUsagePartial, measured: site.fuel === 'Diesel' };
}

export function weeklyAverage(site, kind) {
  const field = weeklyFields(site, kind), value = site[field.average];
  return `${weeklyNumber(value)}${value != null && field.partial ? '*' : ''}`;
}

export function weeklyCoverageNote(report,site,kind) {
  const field=weeklyFields(site,kind),days=report.averageDays ?? 7;
  return `Average = logged total / ${days} calendar days; unrecorded days = 0${!report.elapsed?'; future days excluded':''}.`+
    (field.partial?' * Unresolved source records excluded.':'')+(field.measured&&field.usagePartial?' Usage requires review.':'')+(field.additionInferred?' * Includes inferred net additions.':'');
}

export function weeklyDetails(report, site, kind) {
  const field = weeklyFields(site, kind);
  const details = kind === 'grid'
    ? [['EKEDC meter number', site.meterNumbers?.join(', ') || 'Not available in source']]
    : [[site.generatorCapacitySource ? 'Generator capacity (template)' : 'Generator capacity', site.generatorCapacity || 'Not recorded'], ['Fuel', site.fuel]];
  details.push(['Reporting period', `${weeklyDate(report.weekStart)} – ${weeklyDate(report.weekEnd)} ${report.weekEnd.slice(0, 4)}`],
    [kind === 'grid' ? 'Total availability' : 'Total runtime', `${weeklyNumber(site[field.hours])} hrs${field.partial ? ' · partial' : ''}`],
    ['Daily average (calendar)', `${weeklyAverage(site, kind)} hrs/day`]);
  if (field.measured) details.push([kind === 'grid' ? 'Total EKEDC used' : 'Total diesel used', `${weeklyNumber(site[field.usage])} ${field.unit}${field.usagePartial ? ' · partial' : ''}`]);
  else if (kind === 'gen') details.push(['Consumption', 'Gas usage not tracked']);
  if (field.measured) details.push([kind === 'grid' ? 'Top-ups added' : 'Diesel refills', `+${weeklyNumber(site[kind === 'grid' ? 'gridAdded' : 'dieselAdded'] || 0)} ${field.unit}`]);
  return details;
}

export function drawWeeklyChart(canvas,report,site,kind,theme) {
  renderWeeklyPlot(canvas,report,site,kind,theme,{weeklyFields,weeklyDate,weeklyNumber,weeklyAverage,weeklyCoverageNote});
}

export function drawWeeklyTable(ctx, report, site, kind, theme, top = 650) {
  const field = weeklyFields(site, kind), dark = theme !== 'light';
  const hasAdditions = field.measured && (site[field.addition] || 0) > 0;
  const hoursX = hasAdditions ? 330 : field.measured ? 460 : 738, usageX = hasAdditions ? 520 : 738;
  const ink = dark ? '#e8f2f8' : '#223c50', muted = dark ? '#adc1ce' : '#6b8091';
  const text = (value, x, y, bold = false, align = 'left') => { ctx.font = `${bold ? 700 : 400} 19px Arial`; ctx.fillStyle = ink; ctx.textAlign = align; ctx.fillText(String(value), x, y); };
  ctx.fillStyle = theme === 'excel' ? '#000' : dark ? '#101e2b' : '#fff'; ctx.fillRect(0, top, 1200, 500);
  text(`${site.id} · ${field.name.toUpperCase()} · DAILY SUMMARY`, 40, top + 30, true);
  const headerY = top + 48;
  ctx.fillStyle = dark ? '#253d50' : '#d8e4eb'; ctx.fillRect(40, headerY, 720, 40);
  text('Day (WAT)', 58, headerY + 27, true); text('Hours', hoursX, headerY + 27, true, 'right');
  if (field.measured) text(`${field.unit}${theme === 'excel' ? ' change' : ' used'}`, usageX, headerY + 27, true, 'right');
  if (hasAdditions) text(kind === 'grid' ? 'Top-ups' : 'Refills',738,headerY+27,true,'right');
  const rows = [...site.days.map(row => [weeklyDate(row.date), row[field.hours], row[field.usage],row.future?null:row[field.addition]||0]),
    ['Grand total', site[field.hours], site[field.usage],site[field.addition]], ['Daily average', site[field.average], site[field.usageAverage],site[field.addition]/(report.averageDays||7)]];
  rows.forEach(([label, hours, used, added], i) => {
    const yy = headerY + 40 + i * 36;
    if (i >= 7) { ctx.fillStyle = dark ? '#1b3040' : '#eaf0f4'; ctx.fillRect(40, yy, 720, 36); }
    text(label, 58, yy + 25, i >= 7); text(i === 8 ? weeklyAverage(site, kind) : weeklyNumber(hours), hoursX, yy + 25, i >= 7, 'right');
    if (field.measured) text(weeklyNumber(theme === 'excel' && used ? -used : used), usageX, yy + 25, i >= 7, 'right');
    if (hasAdditions) text(added==null?'—':'+'+weeklyNumber(added),738,yy+25,i>=7,'right');
    ctx.strokeStyle = dark ? '#304655' : '#dce6eb'; ctx.beginPath(); ctx.moveTo(40, yy + 36); ctx.lineTo(760, yy + 36); ctx.stroke();
  });
  ctx.fillStyle = dark ? '#192e3d' : '#eef4f7'; ctx.fillRect(790, headerY, 370, 364);
  weeklyDetails(report, site, kind).forEach(([label, value], i) => {
    const yy = headerY + 24 + i * 48;
    ctx.font = '400 14px Arial'; ctx.fillStyle = muted; ctx.textAlign = 'left'; ctx.fillText(label.toUpperCase(), 810, yy);
    ctx.font = '700 19px Arial'; ctx.fillStyle = ink; ctx.fillText(value, 810, yy + 23, 330);
  });
  ctx.fillStyle = muted; ctx.font = '14px Arial'; ctx.textAlign = 'left';
  ctx.fillText(`Source: ${report.source} · ${report.mode === 'trial' ? 'COLLECTOR TRIAL' : 'Workbook copy'} · Unrecorded dates count as zero; invalid readings need review`, 40, top + 449,1120);
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
