# NOC1 hourly energy workbook upload

## Stop recurring Python windows

The agent checks every minute. Older task definitions launch `python.exe`,
which opens a console each time. The current installer uses `pythonw.exe`
and hides its SSH subprocess. It continues writing results and errors to
`C:\Users\NOC1\AppData\Local\AFLNOC\energy-upload.log`.

Upgrade from Git Bash as NOC1:

```bash
cd /c/NOC
scp steve@192.168.1.24:/home/steve/Downloads/noc_platform/.review-access/energy-windows.zip energy-windows.zip
py -3 -m zipfile -e energy-windows.zip .
bash setup-energy-windows.sh --enable
bash setup-energy-windows.sh --status
```

This replaces the existing scheduled task and preserves the workbook and SSH key.
The setup's test upload runs visibly; subsequent scheduled checks run in the background.

For a passphrase-protected key, enable Windows OpenSSH's agent in administrator PowerShell:

```powershell
Set-Service ssh-agent -StartupType Automatic
Start-Service ssh-agent
```

Then load the key in normal PowerShell as NOC1 and enter its passphrase locally:

```powershell
& "$env:WINDIR\System32\OpenSSH\ssh-add.exe" "$env:USERPROFILE\.ssh\noc-energy-upload"
```

The scheduled sender uses noninteractive SSH and logs authentication failures;
it cannot answer a passphrase prompt itself. Keep the private key on Windows.

Prepared for `NOC1` on Windows, uploading to `steve@192.168.1.24` over the
company network. This does not use the public HTTPS review URL for transfers.

Source:

```text
C:\Users\NOC1\OneDrive - Anker\General - AFL NOC TEAM\Tracker\Site-Energy\2026\SiteEnergyTracker-Q1-5.4.26.xlsx
```

The Windows helper defaults to this exact path and destination. The Linux
receiver was deployed and verified on 2026-10-17, and a 3,874-record workbook
has been delivered successfully. Use the upgrade section below to enable
web-triggered requests in the NOC1 scheduled task. The bundle
contains no passwords or SSH keys. Once imported, the workbook reports are
visible to viewers of the destination platform, including its review users.

## Automated setup with Git Bash

