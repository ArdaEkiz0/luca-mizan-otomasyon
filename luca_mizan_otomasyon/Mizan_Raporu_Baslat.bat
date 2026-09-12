@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   LUCA MIZAN RAPORU OTOMASYONU
echo ==========================================
echo(

REM --- venv yoksa kur (sadece ilk calistirma) ---
if exist "venv\Scripts\python.exe" goto :hazir

echo [*] Ilk calistirma: sanal ortam kuruluyor...
py -3 -m venv venv
call venv\Scripts\python.exe -m pip install -r requirements.txt
call venv\Scripts\python.exe -m playwright install chromium
if not exist ".env" copy ".env.example" ".env" >nul

:hazir

echo(
echo [*] Uygulama baslatiliyor...
echo(
call venv\Scripts\python.exe arayuz.py

echo(
echo ==========================================
echo   Uygulama kapandi.
echo ==========================================
pause