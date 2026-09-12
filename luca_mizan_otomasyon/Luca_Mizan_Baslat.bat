@echo off
cd /d "%~dp0"
if exist "dist\LucaMizanOtomasyon\LucaMizanOtomasyon.exe" (
    start "" "%~dp0dist\LucaMizanOtomasyon\LucaMizanOtomasyon.exe"
) else (
    start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0arayuz.py"
)