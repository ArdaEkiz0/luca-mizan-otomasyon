K10_HATA_ONERILERI: dict[str, str] = {
    "K1": "Hesap 100 (Ana Hesap Alacak) bakiyeli olmasi gerektiginde negatif bakiye var. "
          "Giris yapilisini kontrol edin veya odonmemis alacaklarin varligini dogrulayin.",
    "K2": "Hesap 100 borc bakiyesi 3.000.000 TL limitini asti. "
          "Borc bakiyesini dusurun veya limit degisikligi yapin.",
    "K3": "Hesap 103 (Ana Hesap Borc) borc bakiyeli olmasi gerektiginde pozitif bakiye var. "
          "Borc tahsilatini kontrol edin.",
    "K4": "Hesap 101 (Ana Hesap Alacak) alacak bakiyeli olmasi gerektiginde pozitif bakiye var. "
          "Alacak tahsilatini kontrol edin.",
    "K5": "Hesap 300 (Ana Hesap Borc) borc bakiyeli olmasi gerektiginde pozitif bakiye var.",
    "K6": "Hesap 120 (Arge Alacak) alacak bakiyeli olmasi gerektiginde pozitif bakiye var.",
    "K7": "Hesap 320 (Arge Borc) borc bakiyeli olmasi gerektiginde pozitif bakiye var.",
    "K8": "Hesap 360 (Net Borc Cari) borc bakiyeli olmasi gerektiginde pozitif bakiye var.",
    "K9": "Hesap 361 (Net Alacak Cari) alacak bakiyeli olmasi gerektiginde pozitif bakiye var.",
    "K10": "600 ile baslayan hesaplarin BORCU 0 olmalidir. "
           "Satis faturasi veya evrak giriSI yapilmamis olabilir.",
    "K11": "760/770/780 ile baslayan hesaplarin ALACAGI 0 olmalidir. "
           "Alacak tahsilatini kontrol edin veya fatura giriSI yapilmamis olabilir.",
    "K12": "191/391 hesaplarinin bakiyesi 0 olmalidir. "
           "Periyot sonlandirma yapilmamis veya duzenleme yapilmamis olabilir.",
    "DOSYA": "Dosya okunamadi veya format desteklenmiyor. "
             "Dosya .xlsx/.xls formatinda ve acik olmamali.",
    "OKU": "Dosya icerigi okunamadi. Excel dosyasini duzenleyip tekrar deneyin.",
    "VERI": "Excel dosyasinda urun kaydi bulunamadi. "
            "Dosya yapisini (HESAP KODU basligi) kontrol edin.",
}


def hata_onusu_ara(kural_id: str, hesap_kodu: str = "", mesaj: str = "") -> str:
    if kural_id in K10_HATA_ONERILERI:
        return K10_HATA_ONERILERI[kural_id]
    return ""


def ihlaller_ozeti_ihlaller(ihlaller: list) -> list:
    sonuc = []
    for i in ihlaller:
        oner = hata_onusu_ara(i.get("kural_id", ""), i.get("hesap_kodu", ""), i.get("mesaj", ""))
        sonuc.append({
            "kural_id": i.get("kural_id", ""),
            "hesap_kodu": i.get("hesap_kodu", ""),
            "hesap_adi": i.get("hesap_adi", ""),
            "seviye": i.get("seviye", ""),
            "mesaj": i.get("mesaj", ""),
            "oneri": oner,
        })
    return sonuc
