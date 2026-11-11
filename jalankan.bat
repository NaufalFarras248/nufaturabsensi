@echo off
title Nufatur Absensi
cd /d "%~dp0"
echo ============================================================
echo   NUFATUR ABSENSI ^& TASK MANAGEMENT
echo ============================================================
echo   Server akan berjalan di http://127.0.0.1:8080
echo   Jendela ini HARUS tetap terbuka selama aplikasi dipakai.
echo   Tekan Ctrl + C untuk menghentikan server.
echo ============================================================
echo.
start "" http://127.0.0.1:8080
python server.py
if errorlevel 1 (
  echo.
  echo 'python' tidak ditemukan, mencoba 'py'...
  py server.py
)
pause
