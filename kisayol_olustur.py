#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Masaüstüne ikonlu kısayol (.lnk) oluşturur.

İlk açılışta kullanıcının masaüstüne "Luca Mizan Otomasyonu" kısayolu
koyar; böylece kullanıcı her seferinde klasörden açmak zorunda kalmaz.

Windows'un WScript.Shell COM nesnesini kullanır (her Windows'ta bulunur).
Masaüstü klasörü OneDrive altında olabilir; önce onu dener.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Paketli (PyInstaller) çalışıyorsa _MEIPASS kullan, değilse dosyanın olduğu yer
if hasattr(sys, "_MEIPASS"):
    BASE = Path(sys._MEIPASS)
else:
    BASE = Path(__file__).parent

KISAYOL_ADI = "Luca Mizan Otomasyonu.lnk"

HEDEF = BASE / "venv" / "Scripts" / "pythonw.exe"
if not HEDEF.exists():
    HEDEF = BASE / "venv" / "Scripts" / "python.exe"
ARAYUZ = BASE / "arayuz.py"
IKON = BASE / "web_ui" / "ikon.ico"


def masaustu_bul() -> Path:
    adaylar = [
        Path.home() / "OneDrive" / "Masaüstü",
        Path.home() / "Desktop",
        Path.home() / "OneDrive" / "Desktop",
        Path.home() / "OneDrive - " / "Masaüstü",
    ]
    for p in adaylar:
        if (p / KISAYOL_ADI).parent.exists():
            return p
    # Hiçbiri yoksa Desktop dene; olmazsa ilk adayı oluştur
    for p in adaylar:
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            continue
    return Path.home()


def main() -> None:
    sistem = sys.executable
    try:
        import win32com.client

        masaustu = masaustu_bul()
        hedef_lnk = masaustu / KISAYOL_ADI
        shell = win32com.client.Dispatch("WScript.Shell")
        sc = shell.CreateShortcut(str(hedef_lnk))
        sc.TargetPath = str(HEDEF)
        sc.Arguments = '"' + str(ARAYUZ) + '"'
        sc.WorkingDirectory = str(BASE)
        if IKON.exists():
            sc.IconLocation = str(IKON) + ",0"
        sc.Description = "Luca Mizan Raporu Otomasyonu"
        sc.Save()
        print(f"Kisayol olusturuldu: {hedef_lnk}")
    except Exception as e:
        print(f"Kisayol olusturulamadi: {e}")
        # Yedek: PowerShell denemesi yapma — WScript.Shell en garantilisi
        try:
            from winshell import desktop  # type: ignore
            import winshell  # type: ignore

            hedef_lnk = Path(winshell.desktop()) / KISAYOL_ADI
            with winshell.shortcut(str(hedef_lnk)) as sc:
                sc.path = str(HEDEF)
                sc.description = "Luca Mizan Raporu Otomasyonu"
                sc.arguments = '"' + str(ARAYUZ) + '"'
                if IKON.exists():
                    sc.icon_location = (str(IKON), 0)
            print(f"Kisayol (yedek) olusturuldu: {hedef_lnk}")
        except Exception as e2:
            print(f"Yedek kisayol da olusturulamadi: {e2}")


if __name__ == "__main__":
    main()