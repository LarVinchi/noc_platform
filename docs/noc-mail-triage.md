# NOC mailbox triage and RAG integration

Requested by the user during the FTTH milestone. This is an integration design;
no mailbox is connected and no email has been read or sent by this work.

Monitor newly received mail for the authorized NOC mailbox and display an
explainable triage queue: urgent outage, customer escalation, restoration update,
SLA/deadline risk, installation request, engineering action or routine/uncertain.
Each flag includes its reason, evidence excerpt, received time, confidence,
suggested owner, linked FN/TT/customer/service and acknowledgment/review state.
Sender importance alone does not establish the actual operational severity.

The connector and rule-based triage can operate before the colleague's RAG engine
arrives. The RAG adapter can later enrich suggestions from authorized approved
documents, prior RCAs, related incidents and correspondence examples. Inbox
content does not automatically become approved searchable knowledge.

## Integration sequence

1. Configure an approved mailbox identity and least-privilege read access with
   the Microsoft 365 administrator. For shared/delegated mailbox change
   notifications Microsoft documents application `Mail.Read`; delegated
   `Mail.Read.Shared` does not support that notification scenario. Validate the
   chosen Exchange mailbox restriction mechanism and app consent in staging.
   Monitoring needs no `Mail.Send`; mailbox modification/Outlook flags are a
   separate requested permission, not implied by flags inside this platform.
2. Register a Graph change subscription where a reachable HTTPS endpoint is
   available. Validate subscription challenge and client-state secrets, renew
   subscriptions and handle lifecycle events. If the company server cannot
   receive callbacks, use scheduled folder delta polling initially.
3. Maintain folder inventory and per-folder delta checkpoints, including delivery
   rules that move mail out of Inbox. Initial controlled backfill and periodic
   reconciliation cover downtime and subscription loss; never promise every
   message was processed merely because the webhook is healthy.
4. Persist source mailbox/message IDs, immutable-ID preference, conversation ID,
   message Internet ID, source change/version and processing state. Deduplicate
   retries without assuming that forwarded copies are the same message or that
   a message marked read is already triaged. Measure sync lag and quarantine
   failures visibly.
5. Apply configurable rules and then optional bounded classification. Keep
   ambiguous/low-confidence messages reviewable. Thread grouping reduces repeat
   alerts; actual new evidence or higher urgency must still raise a new update.
6. Suggest incident/customer/service/order links. Staff confirm new incidents and
   FTTH intake initially; pasted/email requests must use the same duplicate and
   required-field checks. Do not create customer outage intervals from an email
   assertion alone. Approved automation rules can be introduced after evaluation.
7. Capture operator acknowledgment, assignment, due reminders, dismissals and
   override feedback, with an audit trail. Proposed replies remain human-reviewed
   drafts; actual delivery remains a separate integration and permission.

## Data and access

Use `mail_sources`, `mail_messages`, durable ingestion jobs, versioned triage
decisions, typed record links and triage actions. Preserve selected evidence bodies
and attachments under private storage with mailbox-scoped ACLs, retention and
authorized source links. Attachment ingestion follows the document validation,
quarantine and completeness pipeline; no automatic macro execution or unsafe
HTML rendering. Email text is untrusted evidence, never instructions to execute
tools, alter permissions or issue messages. External model processing needs
approved company data handling. Never broaden mailbox access through RAG.

## Selective storage, not a duplicate mailbox

Outlook/Exchange remains the authoritative mailbox and its archive/retention
system. Evaluate every newly received message within the approved mailbox/folder
scope, but do not permanently duplicate all bodies and attachments in the platform.
Reading for classification, retaining evidence and making content eligible for
RAG are three separate decisions.

| Mail class | Platform retention proposal |
| --- | --- |
| Routine/irrelevant | Minimal source ID, received time and classification/deduplication decision for a configurable short operational window; no permanent body/attachment copy |
| Uncertain or flagged | Restricted review queue with source link, reason and bounded evidence excerpt; temporary body cache only where necessary for reliable review/reprocessing |
| Incident/FTTH/work-order evidence | Reviewed immutable snapshot of the relevant message and selected attachments, linked to the case with original/source IDs, timestamps and checksum |
| Approved operational knowledge | Separate curated document version, source citations and mailbox/record permissions; eligible for RAG only after required review/completeness checks |

Store only necessary sender/recipient metadata; subject lines and excerpts also
contain sensitive information and require the same access controls. Keep bodies
out of logs, webhook payload archives and general-purpose analytics. Initial
notification ingestion should fetch content under the approved worker identity,
classify it, and discard transient content unless the retention class requires it.
Read-only triage does not mark, move, delete or send anything in Outlook.

Use mailbox ID plus Graph immutable message ID for durable references; include
conversation/Internet message IDs for correlation, not as a globally unique
deduplication guarantee. Immutable IDs survive ordinary moves within the same
mailbox, but archive/export/reimport boundaries need reconciliation. Source links
are convenient pointers, not durable evidence if the message is subsequently
deleted or the user's access is revoked.

Define separate configurable retention classes for transient cache, routine triage
metadata, unresolved reviews, case evidence and approved knowledge. Agree periods
with company records/security owners rather than inventing a universal number of
days. Legal holds and approved case-evidence retention override routine expiry;
mailbox deletion must not silently delete required case evidence. Conversely,
access revocation immediately blocks evidence/index retrieval even when bytes
remain under retention. Expiry must cover chunks, embeddings, caches and backup
expiry policy as well as original files.

Implementation starts with rules, a visible uncertain queue and manual **Preserve
as case evidence**. Evaluate urgent-message recall and false negatives before
automating evidence selection. Temporary retries and reclassification can refetch
the authorized source while it exists; expose source-unavailable cases. Keep
minimal deduplication/checkpoint state so routine retention cleanup does not replay
the entire mailbox. No scheduled deletion is enabled by this design milestone.

## Acceptance checks

Replayed notifications create no duplicate work; missed notifications reconcile
from delta; folder moves and renewal failures remain visible. Evaluate a reviewed
set of actual NOC mail for urgent-message recall, false positive rate, wrong
entity links, thread behavior and classification latency. Test restricted users,
revoked access, malicious attachments and prompt injection. Start with reviewable
flags and measure results before enabling any automatic incident or escalation
actions.

## Primary references

- [Shared/delegated Outlook messages and notification permissions](https://learn.microsoft.com/en-us/graph/outlook-share-messages-folders)
- [Outlook change notification resources and limitations](https://learn.microsoft.com/en-us/graph/outlook-change-notifications-overview)
- [Graph subscription lifecycle and expiry](https://learn.microsoft.com/en-us/graph/change-notifications-overview)
- [Outlook immutable message identifiers](https://learn.microsoft.com/en-us/graph/outlook-immutable-id)
- [Per-folder message delta](https://learn.microsoft.com/en-us/graph/api/message-delta)

Dependencies: approved mailbox resource/configuration, Microsoft 365 administrator
consent and mailbox restrictions, credentials and HTTPS/polling deployment.
None require the handover template. The colleague's RAG code remains pending.
