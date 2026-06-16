param(
    [string]$TaskName = "NSE Research Daily Paper Pipeline",
    [string]$ProjectRoot = "",
    [string]$StartTime = "18:30",
    [int]$PortfolioId = 1,
    [int]$PortfolioSize = 10,
    [int]$MaxCandidateRank = 5,
    [bool]$WeekdaysOnly = $true,
    [switch]$DryRun,
    [switch]$SyncDryRun,
    [switch]$NoRebalance,
    [switch]$Replace
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")
}
else {
    $ProjectRoot = Resolve-Path $ProjectRoot
}

$Wrapper = Join-Path $ProjectRoot "scripts\run_full_daily_pipeline.ps1"
if (-not (Test-Path $Wrapper)) {
    throw "Pipeline wrapper not found: $Wrapper"
}

$Existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Existing -and -not $Replace) {
    throw "Scheduled task already exists: $TaskName. Re-run with -Replace to update it."
}
if ($Existing -and $Replace) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$WrapperArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$Wrapper`"",
    "-PortfolioId", "$PortfolioId",
    "-PortfolioSize", "$PortfolioSize",
    "-MaxCandidateRank", "$MaxCandidateRank"
)

if ($DryRun) {
    $WrapperArgs += "-DryRun"
}
if ($SyncDryRun) {
    $WrapperArgs += "-SyncDryRun"
}
if (-not $NoRebalance) {
    $WrapperArgs += "-RebalancePaper"
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument ($WrapperArgs -join " ") `
    -WorkingDirectory $ProjectRoot

if ($WeekdaysOnly) {
    $Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At $StartTime
}
else {
    $Trigger = New-ScheduledTaskTrigger -Daily -At $StartTime
}
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 6)

$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Runs the NSE Research full daily paper trading pipeline."

Write-Host "Registered scheduled task: $TaskName"
if ($WeekdaysOnly) {
    Write-Host "Schedule: Monday-Friday at $StartTime"
}
else {
    Write-Host "Schedule: daily at $StartTime"
}
Write-Host "Project root: $ProjectRoot"
Write-Host "Wrapper: $Wrapper"
