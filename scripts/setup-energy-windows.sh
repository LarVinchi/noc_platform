#!/usr/bin/env bash
# Run in Git Bash on the Windows computer that syncs the Anker workbook.
set -euo pipefail

MODE=${1:---prepare}
case "$MODE" in
  --help|-h)
    cat <<'HELP'
Usage: bash setup-energy-windows.sh [--prepare|--check|--enable|--status]
  --prepare  Download tools, check the workbook, create/install the upload key.
  --check    Check the local workbook only; do not upload company data.
  --enable   Test an upload, then register the Windows refresh agent.
  --status   Show the scheduled task and recent delivery log.
Run as NOC1 in Git Bash. Requires Windows Python 3.9+ and OpenSSH Client.
The Linux receiver must be deployed before --enable can succeed.
HELP
    exit 0 ;;
  --prepare|--check|--enable|--status) ;;
  *) printf 'Unknown option: %s\n' "$MODE" >&2; exit 2 ;;
esac

case "$(uname -s)" in
  MINGW*|MSYS*) ;;
  *) printf 'Run this script in Git Bash on Windows, not WSL or the Linux server.\n' >&2; exit 2 ;;
esac

# All native Windows arguments are converted explicitly; never let MSYS alter
# the Linux remote path in an SSH/SCP command.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'
SERVER='steve@192.168.1.24'
HOST_IP='192.168.1.24'
EXPECTED_FINGERPRINT='SHA256:la9oBm8syRh3jE2XCWuna5dVxFmiBxsjxMIyJoAES8w'
REMOTE_ROOT='/home/steve/Downloads/noc_platform'
WORKBOOK='C:\Users\NOC1\OneDrive - Anker\General - AFL NOC TEAM\Tracker\Site-Energy\2026\SiteEnergyTracker-Q1-5.4.26.xlsx'
INSTALL_DIR='/c/NOC'
PROFILE_DIR=$(cygpath -u "${USERPROFILE:?Run as the OneDrive Windows user}")
KEY="$PROFILE_DIR/.ssh/noc-energy-upload"
KNOWN_HOSTS="$PROFILE_DIR/.ssh/known_hosts"
OPENSSH="$(cygpath -u "${WINDIR:-C:\\Windows}")/System32/OpenSSH"
POWERSHELL="$(cygpath -u "${WINDIR:-C:\\Windows}")/System32/WindowsPowerShell/v1.0/powershell.exe"

for program in ssh.exe scp.exe ssh-keygen.exe ssh-keyscan.exe; do
  if [[ ! -x "$OPENSSH/$program" ]]; then
    printf 'Missing Windows OpenSSH Client. Install it in Windows Optional Features, then rerun.\n' >&2
    exit 1
  fi
done
if command -v py.exe >/dev/null 2>&1; then
  PYTHON=(py.exe -3)
elif command -v python.exe >/dev/null 2>&1; then
  PYTHON=(python.exe)
else
  printf 'Install Windows Python 3.9+ (including the Python launcher), then reopen Git Bash.\n' >&2
  exit 1
fi
"${PYTHON[@]}" -c 'import sys; assert sys.platform == "win32" and sys.version_info >= (3,9), "Windows Python 3.9+ is required"'
mkdir -p "$INSTALL_DIR" "$PROFILE_DIR/.ssh"
KEY_WIN=$(cygpath -m "$KEY")
INSTALL_WIN=$(cygpath -m "$INSTALL_DIR")
SENDER_WIN="$INSTALL_WIN/send-energy-workbook.py"
SCAN=''
trap 'if [[ -n "$SCAN" ]]; then rm -f -- "$SCAN"; fi' EXIT

if [[ "$MODE" == '--prepare' ]]; then
  # Pin the server's public host key before the first password-based login.
  SCAN=$(mktemp)
  "$OPENSSH/ssh-keyscan.exe" -T 10 -t ed25519 "$HOST_IP" > "$SCAN"
  ACTUAL_FINGERPRINT=$("$OPENSSH/ssh-keygen.exe" -E sha256 -lf "$(cygpath -m "$SCAN")" | awk '{print $2}' | tr -d '\r')
  if [[ "$ACTUAL_FINGERPRINT" != "$EXPECTED_FINGERPRINT" ]]; then
    printf 'Server fingerprint mismatch. Stop and ask the server administrator to check it.\n' >&2
    exit 1
  fi
  if [[ ! -f "$KNOWN_HOSTS" ]] || ! "$OPENSSH/ssh-keygen.exe" -F "$HOST_IP" -f "$(cygpath -m "$KNOWN_HOSTS")" >/dev/null; then
    cat "$SCAN" >> "$KNOWN_HOSTS"
  fi
  printf '\nDownloading the tools. Use your normal Linux server login if prompted.\n'
  "$OPENSSH/scp.exe" -o StrictHostKeyChecking=yes \
    "$SERVER:$REMOTE_ROOT/.review-access/energy-windows.zip" "$INSTALL_WIN/energy-windows.zip"
  "${PYTHON[@]}" -c 'import pathlib,sys,zipfile; root=pathlib.Path(sys.argv[1]); z=zipfile.ZipFile(root/"energy-windows.zip"); assert all("/" not in n and "\\" not in n and n not in (".","..") for n in z.namelist()); z.extractall(root)' "$INSTALL_WIN"
fi

if [[ ! -f "$INSTALL_DIR/send-energy-workbook.py" ]]; then
  printf 'Run --prepare first to download the tools.\n' >&2
  exit 1
