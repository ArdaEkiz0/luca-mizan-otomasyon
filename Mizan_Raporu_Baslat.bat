@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   LUCA MIZAN RAPORU OTOMASYONU
echo ==========================================
echo(

REM --- Python bul ---
set "PYEXE="
py -3 --version >nul 2>nul
if not errorlevel 1 (
    set "PYEXE=py -3"
    goto :python_bulundu
)
where python >nul 2>nul
if not errorlevel 1 (
    python --version >nul 2>nul
    if not errorlevel 1 (
        set "PYEXE=python"
        goto :python_bulundu
    )
)

echo [HATA] Python bulunamadi.
echo(
echo Lutfen once Python'u kurun: https://www.python.org/downloads/
echo Kurulum sirasinda "Add Python to PATH" kutucugunu isaretlemeyi unutmayin.
echo(
pause
exit /b 1

:python_bulundu
echo [OK] Python bulundu: %PYEXE%

REM --- Sanal ortam var mi? Yoksa kur ---
if exist "venv\Scripts\python.exe" goto :venv_hazir

echo [*] Ilk calistirma: sanal ortam kuruluyor (birkac dakika surebilir)...
%PYEXE% -m venv venv
if errorlevel 1 (
    echo [HATA] Sanal ortam olusturulamadi.
    pause
    exit /b 1
)

echo [*] Bagimliliklar yukleniyor...
call venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>nul
call venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo [HATA] Paketler kurulamadi. Internet baglantinizi kontrol edin.
    pause
    exit /b 1
)

echo [*] Chromium tarayici indiriliyor...
call venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 (
    echo [HATA] Chromium kurulamadi. Internet baglantinizi kontrol edin.
    pause
    exit /b 1
)

:venv_hazir

REM --- .env yoksa olustur ---
if not exist ".env" copy ".env.example" ".env" >nul

REM --- Masaustune kisayol olustur (yoksa bir kez) ---
call venv\Scripts\python.exe kisayol_olustur.py >nul 2>nul

echo(
echo [*] Uygulama baslatiliyor...
echo(
call venv\Scripts\python.exe arayuz.py

echo(
echo ==========================================
echo   Uygulama kapandi.
echo ==========================================
pause