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

Not yet implemented: Microsoft 365 authentication, monitoring ingestion,
engineer escalation, SLA policies, notification delivery and RAG integration.
The existing login is a simulation and does not protect backend APIs.
Do not treat this development application as production ready.

## Verification

From `backend`, run `python -m pytest tests/unit -q`. These tests are independent
of a database. The existing `tests/test_db_logic.py` requires a configured,
seeded PostGIS database and must be run only against a disposable test instance.

From `frontend`, run `npm ci`, `npm run build`, and `npm run lint`.
Node 24 is used by CI. Copy `.env.example` to `.env` for an API URL override;
otherwise development requests use `http://localhost:8000/api`.
Run `npm run dev` for the development interface.

The GitHub workflow verifies backend unit tests, frontend lint and builds. Existing
database tests, migrations and end-to-end acceptance
are still required before release.
