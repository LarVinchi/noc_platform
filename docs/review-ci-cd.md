# Review CI/CD and the route to production

This pipeline targets the existing password-protected stakeholder deployment on
Rocky Linux 9. It preserves the database, uploaded documents, energy workbook
and Windows upload key. Production remains a separate deployment with its own
identity configuration, database and release approval.

## Everyday workflow from any computer

1. Clone `https://github.com/LarVinchi/noc_platform.git`, or fetch an existing clone.
2. Create a branch from current `origin/main`, change the code and commit it.
3. Push the branch and open a pull request targeting `main`.
4. Wait for **Verify → Required checks**. Fix any failing checks on the branch.
5. Review and merge the PR. The main-branch checks must also succeed.
6. **Publish tested review release** publishes `review-<commit SHA>` with the
   exact tested production images, runtime configuration and checksums.
7. The Linux service checks every five minutes. It downloads the current main
   release, verifies its successful workflows, commit and hashes, backs up the
   deployment, migrates the database and starts the tested images.

Allow time for main's build and the release upload, plus the next five-minute
server check. Service restarts cause a brief interruption. A failed or missing
main release leaves the current deployment running.

Required checks cover Python 3.12/3.14 unit tests, frontend lint/build, fresh
PostgreSQL/PostGIS migrations and integration tests, production image smoke
checks, and the Windows sender/deployment-tool tests. Configure main branch
protection to require pull requests and the **Required checks** status, with
strict up-to-date checks and no force pushes or deletion. An independent review
can be required when a second maintainer is available.

## Server setup and operation

The installer targets Steve's existing deployment and Docker `desktop-linux`
context. Run as Steve, not root:

```bash
cd /home/steve/Downloads/noc_platform
bash scripts/install-review-deployer.sh
systemctl --user status noc-review-deploy.timer
tail -40 .review-access/cd/deploy.log
```

The controller is copied to protected `.review-access/cd/` so switching a
working branch cannot silently change the active deployment service. Re-run the
installer after reviewing changes to the controller or its systemd units.
The service uses outbound HTTPS and the current Docker context; it needs no
GitHub token or new inbound network port. No general self-hosted Actions runner
is installed on the company server. GitHub recommends avoiding such runners
for public repositories ([runner documentation](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners)).

The protected deployment log is `.review-access/cd/deploy.log`.
The initial service run waits for main to contain this pipeline and publish its
first tested release. The server runs isolated files under
`.review-access/releases/<SHA>/runtime`; it does not pull into or reset the
working checkout. The fixed SSH receiver always invokes `noc-review-api-1`,
so the Windows uploader follows the deployed application automatically.

Inspect deployed state in `.review-access/cd/current.json`. Protected backups
live under `.review-access/backups/`, including a PostgreSQL custom-format dump,
document/workbook volume archives, checksums and the resolved previous Compose
configuration. These contain private data; do not commit or distribute them.
Keep sufficient disk space for image archives and backups; retention is manual.

If deployment fails, the service attempts to restart the previous application
images and records the error in `.review-access/cd/failed.json`. It never
performs an automatic database downgrade or destructive restore. Migrations
must remain compatible with the previous application during this rollback.
Review failed state and backups, resolve the problem, then explicitly retry:

```bash
python3 .review-access/cd/deploy-review-release.py --root "$PWD" --retry
```

To pause automatic deployment:

```bash
systemctl --user disable --now noc-review-deploy.timer
```

To operate the deployed stack manually, use the `runtime` path from current.json
with `--env-file /home/steve/Downloads/noc_platform/.env.review`,
`-p noc-review`, and all three files `compose.review.yaml`,
`compose.review.public.yaml`, `images.json`. Commands using only the source
checkout's Compose files target the old local image tags.

## Reboot and production limits

This review server currently uses Docker Desktop. The user timer needs Steve's
user session and a running `desktop-linux` engine. It resumes when that session
starts. Enabling user lingering alone does not guarantee Docker Desktop starts
without a desktop login. A headless production deployment should use the native
Docker Engine, a dedicated deployment account and system services; adapt the
controller context and units for that target. Do not claim unattended reboot
recovery for the current review host until it has been verified.

Before production, provision that target and its environment, Entra/SSO access,
HTTPS/domain, backups with a tested restore procedure, and a protected production
approval environment. The current pipeline deploys only the stakeholder stack.
Secrets, `.env.review`, `.review-access`, workbook contents and private SSH keys
are excluded from the public release. Releases contain application source and
images, so no secret should be embedded in either.
