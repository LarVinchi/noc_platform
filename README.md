# AFL NOC platform

React operational interface, FastAPI backend and PostgreSQL/PostGIS inventory.
See [the production roadmap](docs/production-roadmap.md) for requirements,
architecture decisions, milestones, external dependencies and release criteria.

## Current development work

Branch: `feat/noc-production-foundation`.
The initial checkout is an isolated Git worktree at
`C:\Users\USER\Desktop\projects\fiberviz\noc-platform-worktree`; it shares
history with `C:\Users\USER\Desktop\projects\noc_platform`. The original
checkout stays on its existing branch. No changes have been pushed or deployed.

Implemented: topology expansion follows actual inventory relationships, omits
inactive allocations and deduplicates enterprise service endpoints. Dashboard
figures come from incident records with timed refresh, errors and freshness.
FTTH requests can be parsed from pasted text and logged with external references,
provenance, duplicate protection and transactional internal numbering.

Microsoft 365 sign-in and API role controls, transactional audit history and
normalized monitoring ingestion are implemented. Live Entra/PRTG setup,
engineer escalation, SLA policies, notification delivery and RAG integration remain.
Local preview uses an explicitly unverified identity; production access requires Entra.
Do not treat this development application as production ready.

See [the requirements review](docs/requirements-review.md) for the document-to-feature
checklist and remaining release gates.

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
