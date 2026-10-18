# AFL NOC platform

React operational interface, FastAPI backend and PostgreSQL/PostGIS inventory.
See [the production roadmap](docs/production-roadmap.md) for requirements,
architecture decisions, milestones, external dependencies and release criteria.

**Energy operations** now provides three-site daily reports from an administrator-
imported RawData tracker, Excel/light/dark email chart exports, traceable source
records and an isolated local collector trial. See [the energy guide](docs/energy-operations.md).
For hourly delivery without Graph access, see [OneDrive desktop → SSH workbook delivery](docs/energy-file-delivery.md).
An optional read-only [OneDrive synchronizer](docs/energy-onedrive-sync.md) is
implemented but disabled pending Anker application access and company sign-in.
Live power detection and operational collector cutover remain unconnected.

Energy operations also includes [weekly reporting](docs/weekly-energy-report.md):
Monday–Sunday charts and pivot tables, separate chart/table image copying,
meter details, and one-second copy feedback for daily and weekly reports.

## Current development work

The production-foundation feature branch was merged into `main` through PR #1
at `57daece` on 2026-10-14. Development continues from that merged baseline.
For server installation, use the [Rocky Linux 9 runbook](docs/rocky-linux-9-setup.md).
The older platform breakdown includes historical Windows worktree instructions.

Implemented: topology expansion follows actual inventory relationships, omits
inactive allocations and deduplicates enterprise service endpoints. Dashboard
figures come from incident records with timed refresh, errors and freshness.
FTTH requests can be parsed from pasted text and logged with external references,
provenance, duplicate protection and transactional internal numbering.

Microsoft 365 sign-in and API role controls, transactional audit history,
normalized monitoring ingestion and the response worker with versioned target
policies are implemented. Live Entra/PRTG setup, contractual target configuration,
notification delivery and RAG integration remain.
Local preview uses an explicitly unverified identity; production access requires Entra.
Do not treat this development application as production ready.

See [the requirements review](docs/requirements-review.md) for the document-to-feature
checklist and remaining release gates.

Container builds now have separate **development** and **production** targets.
Production packages a non-root API and a static Nginx frontend; the preview keeps
hot reload and shares one backend image across API, migration and worker.
See [the cleanup audit and build/deployment guide](docs/container-builds.md).
`compose.production.example.yaml` is a deployment reference with outstanding
security/configuration/recovery gates, not an approved production release.

For interactive stakeholder review on the company network, use the isolated
demo stack in `compose.review.yaml`. See the [review setup and operating commands](docs/stakeholder-review.md).
It serves the compiled frontend, keeps the API/database internal, and uses only
demonstration data with an unverified preview identity.

## Advance orders and inspect customer impact

On the FTTH table or board, use **Assign & schedule** for a new request. Select a
NAP and free port, register/select its drop cable, name the installer and set the
installation time in Lagos/WAT. **Create a NAP** registers a terminal under an
existing splitter. Occupied ports and incompatible drop selections are rejected.

Use **Start installation**, then **Finish Install** with the checklist and four
photos. NOC **Approve** creates the linked CRM service/drop allocation. Generic
Kanban movement cannot skip assignment, evidence or acceptance.

In **CRM & Services → Provision Service**, create/select a customer and provision
DIA, dark fibre or Layer 2 against compatible free cores, with an optional backup
core. This records dependencies; network device configuration remains external.

**Network Topology** offers Geographic and Logical views. Import KMZ/KML or view
the approximate Lekki demo. Select an imported line and explicitly link it to the
correct inventory route. Customer pins then follow recorded allocations. Route
inspection lists potentially affected customers; **Inspect this cable's impact**
narrows the analysis to an individual cable. Monitoring must verify downtime.

The overview now includes the shared daily activity log, maintenance/reminders,
team summary and shift handover. Provisioning events feed the log automatically.
Incident/escalation entries use the existing company TT numbering convention.

## Run the complete preview with one command

Start Docker Desktop. In the working checkout run:

```powershell
.\dev.ps1
```

