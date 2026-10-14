# Operational record corrections

Operators and administrators can correct entry mistakes from these pages:

| Page | Action | Editable details |
| --- | --- | --- |
| Incident response / response workspace | Edit details | Incident type, ticket category, summary, description, severity, planned flag, route/node descriptions, notes, delay reason, resolution action and root-cause details |
| Customers & services | Edit customer | Name, contact details, address and eligible customer references/types |
| Customers & services | Edit service | Bandwidth; dark-fibre services have no bandwidth field |
| FTTH provisioning, table and board / FTTH operations | Edit details | Customer name, service address, contact details, package, FN and work-order references |

Every correction requires a reason. Its history records the changed field names,
actor, request and time. History and Ticket ID aliases cannot be overwritten or
deleted through normal database operations. Existing database change auditing
continues to apply. Viewer roles cannot submit corrections.

## Ticket IDs and classification

TN means **Transmission**. The categories are Transmission (TN), Fiber (OF),
Power (PW), Maintenance (MA) and Other (OT).

Changing an incident's ticket category generates and stores a new Ticket ID.
It replaces the current value used by incident views and future communications.
The former ID remains searchable and appears in correction history. The stable
incident UUID preserves customer, service, outage, activity and document links.
The API exposes `ticket_id` and retains `tt_number` for existing integrations.

The migration converts existing `TECHNICAL` classifications to `TRANSMISSION`
without changing their existing TN identifiers. Legacy incident-create requests
using `TECHNICAL` are normalized to `TRANSMISSION`.

In **Overview > Daily activity & shift handover > Log activity**, choose the
activity Category **Incident** or **Customer Escalation**, then choose the required
**Incident category**. That choice determines the linked incident classification
and Ticket ID prefix. Ordinary activities do not create incidents. Activity cards,
search and handover summaries use the linked incident's current category and
Ticket ID, including after corrections. Finishing an activity does not close its
incident or claim restoration.

## Linked customer and FTTH details

Corrections synchronize accepted FTTH order contact/address details with their
CRM customer and other orders linked to that customer. Package corrections
synchronize the accepted order and its provisioned service. Correcting service
bandwidth updates its linked FTTH orders. Review the editor's linked-record count
before saving: shared customer corrections can affect several orders.

Generated FTTH customer identifiers and customer types remain protected.
Pasted requests retain their FN/work-order references. Duplicate references,
invalid packages, contact formats and missing required details are rejected.

## Concurrency and evidence

The editor checks a revision of the record and its linked customer/service/order
graph. A conflicting update returns a conflict and preserves the unsaved form;
use **Reload latest record** to review current values before submitting again.
Synchronization and correction history commit in one transaction.

Pending/reviewed communication drafts containing affected details are discarded
so they cannot be approved with stale information. Existing response policies,
deadlines and escalation evidence remain pinned; changing severity does not
restart SLA clocks. Completed FTTH incidents retain required resolution evidence;
aborted FTTH incidents retain an abort reason.

Original pasted requests and existing PDFs are historical evidence. Corrections
do not rewrite those files; replacement documents require a new revision.

## Scope and remaining work

These editors correct metadata. Reassigning ports, cores, cables, service type,
customer ownership or physical paths needs a guarded reassignment workflow.
Lifecycle changes, engineer assignment and verified restoration continue through
their existing controls. Correction forms cannot rewrite status, timestamps,
internal UUIDs or physical allocations. VLAN/IP configuration and installation
measurements/evidence are not covered by these editors.

Start or rebuild the local preview from the project root using `./dev.ps1`.
The startup migration service applies both the correction-history schema and
Transmission classification migration. Production deployment must run the same
migrations against the approved database after backups and migration review.
