const siteDefinitions = [['PROJN01', 'Project office', 'Diesel'], ['LEKKP01', 'Lekki', 'Gas'], ['ADEMP01', 'Ademola', 'Gas']];
export function dailyEnergy(day = '2026-10-17', source = 'workbook') {
  return { mode: source, date: day, start: `${day}T00:00:00`, end: `${day}T23:59:59`, source: 'DEMO · RawData-example.xlsx', events: [], sites: siteDefinitions.map(([id, name, fuel], i) => ({
    id, name, fuel, gridHours: [16.5, 18.25, 19][i], gridUsed: [96.4, 58.2, 74.5][i], genHours: [6, 4, 3.5][i], dieselUsed: i === 0 ? 29.5 : null, unaccountedHours: [1.5, 1.75, 1.5][i], gridPartial: false, dieselPartial: false, issues: [],
    records: [{ row: 12 + i * 2, kind: 'grid', active: true, status: 'completed', start: `${day}T00:00:00`, stop: `${day}T16:30:00`, hours: [16.5, 18.25, 19][i], opening: 520, closing: 520 - [96.4, 58.2, 74.5][i], used: [96.4, 58.2, 74.5][i], operator: 'Demo engineer', comment: 'Synthetic workbook example' }, { row: 13 + i * 2, kind: 'gen', active: true, status: 'completed', start: `${day}T17:00:00`, stop: `${day}T23:00:00`, hours: [6, 4, 3.5][i], opening: i === 0 ? 160 : null, closing: i === 0 ? 130.5 : null, used: i === 0 ? 29.5 : null, operator: 'Demo engineer', comment: fuel === 'Gas' ? 'Gas consumption not tracked' : 'Synthetic diesel cycle' }],
  })) };
}
export function weeklyEnergy(weekStart = '2026-10-05', source = 'workbook') {
  const days = Array.from({ length: 7 }, (_, i) => new Date(Date.parse(`${weekStart}T12:00:00Z`) + i * 86400000).toISOString().slice(0, 10));
  return { mode: source, source: 'DEMO · RawData-example.xlsx', elapsed: true, weekStart, weekEnd: days[6], sites: siteDefinitions.map(([id, name, fuel], i) => {
    const daily = days.map(day => ({ date: day, gridHours: 16 + i, genHours: 6 - i, gridUsed: 90 - i * 12, dieselUsed: i === 0 ? 29.5 : null }));
    return { id, name, fuel, days: daily, gridHours: (16 + i) * 7, genHours: (6 - i) * 7, averageGridHours: 16 + i, averageGenHours: 6 - i, gridUsed: (90 - i * 12) * 7, averageGridUsed: 90 - i * 12, dieselUsed: i === 0 ? 206.5 : null, averageDieselUsed: i === 0 ? 29.5 : null, dieselLitresPerHour: i === 0 ? 29.5 / 6 : null, gridAvailabilityPercent: (16 + i) / 24 * 100, daysWithGridRecords: 7, daysWithRecords: 7, gridPartial: false, genPartial: false, gridUsagePartial: false, dieselUsagePartial: false, issues: [], meterNumbers: [`DEMO-${id}`], generatorCapacity: 'Not recorded' };
  }) };
}
