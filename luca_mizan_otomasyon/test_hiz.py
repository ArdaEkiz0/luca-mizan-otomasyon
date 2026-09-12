import sys, os, time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from luca_otomasyon_core import LucaOtomasyonCore

UYE_NO = os.getenv('LUCA_UYE_NO', '').strip()
KULLANICI_ADI = os.getenv('LUCA_KULLANICI_ADI', '').strip()
PAROLA = os.getenv('LUCA_PAROLA', '').strip()
YIL = os.getenv('MIZAN_YIL', '2026').strip()
SINIF = os.getenv('MIZAN_SINIF', '1').strip()
CIKTI = Path(os.getenv('CIKTI_KLASORU', 'raporlar')).resolve()

core = LucaOtomasyonCore(UYE_NO, KULLANICI_ADI, PAROLA, cikti_klasoru=CIKTI, headless=False)
try:
    t0 = time.time()
    musteriler = core.baslat_ve_filtrele(YIL, SINIF, log=print)
    t1 = time.time()
    print(f'\n=== GIRIS + MUSTERI LISTESI: {t1-t0:.1f} sn ===')

    test_musteriler = musteriler[:3]
    for i, m in enumerate(test_musteriler):
        ad = m['kisa_ad']
        print(f'\n--- Musteri {i+1}/{len(test_musteriler)}: {ad} ---')
        core.musteri_sec(ad, log=print)
        core.mizan_raporu_olustur(ad, log=print)
        core.musteri_kartina_don(log=print)
    t2 = time.time()
    print(f'\n=== 3 MUSTERI TOPLAM: {t2-t1:.1f} sn ===')
    print(f'=== PER MUSTERI: {(t2-t1)/3:.1f} sn ===')
finally:
    core.kapat()
