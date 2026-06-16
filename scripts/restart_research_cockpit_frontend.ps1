param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 3000,
    [switch]$Dev
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$LogDir = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($Existing) {
    Stop-Process -Id $Existing.OwningProcess -Force
    Start-Sleep -Seconds 2
}

Push-Location $FrontendRoot
try {
    if (-not $Dev) {
        if (Test-Path ".next") {
            Remove-Item -LiteralPath ".next" -Recurse -Force
        }
        npm run build
        $Command = "npm run start -- -H $HostAddress -p $Port *> '..\logs\frontend_start.log'"
    }
    else {
        if (Test-Path ".next") {
            Remove-Item -LiteralPath ".next" -Recurse -Force
        }
        $Command = "npm run dev -- -H $HostAddress -p $Port *> '..\logs\frontend_dev.log'"
    }

    Start-Process -FilePath "powershell.exe" `
        -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command cd '$FrontendRoot'; $Command" `
        -WindowStyle Hidden
}
finally {
    Pop-Location
}

Write-Host "Started Swing Research Cockpit frontend at http://$HostAddress`:$Port"
Write-Host "Mode: $(if ($Dev) { 'dev' } else { 'production' })"
