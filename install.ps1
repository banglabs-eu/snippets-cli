# cli.Snippets installer for Windows
# Usage: irm https://raw.githubusercontent.com/banglabs-eu/cli.snippets/main/install.ps1 | iex

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Repo = "https://github.com/banglabs-eu/cli.snippets.git"
$InstallDir = Join-Path $env:USERPROFILE ".cli-snippets"
$BinDir = Join-Path $InstallDir "bin"
$CommandName = "snippets"
$BackendUrl = "https://api.snippets.eu"

# ── Banner ──

Write-Host ""
Write-Host "       _ _    ____        _                  _" -ForegroundColor Green
Write-Host "   ___| (_)  / ___| _ __ (_)_ __  _ __   ___| |_ ___" -ForegroundColor Green
Write-Host "  / __| | |  \___ \| '_ \| | '_ \| '_ \ / _ \ __/ __|" -ForegroundColor Green
Write-Host " | (__| | | _ ___) | | | | | |_) | |_) |  __/ |_\__ \" -ForegroundColor Green
Write-Host "  \___|_|_|(_)____/|_| |_|_| .__/| .__/ \___|\__|___/" -ForegroundColor Green
Write-Host "                            |_|   |_|" -ForegroundColor Green
Write-Host ""

# ── Helpers ──

function Write-Info  { param([string]$Msg) Write-Host $Msg -ForegroundColor Green }
function Write-Warn  { param([string]$Msg) Write-Host $Msg -ForegroundColor Yellow }
function Write-Err   { param([string]$Msg) Write-Host $Msg -ForegroundColor Red; exit 1 }
function Write-Dim   { param([string]$Msg) Write-Host $Msg -ForegroundColor DarkGray }

# ── Prerequisites ──

# Check git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Err "git is required but not installed. Run: winget install Git.Git"
}

# Find Python 3.10+
$Python = $null
foreach ($candidate in @("py -3", "python3", "python")) {
    try {
        $parts = $candidate -split ' ', 2
        $exe = $parts[0]
        $args = if ($parts.Length -gt 1) { $parts[1] } else { $null }

        $testArgs = @()
        if ($args) { $testArgs += $args }
        $testArgs += "-c"
        $testArgs += "import sys; print(sys.version_info[:2] >= (3, 10))"

        $result = & $exe @testArgs 2>$null
        if ($result -eq "True") {
            $Python = $candidate
            break
        }
    } catch {
        continue
    }
}

if (-not $Python) {
    Write-Err "Python 3.10+ is required but not found. Run: winget install Python.Python.3.12"
}

# Show Python version
$parts = $Python -split ' ', 2
$exe = $parts[0]
$vArgs = @()
if ($parts.Length -gt 1) { $vArgs += $parts[1] }
$vArgs += "--version"
$pyVersion = & $exe @vArgs 2>&1
Write-Dim "Using $pyVersion"

# ── Mode ──

Write-Host ""
Write-Info "Connecting to $BackendUrl (hosted mode)"
Write-Host ""

# ── Clone / Update CLI ──

if (Test-Path $InstallDir) {
    Write-Info "Updating cli.Snippets..."
    try { git -C $InstallDir pull --ff-only 2>$null | Out-Null }
    catch { Write-Warn "Pull failed - continuing with existing version." }
} else {
    Write-Info "Cloning cli.Snippets..."
    git clone --quiet $Repo $InstallDir
}

# ── Virtual environment ──

$VenvDir = Join-Path $InstallDir ".venv"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvDir)) {
    Write-Info "Creating virtual environment..."
    $parts = $Python -split ' ', 2
    $exe = $parts[0]
    $venvArgs = @()
    if ($parts.Length -gt 1) { $venvArgs += $parts[1] }
    $venvArgs += "-m", "venv", $VenvDir
    & $exe @venvArgs
}

Write-Info "Installing dependencies..."
& $VenvPip install --quiet --upgrade pip 2>$null
& $VenvPip install --quiet -r (Join-Path $InstallDir "requirements.txt")

# ── .env ──

$EnvContent = @"
BACKEND_URL=$BackendUrl
EXPORT_DIR=$InstallDir\exports
SNIPPETS_LANG=en
"@
Set-Content -Path (Join-Path $InstallDir ".env") -Value $EnvContent -Encoding UTF8

$ExportsDir = Join-Path $InstallDir "exports"
if (-not (Test-Path $ExportsDir)) { New-Item -ItemType Directory -Path $ExportsDir | Out-Null }

# ── Wrapper script (.cmd) ──

if (-not (Test-Path $BinDir)) { New-Item -ItemType Directory -Path $BinDir | Out-Null }

$CmdPath = Join-Path $BinDir "$CommandName.cmd"
$CmdContent = @"
@echo off
"%USERPROFILE%\.cli-snippets\.venv\Scripts\python.exe" "%USERPROFILE%\.cli-snippets\main.py" %*
"@
Set-Content -Path $CmdPath -Value $CmdContent -Encoding ASCII

# ── PATH ──

$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($UserPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("PATH", "$BinDir;$UserPath", "User")
    $env:PATH = "$BinDir;$env:PATH"
    Write-Warn "Added $BinDir to your user PATH. Restart your terminal for it to take effect."
}

# ── Done ──

Write-Host ""
Write-Host "cli.Snippets installed!" -ForegroundColor Green
Write-Host ""
Write-Host "  Run:            snippets"
Write-Host "  Config:         $InstallDir\.env"
Write-Host "  Update:         re-run this installer"
Write-Host ""
