@echo off
@echo off
setlocal EnableDelayedExpansion
title ByteForge Server
cd /d "%~dp0ByteForge"

echo.
echo  BYTEFORGE SERVER
echo  ================
echo.

:: ── Stop-argument: start.bat stop ────────────────────────────────────────────
if /i "%1"=="stop" goto :stop_server

:: ── 1. Find Python ───────────────────────────────────────────────────────────
where python >nul 2>&1
if %errorlevel% equ 0 ( set PY=python & goto :check_version )
where python3 >nul 2>&1
if %errorlevel% equ 0 ( set PY=python3 & goto :check_version )
echo  [FEJL] Python ikke fundet i PATH.
echo  Download: https://www.python.org/downloads/
echo  Husk at hakke "Add Python to PATH" under installation!
echo.
pause
exit /b 1

:: ── 2. Tjek Python version (kraever 3.8+) ────────────────────────────────────
:check_version
for /f "tokens=2 delims= " %%v in ('%PY% --version 2^>^&1') do set PY_VER=%%v
for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
  set PY_MAJOR=%%a
  set PY_MINOR=%%b
)
if !PY_MAJOR! lss 3 (
  echo  [FEJL] Python !PY_VER! er for gammel. ByteForge kraever Python 3.8+
  echo  Download: https://www.python.org/downloads/
  echo.
  pause
  exit /b 1
)
if !PY_MAJOR! equ 3 if !PY_MINOR! lss 8 (
  echo  [FEJL] Python !PY_VER! er for gammel. ByteForge kraever Python 3.8+
  echo  Download: https://www.python.org/downloads/
  echo.
  pause
  exit /b 1
)

:: ── 3. Tjek om port 8080 allerede er i brug ──────────────────────────────────
:check_port
netstat -ano 2>nul | findstr /C:":8080 " >nul 2>&1
if %errorlevel% equ 0 (
  echo  [INFO] Port 8080 er allerede i brug.
  echo  ByteForge koerer muligvis allerede.
  echo.
  start "" "http://127.0.0.1:8080"
  pause
  exit /b 0
)

:: ── 4. Vis lokal og netvaerks-IP ─────────────────────────────────────────────
set LAN_IP=
for /f "tokens=2 delims=:" %%a in ('ipconfig 2^>nul ^| findstr /C:"IPv4"') do (
  if not defined LAN_IP (
    set LAN_IP=%%a
    set LAN_IP=!LAN_IP:~1!
  )
)

echo  Python !PY_VER! fundet.
echo  Lokal:     http://127.0.0.1:8080
if defined LAN_IP echo  Netvaerk:  http://!LAN_IP!:8080
echo.
echo  Log gemmes til: ..\byteforge.log
echo  Venter pa server er klar...

:: ── 5. Abn browser automatisk nar port 8080 svarer ───────────────────────────
start /b powershell -NoProfile -WindowStyle Hidden -Command "$t=0;while($t -lt 15){Start-Sleep 1;$t++;try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('127.0.0.1',8080);$c.Close();Start-Process 'http://127.0.0.1:8080';break}catch{}}"

:: ── 6. Start server med auto-restart og log til fil ──────────────────────────
:loop
%PY% byteforge-server.py >> "..\byteforge.log" 2>&1
echo.
echo  [!] Server stoppede uventet — genstarter om 3 sekunder...
echo      Tryk CTRL+C for at afslutte.
echo.
timeout /t 3 /nobreak >nul
goto :loop

:: ── Stop: find PID pa port 8080 og drab processen ────────────────────────────
:stop_server
echo  Stopper ByteForge server...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr /C:":8080 "') do (
  if not "%%p"=="0" (
    taskkill /PID %%p /F >nul 2>&1
    echo  Server stoppet (PID %%p).
    goto :stop_done
  )
)
echo  Ingen server fundet pa port 8080.
:stop_done
echo.
pause
exit /b 0
