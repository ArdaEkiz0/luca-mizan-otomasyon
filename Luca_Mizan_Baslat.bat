@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo   LUCA MIZAN OTOMASYONU - KONTROL PANEL
echo ============================================
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

REM --- Python yoksa otomatik kur ---
echo [*] Python bulunamadi. Otomatik kurulum yapiliyor...
echo(

set "PY_INSTALLER=%TEMP%\python-3.12.7-amd64.exe"
set "PY_URL=https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"

echo [*] Python indiriliyor...
powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%PY_INSTALLER%'" 2>nul

if not exist "%PY_INSTALLER%" (
    echo [HATA] Python indirilemedi.
    echo Lutfen Python'u manuel olarak kurun: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [*] Python kuruluyor...
"%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 TargetDir="%LOCALAPPDATA%\Python\Python312" /norestart
if errorlevel 1 (
    echo [HATA] Python kurulamadi.
    echo Lutfen Python'u manuel olarak kurun: https://www.python.org/downloads/
    del /q "%PY_INSTALLER%" >nul 2>nul
    pause
    exit /b 1
)

del /q "%PY_INSTALLER%" >nul 2>nul
set "PYEXE=%LOCALAPPDATA%\Python\Python312\python.exe"

if not exist "%PYEXE%" (
    echo [HATA] Python kurulamadi.
    echo Lutfen Python'u manuel olarak kurun: https://www.python.org/downloads/
    pause
    exit /b 1
)

:python_bulundu
echo [OK] Python bulundu: %PYEXE%

REM --- Sanal ortam var mi? Yoksa kur ---
if exist "venv\Scripts\python.exe" goto :venv_hazir

echo [*] Ilk calistirma: sanal ortam kuruluyor...
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
    echo [UYARI] Chromium kurulamadi. Bazi ozellikler calismayabilir.
)

:venv_hazir

REM --- .env yoksa olustur ---
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [*] .env dosyasi olusturuldu. Bilgileri duzenleyin.
    )
)

REM --- Masaustune kisayol olustur (yoksa bir kez) ---
if not exist "%USERPROFILE%\Desktop\Luca Mizan.lnk" (
    call venv\Scripts\python.exe kisayol_olustur.py >nul 2>nul
)

echo.
echo [*] Uygulama baslatiliyor...
echo.

REM --- Kontrol motoru testi ---
call venv\Scripts\python.exe -c "import mizan_kontrol; print('[OK] Kontrol motoru yuklendi')" 2>nul
if errorlevel 1 (
    echo [UYARI] Kontrol motoru testi basarisiz. Devam ediliyor...
)

call venv\Scripts\python.exe gui_app.py

echo.
echo ============================================
echo   Uygulama kapandi.
echo ============================================
pause