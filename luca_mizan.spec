# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — Luca Mizan Otomasyonu (.exe)
# Kullanım: venv\Scripts\pyinstaller luca_mizan.spec --noconfirm

a = Analysis(
    ["arayuz.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("web_ui/index.html", "web_ui"),
        ("web_ui/style.css", "web_ui"),
        ("web_ui/app.js", "web_ui"),
        ("web_ui/favicon.svg", "web_ui"),
        ("web_ui/logo.svg", "web_ui"),
        ("web_ui/ikon.ico", "web_ui"),
        (".env.example", "."),
    ],
    hiddenimports=[
        "web_ui",
        "luca_otomasyon_core",
        "dotenv",
        "playwright.sync_api",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="LucaMizanOtomasyon",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="web_ui/ikon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="LucaMizanOtomasyon",
)