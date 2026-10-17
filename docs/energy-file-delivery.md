# Hourly delivery from a OneDrive desktop machine

For the confirmed NOC1 workbook path and this server, use the [prepared Windows setup and Git Bash automation](energy-windows-noc1.md).

This alternative needs no Microsoft Graph application. OneDrive signs in as an
existing authorized user and syncs the SharePoint workbook to their computer.
A scheduled Python agent checks for web requests every minute and sends that
saved copy over SSH when requested or when the hourly upload is due.
The API validates `RawData`, selects the active dataset, and the Energy page
refreshes within 30 seconds. This is hourly workbook data, not live telemetry.

The Linux receiver and browser update button were deployed to the existing
review stack on 2026-10-17. The Windows source has delivered its validated 3,874-record workbook.
The server also supports queued web sync requests; NOC1 must use the updated
one-minute agent task to collect them. Existing manual imports remain stored. The review
stack uses a shared preview identity: its viewers can read delivered reports.
The Windows task must still be enabled on NOC1 with `--enable`.

## 1. Make the workbook available locally

On the source computer, sign in to the OneDrive desktop app with the Anker
account that can read the tracker. In the SharePoint library for `AFLNOCTEAM`,
sync the folder containing:

```text
Shared Documents/General/Tracker/Site-Energy/2026/SiteEnergyTracker-Q1-5.4.26.xlsx
```

