param(
    [string]$TaskName = "NSE Research Daily Paper Pipeline"
)

$ErrorActionPreference = "Stop"

$Existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $Existing) {
    Write-Host "Scheduled task not found: $TaskName"
    exit 0
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Unregistered scheduled task: $TaskName"
