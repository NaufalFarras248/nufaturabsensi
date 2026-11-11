@echo off
setlocal enabledelayedexpansion
title Deploy Internet - Nufatur Absensi
cd /d "%~dp0"

echo ============================================================
echo   DEPLOY INTERNET - NUFATUR ABSENSI
echo ============================================================
echo.

set "URLFILE=%~dp0URL-PUBLIK.txt"
set "TUNNELLOG=%~dp0tools\tunnel.log"

if not exist "%~dp0tools\cloudflared.exe" (
  echo   [X] tools\cloudflared.exe tidak ada. Deploy dibatalkan.
  goto :end
)

rem ---------- 1. pastikan server lokal hidup ----------
netstat -an | findstr ":8080" | findstr /i "LISTENING" >nul
if errorlevel 1 (
  echo   Server lokal belum jalan. Menyalakan di jendela baru...
  start "Nufatur Absensi" cmd /k "cd /d %~dp0 && python server.py"
  echo   Menunggu server siap...
  for /l %%i in (1,1,30) do (
    timeout /t 1 /nobreak >nul
    netstat -an | findstr ":8080" | findstr /i "LISTENING" >nul && goto :serverup
  )
  echo   [!] Server tidak kunjung siap. Cek jendela "Nufatur Absensi".
  goto :end
)
:serverup
echo   [OK] Server lokal hidup di http://127.0.0.1:8080

rem ---------- 2. tunnel ----------
echo.
echo   Menyalakan tunnel Cloudflare...
if exist "%TUNNELLOG%" del "%TUNNELLOG%"
start "Tunnel Absensi" /min cmd /c ""%~dp0tools\cloudflared.exe" tunnel --url http://127.0.0.1:8080 --no-autoupdate --loglevel info > "%TUNNELLOG%" 2>&1"

echo   Menunggu URL publik...
set "PUB="
for /l %%i in (1,1,40) do (
  if not defined PUB (
    timeout /t 1 /nobreak >nul
    for /f "delims=" %%u in ('powershell -NoProfile -Command "if (Test-Path '%TUNNELLOG%') { (Select-String -Path '%TUNNELLOG%' -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -AllMatches | Select-Object -First 1).Matches.Value }"') do set "PUB=%%u"
  )
)

if not defined PUB (
  echo   [!] URL belum muncul. Lihat jendela "Tunnel Absensi" atau %TUNNELLOG%.
  goto :end
)

echo %PUB%> "%URLFILE%"

echo.
echo ============================================================
echo   ALAMAT PUBLIK (dari internet, bukan cuma Wi-Fi):
echo.
echo       %PUB%
echo.
echo   Login admin  : admin
echo   Password     : lihat file AKUN-BARU.txt
echo   Disimpan ke  : %URLFILE%
echo ============================================================
echo.
echo   Aktif selama: server.py hidup DAN jendela "Tunnel Absensi" hidup.
echo   URL ini berubah setiap tunnel dijalankan ulang.
echo.
echo   Jendela ini boleh ditutup. Yang HARUS tetap terbuka:
echo     - "Nufatur Absensi"
echo     - "Tunnel Absensi"
echo.

start "" "%PUB%"

:end
echo.
pause