Use this route to automate the Windows setup. It requires Git Bash from
[Git for Windows](https://git-scm.com/downloads/win), Windows Python 3.9+, and
[Windows OpenSSH Client](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse).
Run as NOC1 with OneDrive signed in. Mark the workbook **Always keep on this
device** and wait for it to finish syncing.

1. Open **Git Bash** from the Windows Start menu.
2. Download the Bash script from Linux:

   ```bash
   mkdir -p /c/NOC
   cd /c/NOC
   scp steve@192.168.1.24:/home/steve/Downloads/noc_platform/scripts/setup-energy-windows.sh setup-energy-windows.sh
   ```

   Compare any first-connect ED25519 fingerprint with
   `SHA256:la9oBm8syRh3jE2XCWuna5dVxFmiBxsjxMIyJoAES8w` before accepting it.
   Enter the normal Linux `steve` password when prompted. Password entry is
   hidden by SSH.
3. Prepare the computer:

   ```bash
   bash setup-energy-windows.sh --prepare
   ```

   It checks dependencies, pins the server's public key, downloads the tools,
   checks the local workbook, creates/reuses a dedicated SSH key, and installs
   only the public key on Linux with the fixed workbook receiver command.
   Existing server authorized keys are preserved. The script may prompt for
   the normal Linux password when downloading and when installing the public
   key. It does not store that password or display the private key.

   A new key prompts for a passphrase. An empty passphrase allows unattended
   use; an encrypted key needs a Windows SSH agent available to scheduled
   tasks. Use the company credential policy. Preparation sends no workbook.
4. Check that preparation reports success. The Linux receiver was deployed
   and verified on 2026-10-17; the Windows schedule is activated in the next step.
5. After the administrator confirms receiver deployment, enable delivery:

   ```bash
   bash /c/NOC/setup-energy-windows.sh --enable
   ```

   This sends the actual workbook once, requires a valid server acknowledgement,
   then creates the hourly Windows task. It invokes the built-in Task Scheduler
   cmdlets internally. The registered task runs Windows Python directly and
   requires no Bash window or PowerShell script to stay running. It does not
   change Windows execution policy. Company policy can still restrict task
   creation; if Windows denies registration, share that error.
6. Check status:

   ```bash
   bash /c/NOC/setup-energy-windows.sh --status
   ```

   Logs are under `%LOCALAPPDATA%\AFLNOC\energy-upload.log`, with rotation.
   Windows must remain awake with NOC1 logged in and OneDrive syncing. The
   Bash helper is prepared and checked on Linux; Windows-specific execution
   and registration still need to be verified on this workstation.

`--prepare` can be rerun safely; it reuses the existing upload key. `--check`
checks the local workbook without uploading it. The bundle below includes
both this Bash setup and the optional PowerShell helper.

## Copy the tools to Windows

In PowerShell under NOC1, create a directory and copy the prepared bundle from
Linux using your normal server login:

```powershell
New-Item -ItemType Directory -Force C:\NOC | Out-Null
scp steve@192.168.1.24:/home/steve/Downloads/noc_platform/.review-access/energy-windows.zip C:\NOC\energy-windows.zip
Expand-Archive -LiteralPath C:\NOC\energy-windows.zip -DestinationPath C:\NOC -Force
```

Only accept the SSH host key after comparing the server's ED25519 fingerprint:

```text
SHA256:la9oBm8syRh3jE2XCWuna5dVxFmiBxsjxMIyJoAES8w
```

This was read directly from the server's public host key during setup. Do not
accept an unexpected changed host key without checking with the administrator.

## Check the workbook

In File Explorer mark the workbook **Always keep on this device** and wait for
OneDrive synchronization. Install Python 3.9+ and OpenSSH Client if needed.
The following local-only check does not need an upload key or enabled receiver:

```powershell
py -3 C:\NOC\send-energy-workbook.py --workbook "C:\Users\NOC1\OneDrive - Anker\General - AFL NOC TEAM\Tracker\Site-Energy\2026\SiteEnergyTracker-Q1-5.4.26.xlsx" --server steve@192.168.1.24 --identity "$env:USERPROFILE\.ssh\noc-energy-upload" --check-only
```

Expected outcome: `local_snapshot_checked`. This checks a stable local XLSX
snapshot; complete RawData validation happens on Linux during delivery.

## Create the upload key

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.ssh" | Out-Null
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\noc-energy-upload"
Get-Content "$env:USERPROFILE\.ssh\noc-energy-upload.pub"
```

If that key already exists, reuse it instead of overwriting it. Share only the
`.pub` line with the Linux administrator. The private key stays on Windows.
An unattended encrypted key requires an SSH agent usable by the scheduled
task; follow the company's credential policy.

The administrator adds the public key with a forced command for this host:

```text
restrict,command="/home/steve/Downloads/noc_platform/scripts/receive-energy-review-workbook.sh" ssh-ed25519 PUBLIC_KEY_HERE
```

After the administrator confirms receiver deployment and key setup, test:

```powershell
py -3 C:\NOC\send-energy-workbook.py --workbook "C:\Users\NOC1\OneDrive - Anker\General - AFL NOC TEAM\Tracker\Site-Energy\2026\SiteEnergyTracker-Q1-5.4.26.xlsx" --server steve@192.168.1.24 --identity "$env:USERPROFILE\.ssh\noc-energy-upload"
```

The upload key cannot run a shell, SCP or SFTP. The initial bundle download
above uses the normal server login, not this restricted key.

## Enable the hourly task

Run the provided helper as NOC1:

```powershell
C:\NOC\energy-upload-windows.ps1 -Action RegisterTask
C:\NOC\energy-upload-windows.ps1 -Action Status
```

The helper first requires a successful upload, then creates **AFL NOC - Hourly
energy workbook** for the current user. It starts at logon and repeats every
hour while that user is logged on. Overlapping task instances are skipped.
The task allows ten minutes per run and records acknowledgement/exit status
in `%LOCALAPPDATA%\AFLNOC\energy-upload.log`.

If company PowerShell execution policy prevents running the helper, use the
manual Python Task Scheduler setup in the [general guide](energy-file-delivery.md#5-schedule-every-hour-on-windows)
or your company's script signing process. The helper does not change execution
policy. Its scheduled PowerShell action also runs under the existing policy.
It uses the standard [Windows Task Scheduler principal](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtaskprincipal)
and [task settings](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtasksettingsset).

Keep Windows awake and OneDrive signed in. If delivery stops, the platform
continues showing the last good workbook and marks it delayed after missed
delivery windows. To pause uploads:

```powershell
Disable-ScheduledTask -TaskName 'AFL NOC - Hourly energy workbook'
```

The PowerShell helper must be tested on this Windows workstation; it cannot
be executed or registered by this Linux workspace session.

## Immediate update without waiting an hour

After server deployment, an administrator can select **Update from this
computer** on the Energy reports page, choose the saved workbook from the
OneDrive folder, and receive updated reports immediately. This uses the same
source as the hourly task and prevents duplicate imports. Save Excel and let
OneDrive sync first. The ordinary Refresh button only reloads server data.

## Linux receiver verification, 2026-10-17

The existing review API now enables file delivery through `.env.review` and
`compose.review.yaml`; Graph polling is disabled. The fixed SSH receiver and
restricted upload key are installed. All five long-running review services
are healthy. The additive migration `14c8e2f7a901` preserved existing database
record counts, including one previous manual workbook import. The automatic
source remains empty until the first successful delivery.

167 backend tests and 11 script tests passed. Local password-gateway tests
verified missing/wrong credentials were rejected and valid credentials worked.
A local browser check verified sign-in and the immediate update button. The
receiver rejected a malformed payload, and the non-root API can write private
snapshots. No operational workbook was uploaded during these checks.

The protected pre-deployment backup is
`.review-access/backups/20261017T150321Z-before-file-delivery`. Image IDs and
rollback tags are recorded privately in `.review-access/energy-delivery-release.json`.

After a reboot, the Windows scheduled task runs when NOC1 signs in; it does
not require reopening Git Bash. Windows must remain awake and OneDrive must
be signed in. If the key is passphrase-protected, the scheduled task also needs
an accessible SSH agent with that key unlocked after reboot.

## Fix for blank task setup/status output

The original Bash helper passed a multiline block to Windows PowerShell over
stdin; PowerShell could exit without executing that block. The corrected
helper passes the full block using the documented UTF-16LE EncodedCommand
interface and requires `NOC_TASK_STATUS_OK` before reporting success. It does
not change execution policy. The handoff and empty/error output paths have
automated regression coverage; Windows registration must be confirmed locally.

Download the updated helper using the normal server login (not the restricted
upload identity), then enable and check it again:

```bash
cd /c/NOC
scp steve@192.168.1.24:/home/steve/Downloads/noc_platform/scripts/setup-energy-windows.sh setup-energy-windows.sh
bash setup-energy-windows.sh --enable
bash setup-energy-windows.sh --status
```

A repeated upload of the same saved workbook returns `unchanged` and creates no
duplicate import. Look for the task name/state/next run time and
`NOC_TASK_STATUS_OK`. An error or empty status is not proof of a working schedule.
The Microsoft [PowerShell executable reference](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_powershell_exe)
describes stdin parsing and EncodedCommand.

## Task registered but not yet run

`State: Ready` with result `267011` (`0x41303`) means the task has not yet
run. The initial 1999 date is a placeholder before its first execution. Wait
for NextRunTime, then check status: a successful scheduled delivery gives
LastTaskResult 0 and an actual LastRunTime. To start a scheduled execution now
from Git Bash:

```bash
powershell.exe -NoProfile -NonInteractive -Command "Start-ScheduledTask -TaskName 'AFL NOC - Hourly energy workbook'"
```

Wait for completion, then run `bash /c/NOC/setup-energy-windows.sh --status`.
PowerShell CLIXML progress text is separate from upload/task success. New
helper downloads suppress this progress output. See Microsoft's
[task result constants](https://learn.microsoft.com/windows/win32/taskschd/task-scheduler-error-and-success-constants).

## Upgrade once for web-triggered Sync now

The updated Energy page queues a request when an administrator clicks
**Sync now**. Upgrade the Windows sender and replace the existing scheduled
task once so it can collect these requests. In Git Bash:

```bash
cd /c/NOC
scp steve@192.168.1.24:/home/steve/Downloads/noc_platform/.review-access/energy-windows.zip energy-windows.zip
py -3 -m zipfile -e energy-windows.zip .
bash setup-energy-windows.sh --enable
bash setup-energy-windows.sh --status
```

The task keeps its name **AFL NOC - Hourly energy workbook**, checks every
minute, and uploads only on request or hourly. The enable step replaces that
existing task instead of adding a second one. It runs at NOC1 logon after a
reboot, as before. Existing upload keys are reused.

After this upgrade, click Sync now in the Energy page. Normally within one
minute the Windows agent reads its configured OneDrive workbook and uploads
it, then the page refreshes. AutoSave may stay on. OneDrive must be connected
and up to date; the agent reads the latest local copy, not unsynced cloud edits.
A queued request remains pending until acknowledged successfully. Invalid
files and failed transfers preserve the last valid report and the request.

The page's messages refer to NOC1 as the **source computer**, not the browser
user's computer. Other PCs need no Bash or upload key. After three minutes
without completion, the page offers Retry sync and keeps the last report.
After acknowledgement it shows Workbook updated and refreshes the report.

## Chart display and final sync UI verification

The Excel-style report cards now use dark navy headers/footers with explicit
high-contrast colors, larger site labels and date badges. The original
blue/orange Excel chart data rendering remains in place. Browser checks
measured label contrast above 11:1 and verified six charts. Frontend lint and
production build passed.

The request queue, acknowledgement, delayed retry and manual fallback paths
passed 114 backend/unit checks; 17 sender/setup checks passed. A local browser
check verified the queued state and simulated an acknowledged status response
to confirm the completion message without writing a fake success to the
server. Actual web-triggered delivery remains dependent on upgrading NOC1.

The final server backup is recorded in
`.review-access/energy-sync-review-release.json`; it was taken before the
final sync-message and chart changes. The last frontend polling correction
replaced only frontend/gateway images, with rollback image IDs retained.
