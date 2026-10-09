param([ValidateSet('start', 'stop', 'logs', 'status')][string]$Action = 'start')
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Install and start Docker Desktop, then run .\dev.ps1 again.'
    }
    docker info --format '{{.ServerVersion}}' *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop and wait for the engine to be ready, then run .\dev.ps1 again.' }
    $taskEnvFile = Join-Path $PSScriptRoot '.env'
    $taskExistingEnv = if (Test-Path -LiteralPath $taskEnvFile) { Get-Content -LiteralPath $taskEnvFile -Raw } else { '' }
    if ($taskExistingEnv -notmatch '(?m)^NOC_DB_PASSWORD=.+$') {
        $taskRandomBytes = New-Object byte[] 32
        $taskCrypto = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try { $taskCrypto.GetBytes($taskRandomBytes) } finally { $taskCrypto.Dispose() }
        $taskPassword = [BitConverter]::ToString($taskRandomBytes).Replace('-', '').ToLower()
        Add-Content -LiteralPath $taskEnvFile -Value "`nNOC_DB_PASSWORD=$taskPassword" -Encoding ASCII
    }
    switch ($Action) {
        'start' {
            docker compose -f compose.dev.yaml up --build -d --wait --wait-timeout 240
            if ($LASTEXITCODE -ne 0) { throw 'Startup failed. Run .\dev.ps1 logs to inspect the failing service.' }
            Write-Host "`nNOC preview: http://localhost:5173"
            Write-Host 'API documentation: http://localhost:18000/docs'
            Write-Host 'Logs: .\dev.ps1 logs | Stop (keeps data): .\dev.ps1 stop'
        }
        'stop' { docker compose -f compose.dev.yaml down }
        'logs' { docker compose -f compose.dev.yaml logs --tail 100 -f }
        'status' { docker compose -f compose.dev.yaml ps }
    }
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose exited with code $LASTEXITCODE" }
} finally { Pop-Location }
