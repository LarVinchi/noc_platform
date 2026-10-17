# Run as NOC1, the Windows account that runs the OneDrive sync app.
[CmdletBinding()]
param(
    [ValidateSet('Check', 'Send', 'RegisterTask', 'Status')]
    [string]$Action = 'Check',
    [string]$Workbook = 'C:\Users\NOC1\OneDrive - Anker\General - AFL NOC TEAM\Tracker\Site-Energy\2026\SiteEnergyTracker-Q1-5.4.26.xlsx',
    [string]$Server = 'steve@192.168.1.24',
    [string]$Identity = "$env:USERPROFILE\.ssh\noc-energy-upload",
    [switch]$AgentCheck
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$TaskName = 'AFL NOC - Hourly energy workbook'
$Sender = Join-Path $PSScriptRoot 'send-energy-workbook.py'
$LogDirectory = Join-Path $env:LOCALAPPDATA 'AFLNOC'
$LogFile = Join-Path $LogDirectory 'energy-upload.log'

function Invoke-Delivery([switch]$CheckOnly) {
    if (-not (Test-Path -LiteralPath $Sender -PathType Leaf)) {
        throw "Place send-energy-workbook.py beside this PowerShell script."
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $Python = & py -3 -c 'import sys; print(sys.executable)'
        if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.9 or newer first.' }
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $Python = & python -c 'import sys; print(sys.executable)'
        if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.9 or newer first.' }
    } else {
        throw 'Install Python 3.9 or newer and the Windows OpenSSH Client first.'
    }
    $DeliveryArguments = @($Sender, '--workbook', $Workbook, '--server', $Server, '--identity', $Identity)
    if ($CheckOnly) { $DeliveryArguments += '--check-only' }
    if ($AgentCheck) { $DeliveryArguments += '--agent-check' }
    New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null
    Add-Content -LiteralPath $LogFile -Value ("{0:o} Starting {1}" -f (Get-Date), $(if ($CheckOnly) { 'local check' } else { 'delivery' }))
    # Inherit the console so errors remain visible. Keep JSON acknowledgements in
    # a local log for the scheduled task; workbook contents are never logged.
    & $Python @DeliveryArguments | Tee-Object -FilePath $LogFile -Append
    $DeliveryExit = $LASTEXITCODE
    Add-Content -LiteralPath $LogFile -Value ("{0:o} Exit code {1}" -f (Get-Date), $DeliveryExit)
    if ($DeliveryExit -ne 0) { throw "Workbook operation failed (exit $DeliveryExit). See $LogFile and the displayed error." }
}

function Quote-TaskArgument([string]$Value) {
    if ($Value -match '["\r\n]') { throw 'Task paths/arguments cannot contain quotes or newlines.' }
    return '"' + $Value + '"'
}

try {
    switch ($Action) {
        'Check' { Invoke-Delivery -CheckOnly }
        'Send' { Invoke-Delivery }
        'RegisterTask' {
            # Require a real successful delivery before enabling any schedule.
            Invoke-Delivery
            $User = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
            $TaskArguments = '-NoProfile -NonInteractive -File {0} -Action Send -AgentCheck -Workbook {1} -Server {2} -Identity {3}' -f `
                (Quote-TaskArgument $PSCommandPath), (Quote-TaskArgument $Workbook), `
                (Quote-TaskArgument $Server), (Quote-TaskArgument $Identity)
            $TaskAction = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
                -Argument $TaskArguments -WorkingDirectory $PSScriptRoot
            $Hourly = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
            $Logon = New-ScheduledTaskTrigger -AtLogOn -User $User
            $Principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
            $Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
                -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
            Register-ScheduledTask -TaskName $TaskName -Action $TaskAction -Trigger @($Hourly, $Logon) `
                -Principal $Principal -Settings $Settings -Description 'Deliver the saved OneDrive energy workbook to the NOC API every hour while signed in.' -Force | Out-Null
            Write-Host "Windows refresh agent registered for $User. Logs: $LogFile"
        }
        'Status' {
            Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State
            Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object LastRunTime, LastTaskResult, NextRunTime
            if (Test-Path -LiteralPath $LogFile) { Get-Content -LiteralPath $LogFile -Tail 12 }
        }
    }
} catch {
    Write-Error -Message $_ -ErrorAction Continue
    exit 1
}
