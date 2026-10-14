# Mail triage local preview

Open http://localhost:5173/mail or choose **Mail triage** in the sidebar.
The screen shows **Mailbox not connected** and does not fabricate mailbox
addresses, received messages or synchronization timestamps. The user will provide
the NOC mailbox address when ready; do not block preview development on it.

## Available now

- Paste a subject, sender and plain-text message to create a manual local review
  record. An optional WAT received time remains unknown if not supplied; entering
  a message does not prove when an email arrived.
- Explicit versioned rules suggest outage, customer escalation, SLA/deadline risk,
  FTTH request, engineering action, restoration, routine or uncertain categories.
  The screen shows matched wording and reasons. No AI/RAG or verified outage
  inference is involved. Quoted messages, negations and unfamiliar language can
  produce false positives/negatives, so all suggestions require review.
- High-priority hints sort before normal and low hints. Filter the persisted queue
  by awaiting review, acknowledged or dismissed, with pagination and counts.
- Review requires a decision note. Staff may link existing incidents or FTTH
  orders; the preview does not create incidents, provisioning requests, customer
  outages or outbound messages automatically.
- Records are private to their creator and administrators. Other operators cannot
  see or change a private record; viewers cannot submit or review. State/link
  changes have transactional audit records with the actual actor and time.
- The form retains a stable request key across retries. Identical retries return
  the original item; changed data under a committed key is rejected.

Full message bodies are used transiently for rules, then discarded. Records keep
subject/sender/time, classification reasons, detected references, state and a
maximum 400-character excerpt for flagged/uncertain messages. Routine previews
retain no excerpt. This metadata can still contain sensitive information and
requires access controls. No attachments or email originals are archived by this
slice, no Outlook messages are changed, and automatic retention expiry is not yet
implemented. This queue is not a legally complete correspondence archive.

Manual submission is disabled outside local development preview. A future live
connector must use its own authenticated ingestion path, mailbox scope and source
identifiers; do not reuse an unverified local preview identity in production.

## Next implementation steps

1. Approve the NOC mailbox scope and Microsoft 365 application configuration when
   the user supplies them. Validate read permissions and mailbox restrictions.
2. Build subscriptions/polling, missed-message reconciliation, stable source IDs,
   retries and visible sync health. Live mode must show actual connection/lag.
3. Agree and implement retention classes and **Preserve as case evidence** using
   immutable documents/attachments. Evaluate rules against real NOC examples
   before allowing automatic record creation or escalation.
4. Integrate the colleague's RAG/audit tools through authorized approved content.
   Add the Knowledge workspace and contextual assistant described in
   [the document architecture](document-storage-and-ftth-design.md).

The MTN handover template, reviewed generation jobs, source-file completeness,
malware scanning, departmental ACLs, backups/restore and production hardening
remain parallel milestones. See [the live mail design](noc-mail-triage.md).

Tests cover rule outcomes, uncertain/conflicting wording, priority ordering,
bounded storage, idempotent retries, preserved review links, private access,
invalid times and the production preview guard. Integration writes roll back.
