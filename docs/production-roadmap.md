# NOC platform production roadmap

## Baseline and scope

Reviewed on 2026-10-08: Product_Documentation (1).pdf (v1) and
NOC_Platform_Product_Documentation_v2.docx (v2). These are product requirements,
not operational instructions to grant permissions or deploy software. V2 expands
v1 with incident migration, PRTG, Microsoft 365 SSO, roles, auditing, reporting,
and reviewed document generation. The user's additional requirements include
FibreViz integration, automatic escalation, customer communication, MTTR and SLA.

The repository has React/Vite, FastAPI, SQLAlchemy/Alembic and PostGIS models.
Incident CRUD and ticket numbering exist; monitoring ingestion, escalation,
SLA policies, notification delivery and real authentication do not yet exist.
The RAG proof of concept described in the documents is not present here.
Docker Compose currently starts only the database, not the full application.
Dashboard numbers and the login are placeholders.

## Architecture decision: retain PostgreSQL and PostGIS

Use a modular monolith: one API, one relational source of truth, and separately
running background workers. Keep network geometry in PostGIS and transactions
in PostgreSQL. Do not migrate databases merely to make the application production
ready. Evaluate a supported PostgreSQL/PostGIS version in staging with backup,
extension compatibility and restore tests; never point a new major image at an
existing data directory without a migration plan.

Store document metadata, versions, access rules and ingestion state in PostgreSQL;
store document bytes in protected object storage or managed company storage.
Evaluate pgvector for retrieval after measuring index size, retrieval quality,
permissions and latency. Introduce a dedicated vector or time-series store only
when measured workload justifies it. Redis may support workers and short-lived
cache, but is not the authoritative incident ledger.

Design additions:

- Monitoring sources, devices/sensors and explicit inventory/service mappings.
- Durable raw events with source ID, external event ID, event time, received time,
  payload hash and processing state; unique keys make retries idempotent.
- Incident events, assignments, acknowledgments and audit records. Record outage
  start, detection, acknowledgment, dispatch, restoration and closure separately.
- Incident-to-service impacts with individual outage intervals and evidence.
- Versioned SLA policies attached to services; snapshot the applicable policy
  for each incident. Record exclusions and pauses explicitly and audit changes.
- On-call schedules, escalation policies and durable scheduled escalation steps.
- A transactional notification outbox, delivery attempts, retry limits and failed
  delivery queue. Workers must survive restart without losing pending actions.
- Document versions, provenance, ACLs, review state and ingestion checkpoints.

Use timezone-aware UTC timestamps; render staff times in Africa/Lagos. Add foreign
keys, CHECK constraints and selective indexes based on actual queries. Review
partial uniqueness for active allocations and sensor mappings; add GiST indexes
where spatial queries require them. Use EXPLAIN against realistic volumes.

## Milestones and acceptance criteria

| Milestone | Work | Evidence required before completion |
| --- | --- | --- |
| M0: baseline | Requirements, architecture, delivery plan, branch | Reviewed docs mapped to work; current limitations stated |
| M1: correctness and security | Fix topology scoping; SSO and roles; secret/config cleanup; audit trail | Unrelated assets excluded; unauthorized requests denied; role tests; no committed secrets |
| M2: geographic operations view | Import FibreViz parser; persist reviewed KMZ/KML imports against inventory IDs; geographic and logical topology | Import validation, provenance, rollback and correct inventory links |
| M3: monitoring and incidents | PRTG adapter; durable ingestion; deduplication, correlation, recovery and FTTH escalation links | Replayed events create no duplicates; out-of-order and flapping tests; recovery evidence |
| M4: response automation | On-call assignment; acknowledgment timers; engineer escalation; customer drafts/templates and delivery history | Restart-safe timers; affected-service filtering; notification retries; review policy enforced |
| M5: operational reporting | Service outage intervals; MTTR, SLA countdowns, availability, FTTH stage duration and handovers | Known example timelines reconcile; overlapping downtime counted once; definitions visible |
| M6: knowledge and documents | OneDrive ingestion; permission-filtered retrieval; RCA, handover and report drafts; Graph correspondence | Source citations, review workflow, ACL tests and labeled evaluation dataset |
| M7: production release | CI, containers, migrations, telemetry, backup/restore, staged rollout | Staging acceptance; restore drill; rollback rehearsal; agreed capacity and RPO/RTO |

M1 begins with topology correctness. Authentication is not complete until both
frontend sign-in and backend token/role enforcement are validated. No placeholder
login or locally invented identity may authorize production requests.

