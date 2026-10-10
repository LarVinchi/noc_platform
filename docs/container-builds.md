# Repository cleanup and container builds

The local preview is a development stack. Production uses separate runtime
targets and an image-only deployment reference; it is not an approved release.

## File audit

Removed unreferenced Vite starter CSS and assets: `src/App.css`, `hero.png`,
`react.svg`, `vite.svg`, and `public/icons.svg`. Replaced the starter frontend
README with project instructions. Removed the stale generated `repo_structure.txt`
and ignored future copies; `generate_tree.py` remains an optional utility.

The active `favicon.svg`, Entra `redirect.html`, sample KMZ generator, customer
router, SQL baseline and migration history remain required. Demo generation is
used by the geographic API. Do not delete these based on their filenames.

`backend/requirements.txt` now references the canonical runtime/test lists instead
of a conflicting old freeze. Direct dependencies remain pinned and the resolved
Linux/Python 3.12 runtime versions are constrained by `requirements-runtime.lock.txt`.
Hashes and multi-platform lock validation remain release gates. Do not silently upgrade
dependencies or treat an image size reduction as vulnerability remediation.

Ignored local `node_modules`, `dist`, virtual environments and Python caches are
regenerable. They are excluded from build contexts and are not shipped. They were
kept locally to preserve working tools. Database/document volumes and `.env` are
data/configuration, not cleanup targets. No Docker prune or volume reset was run.

The legacy database-only `docker-compose.yml` remains to preserve its separate
`noc_pg_data` volume. It now requires `NOC_LEGACY_DB_PASSWORD` to match that existing
database and binds its port to localhost. Editing an environment password does
not rotate an initialized PostgreSQL password. Prefer the complete preview stack.

## Build targets

Backend: compilers/Cairo headers stay in the dependency builder. Production copies
the installed virtual environment and required application/migration/import files,
uses UID/GID 10001, and has no pytest, compiler or tests. Cairo/Pango/fonts remain
because PDF generation needs runtime libraries. Development adds tests and uses
root for compatibility with existing preview volumes; production does not.

Frontend: Node builds the Vite bundle; production contains Nginx and compiled
assets only, runs as `nginx` on 8080, and preserves SPA routes and Entra redirect.
Hashed assets receive immutable caching, HTML is refreshed and responses can be
compressed. `/api` and `/static` proxy to the authenticated backend. No document
volume is exposed directly by Nginx.
The proxy refreshes `api` through Docker DNS rather than retaining a container's
old address after replacement.

BuildKit caches pip/npm downloads and dependency layers independently of source
changes. The API, migration job and response worker share one backend image.
Docker image tags sharing layers do not each consume their displayed image size;
use `docker system df` to assess actual disk use. Cache occupies build-machine
disk but is not copied into runtime images.

```sh
docker build --target production -t registry.example/noc/backend:<commit> backend
docker build --target production -t registry.example/noc/frontend:<commit> frontend
```

`dev.ps1` continues to select development targets and hot reload. Keep it for
local work. The first build downloads dependencies; warm builds reuse caches.

## Company Linux deployment design

Use `compose.production.example.yaml` as a reference. CI should test, scan and
publish the images once; the server pulls the same reviewed commit/digest images.
The reference has no source mounts/reload or preview seed, keeps DB/API internal,
runs migration separately, bounds logs, checks health, and restricts application
containers to read-only roots with writable document volumes and `/tmp`.

The four baseline SQL files initialize an empty database before Alembic; they do
not upgrade an existing database. Never mount preview seed 05 into production.
Reconcile actual company inventory/history through reviewed imports.

Before approving deployment:

- Supply and validate Entra registrations, domain and company TLS ingress.
- Pin reviewed base images/digests and transitive dependency locks; resolve
  reported vulnerabilities, produce an SBOM and scan release images.
- Separate migration/database-owner and least-privilege API/worker roles. The
  example currently shares the bootstrap DB owner and is not the final role design.
- Configure approved secret storage. The reference uses injected environment
  variables; do not commit values or publish expanded Compose output. Protected
  configuration and actual secret-manager integration are still required.
- Configure TLS/proxy trust against the actual ingress. Nginx currently reports
  its own scheme upstream; review original HTTPS forwarding before enabling
  trusted proxy headers, redirects or secure-session behavior.
- Set CPU/memory/process limits from measured traffic and PDF/job workloads,
  tune DB connection pools and worker counts, and keep one response worker until
  concurrency is validated. More processes are not automatically faster.
- Test volume permissions for UID 10001, off-host DB+document backups, restoration,
  migration rollback/forward repair, deployment rollback and alert delivery.
- Complete secure uploads, retention, rate limits, operational metrics/alerts and
  live integration acceptance from the requirements tracker.

The reference binds HTTP to `127.0.0.1:8080` for the company's TLS proxy; it is not
a public HTTPS configuration. Existing preview volumes are not production volumes.
No images have been pushed and no company server has been changed.

## Verification

Measured locally on 2026-10-10 using Docker's reported image size:

| Image | Previous development image | New production image |
| --- | --- | --- |
| Backend | 964 MB | 457 MB |
| Frontend | 556 MB | 95.3 MB |

These are image sizes, not RAM usage or additive physical disk consumption.
The development images remain larger because they include build/test tools.
Warm production rebuilds reused dependency/build layers and completed in about
four seconds locally; this is an observation, not a CI/network performance target.

CI builds production targets, verifies the backend non-root identity and absence
of pytest, generates a real PDF, and validates Nginx configuration. The existing
preview checks still exercise fresh migrations and database workflows.
Local validation passed 91 backend tests and browser checks against the compiled
Nginx frontend, including SPA/Entra redirect paths and API replacement. A separate
disposable stack initialized the four schema files and migrated successfully,
started non-root API/worker services with read-only roots, confirmed writable
private volumes, contained no demo customer/incident records and rejected
unauthenticated API access. The tested preview data was preserved.

Image builds and smoke checks validate packaging; they do not validate production SSO,
contractual SLAs, load capacity or recovery.

References: [Docker build best practices](https://docs.docker.com/build/building/best-practices/),
[cache optimization](https://docs.docker.com/build/cache/optimize/),
and [FastAPI containers](https://fastapi.tiangolo.com/deployment/docker/).
