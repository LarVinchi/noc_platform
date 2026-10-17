# Company-network stakeholder review

The isolated `noc-review` stack serves the compiled frontend and API together at
`http://192.168.1.24:8080`. Select **Open local preview** on the sign-in screen.
Reviewers may create and change sample records. Everyone uses the same unverified
preview identity, so this environment is for demonstration data only.

The stack uses production image targets with development preview authentication.
It has its own seeded database and document volumes, separate from the existing
`noc_postgres_db`, local development preview and production deployment. Only the
frontend port is published; browser API requests use that same address through
Nginx. No Node/Vite development server is exposed.

Verified on this host on 2026-10-15: all four long-running services healthy,
migrations exited successfully, browser preview sign-in and navigation worked,
dashboard/API data loaded, a demonstration activity was saved and updated, and
PDF generation passed. Reachability from a second company workstation still
requires confirmation; host-local checks do not establish firewall access.

## Configuration and startup

Use the ignored `.env.review` file in the repository root. Keep its database
password unchanged after database initialization. The required settings are:

```dotenv
NOC_REVIEW_DB_PASSWORD=YOUR_SEPARATE_RANDOM_PASSWORD
NOC_REVIEW_BIND_ADDRESS=192.168.1.24
NOC_REVIEW_PORT=8080
```

Generate a password with `openssl rand -hex 32` and protect the file with
`chmod 600 .env.review`. Never commit it. These commands use the Docker Desktop
context currently available on this host:

```bash
cd /home/steve/Downloads/noc_platform
docker --context desktop-linux compose --env-file .env.review -f compose.review.yaml config -q
docker --context desktop-linux compose --env-file .env.review -f compose.review.yaml build migrate frontend
docker --context desktop-linux compose --env-file .env.review -f compose.review.yaml up -d --no-build --wait --wait-timeout 240
```

The migration job applies Alembic migrations and seeds demonstration response
policies. A successful migration container exits; the database, API, worker and
frontend remain running.

## Network access

Share `http://192.168.1.24:8080` with reviewers on the company LAN. This address is
currently assigned by DHCP; reserve it in DHCP or update the bind address and
recreate the frontend if the server's IP changes. Remote VLANs also need routing
and an approved firewall rule for their source subnet.

On this host, `enp6s18` is in firewalld's `public` zone. If the host firewall blocks
reviewers on `192.168.1.0/24`, an administrator can allow just that subnet:

```bash
sudo firewall-cmd --zone=public --add-rich-rule='rule family="ipv4" source address="192.168.1.0/24" port port="8080" protocol="tcp" accept'
sudo firewall-cmd --permanent --zone=public --add-rich-rule='rule family="ipv4" source address="192.168.1.0/24" port port="8080" protocol="tcp" accept'
```

The first command applies immediately; the second persists it across firewall
reloads. Do not open the database or API ports for this review. No internet router
port-forward is needed. Validate from another workstation on the intended network:

The source subnet must match the **reviewer computers**, not necessarily the
server's subnet. A remote-desktop connection observed on 2026-10-15 came from
`192.168.10.10`, which is excluded by the example `192.168.1.0/24` rule. Confirm
the reviewer subnet with the network administrator before adding its persistent
rule. To test only that specific workstation temporarily, an administrator can use:

```bash
sudo firewall-cmd --zone=public --timeout=10m --add-rich-rule='rule family="ipv4" source address="192.168.10.10/32" port port="8080" protocol="tcp" accept'
```

Then, from the reviewer workstation:

```bash
curl --fail http://192.168.1.24:8080/health/live
```

Then use a browser to enter the preview, inspect the dashboard and topology, and
try an activity or provisioning workflow. A successful request from the server
itself does not prove another workstation can reach it through the firewall.

## Operations

```bash
# Status and recent logs
docker --context desktop-linux compose --env-file .env.review -f compose.review.yaml ps -a
docker --context desktop-linux compose --env-file .env.review -f compose.review.yaml logs --tail 100

# Stop review while preserving all demonstration records and files
docker --context desktop-linux compose --env-file .env.review -f compose.review.yaml stop

# Resume after stopping
docker --context desktop-linux compose --env-file .env.review -f compose.review.yaml up -d --no-build --wait --wait-timeout 240
```