In File Explorer, right-click the workbook and select **Always keep on this
device**. Wait for OneDrive to report that synchronization is complete. Copy
the actual local path; do not use the SharePoint web URL as a filesystem path.
Microsoft documents [SharePoint desktop synchronization](https://support.microsoft.com/en-us/sharepoint/sync/sync-sharepoint-and-teams-files-with-your-computer)
and [keeping files available locally](https://support.microsoft.com/en-us/onedrive/save-disk-space-with-onedrive-files-on-demand-for-windows).

Keep this computer awake, connected, and signed in so OneDrive can sync. A
successful upload only proves that the local copy reached Linux: it cannot
prove OneDrive downloaded the latest cloud changes. The Energy tab shows both
the workbook modification time and the last delivery time for that reason.
If the annual/quarterly source filename changes, update the scheduled job path.

## 2. Prepare the Linux receiver

Release the updated backend and frontend using the normal reviewed image,
backup, migration and deployment process. The backend needs migration
`14c8e2f7a901` for source revision/state tables. Do not run deployment commands
against an old backend image that does not contain these changes.

In the destination's protected environment file set:

```dotenv
ENERGY_ONEDRIVE_ENABLED=false
ENERGY_FILE_PUSH_ENABLED=true
ENERGY_FILE_PUSH_SOURCE_ID=afl-site-energy
ENERGY_FILE_PUSH_INTERVAL_SECONDS=3600
```

The production Compose example passes these settings to the API. Recreate the
API after changing its configuration. The Graph worker is not needed.
For another Compose deployment, explicitly add these non-secret settings to
its API environment; the review Compose file deliberately does not enable
delivery by default.

Edit `scripts/receive-energy-workbook.sh` **on Linux** to select the fixed
Docker context, Compose files and environment file for this deployment.
Production defaults use `default`, `.env.production` and
`compose.production.example.yaml`. This host's current review deployment uses
Docker context `desktop-linux`, which is different. Keep the receiver command
fixed; it must never accept Compose options or shell commands from the sender.

```bash
chmod 755 scripts/receive-energy-workbook.sh
```

The receiving SSH account must be able to run that Docker Compose command.
For Docker Desktop it normally needs to be the Desktop owner. Keep SSH access
on the company LAN or a private VPN. The existing public HTTPS Funnel address
is for the website; it is not an SSH endpoint. `192.168.1.24` works only from a
network/VPN with a route to that private address.

## 3. Create a restricted upload key

On Windows, install Python 3.9+ and the OpenSSH Client if they are absent. Copy
`scripts/send-energy-workbook.py` to `C:\NOC\send-energy-workbook.py`.
Create a dedicated SSH key (use your normal credential policy; an unattended
encrypted key needs a working agent in the scheduled task session):

```powershell
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\noc-energy-upload"
Get-Content "$env:USERPROFILE\.ssh\noc-energy-upload.pub"
```

Send only the `.pub` line to the Linux administrator. On Linux, append it to
the chosen account's `~/.ssh/authorized_keys` with this restriction prefix,
substituting the actual absolute receiver path and public key:

```text
restrict,command="/home/steve/Downloads/noc_platform/scripts/receive-energy-workbook.sh" ssh-ed25519 AAAA... noc-energy-upload
```

Do not replace existing authorized keys. Use permissions 700 on `.ssh` and
600 on `authorized_keys`. The restricted key runs only this importer, with no
interactive shell or forwarding. It does not support SCP/SFTP; the sender
streams the file directly over SSH instead. This avoids partial files in an
inbox and removes a second remote command/transfer step.

Before scheduling, connect interactively once with the dedicated key:

```powershell
ssh -T -i "$env:USERPROFILE\.ssh\noc-energy-upload" steve@192.168.1.24
```

Verify the host fingerprint with the Linux administrator before accepting it.
The fingerprint can be read on Linux using
`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`.
After the host key is saved, press Ctrl+C: the fixed receiver waits for a
workbook stream. Scheduled transfers require that saved host key and cannot
silently trust a different server.

## 4. Test a delivery

Use PowerShell, substituting the actual workbook path:

```powershell
py -3 C:\NOC\send-energy-workbook.py `
  --workbook "C:\Users\YOURUSER\Anker\AFLNOCTEAM - Documents\General\Tracker\Site-Energy\2026\SiteEnergyTracker-Q1-5.4.26.xlsx" `
  --server steve@192.168.1.24 `
  --identity "$env:USERPROFILE\.ssh\noc-energy-upload" `
  --check-only
```

Remove `--check-only` to deliver. The first successful upload returns JSON
with `"outcome": "updated"`; sending the same workbook again returns
`"outcome": "unchanged"`. Both acknowledge the SHA-256 checksum. Failures
return a nonzero process exit code. Check the Energy page for the expected
source records and workbook save time before enabling the schedule.

## 5. Schedule every hour on Windows

Create a Task Scheduler task under the **same Windows account** that runs
OneDrive and owns the SSH key and known-hosts file:

- Trigger: at logon, repeat every **1 minute**, indefinitely.
- Program: the full path to `python.exe` (find it with `py -3 -c "import sys; print(sys.executable)"`).
- Arguments: `"C:\NOC\send-energy-workbook.py" --workbook "ACTUAL_WORKBOOK_PATH.xlsx" --server steve@192.168.1.24 --identity "C:\Users\YOURUSER\.ssh\noc-energy-upload" --agent-check`.
- Run only when that user is logged on, to match the OneDrive user session.
- Enable **Run task as soon as possible after a scheduled start is missed**.
- If already running: **Do not start a new instance**.
- Enable task history and check **Last Run Result** after the first two runs.

Run the task manually once after saving it. A sleeping/offline/logged-out PC
will not provide hourly updates. For unattended use, choose an always-on
workstation. The same Python sender can run on macOS or Linux when the workbook
is already kept current locally; schedule with that user's scheduler.

## Sync now from the Energy page

The Energy page's **Sync now** button queues a request for the NOC1 Windows
agent. An administrator clicks it without choosing a file or opening a terminal.
The Windows scheduled task checks requests every minute over the existing
restricted SSH key, then runs the normal workbook upload when requested. It
also uploads automatically when the hourly interval is due. Idle checks send
no workbook. OneDrive AutoSave/sync keeps the source file current; no separate
manual save is needed when AutoSave is working.

The page shows a waiting state until an acknowledged delivery finishes, polls
status every five seconds while waiting, and refreshes the report afterward.
NOC1 must be awake, signed in, and connected. Requests remain pending while
it is offline. A recent agent heartbeat is shown separately from the workbook
save time and last successful delivery time. The web request cannot force the
OneDrive desktop app to finish a cloud sync; it uploads the local saved copy.

The existing task must be upgraded once to run the new sender with
`--agent-check` every minute. The task retains its original name to replace it
without creating a duplicate task. The receiver still accepts older direct
hourly uploads, but those older jobs cannot pick up web requests.

**Update from this computer** remains an administrator fallback: choose a
saved RawData XLSX to upload through the browser. Both upload routes share
validation, snapshots, duplicate checks and saved-time ordering. The browser
never executes arbitrary local commands, and the SSH receiver only accepts
fixed poll/upload operations. No inbound Windows port or Microsoft Graph
credential is needed.

## Update and failure behavior

- Each upload is a complete snapshot of the workbook's RawData, not rows
  appended to the existing dataset. Corrections and removed rows appear after
  the next valid delivery. No process writes to the original workbook.
- Identical content does not create duplicate imports or source snapshots.
  Different valid versions are retained privately for audit/recovery. A newly
  saved revert selects the earlier data without duplicating it.
- Size is limited to 10 MB. A truncated transfer, checksum mismatch, invalid
  XLSX or invalid RawData never replaces the active dataset.
- Deliveries older than the current workbook's saved time are rejected. For
  an intentional restore, save a new copy so its modification time is current.
- Concurrent/retried uploads are serialized in PostgreSQL. The sender retries
  failed deliveries up to three times; an interrupted acknowledgement can be
  retried safely.
- The page marks delivery delayed after two missed hourly windows plus five
  minutes and continues serving the last valid dataset. Failed uploads appear
  in the sender's task result/receiver stderr; no success time is recorded.
- Received snapshots are in the private document volume, outside nginx's
  static directory. Existing API authorization controls reports; original
  revision downloads require `NOC.Admin`. Include the database and private
  document volume in backups. Historical versions currently have no automatic
  retention cleanup.

To pause delivery, disable the scheduled task. Leave the last dataset enabled
to continue showing it with a delayed indicator. Revoking the upload public key
prevents further transfers. Switching to Graph later is explicit: stop this
job, set file push false, and configure/enable Graph separately.

## Sync messages on any viewing computer

All browsers request a sync through the same Linux server; only the designated
NOC1 source computer needs upload tools. Its scheduled agent checks the server
every minute over the existing restricted SSH connection. The server never
executes a command on the computer viewing the page.

The page shows Sync requested while waiting, Workbook updated after an
acknowledged upload, and Sync delayed after three minutes without completion.
Delayed requests can be retried; the previous report remains available, and
the pending request can still complete when the source agent reconnects. The
source uploader's last-seen state helps distinguish it from the viewing PC.
