# Server health and deployment monitoring

The **Governance → Server health** page is restricted to NOC administrators and
is read-only. It displays real Linux-host measurements, Docker engine allocation,
container observations, application readiness, GitHub build/release information,
and explicitly instrumented server deployment phases. No agent means an empty
state, never fabricated metrics. Stale reports remain labelled as last known data.

## Collected evidence

- Hostname, distribution/version, kernel, architecture, CPU model/cores and uptime.
- Host CPU utilization excluding guest double-counting; 1/5/15-minute load averages.
- RAM total/available/used percentage and swap total/used.
- Configured filesystem total/available/used capacity and inode utilization.
- Network rates and cumulative errors by interface; disk I/O rates by whole device.
- Docker engine/context name, CPU/RAM allocation, Compose application container
  state/health/restarts, CPU/RAM usage and image revision labels. Expected completed
  migrations and one-off containers are excluded from application health.
- API/database readiness via the existing `/health/ready` endpoint.
- Latest main SHA, published release SHA, actual API/frontend image revisions,
  last successful deployment SHA/time, checker heartbeat, stage, result and rollback.

Docker Desktop runs containers in its VM. Engine allocation, individual container
usage and physical Linux-host utilization are labelled separately. They must not
be added together or substituted for one another. Docker CPU can exceed 100% across
multiple cores. First-sample CPU and rate measurements are unavailable until a
second observation establishes an interval; absent measurements are not zero.

## Data flow and access

`scripts/noc-host-agent.py` is a standard-library Linux process outside the application
containers. Every approximately 30 seconds it collects allowlisted measurements,
reads sanitized deployment state, and posts a report to the existing FastAPI app.
GitHub metadata is cached and polled every five minutes, not on every browser refresh.
The React page refreshes every 15 seconds; history refreshes every 30 seconds.

The host intake uses a separate secret bound to one configured host ID. It cannot
read admin routes or invoke ordinary NOC operations. The installer binds intake to
`127.0.0.1:18001`; existing public gateway behavior is preserved. Remote collectors
require HTTPS. The web application receives reports without Docker socket access.
Requests are bounded to 256 KiB; nested arrays, strings, finite counters and aware
timestamps are validated. Duplicate sample IDs are idempotent; conflicting reuse
is rejected. Replayed older samples do not advance the current host heartbeat.

Seven days of CPU/RAM/storage samples are retained with indexed, bounded history
queries. Cleanup runs on ingestion. History buckets use average CPU/RAM and maximum
filesystem capacity utilization; missing intervals stay visible. Current details
include the last 30 deployment attempts. The controller retains up to 100 attempts.
The local agent queue retains at most 120 reports, sends the newest first on recovery,
and retries with bounded backoff. It continues collecting during API restarts; it
cannot provide an accessible dashboard while the whole NOC application is offline.

## Status rules

- **Up to date** requires current host and GitHub evidence, a recent deployer check,
  and actual running API/frontend image labels matching main, the published release
  and the recorded successful installation.
- **Update pending** means a newer main commit is awaiting build/release/installation.
- **Deploying** requires an active user deployment service and a recent running stage.
- **Failed** identifies the current main build or server deployment failure.
  Application health is separate: an update may fail while the previous app remains healthy.
- **Status stale** covers old host samples (>120 seconds), unavailable GitHub evidence,
  old checker/GitHub observations (>15 minutes), unconfirmed image identity or an
  abandoned deployment. Running stages also have a 30-minute freshness limit.

The deployment timeline shows build, release, server progress and final result.
Deployer stages are downloading, verifying, loading images, backing up, migrating,
starting, checking health and rollback. Private logs, environment values and backup
contents are never included in agent reports or published to GitHub.

`PLATFORM_WARNING_PERCENT` (80) and `PLATFORM_CRITICAL_PERCENT` (90) configure sample
threshold flags for CPU, RAM, storage and inodes. Warning must be below critical.
These flags are observations, not sustained alarms or automatically created incidents.

## One-time activation on the existing review server

Merge and deploy the feature through the normal reviewed-release workflow first.
Then run the following as **steve**, not root, on the Linux server:

```bash
cd /home/steve/Downloads/noc_platform
runtime=$(python3 -c 'import json; print(json.load(open(".review-access/cd/current.json"))["runtime"])')
python3 "$runtime/scripts/install-host-monitoring.py" --root "$PWD" --activate
systemctl --user status noc-host-agent.service --no-pager
journalctl --user -u noc-host-agent.service -n 40 --no-pager
```

The installer first confirms that the running API contains this feature. It preserves
the existing ingest token on repeat runs, writes a protected host configuration and
loopback-only Compose overlay, updates the protected deployment controller after
backing up its previous copy, applies the overlay to the current API image, and enables
the user collector service. No replacement images are built on the server.
It takes the deployment controller lock to avoid racing an installation.
Without `--activate`, it only prepares files and does not replace the active controller,
enable its overlay or start the collector.

The protected config is `.review-access/monitoring/agent.json`. It holds paths to
credentials, not browser-visible secrets. Configure the actual filesystem mounts
there (including the Docker Desktop image storage filesystem when different).
Restart the collector after configuration changes. The first report may lack CPU
rates/GitHub metadata; the next observations fill them. The updated deployment checker
reports on its next scheduled five-minute check.

```bash
systemctl --user restart noc-host-agent.service
tail -n 60 .review-access/cd/deploy.log
python3 -m json.tool .review-access/cd/status.json
python3 -m json.tool .review-access/monitoring/heartbeat.json
```

Docker Desktop and the user services still require Steve's session on this host.
This feature does not claim unattended host reboot recovery. A native Docker Engine
and dedicated system service account remain the headless production target.

To stop collection: `systemctl --user disable --now noc-host-agent.service`.
Keep the protected overlay/controller for normal deployment operation, or remove
the `enabled` marker and reapply the running Compose configuration after reviewing
the rollback procedure. Do not remove tokens/overlays during an active deployment.

## Optional GitHub deployment reporting

NOC deployment tracking works without a GitHub write credential. To also retain
deployment outcomes in GitHub, supply a fine-grained token scoped to this repository
with **Deployments: write**, stored privately on the server. Add its absolute file
path as `github_token_file` in `agent.json` and restart the collector. It creates
`stakeholder-review` deployment records tied to server attempt IDs and reports
in-progress/success/failure states. No host metrics, private log text or secrets are
uploaded. Credential provisioning is a separate server configuration step; no token
is committed, generated for GitHub, or enabled automatically by this feature.

## Verification

Unit tests cover state/freshness, actual image identity, failed update versus app
health, thresholds, bounded/finite reports and admin/agent separation. Collector tests
cover CPU/rate arithmetic, bounded replay queues, Docker failure, redirect refusal
and idempotent preparation. Deployment tests verify private overlays and attempt
history alongside existing checksum/backup/rollback tests. CI PostgreSQL tests cover
migration, authenticated ingestion, deduplication, conflicting samples, host binding,
replay ordering, history aggregation and administrator access. Real-server activation
and measured host values must still be verified after installation.
