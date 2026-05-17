param(
    [switch]$Build,
    [switch]$Detached,
    [switch]$ExposeDatabase
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$EnvFile = Join-Path $RepoRoot ".env"

Set-Location $RepoRoot

if (-not (Test-Path $EnvFile)) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. Edit admin/password values if needed."
}

$args = @("compose")
if ($ExposeDatabase) {
    $args += @("-f", "docker-compose.yml", "-f", "docker-compose.db-port.yml")
}
$args += "up"
if ($Build) {
    $args += "--build"
}
if ($Detached) {
    $args += "-d"
}

& docker @args
