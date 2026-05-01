param(
    [string]$InstallDir = "$env:ProgramData\ByteForge",
    [int]$Port = 8080,
    [switch]$InstallDocker
)

$ErrorActionPreference = "Stop"

function ConvertTo-PlainText {
    param([Security.SecureString]$Secure)
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try {
        [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

function Get-AdminPassword {
    if ($env:BYTEFORGE_ADMIN_PASSWORD) {
        return $env:BYTEFORGE_ADMIN_PASSWORD
    }
    while ($true) {
        $first = Read-Host "Choose ByteForge ADMIN password" -AsSecureString
        $second = Read-Host "Confirm ByteForge ADMIN password" -AsSecureString
        $plainFirst = ConvertTo-PlainText $first
        $plainSecond = ConvertTo-PlainText $second
        if ($plainFirst.Length -lt 8) {
            Write-Host "Password must be at least 8 characters." -ForegroundColor Yellow
        } elseif ($plainFirst -ne $plainSecond) {
            Write-Host "Passwords do not match." -ForegroundColor Yellow
        } else {
            return $plainFirst
        }
    }
}

function Find-Python {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return $py.Source }
    throw "Python 3 is required. Install it from https://www.python.org/downloads/windows/"
}

function Install-DockerDesktop {
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($docker) {
        Write-Host "[OK] Docker CLI already installed."
        return
    }
    if (-not $InstallDocker) {
        $answer = Read-Host "Docker Desktop is not installed. Install with winget now? [y/N]"
        if ($answer -notin @("y","Y","yes","YES")) {
            Write-Host "Install Docker Desktop later from https://www.docker.com/products/docker-desktop/"
            return
        }
    }
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        Write-Host "winget not found. Install Docker Desktop manually from https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
        return
    }
    winget install --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
    Write-Host "Start Docker Desktop once after install so the Docker engine runs."
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$src = Join-Path $root "ByteForge"
if (-not (Test-Path (Join-Path $src "byteforge-server.py"))) {
    throw "ByteForge files not found next to install.ps1"
}

Write-Host "ByteForge Windows terminal installer" -ForegroundColor Cyan
$adminPassword = Get-AdminPassword
$python = Find-Python

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
foreach ($file in @("byteforge-server.py","byteforge-platform.html","byteforge-platform.css","byteforge-platform.js","byteforge-logo.svg","byteforge-icon.svg")) {
    $source = Join-Path $src $file
    if (Test-Path $source) {
        Copy-Item $source (Join-Path $InstallDir $file) -Force
    }
}

Install-DockerDesktop

$launcher = Join-Path $InstallDir "start-byteforge.ps1"
@"
`$env:BYTEFORGE_PORT = "$Port"
`$env:BYTEFORGE_ADMIN_PASSWORD = "$adminPassword"
Set-Location "$InstallDir"
& "$python" "$InstallDir\byteforge-server.py"
"@ | Set-Content -Path $launcher -Encoding UTF8

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$launcher`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "ByteForge" -Action $action -Trigger $trigger -Settings $settings -Description "ByteForge Platform" -Force | Out-Null

Start-ScheduledTask -TaskName "ByteForge"

Write-Host ""
Write-Host "ByteForge installed." -ForegroundColor Green
Write-Host "Open: http://127.0.0.1:$Port"
Write-Host "Login username: ADMIN"
