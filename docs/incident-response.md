# Incident response and service outage preview

Open http://localhost:5173, choose **Open local preview**, then **Response centre**.
Start the database, API, frontend and escalation worker together with `./dev.ps1`
from the worktree. Existing preview data is retained.

## First run

1. In **Configuration**, register engineers with their real operational email
   addresses. This directory establishes ownership; it does not grant sign-in roles.
2. Review the four severity policies. Preview acknowledgment/restoration targets
   are Critical 15/120, High 30/240, Medium 60/480 and Low 240/1440 minutes.
   Follow-up escalation is 60 minutes after the restoration deadline. Add default
   engineers and escalation recipients by creating a new policy version.
3. Create individual **Customer service SLA** policies for provisioned services
   when appropriate. These are separate from incident severity goals.
4. Open **Manage response** on an incident. Assign an enabled directory engineer,
   acknowledge the incident, and use **Service outages** to confirm affected
   services with a start time and evidence. Potential topology/PRTG impact alone
   does not prove an outage.
5. Verify restoration and record its time and evidence before resolving the
   incident. An incident with an open confirmed service outage cannot be closed.
6. Review generated engineer/customer messages under **Notification drafts**.
   A valid recipient is required for review. No messages are sent by this release.

Preview policies are editable examples, not agreed contractual targets. Changes
create immutable versions; incidents and outages retain their pinned version.
Future-effective policies apply only after their effective time. Preview policies
are ignored outside development. Production contracts require explicit approval
and configuration before use.

Existing incidents are not silently backfilled. **Apply current policy** pins an
unconfigured incident to the current severity policy using its original report
time, so an older incident may immediately become overdue. Acknowledgment records
the current server time and operator identity. Completion is not silently undone;
a new fault needs a new incident.

## Escalation and communication

The worker checks every 30 seconds. Its database heartbeat appears in the Response
centre. L1 records a missed acknowledgment, L2 a missed incident restoration goal,
and L3 a missed follow-up. Planned incidents are excluded from this incident
escalation ladder. Confirmed, non-excluded service outages independently generate
drafts when their service acknowledgment or restoration target is breached.
Overlapping workers serialize escalation with a PostgreSQL advisory lock;
unique event keys prevent duplicate events and drafts on retries.

Engineer assignment, escalation, outage confirmation and restoration prepare
reviewable drafts. Review records the actor and time, not delivery. Missing
contacts remain visible rather than being replaced with invented addresses.
Reassignment supersedes earlier engineer drafts; incident completion supersedes
engineer/escalation drafts; restoration supersedes earlier customer drafts for
that incident/service. Discarded drafts cannot be re-reviewed. If another
confirmed outage remains open on the same service, the restoration draft calls
out partial restoration and requests reconciliation. A reviewed draft still
requires a future delivery integration before it can reach anyone.

## Reporting rules

MTTR averages complete durations of verified, restored service outage episodes
whose restoration falls within the selected reporting window. It does not use
ticket closure as proof of service restoration. Recorded downtime clips intervals
to the window and merges overlaps per service, avoiding double-counting a customer
affected by multiple simultaneous faults. Explicitly excluded intervals require
a reason and are omitted from MTTR/downtime and service-target escalation.
Deadlines preserve the version selected at incident report or outage start time.
Open intervals and late restorations remain visible.

Availability coverage is **Unverified**. No percentage is inferred from an empty
outage log. Contractual availability needs agreed eligible service hours, calendar
and maintenance rules, validated monitoring coverage and historical reconciliation.
This preview provides auditable incident goals and outage target results, not
contractual availability certification.

## Validation and release boundaries

Database-backed tests exercise ownership, acknowledgment idempotence, policy
history, closure guards, restoration evidence, escalation deduplication, draft
review, superseded draft protection, overlapping faults and role boundaries.
Pure tests cover interval unions and deadline boundaries. Integration writes are
rolled back in the isolated `noc_preview` database.

Live Entra/PRTG acceptance, actual email/Teams delivery with durable attempts and
retries, on-call rotation, agreed contracts, production database role separation,
dependency remediation, upload hardening and tested backups remain release gates.
FTTH-stage escalation and business-hours policies remain follow-up work.
