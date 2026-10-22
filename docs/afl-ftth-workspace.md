# AFL FTTH workspace

The organization reference is `philipakomolafe/afl-operations` at commit `6a4596a`.
The official logo/icon and navy `#36396E` / green `#5ECE5F` palette are reused from that repository.
The implementation remains React/Vite, FastAPI and PostgreSQL, with the existing NOC identity and deployment pipeline.
No reference accounts, password database, SMTP settings or seed customer/network figures are imported.

## Routes and roles

The NOC sidebar has a dedicated FTTH workspace entry. Inside `/ftth`, navigation includes:

- `/ftth`: recorded installation pipeline and partner distribution.
- `/ftth/provisioning`: existing provisioning workflow, including Telewyz intake.
- `/ftth/service-areas`: distribution of actual NOC order records by recorded coverage zone.
- `/ftth/daily-plans`: daily planning, frozen starting plan, closure, weekly reports and delivery history.
- `/ftth/activity`: activity derived from existing provisioning timestamps; this is separate from frozen plans.
- `/ftth/network-reports`: reconciled cumulative service-area and outside-RFS snapshots.
- `/ftth/history`: existing lifecycle evidence and linked faults.

Legacy `/provisioning` and `/ftth-operations` links redirect to their FTTH equivalents.
Light/dark/system preference is shared with NOC. The browser icon is the official AFL icon.
Viewer roles read; Operator/Admin roles manage provisioning and daily work. Only Admin publishes reconciled
network totals or reads report-delivery recipients/history. Existing incident/acceptance permissions still apply.

## Counting rules

Daily plans reference existing FTTH order IDs, with a captured customer/FN/provider/area for historical evidence.
One plan exists per Lagos calendar date. Save requires the exact current revision; a conditional database update
rejects concurrent stale saves. Each saved action retains its report snapshot and actor in `ftth_plan_events`.
Saved customers cannot be removed: use Excluded with a reason. Both Excluded and Not completed require a reason.
Start freezes non-excluded planned IDs. Additional work after start does not increase that denominator.
Only active plans can record outcomes; future work cannot start. Closure requires every pending outcome to be resolved.
An empty plan may be started and closed to explicitly report that no work was scheduled. Closed reports cannot change.

Daily completion is a field-work declaration, **not** an automatic provisioning transition or NOC acceptance.
A repeated customer on multiple days counts as multiple daily work entries. Weekly reports disclose that basis,
missing daily plans and unclosed days. A complete week requires seven closed dates and an elapsed Monday–Sunday week.

Cumulative network snapshots are immutable, hash-idempotent and Admin-published. They retain four partner columns:
MetroReach Retail, MTNN, MANGONET, TELEWYZ. Outside-RFS counts are orders, excluded from connected totals/take-up.
Daily work never adds to cumulative totals automatically. Order distribution is not represented as homes passed.

## Historical migration

Before entering historical figures, obtain an approved export from the source app/database. Reconcile report dates,
service-area IDs, homes passed, all four partner counts and outside-RFS orders with the report owner.
Use Network reports > Publish snapshot to enter approved cumulative figures, recording the source/date/reconciliation note.
Identical submissions are idempotent; corrections become another retained snapshot rather than overwriting history.

Historical daily customer rows need matching NOC provisioning orders and a separate reviewed mapping of source IDs,
FN/provider, dates, frozen planned IDs and outcomes. Do not manufacture a frozen starting plan from final totals.
This release does not bulk-import those historical daily rows or copy source accounts. Retain the source export until
that mapping and import have been reviewed. New daily work is fully supported.

## Optional weekly mail

The job captures the previous Monday–Sunday week, due Monday 11:45 WAT. A later check in the same week catches up.
Each recipient receives one captured snapshot per week, even if reports change afterwards. A partial report explicitly
lists missing/unclosed days. Attachments are a detailed CSV and summary PDF; CSV formula-like fields are neutralized.
Credentials stay in a protected server configuration. Browser actions never send mail.

