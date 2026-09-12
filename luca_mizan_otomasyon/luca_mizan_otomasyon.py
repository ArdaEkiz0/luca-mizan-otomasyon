#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Luca Mizan Raporu Otomasyonu - Komut Satırı (CLI) sürümü
==========================================================

Bu, luca_otomasyon_core.py içindeki motoru kullanan basit bir komut
satırı arayüzüdür. Grafik arayüz tercih ederseniz "gui_app.py" dosyasını
çalıştırın (README.md içinde ayrıntılar var).

Kurulum ve kullanım için README.md dosyasına bakın.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv
import os

from luca_otomasyon_core import LucaOtomasyonCore, SINIF_ETIKETLERI

load_dotenv()

UYE_NO = os.getenv("LUCA_UYE_NO", "").strip()
KULLANICI_ADI = os.getenv("LUCA_KULLANICI_ADI", "").strip()
PAROLA = os.getenv("LUCA_PAROLA", "").strip()
VARSAYILAN_YIL = os.getenv("MIZAN_YIL", "2026").strip()
VARSAYILAN_SINIF = os.getenv("MIZAN_SINIF", "1").strip()
CIKTI_KLASORU = Path(os.getenv("CIKTI_KLASORU", "raporlar")).resolve()


def dur(mesaj: str) -> None:
    print(f"\n[HATA] {mesaj}")
    sys.exit(1)


def kimlik_bilgilerini_dogrula() -> None:
    if not UYE_NO or not KULLANICI_ADI or not PAROLA:
        dur(
            "LUCA_UYE_NO / LUCA_KULLANICI_ADI / LUCA_PAROLA .env dosyasında "
            "eksik. '.env.example' dosyasını '.env' olarak kopyalayıp "
            "bilgilerinizi girin."
        )


def musteri_sec(musteriler: list[dict]) -> str:
    if not musteriler:
        dur("Filtre sonucunda hiç müşteri bulunamadı. Yıl/Sınıf kombinasyonunu kontrol edin.")

    print(f"\n{len(musteriler)} müşteri bulundu:\n")
    for m in musteriler:
        print(f"  [{m['index']:>3}] {m['kisa_ad']:<15} {m['uzun_ad']:<40} {m['vergi_dairesi']}")

    print("\nSeçenekler:")
    print("  - Rapor oluşturulacak müşterinin numarasını girin (ör. 0)")
    print("  - 'tumu' yazarak TÜM müşteriler için toplu rapor oluşturun")
    print("  - 'cikis' yazarak çıkış yapın\n")

    while True:
        secim = input("Seçiminiz: ").strip().lower()
        if secim == "tumu":
            return "__TUMU__"
        if secim == "cikis":
            dur("İşlem kullanıcı tarafından iptal edildi.")
        if secim.isdigit() and 0 <= int(secim) < len(musteriler):
            secilen = musteriler[int(secim)]
            print(f"[*] Seçilen müşteri: {secilen['kisa_ad']} ({secilen['uzun_ad']})")
            return secilen["kisa_ad"]
        print("Geçersiz seçim, tekrar deneyin.")


def main() -> None:
    kimlik_bilgilerini_dogrula()

    core = LucaOtomasyonCore(UYE_NO, KULLANICI_ADI, PAROLA, cikti_klasoru=CIKTI_KLASORU, headless=False)
    try:
        musteriler = core.baslat_ve_filtrele(VARSAYILAN_YIL, VARSAYILAN_SINIF, log=print)
        kisa_ad = musteri_sec(musteriler)

        if kisa_ad == "__TUMU__":
            print(f"\n[*] Tüm {len(musteriler)} müşteri için toplu rapor başlatılıyor...\n")
            sonuclar = core.toplu_mizan_raporu(musteriler, log=print)
            basarili = sum(1 for s in sonuclar if s["durum"] in ("başarılı", "kuyruğa alındı"))
            basarisiz = sum(1 for s in sonuclar if s["durum"] == "hatalı")
            print(f"\n[*] Toplu rapor tamamlandı: {basarili} başarılı, {basarisiz} hatalı")
            for s in sonuclar:
                if s["durum"] == "hatalı":
                    print(f"  X {s['kisa_ad']}: {s['hata']}")
                else:
                    print(f"  OK {s['kisa_ad']}: {s['dosya_yolu'] or 'kuyruğa alındı'}")
        else:
            core.musteri_sec(kisa_ad, log=print)
            core.mizan_raporu_olustur(kisa_ad, log=print)

        print("\n[*] İşlem tamamlandı. Tarayıcıyı kontrol edip kapatabilirsiniz.")
        input("\nÇıkmak için Enter'a basın...")
    finally:
        core.kapat()


if __name__ == "__main__":
    main()