## Professional NOC interface

Build an operations console around decisions, not decorative animation:

- Responsive navigation, consistent spacing/type, restrained severity colors,
  keyboard access, sufficient contrast and reduced-motion support.
- Real counts and an incident work queue with severity, ownership, elapsed time,
  next action and SLA remaining. Clearly distinguish unknown from healthy.
- API connection state and last refresh time; never hard-code "System Online".
- Polling initially, then SSE for incident updates with reconnect and stale-state
  handling; retain visible errors and manual refresh.
- Geographic/logical views, affected-service drill-down, search and contextual
  incident actions; monitoring health separate from inventory lifecycle status.
- Timeline and runbook panel, engineer acknowledgment, customer update status,
  maintenance banner and shift handover view.
- Do not show fabricated charts, MTTR or availability when data is unavailable.

## Delivery, data engineering and operations

Use small conventional commits per milestone and reviewed pull requests. CI runs
Python tests, frontend lint/build, dependency/security checks and migration tests
against disposable PostgreSQL/PostGIS. Separate pure unit tests from database
integration tests; integration tests never use an existing production database.
Keep environments and secrets separate. Dependencies need reproducible locks and
supported versions; the current Python requirements include large PDF dependencies
that should be separated from API runtime dependencies after validation.

Alembic is the schema authority. Reconcile init scripts and migrations on an empty
database and on a representative existing database. Use backward-compatible
expand/backfill/contract migrations where needed; rehearse restore/rollback.
Historical ingestion needs dry runs, source row IDs, row counts, normalization
reports and quarantined invalid rows. The 514 historical records mentioned in v2
must be reconciled against the actual workbook, not assumed to have been imported.

Deploy behind TLS with restricted CORS, authenticated document downloads,
least-privilege database roles, health/readiness endpoints and structured logs.
Measure API latency, ingestion lag, worker queue age, failed notifications and
backup freshness. Alert on the monitoring pipeline itself.

Back up database and documents, retain an off-host copy, and test restoration.
Agree retention, RPO, RTO and escalation ownership before production release.
Enable continuous WAL archiving if required RPO makes daily backups insufficient.

## External dependencies and decisions

- Confirm PRTG sensor identifiers, push payloads and recovery behavior with its owner.
- Obtain Entra tenant/app registration, API audience, role claims and SPA redirect
  URIs. Validate API token signature, issuer, audience, expiry and tenant; Graph
  tokens are not tokens for this API.
- Confirm Graph/OneDrive access boundaries and correspondence approval policy.
  V2 specifies human-reviewed generated correspondence; implement automatic
  customer templates only after deciding which classes may bypass review.
- Obtain SLA contracts: targets, periods, maintenance treatment and pause rules.
- Confirm company server capacity, connectivity, backup ownership and RPO/RTO.
- Locate the separate RAG proof of concept and define its API and permission model.

## References

- PostGIS spatial indexes: https://postgis.net/documentation/faq/spatial-indexes/
- PostgreSQL recovery: https://www.postgresql.org/docs/current/continuous-archiving.html
- Entra API claims: https://learn.microsoft.com/en-us/entra/identity-platform/claims-validation
- PRTG notifications: https://www.paessler.com/manuals/prtg/notification_templates

## Progress

- M0: document/code baseline reviewed and roadmap recorded.
- Target integrations confirmed by the user: PRTG, Microsoft 365 SSO and company Linux server.
- M1 topology slice: actual descendant traversal, active allocation filtering,
  unique service endpoints and regression tests implemented. SSO/roles/audit remain outstanding.
- Interface slice: actual incident counts, prioritized work queue, ownership gaps,
  periodic refresh, connection errors and last-successful-refresh time implemented.
- CI starter: database-independent backend unit tests, frontend lint and production build.
- Preview launcher: database, migrations, API and frontend start together with
  `dev.ps1`, using isolated preview volumes, localhost ports and generated credentials.
- FTTH intake slice: labeled paste extraction, editable review, external work order
  references, raw-text provenance, duplicate/conflict handling and atomic numbering.
  The user confirmed paste-only intake for this release; inbox/WhatsApp ingestion is deferred.
- Fresh-start verification corrected the seed incident category and refreshed the
  impact view after seeding. Unit, PostgreSQL/API and seeded traversal tests pass.
- CI now also builds the preview and runs its migrations and database-backed tests.
- M1 onward: incomplete; report each implemented and tested slice in its commit.