`python -m app.ftth_report_worker` is a dry-run. Sending additionally requires both enabled configuration and `--send`.
There is no in-process API scheduler, source GitHub Actions email job or dependency on the source app's accounts.
Queued deliveries are claimed atomically. Interrupted/ambiguous SMTP attempts become `uncertain`; they are not
automatically resent. Admin delivery history shows queued/sending/sent/failed/uncertain states. Resolve uncertain
delivery against the mail server logs before any explicit administrative resend. SMTP does not guarantee exactly-once delivery.

After this release has passed CI and been installed, prepare the Linux server as its Docker Desktop user:

```bash
cd /home/steve/Downloads/noc_platform
runtime=$(python3 -c 'import json; print(json.load(open(".review-access/cd/current.json"))["runtime"])')
install -d -m 700 .review-access/ftth-mail
install -m 700 "$runtime/scripts/run-ftth-weekly-reports.py" .review-access/ftth-mail/
```

Create `.review-access/ftth-mail/config.json`, owner-readable only (`chmod 600`), with string settings:

```json
{
  "FTTH_WEEKLY_EMAIL_ENABLED": "false",
  "FTTH_WEEKLY_RECIPIENTS": "approved-recipient@example.org",
  "FTTH_SMTP_HOST": "approved-relay.example.org",
  "FTTH_SMTP_PORT": "587",
  "FTTH_SMTP_FROM": "approved-sender@example.org",
  "FTTH_SMTP_USERNAME": "",
  "FTTH_SMTP_PASSWORD": ""
}
```

Replace placeholders privately. SMTP requires STARTTLS; both credentials may be empty only for an approved TLS relay.
The wrapper verifies that the running API image matches the installed SHA, and passes credential values through its child
environment rather than command arguments. Protect access to the Docker account and config file as server secrets.
Enable the setting only after the mail owner approves recipients. Inspect a dry-run first:

```bash
python3 .review-access/ftth-mail/run-ftth-weekly-reports.py --root "$PWD"
```

For opt-in automatic delivery, install the supplied units after dry-run review:

```bash
install -m 600 "$runtime/deploy/systemd/noc-ftth-weekly-report.service" ~/.config/systemd/user/
install -m 600 "$runtime/deploy/systemd/noc-ftth-weekly-report.timer" ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now noc-ftth-weekly-report.timer
```

The timer checks every 15 minutes; sending is still gated by the Lagos due time, enabled configuration and unique weekly key.
Inspect `systemctl --user status noc-ftth-weekly-report.timer` and `.review-access/ftth-mail/worker.log`.
Pause with `systemctl --user disable --now noc-ftth-weekly-report.timer`. Log rotation should cover `worker.log`.
No timer or SMTP transport has been enabled as part of local development.

## Verification and deployment

Apply migrations through the existing tested-release deployment method: `58a2c6d1e345` adds network snapshots;
`69b3d7e2f456` adds plans/events/deliveries and extends the PostgreSQL ISP enum with TELEWYZ.
There is one migration head, following the linked-OneDrive migration `47f1b5c0d234`.
The enum value is retained on downgrade; restoring an older UI is not a reason to drop report history or provider values.
Use the tested release rollback procedure and database backup. UI Git tags identify code snapshots, not database rollback.

Local checks cover backend rules, role boundaries, stale revisions, immutable snapshots, weekly missing dates,
delivery idempotency/ambiguous failures, actual CSV/PDF MIME generation and script argument secrecy.
Frontend checks cover lint/build, calculation helpers and read-only browser preview in both themes and at mobile width.
PostgreSQL migrations, Docker image checks and nginx validation still run in the existing GitHub Actions jobs.
No Docker/PostgreSQL instance or approved SMTP transport is available on this local PC.

The design-only preview uses synthetic fixtures and rejects writes. It is not a substitute for the server acceptance test:
create an FTTH order, plan it, start, record an outcome, close, and inspect the weekly result with approved server data.
