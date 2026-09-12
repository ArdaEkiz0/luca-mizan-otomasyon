@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ==========================================
echo   LUCA MIZAN RAPORU OTOMASYONU
echo ==========================================
echo(

set "PYEXE="

where python >nul 2>nul
if not errorlevel 1 set "PYEXE=python"

if not defined PYEXE (
    where py >nul 2>nul
    if not errorlevel 1 set "PYEXE=py -3"
)

if not defined PYEXE (
    echo [HATA] Python bulunamadi.
    echo(
    echo Lutfen once Python'u kurun: https://www.python.org/downloads/
    echo Kurulum sirasinda "Add Python to PATH" kutucugunu isaretlemeyi unutmayin.
    echo(
    pause
    exit /b 1
)

echo [*] Python bulundu: %PYEXE%
echo(

if exist "venv\Scripts\python.exe" goto :venv_var

echo [*] Ilk calistirma: sanal ortam kuruluyor...
%PYEXE% -m venv venv
if errorlevel 1 (
    echo [HATA] Sanal ortam olusturulamadi.
    pause
    exit /b 1
)

:venv_var

REM --- Bagimliliklari HER CALISTIRMADA kontrol et (requirements.txt -------
REM     degisirse otomatik yakalanir; zaten kuruluysa bu adim saniyeler ----
REM     surer) --------------------------------------------------------------
echo [*] Bagimliliklar kontrol ediliyor / guncelleniyor...
call venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>nul
call venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo [HATA] Paketler kurulamadi. Internet baglantinizi kontrol edin.
    pause
    exit /b 1
)

call venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 (
    echo [HATA] Chromium kurulamadi. Internet baglantinizi kontrol edin.
    pause
    exit /b 1
)

echo [OK] Kurulum hazir.
echo(

if exist ".env" goto :env_hazir

copy ".env.example" ".env" >nul
echo [*] ".env" dosyasi olusturuldu. Giris bilgilerinizi acilacak pencerede
echo     girip "Bilgileri Kaydet" butonuna basabilirsiniz.
echo(

:env_hazir

echo(
echo [*] Uygulama baslatiliyor...
echo(
call venv\Scripts\python.exe gui_app.py

echo(
echo ==========================================
echo   Uygulama kapandi.
echo ==========================================
pause
