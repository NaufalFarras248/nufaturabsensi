@echo off
setlocal enabledelayedexpansion
title Alamat Akses Absensi dari Device Lain

echo ============================================================
echo   ALAMAT AKSES APLIKASI ABSENSI DARI HP / LAPTOP LAIN
echo ============================================================
echo.

set "IP="
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4"') do (
  if not defined IP set "IP=%%a"
)
set "IP=%IP: =%"

if not defined IP (
  echo   [X] Tidak menemukan IP LAN. Pastikan terhubung Wi-Fi/LAN.
  goto :end
)

echo   IP komputer ini  : %IP%
echo.
echo   Dari HP/laptop lain yang SATU Wi-Fi, buka:
echo.
echo       http://%IP%:8080
echo.
echo   Di komputer ini    : http://127.0.0.1:8080
echo.

netstat -an | findstr ":8080" | findstr /i "LISTENING" >nul
if errorlevel 1 (
  echo   [!] Server BELUM jalan. Jalankan dulu: jalankan.bat
) else (
  echo   [OK] Server sedang jalan di port 8080.
)

echo.
echo   Catatan kamera HP:
echo     Browser HP hanya kasih kamera langsung di alamat aman
echo     (https / 127.0.0.1). Lewat http://%IP%:8080 halaman akan
echo     menampilkan tombol "Buka Kamera Perangkat" - pakai kamera
echo     bawaan HP, foto tetap tersimpan dan absensi tetap sah.
echo.
echo   Kalau dari HP masih timeout, buka CMD sebagai Administrator
echo   lalu jalankan sekali:
echo       netsh advfirewall firewall add rule name="Absensi 8080" dir=in action=allow protocol=TCP localport=8080
echo.

:end
echo ============================================================
pause
