# Weekly energy dashboard

Open **Energy → Weekly report**. Select a Monday, site and workbook or isolated
collector dataset. The report covers Monday through Sunday in Africa/Lagos.
Its daily bars, consumption line and seven-row pivot table follow the structure
of the supplied PowerPoint slides 8–15. The presentation is a layout reference;
figures come from the selected imported RawData snapshot, not slide caches.

All three sites have EKEDC sections. Project Office includes diesel generator
runtime and litres. Optional Lekki/Ademola sections show gas-generator runtime;
gas consumption is not tracked. EKEDC usage appears where readings exist.

## Calculations and interpretation

- Each daily interval runs from the preceding 23:59:59 to that day's 23:59:59
  Lagos time, following the existing daily service.
- Totals sum unrounded daily results. Daily averages divide by seven, provided
  the week has elapsed and each day has relevant completed source records.
- Missing dates or readings remain null, displayed as a dash. Missing usage,
  open records and overlaps can withhold consumption averages. Recorded totals
  can be partial; review the source validation notes in the daily report.
- A day with records does not establish complete 24-hour observation coverage.
  Availability describes recorded EKEDC supply, not equipment uptime. All sites
  have batteries. No completed generator run logged is not proof it was off.
- Consumption uses opening/closing readings, excludes top-up/refill increases
  and prorates intervals across boundaries, as in the daily report.
- Excel appearance shows negative balance change. Light and dark appearances
  show positive consumption. Calculations are identical across appearances.

Copy or download charts and tables independently, or download the entire report.
Chart images are 2400 × 1300; table images are 2400 × 1000 and include a side
summary with meter number, reporting period, total and average hours, and measured
consumption where available. Meter numbers come from workbook source identifiers
and preserve leading zeros. Project Office's 22 kVA capacity is a presentation
template reference, labeled accordingly in the app. Unknown capacities are not
invented. Combined sections remain available in the full-report download.

After a successful clipboard write, the clicked button shows **Copied** for about
one second, then returns to **Copy chart** or **Copy table**. Copy requires browser
clipboard permission; when unavailable, the app downloads the image and reports
**Downloaded**, without claiming a successful copy. No email is sent.

## Integration and verification

The authenticated NOC API exposes `GET /api/energy/weekly?week_start=YYYY-MM-DD`.
It reads the same selected imported revision as daily reports through the existing
Postgres session and source selection service. No new migration, environment
variable, dependency, authentication mode or deployment process is required.
The React page uses the existing API client and bearer-token handling.

Local-only SQLite preview tools and sign-in bypasses are excluded from this change.

Validation includes calendar boundaries, seven-day arithmetic, missing readings,
in-progress weeks and empty datasets. Local real-workbook reconciliation compares
every weekly daily value to its existing daily report. Postgres-backed integration
and deployment checks still belong in the platform CI before a release.
