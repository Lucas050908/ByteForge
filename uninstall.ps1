param(
    [string]$InstallDir = "$env:ProgramData\ByteForge",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# ── Banner ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  BYTEFORGE UNINSTALLER" -ForegroundColor DarkYellow
Write-Host "  ─────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""

# ── Detect install directory ───────────────────────────────────────────────
$userDir  = "$env:APPDATA\ByteForge"
$dirs = @($InstallDir, $userDir) | Where-Object { Test-Path $_ }

if ($dirs.Count -eq 0) {
    Write-Host "  ! ByteForge does not appear to be installed." -ForegroundColor Yellow
    Write-Host "    Checked: $InstallDir" -ForegroundColor DarkGray
    Write-Host "    Checked: $userDir"   -ForegroundColor DarkGray
    Write-Host ""
    exit 0
}

$foundDir = $dirs[0]

# ── Summary ────────────────────────────────────────────────────────────────
Write-Host "  This will remove:" -ForegroundColor White
Write-Host "    • Files:   $foundDir" -ForegroundColor DarkYellow
$task = Get-ScheduledTask -TaskName "ByteForge" -ErrorAction SilentlyContinue
if ($task) {
    Write-Host "    • Scheduled Task: ByteForge" -ForegroundColor DarkYellow
}
Write-Host ""

# ── Confirm ────────────────────────────────────────────────────────────────
if (-not $Force) {
    $ans = Read-Host "  Are you sure you want to uninstall ByteForge? [y/N]"
    if ($ans -notmatch '^[Yy]') {
        Write-Host ""
        Write-Host "  Aborted." -ForegroundColor DarkGray
        Write-Host ""
        exit 0
    }
}
Write-Host ""

# ── Stop and remove Scheduled Task ────────────────────────────────────────
if ($task) {
    Write-Host "  → Stopping scheduled task..." -ForegroundColor DarkYellow
    try { Stop-ScheduledTask -TaskName "ByteForge" -ErrorAction SilentlyContinue } catch {}
    Unregister-ScheduledTask -TaskName "ByteForge" -Confirm:$false
    Write-Host "  ✓ Scheduled task removed." -ForegroundColor Green
}

# ── Kill any running process ───────────────────────────────────────────────
$procs = Get-Process -Name python* -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*byteforge*" -or
    (Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine -like "*byteforge*"
}
if ($procs) {
    $procs | Stop-Process -Force
    Write-Host "  ✓ Running process stopped." -ForegroundColor Green
}

# ── Remove install directory ───────────────────────────────────────────────
foreach ($dir in $dirs) {
    if (Test-Path $dir) {
        Write-Host "  → Removing $dir..." -ForegroundColor DarkYellow
        Remove-Item -Recurse -Force $dir
        Write-Host "  ✓ Removed $dir." -ForegroundColor Green
    }
}

# ── Done ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ─────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  ByteForge has been uninstalled." -ForegroundColor Green
Write-Host "  To reinstall: run install.bat" -ForegroundColor DarkGray
Write-Host ""
