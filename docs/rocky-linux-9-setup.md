# Rocky Linux 9 server setup

Reviewed against the merged application at `57daece` on 2026-10-15. Use Docker
Engine and Compose on the server. Python, Node and PostgreSQL do not need separate
host installations. The production reference starts PostGIS, migrations, API,
response worker and the compiled frontend.

**Start with staging and test data.** The reference still uses the bootstrap
database owner for API/worker access. Separate runtime/migration database roles,
release scans, live sign-in and backup restoration remain go-live requirements.
See [container builds](container-builds.md) and the
[requirements review](requirements-review.md). The commands below make that
staging installation concrete; they do not close those release requirements.

## 1. Inspect the target host

```bash
cat /etc/os-release
uname -m
free -h
df -h /var/lib/docker /opt
getenforce
docker context ls
sudo systemctl status docker --no-pager
sudo ss -lntp
```

If `/var/lib/docker` does not exist, check its parent filesystem with `df -h /var`.
Reserve room for image builds, database growth, uploads and backups. Size the
server from staging measurements; this repository has no validated capacity
benchmark. Confirm existing workloads before installing packages or taking ports.

## 2. Install Docker Engine when missing

For Rocky Linux 9, follow the [official Rocky Docker guide](https://docs.rockylinux.org/gemstones/containers/docker/):

```bash
sudo dnf install -y dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker --context default version
sudo docker --context default compose version
```

If Docker Engine is already installed, verify it instead of reinstalling it.
This runbook uses `sudo` and the `default` context explicitly. A selected
`desktop-linux` context uses Docker Desktop's VM/socket and volumes, separate
from the host Engine. Changing contexts does not migrate database or uploads.

Keep SELinux enforcing on the target server. Compose bind mounts include `z`
to label only the application paths for container sharing; API and worker share
the same source path in preview. Named data volumes are managed by Docker.
Do not relabel system directories or disable SELinux to work around a mount error.
See [Docker bind mount labeling](https://docs.docker.com/engine/storage/bind-mounts/#configure-the-selinux-label).

## 3. Prepare release images on a build machine

CI currently tests and builds images but does **not** publish them. Build a
reviewed, committed checkout on a trusted build machine. It must target the
server's architecture; these simple commands assume matching architectures.
First run the existing CI checks and review dependency/image scan results.

```bash
git status --short
git rev-parse HEAD
```

Resolve any uncommitted changes before choosing the release. In Bash:

```bash
NOC_RELEASE=$(git rev-parse --short=12 HEAD)
docker build --target production -t noc-backend:"$NOC_RELEASE" backend
docker build --target production -t noc-frontend:"$NOC_RELEASE" frontend
docker pull postgis/postgis:15-3.3
docker image inspect postgis/postgis:15-3.3 --format '{{index .RepoDigests 0}}'
```

Record that PostGIS digest with the release. For a registry-based release, push
the application images to the approved registry and use immutable digests in
the server configuration. Until that pipeline exists, a manual staging transfer
is possible:

```bash
docker save -o noc-images.tar noc-backend:"$NOC_RELEASE" noc-frontend:"$NOC_RELEASE" postgis/postgis:15-3.3
tar -czf noc-config.tar.gz compose.production.example.yaml db/init-scripts/01_infrastructure.sql db/init-scripts/02_customers_services.sql db/init-scripts/03_incidents_tickets.sql db/init-scripts/04_optimized_view.sql
sha256sum noc-images.tar noc-config.tar.gz > noc-release.sha256
scp noc-images.tar noc-config.tar.gz noc-release.sha256 steve@SERVER:/tmp/
```

Replace `SERVER` and the SSH user. Keep these generated release archives outside
Git. Record the full commit and image IDs in the release record. The server does
not need the application source or the preview seed script.

## 4. Install the staging bundle

On the server, as the deployment user:

```bash
cd /tmp
sha256sum -c noc-release.sha256
sudo install -d -m 0750 -o "$USER" /opt/noc-platform
tar -xzf /tmp/noc-config.tar.gz -C /opt/noc-platform
sudo docker --context default load -i /tmp/noc-images.tar
cd /opt/noc-platform
cp -n compose.production.example.yaml compose.production.yaml
sudo install -d -m 0700 /etc/noc-platform
sudoedit /etc/noc-platform/production.env
```

Enter the following, replacing every placeholder. Use the release identifier
created above. `sudoedit` opens the file in an editor; do not paste real secrets
into chat, Git or command arguments.

```dotenv
NOC_BACKEND_IMAGE=noc-backend:RELEASE_ID
NOC_FRONTEND_IMAGE=noc-frontend:RELEASE_ID
NOC_PRODUCTION_DB_PASSWORD=REPLACE_WITH_RANDOM_SECRET
ENTRA_TENANT_ID=REPLACE_WITH_TENANT_UUID
ENTRA_API_CLIENT_ID=REPLACE_WITH_API_APP_UUID
ENTRA_SPA_CLIENT_ID=REPLACE_WITH_SPA_APP_UUID
ENTRA_SCOPE=access_as_user
MONITORING_INGEST_TOKEN=
```

Generate a password with `openssl rand -hex 32`, then enter it in the protected
file. Keep monitoring intake disabled until its producer is configured; enable
it later with a separate random token of at least 32 characters.

```bash
sudo chmod 0600 /etc/noc-platform/production.env
```

For team releases, replace the PostGIS tag in the server's `compose.production.yaml`
with the recorded approved digest. For an archive transfer, ensure the digest
reference resolves to the loaded image; otherwise use an approved registry or
the recorded local image ID. Verify image identities before starting services.
Environment files are the current reference mechanism; approved secret storage
and database role separation still need implementation for production.

## 5. Configure Microsoft 365 access

Create the API and SPA registrations as described in
[access and monitoring](access-and-monitoring.md#microsoft-365-configuration).
The required details are:

- API: single tenant, v2 access tokens, delegated `access_as_user` scope.
- SPA: permission to that API scope and tenant admin consent.
- SPA redirect URI: `https://YOUR_NOC_HOST/redirect.html`, registered as a SPA URI.
- API roles: `NOC.Viewer`, `NOC.Operator`, `NOC.Admin`; assign users/groups.
- Use the tenant, API application and SPA application IDs in the environment file.

The frontend reads these public settings from `/api/auth/config` at runtime.
It does not require rebuilding for a different tenant. No Entra client secret
is needed by this SPA sign-in flow. Company DNS, trusted HTTPS and outbound
access to Microsoft's identity endpoints must work for browser and API.

## 6. Start the stack in stages

Define this Bash helper in the server shell:

```bash
noc() {
  sudo docker --context default compose \
    --env-file /etc/noc-platform/production.env \
    -f /opt/noc-platform/compose.production.yaml "$@"
}
```

Then run each command and check its result before proceeding:

```bash
noc config -q
noc up -d --wait --wait-timeout 180 db
noc run --rm --no-deps migrate
noc up -d --no-deps --wait --wait-timeout 180 api response-worker
noc up -d --no-deps --wait --wait-timeout 180 frontend
noc ps -a
curl --fail http://127.0.0.1:8080/health/live
curl --fail http://127.0.0.1:8080/api/auth/config
```

For registry images, run `noc pull` before starting; archive-loaded images can
run without a registry. `config -q` validates without printing expanded secrets.
Frontend liveness and public auth configuration do not prove database readiness
or working sign-in; inspect the API and worker health status as well.

The first empty database runs **only** baseline SQL 01–04 and then Alembic. It
contains no preview customers, inventory or incidents. Production migration
does not run `app.preview_response_seed`; configure real engineers and response
policies through the application. Existing databases require a reviewed migration
plan; init scripts do not rerun against populated volumes.

Troubleshoot with:

```bash
noc logs --tail 100 db api response-worker frontend
noc run --rm --no-deps migrate alembic current
```

For a failed initial migration, read the migration command's output before retrying.
For mount denials, inspect `ls -Z` on the specific mounted files and
`sudo ausearch -m AVC -ts recent`. Verify writable document volumes for UID 10001.
Preserve the database password: changing the environment file does not rotate an
initialized database user's password. Never use `down -v` to fix startup failures.

## 7. Put the team endpoint behind HTTPS

The frontend listens on **127.0.0.1:8080**. Database and API ports are internal.
Use the company's TLS ingress to proxy the entire site to that loopback address
when ingress runs on this host. An ingress on another server cannot reach this
host's loopback; arrange a secured private upstream for that topology first.

For a host Nginx server, the essential location configuration inside its company
HTTPS virtual host is:

```nginx
client_max_body_size 22m;
location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 60s;
}
```

Have the server administrator configure the approved DNS name, certificate and
key, validate `nginx -t`, then reload Nginx. On an SELinux-enforcing host, host
Nginx may need `sudo setsebool -P httpd_can_network_connect on` to proxy upstream;
apply it only as part of that host's approved proxy configuration. Open HTTPS in
the correct firewalld zone for the intended company network. Leave ports 5432,
8000, 5173 and 18000 unpublished to the LAN.

The inner frontend Nginx currently overwrites `/api`'s forwarded scheme with
its own HTTP scheme. Review that chain and trusted proxy handling before relying
on original HTTPS scheme or client IP in application behavior. This remains a
production configuration task. See [Docker firewall integration](https://docs.docker.com/engine/network/packet-filtering-firewalls/).

## 8. Acceptance, persistence and updates

Before staff use real operational data, verify:

- Actual Entra sign-in and viewer/operator/admin permissions, including rejection
  of unauthenticated API requests and document downloads.
- FTTH assignment, evidence, acceptance and incident workflows with approved test data.
- PDF generation and authorized document uploads/downloads.
- Worker heartbeat, policy configuration and escalation drafts; delivery is pending.
- Off-host backup and successful restore of database **and both document volumes**.
- Runtime database role separation, release scans, resource limits and alerts.

The Compose project is `noc-production`; persistent volumes are
`noc-production_database`, `noc-production_documents` and
`noc-production_private_documents`. Engine restart policies restart long-running
services. Preview volumes and Docker Desktop volumes are separate.

Back up during a controlled write pause so database records and files correspond;
retain configuration and release identities securely with recovery instructions.
`pg_dump` alone omits uploaded originals and installation evidence. Test recovery
in an isolated stack before go-live. Agree backup retention and recovery targets.

For updates, preserve the previous configuration/image identities, take a tested
backup, stop writers under the maintenance plan, load/pull the reviewed release,
update image references, migrate, start services and repeat acceptance. An older
image cannot automatically undo schema changes. Use a reviewed compatibility or
restore procedure if a migration fails.

The private seeded preview remains available for development through
`compose.dev.yaml`; it uses an unauthenticated preview identity and is unsuitable
for team access with real data. Use `ssh -L 5173:127.0.0.1:5173 USER@SERVER` for
private review instead of publishing the preview port to the network.