If your PowerShell execution policy blocks a local script, use:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\dev.ps1
```

The launcher generates a local database password in the ignored root `.env`,
builds the containers, initializes a separate seeded preview database, applies
Alembic migrations, and starts the API and frontend after their health checks.
The first build downloads dependencies and takes longer; subsequent starts reuse
cached images. Preserve `.env` so its password continues to match the database.

Open **http://localhost:5173** and select **Open local preview**. The API
documentation is at **http://localhost:18000/docs**.

```powershell
.\dev.ps1 status
.\dev.ps1 logs
.\dev.ps1 stop
```

Stop keeps preview data and uploaded documents. This stack uses the Compose
project `noc-preview`, separate named volumes and no published database port;
it does not migrate the original database. Ports are bound to localhost.
It is for development review, not production deployment.

On Linux, initialize a root `.env` with a strong `NOC_DB_PASSWORD`, then run
`docker compose -f compose.dev.yaml up --build -d --wait`.

## Paste an FTTH request

Open **FTTH Provisioning → Paste request**. Paste one labeled text request,
select the ISP, and click **Extract details**. Review/edit the extracted fields,
then click **Log FTTH request**. The table and board refresh automatically.

Accepted labels: FN NUMBER, CUSTOMER NAME, SERVICE ADDRESS, SERVICE PACKAGE,
CONTACT PHONE, EMAIL and WORK ORDER ID. Wrapped addresses, repeated matching FN
labels and `Label: value` lines are supported. Name, address, speed, FN and work
order ID are required; incomplete or conflicting requests produce a visible error.
No OCR, email, WhatsApp or external WFM integration is connected in this release.

The external work order ID is stored separately from the internally generated
service/order IDs. Copied OPEN/PENDING statuses are retained as source metadata;
they do not bypass local allocation/scheduling. Original pasted text is retained
for traceability and is not included in the public order-list response.

FN and work-order references are unique within an ISP. Repeated identical orders
return the existing record; changed customer/reference/contact details return a
conflict instead of overwriting it. PostgreSQL uniqueness also protects against
concurrent duplicate submissions. Internal numbering uses a transactional counter.
The migration refuses existing duplicate FN records rather than deleting them.

## Tests

From `backend`, install `requirements-unit.txt`, then run `python -m pytest tests/unit -q`. These tests are independent
of a database. The existing `tests/test_db_logic.py` requires a configured,
seeded PostGIS database and must be run only against a disposable test instance.

From `frontend`, run `npm ci`, `npm run build`, and `npm run lint`.
Node 24 is used by CI. Copy `.env.example` to `.env` for an API URL override;
otherwise development requests use `http://localhost:8000/api`.
Run `npm run dev` for the development interface.

The GitHub workflow verifies backend unit tests, frontend lint/build, a fresh
database migration, FTTH intake integration tests and seeded inventory traversal.
Production-data migrations, browser acceptance, SSO, security review and recovery
testing are still required before release.

For database-backed intake tests after starting the preview:

```powershell
docker compose -f compose.dev.yaml exec -e NOC_ALLOW_INTEGRATION_TESTS=1 api python -m pytest tests/integration -q
```

These tests verify parsing through the API, persistence, duplicate/conflict
behavior and database uniqueness. Writes are rolled back after each test, and
the tests refuse databases other than `noc_preview`. Containers also support
`python -m pytest tests/unit -q`.

## Access and monitoring milestone

Local preview now opens with **Open local preview**. Use **Monitoring** to map a
sensor and exercise Down/Up events; use **Audit history** to inspect committed
changes. Microsoft 365 registration and live PRTG connection are still pending.
See [configuration and operational limits](docs/access-and-monitoring.md).

The topology now fills the workspace, restores the original FibreViz controls,
and includes a redesigned logical network with named cables and core labels.
Use the command-bar sidebar toggle or the topology full-screen button for more
space. See [the topology workspace guide](docs/topology-workspace.md).

The **Response centre** adds engineer ownership, acknowledgment, versioned preview
targets, a timed escalation worker, evidence-based customer outages, restoration,
MTTR and communication review. All services start through the same `dev.ps1`
command. See [the incident response guide](docs/incident-response.md) for setup,
reporting rules and the remaining production requirements. Notification drafts
are not delivered, and preview targets are not contractual SLAs.

Document storage/RAG and the remaining FTTH handover, reporting and fault-history
requirements are investigated in [the document and FTTH design](docs/document-storage-and-ftth-design.md).
The colleague's RAG/audit tools and approved MTN handover template are pending;
the design separates work that can proceed now from those dependencies.

The first document foundation is now available under **Documents**: private
uploads, immutable revisions, order/service/incident links, access checks and
verified downloads. See [the catalogue guide](docs/document-catalogue.md).
Approval, malware scanning, RAG indexing and OneDrive sync remain pending.

**FTTH operations** now reports installation/acceptance totals, recorded stage
visits and linked customer faults. Use **History / incidents** to escalate a
pre-activation blocker or report a service fault and record resolution evidence.
See [the FTTH operations guide](docs/ftth-operations.md). Proposed NOC mailbox
flagging and selective evidence retention are described in [mail triage](docs/noc-mail-triage.md);
no mailbox is connected.

**Record corrections** are available for incidents, customers, provisioned service
bandwidth and FTTH orders. Category corrections replace the stored Ticket ID and
preserve previous IDs for search; TN means Transmission. Overview activity logging
also requires an incident category when creating an incident or customer escalation.
See [the correction guide](docs/record-corrections.md) for synchronization, history
and fields requiring dedicated reassignment workflows.

**Knowledge assistant** now has a dedicated source workspace and a bottom-right
**AI assistant** launcher on every signed-in page, with Chat and Sources tabs.
Open **Response centre → Manage response → Ask about this incident**, or
**FTTH operations → History / incidents → Ask about this FTTH case**.
The panel follows the active case, floats on desktop and fills the screen on
mobile. The preview shows real case facts and accessible source revisions; RAG answers
remain disabled until the engine and approval/extraction pipeline are connected.
See [the Knowledge workspace guide](docs/knowledge-workspace.md).

**Mail triage** now includes a private manual preview queue, rule explanations,
priority hints and review links to existing incidents/FTTH cases. It does not
monitor a live inbox. See [the preview guide](docs/mail-preview.md).

The stakeholder server can receive CI-verified releases after PRs merge into
`main`. See [review CI/CD](docs/review-ci-cd.md) for the developer workflow,
server timer, backup/rollback behavior and production deployment requirements.
