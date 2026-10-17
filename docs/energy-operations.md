# Energy operations: imported workbook reports and collector trial

Open **Energy operations** in the Operations navigation after starting the normal
`dev.ps1` preview. Existing Microsoft 365/preview access controls apply. This
milestone does not write to Excel, ingest telemetry, send mail, or establish a
production data cutover. An optional read-only OneDrive/SharePoint synchronizer
is implemented, disabled by default. See [configuration and activation](energy-onedrive-sync.md).
The supplied Anker workbook still requires an approved application identity,
resource grant and live tenant acceptance before it can be connected.

## Workbook reporting

An administrator selects **Import RawData tracker** and uploads the main XLSX,
not one of the three summary workbooks. The importer validates the fixed RawData
header contract and recognized sources. Limits: 10 MB compressed, 40 MB expanded,
2,000 archive entries and 50,000 operational rows. A successful import becomes
an immutable Postgres revision; duplicate file content returns the existing
revision without replacing the current one. Failed imports leave previous data
intact. Original XLSX files are processed transiently, not retained in this milestone.

Select a day/site and Excel, light or modern dark appearance. Copy individual
chart images, download PNGs or download all charts. Clipboard restrictions fall
back to downloading a PNG. PROJN01 reports EKEDC kWh and diesel litres. Lekki
and Ademola use gas, whose consumption is not tracked. All chart styles share
the same data. Source records retain operator comments and original row numbers.

Hours use elapsed time, merge overlaps, and preserve one-second logging gaps.
The Lagos reporting window ends at 23:59:59 and owns events at that cutoff.
Missing stops are excluded; missing balances remain unknown/partial. Consumption
is opening minus closing; additions are separate. Cross-boundary consumption is
prorated, with a warning. Excel charts round session durations like Power Query
and plot consumption as negative balance change; overview values retain full
precision. Hour-meter values remain visible separately.

Each import stores a content hash, normalized records, actor and import time.
Audit triggers record revision metadata without duplicating full workbooks into
audit history. New imports replace the active report source as whole revisions;
row matching, correction reconciliation and immutable report publication are
future work. Imported operator names/comments are organizational data and need
the platform's deployment access and retention policy.

## Isolated collector trial

Available only when ENVIRONMENT=development and AUTH_MODE=preview. Entries are
shared preview trial data, not operational records. Viewer roles cannot submit.
An operator records a timestamp, independently observed EKEDC and generator
states, optional new balance readings and a comment. Previous state is shown;
missing measurements stay blank. The next observation closes the prior intervals
automatically, removing duplicate OFF entries and manual midnight splitting.

Use the **Isolated collector trial** dataset to review generated reports. The
last observation remains open and excluded until the next arrives. Reports also
calculate confirmed periods with both sources off between observations. Unknown
states are not classified as off. Batteries are present at every site: no grid/gen
supply does not establish equipment downtime. There is no automatic physical
detection. Lekki's weak UPS must not be represented by a fixed assumed runtime.

Submissions use a unique retry key and an expected per-site revision. A stale tab
returns a conflict instead of overwriting another operator. Records are append-only
and audited. Trial timestamps must increase; late corrections, refill/top-up forms,
measurement checks and cutover review are intentionally subsequent milestones.
Do not use the trial to enter operational refills: balance increases remain
unresolved consumption requiring review. Gas sites reject diesel readings.

## Verification and next gates

The existing GitHub workflow runs the new pure reporting/collector unit tests and
database-backed energy integration tests with the existing disposable preview.
Synthetic XLSX fixtures avoid committing operational files or personal data.
Frontend lint/build and production image gates continue to apply.

The sync slice adds ETag polling, retries, import health, source-version
reconciliation and protected original snapshots. Next: obtain Anker IT approval
for a scoped Graph download identity and complete real Entra/role configuration, data access/retention review,
backup/restore validation, concurrency acceptance and operator reconciliation.
Then add collector additions/corrections, state confirmation/freshness and a
reviewed site-by-site cutover. Integrate actual ATS/controller/UPS signals only
when their meaning and reliability are established. The production design is a
roadmap, not a claim that these gates have passed.

For an alternative without Graph application access, see [hourly desktop workbook delivery over SSH](energy-file-delivery.md).
