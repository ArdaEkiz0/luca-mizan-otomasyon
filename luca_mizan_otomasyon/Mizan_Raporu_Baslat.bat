@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ==========================================
echo   LUCA MIZAN RAPORU OTOMASYONU
echo ==========================================
echo(

REM --- Oncelikle venv kontrolü (zaten kurulu mu ve calisiyor mu?) ---
if exist "venv\Scripts\python.exe" (
    echo [*] Mevcut sanal ortam kontrol ediliyor...
    venv\Scripts\python.exe --version >nul 2>nul
    if not errorlevel 1 (
        echo [*] Sanal ortam saglam, devam ediliyor...
        goto :venv_var
    )
    echo [*] Eski sanal ortam bozuk, siliniyor...
    rmdir /s /q venv
    echo [*] Yeni sanal ortam kurulacak...
)

REM --- Python bul ---
set "PYEXE="

REM Oncelikle py launcher'i dene (guvenilir)
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
echo [*] Python bulundu: %PYEXE%
echo(

REM --- Python'un calisip calismadigini test et ---
%PYEXE% --version >nul 2>nul
if errorlevel 1 (
    echo [HATA] Python calistirilamiyor: %PYEXE%
    echo Bu Python surumu bozuk olabilir.
    echo(
    echo Cozum: Python'u kaldirip tekrar kurun:
    echo   1. Ayarlar > Uygulamalar > Python'u kaldirin
    echo   2. https://www.python.org/downloads/ adresinden tekrar kurun
    echo   3. Kurulum sirasinda "Add Python to PATH" isaretleyin
    echo(
    pause
    exit /b 1
)

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
echo [*] Uygulama baslatiliyor (masaustu pencere)...
echo(
call venv\Scripts\python.exe arayuz.py

echo(
echo ==========================================
echo   Uygulama kapandi.
echo ==========================================
pause
