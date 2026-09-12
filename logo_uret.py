#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Logo üretici — terazi temalı logoyu .ico ve .png olarak oluşturur.

web_ui/logo.svg ile birebir aynı tasarımı Pillow ile çizer:
    - web_ui/ikon.ico   (Windows görev çubuğu + pencere ikonu)
    - web_ui/logo.png   (istenirse kullanılmak üzere)

Kullanım:  venv\\Scripts\\python.exe logo_uret.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

BASE = Path(__file__).parent
CIKTI_ICO = BASE / "web_ui" / "ikon.ico"
CIKTI_PNG = BASE / "web_ui" / "logo.png"

BOYUT = 256  # ana çizim tuvali (istenen boyutlara küçültülür)


def _yumusat_cizgi(ciz: ImageDraw.ImageDraw, p1, p2, renk, kalinlik):
    """Uçları yuvarlatılmış çizgi çizer."""
    ciz.line([p1, p2], fill=renk, width=kalinlik)


def _ciz_logo(tuval: int) -> Image.Image:
    """Terazi temalı logoyu verilen tuval boyutunda çizer."""
    k = tuval / 256.0  # ölçek

    # Şeffaf arka plana tüm içerik çizilir, en son yuvarlak maskeyle kesilir.
    img = Image.new("RGBA", (tuval, tuval), (0, 0, 0, 0))
    ciz = ImageDraw.Draw(img)

    # --- Gradyan dolgu (daire içinde) ---
    renkler = [(0x7c, 0x3a, 0xed), (0x4f, 0x46, 0xe5), (0x06, 0xb6, 0xd4)]
    adim = 3
    for i in range(0, tuval, adim):
        oran = i / tuval
        if oran < 0.5:
            t = oran * 2
            r = int(renkler[0][0] + (renkler[1][0] - renkler[0][0]) * t)
            g = int(renkler[0][1] + (renkler[1][1] - renkler[0][1]) * t)
            b = int(renkler[0][2] + (renkler[1][2] - renkler[0][2]) * t)
        else:
            t = (oran - 0.5) * 2
            r = int(renkler[1][0] + (renkler[2][0] - renkler[1][0]) * t)
            g = int(renkler[1][1] + (renkler[2][1] - renkler[1][1]) * t)
            b = int(renkler[1][2] + (renkler[2][2] - renkler[1][2]) * t)
        ciz.line([(i, 0), (i, tuval)], fill=(r, g, b, 255), width=adim)

    # --- İç koyu halka kenarı ---
    ciz.arc([6 * k, 6 * k, 250 * k, 250 * k], start=0, end=360,
            fill=(15, 16, 35, 255), width=int(6 * k))

    # --- Terazi kolu ---
    beyaz = (255, 255, 255, 235)
    _yumusat_cizgi(ciz, (52 * k, 116 * k), (204 * k, 116 * k), beyaz, int(10 * k))
    _yumusat_cizgi(ciz, (128 * k, 116 * k), (128 * k, 140 * k), beyaz, int(10 * k))
    _yumusat_cizgi(ciz, (68 * k, 140 * k), (68 * k, 172 * k), beyaz, int(10 * k))
    _yumusat_cizgi(ciz, (188 * k, 140 * k), (188 * k, 172 * k), beyaz, int(10 * k))

    # --- Kefeler ---
    ciz.arc([46 * k, 168 * k, 78 * k, 200 * k], start=30, end=150,
            fill=beyaz, width=int(9 * k))
    ciz.arc([178 * k, 168 * k, 210 * k, 200 * k], start=30, end=150,
            fill=beyaz, width=int(9 * k))
    _yumusat_cizgi(ciz, (46 * k, 214 * k), (78 * k, 214 * k), beyaz, int(7 * k))
    _yumusat_cizgi(ciz, (178 * k, 214 * k), (210 * k, 214 * k), beyaz, int(7 * k))
    _yumusat_cizgi(ciz, (46 * k, 222 * k), (78 * k, 222 * k), beyaz, int(7 * k))
    _yumusat_cizgi(ciz, (178 * k, 222 * k), (210 * k, 222 * k), beyaz, int(7 * k))

    # --- Parlamalar ---
    ciz.ellipse([76 * k, 74 * k, 94 * k, 92 * k], fill=(255, 255, 255, 190))
    ciz.ellipse([176 * k, 196 * k, 188 * k, 208 * k], fill=(255, 255, 255, 140))

    # --- Yuvarlak maske (daire) — en son uygulanır ---
    maske = Image.new("L", (tuval, tuval), 0)
    md = ImageDraw.Draw(maske)
    md.ellipse([0, 0, tuval, tuval], fill=255)
    img.putalpha(maske)

    return img




def main() -> None:
    ana = _ciz_logo(BOYUT)

    # ICO: çoklu boyut (Windows görev çubuğu + pencere köşesi için)
    ana.save(
        str(CIKTI_ICO),
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    # PNG: tam boyut
    ana.save(str(CIKTI_PNG), format="PNG")

    print(f"Logo uretildi: {CIKTI_ICO}")
    print(f"              {CIKTI_PNG}")
    print("Not: Pencere/görev çubuğu ikonu, arayuz.py içindeki "
          "webview.start(icon=...) ile otomatik kullanılır.")


if __name__ == "__main__":
    main()