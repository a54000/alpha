param(
    [Parameter(Mandatory = $true)]
    [string]$DumpPath,

    [string]$DatabaseName = "angel_data",
    [string]$HostName = "localhost",
    [int]$Port = 5432,
    [string]$UserName = "postgres",
    [string]$PgBin = ""
)

$ErrorActionPreference = "Stop"

$resolvedDump = Resolve-Path -LiteralPath $DumpPath
if (-not $resolvedDump) {
    throw "Dump file not found: $DumpPath"
}

function Resolve-PgTool {
    param([string]$Name)

    if ($PgBin) {
        $candidate = Join-Path $PgBin "$Name.exe"
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    throw "$Name was not found. Pass -PgBin, for example: -PgBin 'C:\Program Files\PostgreSQL\16\bin'"
}

$psql = Resolve-PgTool "psql"
$pgRestore = Resolve-PgTool "pg_restore"

$env:PGHOST = $HostName
$env:PGPORT = [string]$Port
$env:PGUSER = $UserName

Write-Host "Creating database if missing: $DatabaseName"
$exists = & $psql --dbname postgres --tuples-only --no-align --command "SELECT 1 FROM pg_database WHERE datname = '$DatabaseName';"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to check whether database '$DatabaseName' exists. Verify the PostgreSQL username/password and server settings."
}

$existsText = if ($null -eq $exists) { "" } else { ($exists -join "").Trim() }
if ($existsText -ne "1") {
    & $psql --dbname postgres --command "CREATE DATABASE $DatabaseName;"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create database '$DatabaseName'."
    }
} else {
    Write-Host "Database already exists: $DatabaseName"
}

Write-Host "Restoring dump: $resolvedDump"
& $pgRestore --dbname $DatabaseName --clean --if-exists --no-owner --no-privileges --verbose $resolvedDump
if ($LASTEXITCODE -ne 0) {
    throw "pg_restore failed for '$resolvedDump'."
}

Write-Host "Checking tables"
& $psql --dbname $DatabaseName --command "\dt"
if ($LASTEXITCODE -ne 0) {
    throw "Restore finished, but table check failed for database '$DatabaseName'."
}

Write-Host "Restore complete. Use ANGEL_DATABASE_URL with database '$DatabaseName' for the audit."
