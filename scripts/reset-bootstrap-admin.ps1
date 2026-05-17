$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

Set-Location $RepoRoot

if (-not (Test-Path $Python)) {
    throw "Python virtual environment not found at $Python."
}

& $Python scripts\reset_bootstrap_admin.py
