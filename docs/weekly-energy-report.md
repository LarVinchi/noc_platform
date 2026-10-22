# Weekly energy dashboard

Open **Energy → Weekly report**. Select a week, site and workbook or isolated
collector dataset. The report covers Monday through Sunday in Africa/Lagos.
Its daily bars, separate quantity band and seven-row pivot table follow the structure
of the supplied PowerPoint slides 8–15. The presentation is a layout reference;
figures come from the selected imported RawData snapshot, not slide caches.

All three sites have EKEDC sections. Project Office includes diesel generator
runtime and litres. Optional Lekki/Ademola sections show gas-generator runtime;
gas consumption is not tracked. EKEDC usage appears where readings exist.

## Calculations and interpretation

- Each daily interval runs from the preceding 23:59:59 to that day's 23:59:59
  Lagos time, following the existing daily service.
- Totals sum unrounded daily results. An elapsed week averages over seven calendar
  days, treating dates without entries as zero under the requested reporting policy.
- Current week reports are selectable and average over calendar days reached,
  including today. Future dates are excluded, not counted as zero. The denominator
  and week-to-date qualification appear in the screen and copied images.
- A missing reading within an actual session remains unresolved. Missing balances,
  open records and overlaps can still withhold consumption averages; they do not
  invent measurements. A failed source/API load is an error, not an empty zero week.
- A day with records does not establish complete 24-hour observation coverage.
  Availability describes recorded EKEDC supply, not equipment uptime. All sites
  have batteries. No completed generator run logged is not proof it was off.
- Explicit refill/top-up quantities in comments adjust consumption as opening +
  in-session addition − closing. Examples: `Refill of 50 litres`, `Top-up 100 kWh`,
  `50 liters top up`, `25L Top up`, or the source wording `25 Litres geneator top up`.
  Additions already detected between a previous closing and new opening are not
  added twice. Level increases without a quantity show inferred net additions;
  actual consumption remains unresolved. Refills are shown upward in green,
  separately from orange consumption, in charts and relevant pivot tables.
- Excel appearance shows negative balance change. Light and dark appearances
  show positive consumption. Calculations are identical across appearances.

Use **Current week**, the recent-week dropdown or previous/next arrows for quick
navigation. Editing the date does not reload the report until **Apply**; choosing
any day resolves to its Monday. This avoids the calendar jumping while selecting.
Runtime and quantity values occupy separate weekly chart bands with outlined
value labels so the orange figures remain legible alongside the blue hours bars.

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