For code updates, rebuild `migrate frontend`, then run the startup command again.
The application images include the code; edits do not appear until rebuilt.
Keep Docker Desktop running and the machine awake during review. Container restart
policies do not start Docker Desktop itself after logout or reboot. For the later
permanent deployment, follow the [Rocky Linux 9 runbook](rocky-linux-9-setup.md)
using host Docker Engine, Entra sign-in, HTTPS and the production release controls.

Persistent volumes are `noc-review_database`, `noc-review_documents` and
`noc-review_private_documents`. Avoid `down -v`, which would delete review data.
To remove the LAN firewall exception when review ends, use the same two firewall
commands above with `--remove-rich-rule` in place of `--add-rich-rule`.

## Temporary internet review with a password

The optional `compose.review.public.yaml` adds a password gateway at
`127.0.0.1:18080`. Tailscale Funnel provides public HTTPS and forwards to this
gateway. Every proxied path, including API, documents and frontend assets,
requires the review password. The existing LAN frontend still uses preview
access. Do not forward the unprotected LAN port 8080 through the internet router.

Prepare and start the gateway:

```bash
python3 scripts/setup-review-access.py
docker --context desktop-linux compose --env-file .env.review -f compose.review.yaml -f compose.review.public.yaml up -d --no-deps --no-build --wait public-gateway
```

The generator preserves existing credentials. The username and password are in
`.review-access/credentials.txt`, readable only by the local owner. The directory
is ignored by Git. Only the password hash is mounted into the gateway. Share the
credentials privately with reviewers; everyone with them can edit demonstration
records under the same preview identity.

Start sharing after the gateway is healthy:

```bash
tailscale funnel --bg --https=443 http://127.0.0.1:18080
tailscale funnel status
```

If Tailscale prints an account approval URL, the account administrator must open
it and enable Funnel. If it instead reports local permission denied, run the
same command with `sudo` in the server terminal. A pending approval is not a live
public endpoint. Use the HTTPS address printed after successful activation;
the current node name is `localhost-0.tailf85dbe.ts.net`.

Reviewers enter the gateway username/password in the browser prompt, then select
**Open local preview**. Keep Tailscale, Docker Desktop and this server running.
Funnel with `--bg` stays enabled until explicitly disabled; it does not expire
automatically. It supports HTTPS sharing without an inbound router port-forward.
See [Tailscale's Funnel documentation](https://tailscale.com/docs/reference/tailscale-cli/funnel).

To end internet review:

```bash
tailscale funnel --https=443 off
docker --context desktop-linux compose --env-file .env.review -f compose.review.yaml -f compose.review.public.yaml stop public-gateway
```

Use `sudo` for the Funnel command if required by the local Tailscale permissions.
To rotate access later, stop public sharing and the gateway, securely replace
both generated credential files, then recreate the gateway and verify password
rejection before restarting Funnel. Do not publish the generated credential files.

Gateway validation on 2026-10-15: missing credentials returned 401 for the site,
auth configuration, incident API, document path and health path; an incorrect
password returned 401; valid credentials returned 200 for the site and API.
Public sharing was activated on 2026-10-15 at
**https://localhost-0.tailf85dbe.ts.net** after account approval and the local
administrator's Funnel command. HTTPS certificate validation, password rejection,
authenticated API access, browser password entry, preview sign-in and dashboard
navigation all passed through that address.

### Map tiles blocked with HTTP 403

OpenStreetMap requires browser tile requests to include a valid `Referer` header.
The frontend and public gateway use `Referrer-Policy: strict-origin-when-cross-origin`
so cross-origin tile requests identify only the site's origin, excluding page
paths and query strings. Do not change either proxy to `same-origin` or
`no-referrer`, which suppresses that header and can cause blocked tiles. See the
[OpenStreetMap tile usage policy](https://operations.osmfoundation.org/policies/tiles/).

On 2026-10-16, both proxy configurations were corrected and deployed. A browser
check intercepted tile requests before they reached OpenStreetMap and verified
the origin-only referrer with no review credentials attached. This validates
request headers; it does not guarantee availability of the external tile service.
