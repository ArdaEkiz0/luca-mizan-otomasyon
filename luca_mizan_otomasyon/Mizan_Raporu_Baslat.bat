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
call venv\Scripts\python.exe -m pip install pyinstaller
if not exist ".env" copy ".env.example" ".env" >nul

:hazir

echo(
REM --- Derlenmis .exe varsa onu kullan (gorev cubugu ikonu icin) ---
if exist "%~dp0dist\LucaMizanOtomasyon\LucaMizanOtomasyon.exe" (
    echo [*] Uygulama baslatiliyor...
    echo(
    start "" "%~dp0dist\LucaMizanOtomasyon\LucaMizanOtomasyon.exe"
) else (
    echo [*] Uygulama baslatiliyor...
    echo(
    start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0arayuz.py"
)

echo(
echo Uygulama acildi. Bu pencereyi kapatabilirsiniz.
timeout /t 3 /nobreak >nul