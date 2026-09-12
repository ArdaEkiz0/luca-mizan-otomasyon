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

import ctypes
import threading
import time
import traceback
from pathlib import Path

import web_ui

PENCERE_BASLIK = "Luca Mizan Otomasyonu — Developer: Arda M. Ekiz"
PENCERE_GENISLIK = 1180
PENCERE_YUKSEKLIK = 800
IKON_YOLU = Path(__file__).parent / "web_ui" / "ikon.ico"

_WM_SETICON = 0x0080
_IMAGE_ICON = 1
_LR_LOADFROMFILE = 0x00000010
_GCL_HICON = -14
_GCL_HICONSM = -34
_RDW_INVALIDATE = 0x0001
_RDW_UPDATENOW = 0x0100
_RDW_FRAME = 0x0400


def _pencere_ikonu_ayarla() -> None:
    """Windows görev çubuğu ve pencere köşesi ikonunu ayarlar.

    pywebview (6.x) create_window'da icon parametresi sunmaz; bu yüzden
    pencere render olduktan sonra başlığına göre (FindWindow) doğru
    pencereyi bulur, hem örnek ikonu (WM_SETICON) hem sınıf ikonunu
    (SetClassLong) atar ve pencereyi yeniden çizer. Bu üçü birlikte
    görev çubuğu + pencere başlığı ikonunu da günceller.
    """
    if not IKON_YOLU.exists():
        return

    try:
        user32 = ctypes.windll.user32

        # 1) Başlığa göre asıl pencereyi bul (WebView2'nin iç paneli değil)
        hwnd = 0
        for _ in range(100):  # ~20 sn
            hwnd = user32.FindWindowW(None, PENCERE_BASLIK)
            if hwnd:
                break
            time.sleep(0.2)
        if not hwnd:
            web_ui._dosyaya_log_yaz("Pencere ikonu ayarlanamadi: pencere bulunamadi.")
            return

        # 2) İkonları yükle
        hicon_small = user32.LoadImageW(
            None, str(IKON_YOLU), _IMAGE_ICON, 16, 16, _LR_LOADFROMFILE
        )
        hicon_big = user32.LoadImageW(
            None, str(IKON_YOLU), _IMAGE_ICON, 32, 32, _LR_LOADFROMFILE
        )

        # 3) Örnek ikon (pencere başlık çubuğu)
        user32.SendMessageW(hwnd, _WM_SETICON, 0, hicon_small)
        user32.SendMessageW(hwnd, _WM_SETICON, 1, hicon_big)

        # 4) Sınıf ikonu (görev çubuğu)
        user32.SetClassLongW(hwnd, _GCL_HICON, hicon_big)
        user32.SetClassLongW(hwnd, _GCL_HICONSM, hicon_small)

        # 5) Yeniden çiz
        user32.RedrawWindow(
            hwnd, None, None, _RDW_INVALIDATE | _RDW_UPDATENOW | _RDW_FRAME
        )
    except Exception as e:
        web_ui._dosyaya_log_yaz(f"Pencere ikonu ayarlanamadi: {e}")


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

        # Pencere oluşunca görev çubuğu / köşe ikonunu ayarla
        threading.Thread(target=_pencere_ikonu_ayarla, daemon=True).start()

        # Not: webview.start() döndüğünde pencere kapatılmıştır;
        # o noktada sunucuyu ve tarayıcıyı temiz kapat.
        webview.start()
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