# FTTH operations preview

Open **FTTH operations** at http://localhost:5173/ftth-operations. Filter by MTN,
Metroreach or Mangonet and select a rolling 7/30/90-day window. The same `dev.ps1`
command starts the preview and applies the additive lifecycle migration.

## Installation evidence and reporting

New requests, infrastructure scheduling, installation start/rescheduling,
installation completion and NOC acceptance now emit append-only structured
events in the same transaction as the order change. Events include stage,
authenticated actor, server time and reason. Repeated identical intake does not
create duplicate stage events. Stage mutations serialize on the order row.

Lifetime completed counts use recorded completion dates; lifetime accepted counts
use the current NOC-accepted stage. Period completed counts use completion dates;
period acceptances use explicit acceptance events. Historical accepted orders
without acceptance events appear in the missing-date count, never receive guessed
dates. Current backlog is independent of the reporting window. Availability and
handover delivery are not inferred from activation or acceptance.

Stage duration samples are completed visits ending in the selected half-open UTC
window. Means and medians use the full elapsed visit duration, including time
before the window. Rescheduling preserves multiple visits. No business-hours or
hold pause is inferred. Older cases without initial events have partial history;
their first observed transition does not prove when the preceding stage began.
Open-stage ages use the last known event at the reporting end. Date display is WAT.
Distinct mobilization/dispatch, cancellation, rework and documented pause events
remain future extensions; IN_PROGRESS records installation start.

## Linked incidents

Use **History / incidents** on a case. Before activation, **Escalate installation**
creates a TT or links an active existing incident. The order keeps its installation
stage, and any unresolved blocker prevents NOC acceptance. Work/evidence can
continue while a blocker is investigated. After activation, **Report service
fault** creates/links an incident and service ticket; it does not manufacture a
confirmed outage interval. Confirm/restore outages separately in **Manage response**.

Requests carry an idempotency key; retries return the same link/incident, and
changed details under a previously committed key produce a conflict. Shared
faults can link to several cases without creating another incident per customer.
Existing linked service tickets, including monitoring-created faults, also appear
in the order history. Completed incidents cannot be reused for new recurring faults.

Record resolution actions/verification and root cause before resolving an FTTH
incident. Confirmed open service outages must be restored first. Aborting a linked
FTTH incident requires a reason. Closure actor is server-recorded. An incident
resolution does not automatically accept the installation or deliver a handover.
Resolving a shared incident affects every associated case; review its impact first.

FTTH incident MTTR averages report-to-resolution durations for distinct incidents
resolved in the window, with valid times and category/sample counts. It is separate
from confirmed service-outage MTTR. Provider attribution follows the originating
order. All-provider incident reporting additionally includes FTTH services without
orders; those cannot be assigned a provider without historical reconciliation.

## Validation and remaining work

Integration tests cover stage history, completion/acceptance counts, repeat intake,
blocked acceptance, required resolution evidence, actor recording, idempotent
incident creation, shared ticket deduplication, invalid pre-activation faults,
legacy missing dates, provider scopes and rescheduling. Database writes roll back.

The existing pre-acceptance PDF flow remains; this milestone does not generate
approved MTN handovers. The template, generation jobs/review/delivery, historical
backfill, explicit SLA pauses and broader performance/pagination remain pending.
Reporting currently reads the eligible case/event set; measure production volume
and move aggregates into SQL/materialized reports where required.

NOC mailbox triage has also been added to [the integration design](noc-mail-triage.md).
It is not connected to a live mailbox.
