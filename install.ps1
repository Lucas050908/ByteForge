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
    # Already installed?
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        Write-Host "[OK] Docker already installed." -ForegroundColor Green
        return
    }

    # Windows version check — Docker Desktop requires Windows 10 build 19041+
    $build = [System.Environment]::OSVersion.Version.Build
    $major = [System.Environment]::OSVersion.Version.Major
    if ($major -lt 10 -or ($major -eq 10 -and $build -lt 19041)) {
        Write-Host ""
        Write-Host "  [!] Docker Desktop requires Windows 10 (build 19041) or newer." -ForegroundColor Yellow
        Write-Host "      Game servers and Docker apps will not work on this system." -ForegroundColor Yellow
        Write-Host "      ByteForge panel, file manager and NAS still work fine." -ForegroundColor Cyan
        Write-Host ""
        return
    }

    if (-not $InstallDocker) {
        $answer = Read-Host "  Docker is not installed. Install Docker Desktop automatically? [y/N]"
        if (@("y","Y","yes","YES") -notcontains $answer) {
            Write-Host "  Skipping Docker. Install later from: https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
            return
        }
    }

    # Try winget first (Windows 10 1709+ / Windows 11)
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host "  Installing Docker Desktop via winget..." -ForegroundColor Cyan
        $result = & winget install --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] Docker Desktop installed. Start it once from the Start Menu." -ForegroundColor Green
            return
        }
        Write-Host "  winget install failed (exit $LASTEXITCODE). Trying direct download..." -ForegroundColor Yellow
    }

    # Fallback: download installer directly
    $url      = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
    $dest     = Join-Path $env:TEMP "DockerDesktopInstaller.exe"
    Write-Host "  Downloading Docker Desktop installer (~600 MB)..." -ForegroundColor Cyan
    try {
        $wc = New-Object System.Net.WebClient
        $wc.DownloadFile($url, $dest)
        Write-Host "  Running installer (this may take a few minutes)..." -ForegroundColor Cyan
        $proc = Start-Process $dest -ArgumentList "install --quiet --accept-license" -Wait -PassThru
        if ($proc.ExitCode -eq 0) {
            Write-Host "  [OK] Docker Desktop installed. Start it once from the Start Menu." -ForegroundColor Green
        } else {
            throw "Installer exited with code $($proc.ExitCode)"
        }
        Remove-Item $dest -ErrorAction SilentlyContinue
    } catch {
        Write-Host ""
        Write-Host "  [!] Automatic Docker install failed: $_" -ForegroundColor Red
        Write-Host "  Download manually from: https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
        Start-Process "https://www.docker.com/products/docker-desktop/"
    }
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

# Copy individual files
foreach ($file in @(
    "byteforge-server.py","byteforge-platform.html",
    "byteforge-platform.css","byteforge-custom.css","byteforge-platform.js",
    "byteforge-logo.png","byteforge-icon.png"
)) {
    $source = Join-Path $src $file
    if (Test-Path $source) {
        Copy-Item $source (Join-Path $InstallDir $file) -Force
    }
}

# Copy api/ module directory (required — server imports from here)
$apiSrc = Join-Path $src "api"
if (Test-Path $apiSrc) {
    $apiDest = Join-Path $InstallDir "api"
    if (Test-Path $apiDest) { Remove-Item $apiDest -Recurse -Force }
    Copy-Item $apiSrc $apiDest -Recurse -Force
}

Install-DockerDesktop

# Store password in a separate file with restricted permissions
$credFile = Join-Path $InstallDir "byteforge.env"
"BYTEFORGE_ADMIN_PASSWORD=$adminPassword" | Set-Content -Path $credFile -Encoding UTF8
$acl = Get-Acl $credFile
$acl.SetAccessRuleProtection($true, $false)
$adminRule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    "BUILTIN\Administrators","FullControl","Allow")
$acl.SetAccessRule($adminRule)
Set-Acl $credFile $acl

$launcher = Join-Path $InstallDir "start-byteforge.ps1"
@"
`$env:BYTEFORGE_PORT = "$Port"
Get-Content "$credFile" | ForEach-Object {
    if (`$_ -match '^([^=]+)=(.*)$') { [System.Environment]::SetEnvironmentVariable(`$matches[1], `$matches[2]) }
}
Set-Location "$InstallDir"
& "$python" "$InstallDir\byteforge-server.py"
"@ | Set-Content -Path $launcher -Encoding UTF8

# Register scheduled task using schtasks.exe (compatible with PS 2.0 / Windows 7+)
$psExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$taskXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>ByteForge Platform</Description></RegistrationInfo>
  <Triggers><LogonTrigger><Enabled>true</Enabled></LogonTrigger></Triggers>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <RestartOnFailure><Interval>PT1M</Interval><Count>3</Count></RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$([System.Security.SecurityElement]::Escape($psExe))</Command>
      <Arguments>-NoProfile -ExecutionPolicy Bypass -File "$([System.Security.SecurityElement]::Escape($launcher))"</Arguments>
    </Exec>
  </Actions>
</Task>
"@
$xmlPath = Join-Path $env:TEMP "byteforge-task.xml"
[System.IO.File]::WriteAllText($xmlPath, $taskXml, [System.Text.Encoding]::Unicode)
& schtasks /create /tn "ByteForge" /xml $xmlPath /f 2>&1 | Out-Null
Remove-Item $xmlPath -ErrorAction SilentlyContinue
& schtasks /run /tn "ByteForge" 2>&1 | Out-Null

Write-Host ""
Write-Host "ByteForge installed." -ForegroundColor Green
Write-Host "Open: http://127.0.0.1:$Port"
Write-Host "Login username: ADMIN"
