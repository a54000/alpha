param(
    [string]$BusinessDate = (Get-Date -Format "yyyy-MM-dd"),
    [int]$PortfolioId = 1,
    [int]$PortfolioSize = 10,
    [int]$MaxCandidateRank = 5,
    [string]$PythonPath = "",
    [switch]$DryRun,
    [switch]$SyncDryRun,
    [switch]$RebalancePaper,
    [switch]$Resume,
    [string]$FromStep = ""
)

$ErrorActionPreference = "Stop"

$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptPath "..")
$LogDir = Join-Path $ProjectRoot "logs\daily_pipeline"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
}

if (-not (Test-Path $PythonPath)) {
    throw "Python executable not found: $PythonPath"
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $LogDir "daily_pipeline_${BusinessDate}_${Timestamp}.log"
$SummaryPath = Join-Path $ProjectRoot "reports\phase4b_full_daily_pipeline_${BusinessDate}.json"

$Arguments = @(
    "scripts\run_full_daily_pipeline.py",
    "--business-date", $BusinessDate,
    "--portfolio-id", "$PortfolioId",
    "--portfolio-size", "$PortfolioSize",
    "--max-candidate-rank", "$MaxCandidateRank",
    "--output-json", $SummaryPath
)

if ($DryRun) {
    $Arguments += "--dry-run"
}
if ($SyncDryRun) {
    $Arguments += "--sync-dry-run"
}
if ($RebalancePaper) {
    $Arguments += "--rebalance-paper"
}
if ($Resume) {
    $Arguments += "--resume"
}
if (-not [string]::IsNullOrWhiteSpace($FromStep)) {
    $Arguments += @("--from-step", $FromStep)
}

Push-Location $ProjectRoot
try {
    $StartedAt = Get-Date -Format "o"
    "[$StartedAt] Starting full daily pipeline" | Tee-Object -FilePath $LogPath
    "ProjectRoot=$ProjectRoot" | Tee-Object -FilePath $LogPath -Append
    "BusinessDate=$BusinessDate" | Tee-Object -FilePath $LogPath -Append
    "PortfolioId=$PortfolioId" | Tee-Object -FilePath $LogPath -Append
    "Command=$PythonPath $($Arguments -join ' ')" | Tee-Object -FilePath $LogPath -Append

    & $PythonPath @Arguments 2>&1 | Tee-Object -FilePath $LogPath -Append
    $ExitCode = $LASTEXITCODE

    $CompletedAt = Get-Date -Format "o"
    "[$CompletedAt] Pipeline completed with exit code $ExitCode" | Tee-Object -FilePath $LogPath -Append
    exit $ExitCode
}
finally {
    Pop-Location
}