fi

if [[ "$MODE" == '--prepare' || "$MODE" == '--check' ]]; then
  "${PYTHON[@]}" "$SENDER_WIN" --workbook "$WORKBOOK" --server "$SERVER" --identity "$KEY_WIN" --check-only
fi

if [[ "$MODE" == '--prepare' ]]; then
  if [[ ! -f "$KEY" ]]; then
    printf '\nCreating a dedicated upload key. For unattended use, an encrypted key needs an SSH agent.\n'
    "$OPENSSH/ssh-keygen.exe" -t ed25519 -f "$KEY_WIN" -C 'noc-energy-upload'
  else
    printf '\nReusing the existing dedicated upload key.\n'
  fi
  if [[ ! -s "$KEY.pub" ]]; then
    "$OPENSSH/ssh-keygen.exe" -y -f "$KEY_WIN" > "$KEY.pub"
  fi
  printf '\nInstalling the public key using your normal Linux login. This preserves existing SSH keys.\n'
  "$OPENSSH/ssh.exe" -T -o StrictHostKeyChecking=yes "$SERVER" \
    "python3 $REMOTE_ROOT/scripts/install-energy-upload-key.py" < "$KEY.pub"
  printf '\nWindows preparation complete. No workbook has been uploaded.\n'
  printf 'After the Linux receiver is deployed, run:\n  bash /c/NOC/setup-energy-windows.sh --enable\n'
  exit 0
fi

if [[ "$MODE" == '--enable' ]]; then
  printf '\nTesting workbook delivery before enabling the schedule...\n'
  "${PYTHON[@]}" "$SENDER_WIN" --workbook "$WORKBOOK" --server "$SERVER" --identity "$KEY_WIN"
fi

if [[ "$MODE" == '--enable' || "$MODE" == '--status' ]]; then
  # Pass data in environment variables, never as executable PowerShell text.
  export NOC_UPLOAD_MODE="$MODE" NOC_UPLOAD_WORKBOOK="$WORKBOOK" NOC_UPLOAD_SERVER="$SERVER" NOC_UPLOAD_KEY="$KEY_WIN"
  export NOC_UPLOAD_SENDER="$SENDER_WIN"
  NOC_UPLOAD_PYTHON=$("${PYTHON[@]}" -c 'import sys; print(sys.executable)' | tr -d '\r')
  export NOC_UPLOAD_PYTHON
  # Windows PowerShell can silently leave a multiline stdin block unexecuted.
  # Encode the complete, fixed script as UTF-16LE so it is parsed in one call.
  SCHEDULER_COMMAND=$("${PYTHON[@]}" -c 'import base64,sys; print(base64.b64encode(sys.stdin.read().encode("utf-16le")).decode())' <<'POWERSHELL_CODE'
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try {
    $Name = 'AFL NOC - Hourly energy workbook'
    $Log = Join-Path $env:LOCALAPPDATA 'AFLNOC\energy-upload.log'
    if ($env:NOC_UPLOAD_MODE -eq '--enable') {
        function Quote-Argument([string]$Value) {
            if ($Value -match '["\r\n]') { throw 'Unexpected quote/newline in a task argument.' }
            return '"' + $Value + '"'
        }
        $Arguments = '{0} --workbook {1} --server {2} --identity {3} --log-file {4} --agent-check' -f (Quote-Argument $env:NOC_UPLOAD_SENDER), (Quote-Argument $env:NOC_UPLOAD_WORKBOOK), (Quote-Argument $env:NOC_UPLOAD_SERVER), (Quote-Argument $env:NOC_UPLOAD_KEY), (Quote-Argument $Log)
        $User = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $Action = New-ScheduledTaskAction -Execute $env:NOC_UPLOAD_PYTHON -Argument $Arguments
        $Hourly = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
        $Logon = New-ScheduledTaskTrigger -AtLogOn -User $User
        $Principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
        $Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        Register-ScheduledTask -TaskName $Name -Action $Action -Trigger @($Hourly, $Logon) -Principal $Principal -Settings $Settings -Description 'Check web refresh requests every minute; upload workbook on request or hourly' -Force | Out-Null
        [Console]::WriteLine("Windows refresh agent registered for $User. Checks every minute; uploads on request or hourly.")
    }
    Get-ScheduledTask -TaskName $Name | Select-Object TaskName, State | Format-List
    Get-ScheduledTaskInfo -TaskName $Name | Select-Object LastRunTime, LastTaskResult, NextRunTime | Format-List
    [Console]::WriteLine("Delivery log: $Log")
    if (Test-Path -LiteralPath $Log) { Get-Content -LiteralPath $Log -Tail 10 }
    [Console]::WriteLine('NOC_TASK_STATUS_OK')
    exit 0
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
POWERSHELL_CODE
  )
  if TASK_OUTPUT=$("$POWERSHELL" -NoProfile -NonInteractive -OutputFormat Text -EncodedCommand "$SCHEDULER_COMMAND" 2>&1); then
    printf '%s\n' "$TASK_OUTPUT"
    if [[ "$TASK_OUTPUT" != *'NOC_TASK_STATUS_OK'* ]]; then
      printf 'Windows did not confirm task status. The hourly schedule is not verified.\n' >&2
      exit 1
    fi
  else
    printf '%s\n' "$TASK_OUTPUT" >&2
    printf 'Windows task setup/status failed. Share the error above; the last uploaded workbook remains on Linux.\n' >&2
    exit 1
  fi
fi
