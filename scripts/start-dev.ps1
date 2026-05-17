param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$SkipMigrations,
    [switch]$ResetBootstrapAdmin,
    [switch]$NoPrompt
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$EnvFile = Join-Path $RepoRoot ".env"
$FrontendDir = Join-Path $RepoRoot "frontend"
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

function ConvertTo-PlainText {
    param([securestring]$SecureValue)

    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function ConvertTo-DotEnvValue {
    param([string]$Value)

    '"' + ($Value -replace '\\', '\\' -replace '"', '\"') + '"'
}

function Get-DotEnvValue {
    param(
        [string]$Path,
        [string]$Key
    )

    if (-not (Test-Path $Path)) {
        return $null
    }

    $line = Get-Content $Path | Where-Object { $_ -match "^\s*$([regex]::Escape($Key))\s*=" } | Select-Object -Last 1
    if (-not $line) {
        return $null
    }

    $value = ($line -split "=", 2)[1].Trim()
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
        return $value.Substring(1, $value.Length - 2)
    }
    return $value
}

function Set-DotEnvValue {
    param(
        [string]$Path,
        [string]$Key,
        [string]$Value
    )

    $encodedValue = ConvertTo-DotEnvValue $Value
    $entry = "$Key=$encodedValue"

    if (-not (Test-Path $Path)) {
        Set-Content -Path $Path -Value $entry -Encoding UTF8
        return
    }

    $lines = Get-Content $Path
    $updated = $false
    $newLines = foreach ($line in $lines) {
        if ($line -match "^\s*$([regex]::Escape($Key))\s*=") {
            $updated = $true
            $entry
        }
        else {
            $line
        }
    }

    if (-not $updated) {
        $newLines += $entry
    }

    Set-Content -Path $Path -Value $newLines -Encoding UTF8
}

function Import-DotEnv {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return
    }

    foreach ($line in Get-Content $Path) {
        if ($line -notmatch "^\s*([^#][^=]+?)\s*=\s*(.*)\s*$") {
            continue
        }

        $key = $matches[1].Trim()
        $value = $matches[2].Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        [Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

function New-LocalEnvFile {
    param([string]$Path)

    @"
ENVIRONMENT=development
LOG_LEVEL=INFO
SECRET_KEY=change-me-local-dev
API_V1_PREFIX=/api/v1
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
DATABASE_URL=postgresql+asyncpg://nexusops:nexusops@localhost:5432/nexusops
NEXUSOPS_MASTER_KEY=
VITE_API_BASE_URL=http://localhost:8000/api/v1
"@ | Set-Content -Path $Path -Encoding UTF8
}

Set-Location $RepoRoot

if (-not (Test-Path $Python)) {
    throw "Python virtual environment not found at $Python. Create it before running this script."
}

if (-not (Test-Path $FrontendDir)) {
    throw "Frontend directory not found at $FrontendDir."
}

if (-not (Test-Path $EnvFile)) {
    Write-Host "Creating local .env file..."
    New-LocalEnvFile $EnvFile
}

$adminUser = Get-DotEnvValue $EnvFile "NEXUSOPS_ADMIN_USER"
$adminEmail = Get-DotEnvValue $EnvFile "NEXUSOPS_ADMIN_EMAIL"
$adminPassword = Get-DotEnvValue $EnvFile "NEXUSOPS_ADMIN_PASSWORD"

if (-not $adminUser -or -not $adminEmail -or -not $adminPassword) {
    if ($NoPrompt) {
        throw "Missing bootstrap admin settings in .env. Add NEXUSOPS_ADMIN_USER, NEXUSOPS_ADMIN_EMAIL, and NEXUSOPS_ADMIN_PASSWORD."
    }

    Write-Host "Bootstrap admin settings are missing. These will be saved only in your ignored local .env file."
    if (-not $adminUser) {
        $adminUser = Read-Host "Admin username"
        Set-DotEnvValue $EnvFile "NEXUSOPS_ADMIN_USER" $adminUser
    }
    if (-not $adminEmail) {
        $adminEmail = Read-Host "Admin email"
        Set-DotEnvValue $EnvFile "NEXUSOPS_ADMIN_EMAIL" $adminEmail
    }
    if (-not $adminPassword) {
        $adminPassword = ConvertTo-PlainText (Read-Host "Admin password" -AsSecureString)
        Set-DotEnvValue $EnvFile "NEXUSOPS_ADMIN_PASSWORD" $adminPassword
    }
}

Set-DotEnvValue $EnvFile "VITE_API_BASE_URL" "http://localhost:$BackendPort/api/v1"
Import-DotEnv $EnvFile
$env:VITE_API_BASE_URL = "http://localhost:$BackendPort/api/v1"

if (-not $SkipMigrations) {
    Write-Host "Running Alembic migrations..."
    & $Python -m alembic upgrade head
}

if ($ResetBootstrapAdmin) {
    Write-Host "Resetting bootstrap admin from local .env..."
    & $Python scripts\reset_bootstrap_admin.py
}

$backendCommand = "Set-Location '$RepoRoot'; `$env:BACKEND_PORT='$BackendPort'; .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port $BackendPort"
$frontendCommand = "Set-Location '$FrontendDir'; `$env:VITE_API_BASE_URL='http://localhost:$BackendPort/api/v1'; npm run dev -- --host 0.0.0.0 --port $FrontendPort"

Write-Host "Starting backend on http://localhost:$BackendPort"
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $backendCommand

Write-Host "Starting frontend on http://localhost:$FrontendPort"
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $frontendCommand

Write-Host ""
Write-Host "NexusOps is starting."
Write-Host "Frontend: http://localhost:$FrontendPort"
Write-Host "Backend:  http://localhost:$BackendPort/api/v1"
Write-Host "Login with username '$adminUser' or email '$adminEmail'."
