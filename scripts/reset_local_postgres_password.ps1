param(
    [Parameter(Mandatory = $true)]
    [string]$NewPassword,

    [string]$ServiceName = "postgresql-x64-18",
    [string]$PgBin = "C:\Program Files\PostgreSQL\18\bin",
    [string]$DataDir = "C:\Program Files\PostgreSQL\18\data",
    [string]$UserName = "postgres"
)

$ErrorActionPreference = "Stop"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an Administrator PowerShell."
    }
}

function Resolve-PgTool {
    param([string]$Name)

    $candidate = Join-Path $PgBin "$Name.exe"
    if (Test-Path -LiteralPath $candidate) {
        return $candidate
    }

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    throw "$Name was not found. Pass -PgBin, for example: -PgBin 'C:\Program Files\PostgreSQL\18\bin'"
}

Assert-Administrator

$psql = Resolve-PgTool "psql"
$pgHba = Join-Path $DataDir "pg_hba.conf"
if (-not (Test-Path -LiteralPath $pgHba)) {
    throw "pg_hba.conf not found: $pgHba"
}

$backup = "$pgHba.codex-backup-$(Get-Date -Format 'yyyyMMddHHmmss')"
Copy-Item -LiteralPath $pgHba -Destination $backup
Write-Host "Backed up pg_hba.conf to $backup"

try {
    $trustConfig = @"
# Temporary local trust auth for password reset.
local   all             all                                     trust
host    all             all             127.0.0.1/32            trust
host    all             all             ::1/128                 trust
local   replication     all                                     trust
host    replication     all             127.0.0.1/32            trust
host    replication     all             ::1/128                 trust
"@
    Set-Content -LiteralPath $pgHba -Value $trustConfig -Encoding ASCII

    Write-Host "Restarting PostgreSQL with temporary local trust auth"
    Restart-Service -Name $ServiceName -Force
    Start-Sleep -Seconds 3

    $escapedPassword = $NewPassword.Replace("'", "''")
    & $psql --username $UserName --dbname postgres --command "ALTER USER $UserName WITH PASSWORD '$escapedPassword';"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to reset password for user '$UserName'."
    }

    Write-Host "Password reset succeeded"
}
finally {
    Copy-Item -LiteralPath $backup -Destination $pgHba -Force
    Write-Host "Restored original pg_hba.conf"
    Restart-Service -Name $ServiceName -Force
    Start-Sleep -Seconds 3
}

Write-Host "PostgreSQL password reset complete for user '$UserName'."
