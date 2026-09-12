#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Luca Mizan Raporu Otomasyonu - Masaüstü Arayüz (Pencere)
=========================================================

Modern animasyonlu arayüzü GERÇEK bir masaüstü penceresi içinde gösterir
(pywebview / Windows WebView2). Sunucu arka planda çalışır, arayüz o
sunucuya bağlanır. pywebview kurulu değilse veya pencere açılamazsa
otomatik olarak varsayılan tarayıcıya düşer (yine çalışır).
"""

from __future__ import annotations

import os
import sys
import threading
import traceback
from pathlib import Path

import web_ui

PENCERE_BASLIK = "Luca Mizan Otomasyonu — Developer: Arda M. Ekiz"
PENCERE_GENISLIK = 1180
PENCERE_YUKSEKLIK = 800


def _ikon_yolu() -> Path:
    """İkon dosyasının yolunu döndürür (PyInstaller paketinde _MEIPASS içinde)."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "web_ui" / "ikon.ico"
    return Path(__file__).parent / "web_ui" / "ikon.ico"


def main() -> None:
    web_ui._dosyaya_log_yaz("=" * 20 + " Uygulama baslatildi (masaustu pencere) " + "=" * 20)

    # HTTP sunucusunu arka planda başlat
    try:
        adres, sunucu = web_ui.sunucu_baslat()
    except OSError as e:
        print(f"[HATA] Sunucu baslatilamadi: {e}")
        return
    except Exception as e:
        print(f"[HATA] Beklenmedik sunucu hatasi: {e}")
        traceback.print_exc()
        return

    # Önce pencere modunu dene
    try:
        import webview  # pywebview

        window = webview.create_window(
            PENCERE_BASLIK,
            adres,
            width=PENCERE_GENISLIK,
            height=PENCERE_YUKSEKLIK,
            resizable=True,
            min_size=(960, 680),
            background_color="#0f1023",
        )

        # Not: webview.start(icon=...) pencere ikonunu .NET üzerinden kurar
        # (görev çubuğu + pencere köşesi). webview.start() döndüğünde pencere
        # kapatılmıştır; o noktada sunucuyu ve tarayıcıyı temiz kapat.
        start_ayarlari = {}
        ikon = _ikon_yolu()
        if ikon.exists():
            start_ayarlari["icon"] = str(ikon)
        webview.start(**start_ayarlari)
        web_ui._temiz_kapat(sunucu)
        return

    except Exception as e:
        print(f"Pencere modu acilamadi ({e}), tarayiciya geciliyor...")
        web_ui._dosyaya_log_yaz(f"Pencere modu basarisiz: {e}")

    # Yedek: tarayıcıda aç
    import webbrowser
    try:
        webbrowser.open(adres)
    except Exception:
        pass
    print(f"Arayuz tarayicida acildi: {adres}")
    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        pass
    finally:
        web_ui._temiz_kapat(sunucu)


if __name__ == "__main__":
    main()