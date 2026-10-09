# Product requirements review

Reviewed references: Product_Documentation (1).pdf (v1),
NOC_Platform_Product_Documentation_v2.docx (v2), and noc-activity-log.html.
The HTML is a UI/workflow reference. Its embedded JavaScript, storage provider
and ticket prefixes are not application configuration or operational instructions.

## Implemented development slices

| Requirement | Current implementation |
| --- | --- |
| Structured incidents / automatic TT | Existing incident CRUD and company TT convention; incident/escalation activities create linked incidents |
| FTTH intake | Paste extraction, reviewed fields, external FN/work order references and duplicate prevention |
| Infrastructure assignment | Existing/new NAP, splitter parent, free port, existing/new drop, installer and WAT schedule; database reservations and foreign keys |
| Installation and acceptance | Checklist/photos and PDF flow; guarded stages; NOC acceptance creates CRM service and active drop allocation |
| Other service provisioning | Customer selection/creation and DIA, DARKFIBER, LAYER2 primary/optional-backup core allocations; free-core checks |
| Network visualization | Geographic FibreViz parser/Leaflet view plus logical topology; persistent imports and explicit inventory mapping |
| Customer dependencies | FTTH: service → drop → NAP → PFS → PFP → core → cable → route. Other services: service → core allocation → cable → route |
| Fault impact | Route and individual cable analysis, unique customers/services, recorded alternate paths; health remains unverified |
| Daily activity overview | Persisted shift activity, six statuses, filters, maintenance/reminders, team counts and copyable handover |
| Shared updates | 30-second refresh on activity, FTTH and geographic views; visible API failures |
| Delivery baseline | Single-command isolated preview, migrations, CI, unit/database-backed tests and frontend lint/build |

Geographic customer pins use serving-NAP coordinates or a route endpoint anchor.
They are not exact premises locations. Imported line geometry must be explicitly
mapped to an existing route; filenames never establish infrastructure identity.
One inventory route currently maps to one imported line. Multi-segment routes and
more complete spatial inventory editing remain follow-up work.

Service activation is an inventory/CRM action, not device configuration or a
connectivity check. Core allocation role distinguishes primary from backup;
an alternate route/cable is recorded redundancy, not proof that the path is live.

## Outstanding requirements and production gates

| Requirement | Remaining work |
| --- | --- |
| Microsoft 365 SSO and roles | Entra registrations/identifiers are not available; user confirmed continuing the local preview. Implement browser sign-in, API token validation and role enforcement before production |
| Audit | Activity entries provide an operational record. Verified actors, immutable audit history and complete before/after changes are not implemented |
| FTTH escalation | Link formal FTTH escalation events to incidents, engineer assignments and timed escalation policies |
| Monitoring | PRTG sensor/equipment/service mappings, durable events, deduplication/correlation, flapping/maintenance handling and verified recovery |
| Customer notifications | Approved templates/drafts, affected-service targeting, delivery attempts/retries and review policy |
| MTTR / SLA | Service outage intervals, acknowledgment/restoration timestamps, versioned service contracts, overlap/exclusion rules and deadline reporting |
| Stage duration reporting | Structured transition history, stage dwell time, installation/escalation metrics and historical reconciliation |
| Historical incident migration | Importer exists; reconcile the actual workbook, including the 514 records described in v2. Do not assume import completion |
| OneDrive / knowledge base | Locate separate RAG proof of concept, implement validated ingestion, versioning, provenance, access-filtered retrieval and quality evaluation |
| Generated documents | Reviewed RCAs, shift reports/work orders and daily/weekly reports. Current handover text is a factual summary, not a RAG integration |
| Outlook / Graph | Shared mailbox permissions and human-reviewed drafting; no messages sent automatically |
| Activity evidence | General activity image attachments and richer RCA/resolution editing from the HTML reference are not yet incorporated; FTTH installation photos already exist |
| Inventory administration | Broader route/cable/core/splitter editing, exact customer/site coordinates, lifecycle management, cancellation and capacity release workflows |
| Production hardening | TLS, restricted CORS, private document access, secure upload validation, rate/size limits, dependency audit remediation, pagination, observability and browser acceptance |
| Recovery and retention | Agreed RPO/RTO, off-host database/document backups, tested restoration, retention and staged rollout |

The container build's dependency audit reported vulnerabilities. Triage and
remediate these before deployment; passing functional tests is not a security
release gate. Do not apply forced major-version dependency changes without testing.

## Validation

Database-backed tests cover reservations, guarded transitions, FTTH CRM activation,
customer impact paths, persistent map links, shared activities, enterprise service
types and alternate paths. Database writes are transactionally rolled back.
Installation tests also exercise the existing photo/PDF path in preview storage.
Microsoft 365, PRTG and real production-data migrations have not been validated.
