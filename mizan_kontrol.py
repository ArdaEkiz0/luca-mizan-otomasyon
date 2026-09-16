#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mizan_kontrol - Luca mizan kontrol motoru (geliştirilmiş versiyon)
===================================================================
- İndeksli kural karşılaştırma (performans)
- Dinamik kural ekleme/kaldırma
- Deduplanmış ihlal raporlama
- Kural bazlı istatistik
- dosya yapısı doğrulama
- Python logging entegrasyonu
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from collections import defaultdict

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

logger = logging.getLogger("mizan_kontrol")


# --- Sabitler ---

KURALLAR = [
    {"id": "K1", "tip": "ana_hesap", "kodlar": ["100"], "hedef_kolon": "alacak_bakiye",
     "seviye": "HATA", "kosul": "100 ana hesap ALACAK bakiyeli olmamali (negatif olmamali)"},
    {"id": "K2", "tip": "borc_limit", "kodlar": ["100"], "limit": 3000000, "seviye": "HATA",
     "kosul": "100 ana hesap borc bakiyesi 3.000.000 TL yi gecmemeli", "kolon": "borc_bakiye"},
    {"id": "K3", "tip": "ana_hesap", "kodlar": ["103"], "hedef_kolon": "borc_bakiye",
     "seviye": "HATA", "kosul": "103 ana hesap BORC bakiyeli olmamali"},
    {"id": "K4", "tip": "ana_hesap", "kodlar": ["101"], "hedef_kolon": "alacak_bakiye",
     "seviye": "HATA", "kosul": "101 ana hesap ALACAK bakiyeli olmamali"},
    {"id": "K5", "tip": "ana_hesap", "kodlar": ["300"], "hedef_kolon": "borc_bakiye",
     "seviye": "HATA", "kosul": "300 ana hesap BORC bakiyeli olmamali"},
    {"id": "K6", "tip": "ana_hesap", "kodlar": ["120"], "hedef_kolon": "alacak_bakiye",
     "seviye": "HATA", "kosul": "120 ana hesap ALACAK bakiyeli olmamali"},
    {"id": "K7", "tip": "ana_hesap", "kodlar": ["320"], "hedef_kolon": "borc_bakiye",
     "seviye": "HATA", "kosul": "320 ana hesap BORC bakiyeli olmamali"},
    {"id": "K8", "tip": "ana_hesap", "kodlar": ["360"], "hedef_kolon": "borc_bakiye",
     "seviye": "HATA", "kosul": "360 ana hesap BORC bakiyeli olmamali"},
    {"id": "K9", "tip": "ana_hesap", "kodlar": ["361"], "hedef_kolon": "borc_bakiye",
     "seviye": "HATA", "kosul": "361 ana hesap BORC bakiyeli olmamali"},
    {"id": "K10", "tip": "on_ek_borc", "kodlar": ["600"], "seviye": "HATA",
     "kosul": "600 ile baslayan tum hesaplarin BORCU 0 olmali"},
    {"id": "K11", "tip": "on_ek_alacak", "kodlar": ["760", "770", "780"], "seviye": "UYARI",
     "kosul": "760/770/780 ile baslayan tum hesaplarin ALACAGI 0 olmali"},
    {"id": "K12", "tip": "bakiye_yok", "kodlar": ["191", "391"], "seviye": "HATA",
     "kosul": "191 ve 391 hesaplarin bakiyesi olmamali"},
]


# --- Veri yapıları ---

@dataclass
class KuralIhlali:
    kural_id: str
    hesap_kodu: str
    hesap_adi: str
    mesaj: str
    seviye: str = "HATA"
    deger: str = ""


@dataclass
class KontrolSonucu:
    dosya_adi: str
    firma_adi: str = ""
    donem: str = ""
    satir_sayisi: int = 0
    ihlaller: list = field(default_factory=list)
    hata_sayisi: int = 0
    uyari_sayisi: int = 0

    @property
    def durum(self) -> str:
        if self.hata_sayisi > 0:
            return "HATA"
        if self.uyari_sayisi > 0:
            return "UYARI"
        return "OK"

    @property
    def ozet(self) -> str:
        if self.hata_sayisi == 0 and self.uyari_sayisi == 0:
            return "Tum kurallar saglandi"
        parcalar = []
        if self.hata_sayisi:
            parcalar.append(f"{self.hata_sayisi} hata")
        if self.uyari_sayisi:
            parcalar.append(f"{self.uyari_sayisi} uyari")
        return ", ".join(parcalar)


@dataclass
class KuralIstatistik:
    kural_id: str
    toplam: int = 0
    hata: int = 0
    uyari: int = 0
    hesaplar: dict = field(default_factory=dict)


# --- Yardımcı fonksiyonlar ---

def _sayi(c) -> float:
    if c is None:
        return 0.0
    if isinstance(c, (int, float)):
        return float(c)
    s = str(c).strip()
    if not s:
        return 0.0
    try:
        return float(s.replace(",", "."))
    except ValueError:
        try:
            return float(s.replace(".", "").replace(",", "."))
        except ValueError:
            return 0.0


def _kod_esles(kod: str, hedef: str) -> bool:
    return kod.strip() == hedef.strip()


# --- Excel dosya okuma ---

def _dosya_oku(dosya_yolu: Path):
    wb = None
    try:
        wb = openpyxl.load_workbook(dosya_yolu, data_only=True)
        ws = wb.active
        satirlar = []
        firma = ""
        donem = ""
        baslik = False

        for row in ws.iter_rows(values_only=True):
            if not row:
                continue
            ilk = str(row[0]).strip() if row[0] is not None else ""
            ikinci = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
            ilk_ust = (ilk.upper()
                       .replace("\u0131", "I").replace("\u00f6", "O").replace("\u00fc", "U")
                       .replace("\u00c7", "C").replace("\u015e", "S").replace("\u011e", "G"))

            if baslik:
                kod = ilk
                if not kod:
                    continue
                satirlar.append({
                    "kod": kod,
                    "ad": ikinci,
                    "borc": _sayi(row[2] if len(row) > 2 else None),
                    "alacak": _sayi(row[3] if len(row) > 3 else None),
                    "borc_bakiye": _sayi(row[4] if len(row) > 4 else None),
                    "alacak_bakiye": _sayi(row[5] if len(row) > 5 else None),
                })
                continue

            if ilk_ust == "HESAP KODU":
                baslik = True
                continue
            if ilk_ust == "MIZAN":
                continue
            if "DONEM" in ilk_ust:
                donem = ikinci
                continue
            if "TARIH" in ilk_ust:
                continue
            if not firma and (ilk or ikinci):
                try:
                    float(ilk.replace(".", "").replace(",", "."))
                    continue
                except ValueError:
                    pass
                firma = ilk or ikinci
                continue

        wb.close()
        return satirlar, firma, donem
    except Exception:
        if wb is not None:
            try:
                wb.close()
            except Exception:
                pass
        raise


def _dosya_yapisi_kontrol(dosya_yolu: Path) -> tuple[bool, str]:
    """Excel dosyasının temel kontrolü."""
    if not dosya_yolu.exists():
        return False, "Dosya bulunamadi"
    if not dosya_yolu.suffix.lower() in (".xlsx", ".xls"):
        return False, "Dosya formati desteklenmiyor (sadece .xlsx/.xls)"
    if dosya_yolu.stat().st_size == 0:
        return False, "Dosya bos"
    try:
        wb = openpyxl.load_workbook(dosya_yolu, data_only=True, read_only=True)
        wb.close()
        return True, "OK"
    except openpyxl.utils.exceptions.InvalidFileException:
        return False, "Gecersiz Excel dosyasi"
    except PermissionError:
        return False, "Dosya kilitli (Diger program acik olabilir)"
    except Exception as e:
        return False, f"Dosya acilamadi: {e}"


_KONTROL_HATA_KODLARI: dict[str, str] = {
    "DOSYA": "Dosya hatasi — kontrol edilemedi",
    "OKU": "Okuma hatasi — dosya içeriği okunamadi",
    "VERI": "Veri hatasi — dosyada gecerli mizan verisi yok",
}


# --- Kontrol motoru ---

class MizanKontrolMotoru:
    """Geliştirilmiş mizan kontrol motoru."""

    def __init__(self, yil: str = "2026", sinif: str = "1"):
        self.yil = yil
        self.sinif = sinif
        self.kurallar: list[dict] = [dict(k) for k in KURALLAR]
        self._kurallar_indeks: dict[str, list[dict]] = {}
        self._istatistikler: dict[str, KuralIstatistik] = {}
        self._istatistikleri_guncelle()

    def _istatistikleri_guncelle(self):
        """Kural istatistiklerini baslatir."""
        self._istatistikler = {}
        for k in self.kurallar:
            kid = k["id"]
            self._istatistikler[kid] = KuralIstatistik(kural_id=kid)

    def kural_ekle(self, kural: dict) -> None:
        """Dinamik olarak yeni bir kural ekler."""
        self.kurallar.append(kural)
        self._istatistikleri_guncelle()
        logger.info("Yeni kural eklendi: %s", kural.get("id", "?"))

    def kural_kaldir(self, kural_id: str) -> bool:
        """ID'ye gore kural kaldirir."""
        once = len(self.kurallar)
        self.kurallar = [k for k in self.kurallar if k.get("id") != kural_id]
        if len(self.kurallar) < once:
            self._istatistikleri_guncelle()
            logger.info("Kural kaldirildi: %s", kural_id)
            return True
        return False

    def _indeks_olustur(self) -> dict[str, list[dict]]:
        """Hesap kodlarini kurallara baglayan indeks olusturur."""
        indeks = defaultdict(list)
        for kural in self.kurallar:
            kodlar = kural.get("kodlar", [])
            tip = kural.get("tip", "")
            for kod in kodlar:
                if tip in ("on_ek_borc", "on_ek_alacak", "bakiye_yok"):
                    indeks[kod].append(kural)
                else:
                    indeks[kod].append(kural)
        return dict(indeks)

    def kontrol_raporu_yaz(self, sonuc: KontrolSonucu, hedef: Path) -> Path:
        """Kontrol sonucunu Excel dosyasi olarak yazar."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Kontrol Raporu"

        kalin = Font(bold=True, size=14)
        ws["A1"] = "MIZAN KONTROL RAPORU"
        ws["A1"].font = kalin
        ws["A2"] = "Firma: " + sonuc.firma_adi
        ws["A3"] = "Donem: " + sonuc.donem
        ws["A4"] = "Dosya: " + sonuc.dosya_adi
        ws["A5"] = f"Satir sayisi: {sonuc.satir_sayisi}"
        ws["A6"] = f"Tarih: {self.yil}"

        basliklar = ["Durum", "Kural", "Hesap kodu", "Hesap adi", "Seviye", "Deger", "Mesaj"]
        for i, b in enumerate(basliklar):
            h = ws.cell(row=8, column=i + 1, value=b)
            h.font = Font(bold=True)

        satir = 9
        yesil = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
        kirmizi = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        sari = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")

        if not sonuc.ihlaller:
            ws.cell(row=satir, column=1, value="OK")
            ws.cell(row=satir, column=1).fill = yesil
            ws.cell(row=satir, column=4, value="Tum kurallar saglandi")
            ws.cell(row=satir, column=4).fill = yesil
            satir += 1
        else:
            for ihlal in sonuc.ihlaller:
                ws.cell(row=satir, column=1, value=ihlal.seviye)
                ws.cell(row=satir, column=2, value=ihlal.kural_id)
                ws.cell(row=satir, column=3, value=ihlal.hesap_kodu)
                ws.cell(row=satir, column=4, value=ihlal.hesap_adi)
                ws.cell(row=satir, column=5, value=ihlal.seviye)
                ws.cell(row=satir, column=6, value=ihlal.deger)
                ws.cell(row=satir, column=7, value=ihlal.mesaj)

                fmt = kirmizi if ihlal.seviye == "HATA" else sari
                for col in [1, 5]:
                    ws.cell(row=satir, column=col).fill = fmt
                ws.cell(row=satir, column=1).alignment = Alignment(horizontal="center")
                ws.cell(row=satir, column=5).alignment = Alignment(horizontal="center")
                satir += 1

        for kolon, g in zip("ABCDEFG", [10, 10, 12, 30, 10, 18, 60]):
            ws.column_dimensions[kolon].width = g

        wb.save(hedef)
        return hedef


_motor = MizanKontrolMotoru()


def mizan_kontrol(dosya_yolu: Path | str) -> KontrolSonucu:
    """Verilen Excel dosyasini kontrol edip sonuc dondurur."""
    yol = Path(dosya_yolu) if isinstance(dosya_yolu, str) else dosya_yolu

    dosya_ok, mesaj = _dosya_yapisi_kontrol(yol)
    if not dosya_ok:
        logger.warning("Dosya kontrolü basarisiz: %s - %s", yol.name, mesaj)
        sonuc = KontrolSonucu(dosya_adi=yol.name)
        sonuc.ihlaller.append(KuralIhlali(
            kural_id="DOSYA", hesap_kodu="-", hesap_adi="-",
            mesaj=mesaj, seviye="HATA",
        ))
        sonuc.hata_sayisi = 1
        return sonuc

    satirlar, firma, donem = [], "", ""
    try:
        satirlar, firma, donem = _dosya_oku(yol)
        logger.info("Dosya yüklendi: %s (%d satır, firma: %s)", yol.name, len(satirlar), firma)
    except Exception as e:
        logger.warning("Dosya okunamadi: %s - %s", yol.name, e)
        sonuc = KontrolSonucu(
            dosya_adi=yol.name, firma_adi=firma, donem=donem,
        )
        sonuc.ihlaller.append(KuralIhlali(
            kural_id="OKU", hesap_kodu="-", hesap_adi="-",
            mesaj=f"Dosya okunamadi: {e}", seviye="HATA",
        ))
        sonuc.hata_sayisi = 1
        return sonuc

    sonuc = KontrolSonucu(
        dosya_adi=yol.name,
        firma_adi=firma,
        donem=donem,
        satir_sayisi=len(satirlar),
    )

    if not satirlar:
        logger.info("Dosyada satir yok: %s", yol.name)
        sonuc.ihlaller.append(KuralIhlali(
            kural_id="VERI", hesap_kodu="-", hesap_adi="-",
            mesaj="Excel dosyasinda urun kaydi bulunamadi",
            seviye="UYARI",
        ))
        sonuc.uyari_sayisi = 1
        return sonuc

    indeks = _motor._indeks_olustur()

    seen = set()
    for satir in satirlar:
        kod = satir["kod"]
        ad = satir["ad"]
        eslesen_kurallar = indeks.get(kod, [])

        for kural in eslesen_kurallar:
            ihlal = _kural_uygula(kural, kod, ad, satir)
            if ihlal is not None:
                key = (kural["id"], kod)
                if key not in seen:
                    seen.add(key)
                    sonuc.ihlaller.append(ihlal)
                    _istatistik_guncelle(kural["id"], ihlal.seviye, kod, ad)

    sonuc.hata_sayisi = sum(1 for i in sonuc.ihlaller if i.seviye == "HATA")
    sonuc.uyari_sayisi = sum(1 for i in sonuc.ihlaller if i.seviye == "UYARI")

    logger.info("Kontrol tamamlandi: %s -> %s (%d hata, %d uyari)",
                yol.name, sonuc.durum, sonuc.hata_sayisi, sonuc.uyari_sayisi)
    return sonuc


def _kural_uygula(kural: dict, kod: str, ad: str, satir: dict) -> Optional[KuralIhlali]:
    """Tek bir kurali uygular. Ihlal varsa KuralIhlali dondurur, yoksa None."""
    tip = kural["tip"]
    kosul = kural.get("kosul", "")
    seviye = kural.get("seviye", "HATA")

    if tip == "ana_hesap":
        kolon = kural["hedef_kolon"]
        deger = satir.get(kolon, 0)
        if deger != 0:
            return KuralIhlali(
                kural_id=kural["id"], hesap_kodu=kod, hesap_adi=ad,
                mesaj=f"{kosul} (mevcut: {deger:,.2f})",
                seviye=seviye, deger=f"{deger:,.2f}",
            )

    elif tip == "borc_limit":
        limit = kural.get("limit", 0)
        kolon = kural.get("kolon", "borc")
        borc = satir.get(kolon, 0)
        if borc > limit:
            return KuralIhlali(
                kural_id=kural["id"], hesap_kodu=kod, hesap_adi=ad,
                mesaj=f"{kosul} ({kolon}: {borc:,.2f}, limit: {limit:,.2f})",
                seviye=seviye, deger=f"{borc:,.2f}",
            )

    elif tip == "on_ek_borc":
        borc = satir["borc"]
        if borc != 0:
            return KuralIhlali(
                kural_id=kural["id"], hesap_kodu=kod, hesap_adi=ad,
                mesaj=f"{kosul} (borc: {borc:,.2f})",
                seviye=seviye, deger=f"{borc:,.2f}",
            )

    elif tip == "on_ek_alacak":
        alacak = satir["alacak"]
        if alacak != 0:
            return KuralIhlali(
                kural_id=kural["id"], hesap_kodu=kod, hesap_adi=ad,
                mesaj=f"{kosul} (alacak: {alacak:,.2f})",
                seviye=seviye, deger=f"{alacak:,.2f}",
            )

    elif tip == "bakiye_yok":
        bb = satir.get("borc_bakiye", 0)
        ab = satir.get("alacak_bakiye", 0)
        if bb != 0 or ab != 0:
            return KuralIhlali(
                kural_id=kural["id"], hesap_kodu=kod, hesap_adi=ad,
                mesaj=f"{kosul} (bb: {bb:,.2f}, ab: {ab:,.2f})",
                seviye=seviye, deger=f"{bb:,.2f}/{ab:,.2f}",
            )

    return None


def _istatistik_guncelle(kural_id: str, seviye: str, kod: str, ad: str) -> None:
    """Kural istatistigini gunceller."""
    ist = _motor._istatistikler.get(kural_id)
    if ist is None:
        ist = KuralIstatistik(kural_id=kural_id)
        _motor._istatistikler[kural_id] = ist
    ist.toplam += 1
    if seviye == "HATA":
        ist.hata += 1
    elif seviye == "UYARI":
        ist.uyari += 1
    ist.hesaplar[kod] = ist.hesaplar.get(kod, 0) + 1


def kural_istatistikleri() -> dict[str, KuralIstatistik]:
    """Tum kural istatistiklerini dondurur."""
    return dict(_motor._istatistikler)


def retry_islem(islem, deneme_sayisi: int = 3, bekleme_saniye: float = 1.0):
    """Bir islemi belirtilen sayida deneme ile yapar.

    Args:
        islem: Calistirilacak fonksiyon
        deneme_sayisi: Deneme sayisi (varsayilan 3)
        bekleme_saniye: Denemeler arasi bekleme suresi (saniye)

    Returns:
        islem() dondurdugu deger

    Raises:
        Son denemedeki hata
    """
    import time
    son_hata = None
    for deneme in range(1, deneme_sayisi + 1):
        try:
            return islem()
        except Exception as e:
            son_hata = e
            if deneme < deneme_sayisi:
                logger.warning("Deneme %d/%d basarisiz: %s", deneme, deneme_sayisi, e)
                time.sleep(bekleme_saniye * deneme)
    logger.error("Tum denemeler basarisiz: %s", son_hata)
    raise son_hata


def kural_istatistik_yaz(hedef: Path | None = None) -> Path:
    """Kural istatistiklerini Excel olarak yazar."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Kural Istatistik"

    kalin = Font(bold=True, size=14)
    ws["A1"] = "KURAL ISTATISTIK"
    ws["A1"].font = kalin

    basliklar = ["Kural ID", "Toplam", "Hata", "Uyari", "En Cok Ihlal Eden Hesap"]
    for i, b in enumerate(basliklar):
        h = ws.cell(row=3, column=i + 1, value=b)
        h.font = Font(bold=True)

    satir = 4
    for kid, ist in sorted(_motor._istatistikler.items()):
        en_cok = max(ist.hesaplar, key=ist.hesaplar.get, default="-")
        ws.cell(row=satir, column=1, value=kid)
        ws.cell(row=satir, column=2, value=ist.toplam)
        ws.cell(row=satir, column=3, value=ist.hata)
        ws.cell(row=satir, column=4, value=ist.uyari)
        ws.cell(row=satir, column=5, value=f"{en_cok} ({ist.hesaplar.get(en_cok, 0)} kez)")
        satir += 1

    for kolon, g in zip("ABCDE", [12, 10, 10, 10, 25]):
        ws.column_dimensions[kolon].width = g

    if hedef:
        wb.save(hedef)
    return hedef or Path("kural_istatistik.xlsx")


def kontrol_raporu_yaz(sonuc: KontrolSonucu, hedef: Path) -> Path:
    """Kontrol sonucunu Excel dosyasi olusturur."""
    return _motor.kontrol_raporu_yaz(sonuc, hedef)


def kontrol_json_yaz(sonuc: KontrolSonucu, hedef: Path) -> Path:
    """Kontrol sonucunu JSON dosyasi olarak yazar."""
    data = {
        "dosya_adi": sonuc.dosya_adi,
        "firma_adi": sonuc.firma_adi,
        "donem": sonuc.donem,
        "satir_sayisi": sonuc.satir_sayisi,
        "durum": sonuc.durum,
        "ozet": sonuc.ozet,
        "hata_sayisi": sonuc.hata_sayisi,
        "uyari_sayisi": sonuc.uyari_sayisi,
        "ihlaller": [
            {
                "kural_id": i.kural_id,
                "hesap_kodu": i.hesap_kodu,
                "hesap_adi": i.hesap_adi,
                "mesaj": i.mesaj,
                "seviye": i.seviye,
                "deger": i.deger,
            }
            for i in sonuc.ihlaller
        ],
    }
    with open(hedef, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return hedef


def kontrol_csv_yaz(sonuc: KontrolSonucu, hedef: Path) -> Path:
    """Kontrol sonucunu CSV dosyasi olarak yazar."""
    with open(hedef, "w", encoding="utf-8-sig", newline="") as f:
        yazici = csv.writer(f)
        yazici.writerow(["Dosya", sonuc.dosya_adi])
        yazici.writerow(["Firma", sonuc.firma_adi])
        yazici.writerow(["Donem", sonuc.donem])
        yazici.writerow(["Satir Sayisi", sonuc.satir_sayisi])
        yazici.writerow(["Durum", sonuc.durum])
        yazici.writerow(["Ozet", sonuc.ozet])
        yazici.writerow([])
        yazici.writerow(["Kural ID", "Hesap Kodu", "Hesap Adi", "Seviye", "Deger", "Mesaj"])
        for i in sonuc.ihlaller:
            yazici.writerow([
                i.kural_id, i.hesap_kodu, i.hesap_adi,
                i.seviye, i.deger, i.mesaj,
            ])
    return hedef


def kontrol_pdf_yaz(sonuc: KontrolSonucu, hedef: Path) -> Path:
    """Kontrol sonucunu PDF dosyasi olarak yazar."""
    from fpdf import FPDF

    class KontrolPDF(FPDF):
        def header(self):
            self.set_font("Helvetica", "B", 14)
            self.cell(0, 10, "MIZAN KONTROL RAPORU", new_x="LMARGIN", new_y="NEXT", align="C")
            self.ln(3)

        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 8)
            self.cell(0, 10, f"Sayfa {self.page_no()}/{{nb}}", align="C")

    pdf = KontrolPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font("Helvetica", "", 10)

    pdf.cell(0, 6, f"Dosya: {sonuc.dosya_adi}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Firma: {sonuc.firma_adi}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Donem: {sonuc.donem}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Satir Sayisi: {sonuc.satir_sayisi}", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)

    if sonuc.durum == "OK":
        pdf.set_text_color(0, 150, 0)
    elif sonuc.durum == "HATA":
        pdf.set_text_color(220, 50, 50)
    else:
        pdf.set_text_color(200, 160, 0)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Durum: {sonuc.durum} ({sonuc.ozet})", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)

    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Kural Ihlalleri:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)

    for i in sonuc.ihlaller:
        pdf.set_text_color(220, 50, 50) if i.seviye == "HATA" else pdf.set_text_color(200, 160, 0)
        pdf.cell(0, 5, f"[{i.kural_id}] {i.hesap_kodu} {i.hesap_adi}: {i.mesaj}", new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(0, 0, 0)
    pdf.output(str(hedef))
    return hedef


def kontrol_html_yaz(sonuc: KontrolSonucu, hedef: Path) -> Path:
    """Kontrol sonucunu HTML dosyasi olarak yazar."""
    durum_renk = {"OK": "#22c55e", "HATA": "#ef4444", "UYARI": "#facc15"}
    renk = durum_renk.get(sonuc.durum, "#9aa5b8")
    ihlaller_html = ""
    for i in sonuc.ihlaller:
        ihl_renk = "#ef4444" if i.seviye == "HATA" else "#facc15"
        ihlaller_html += (
            '<div style="padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.06);'
            f'border-left:3px solid {ihl_renk};padding-left:10px;">'
            f'<strong>[{i.kural_id}]</strong> {i.hesap_kodu} {i.hesap_adi}: {i.mesaj}'
            f' <span style="color:{ihl_renk};font-size:11px;">[{i.seviye}]</span>'
            '</div>'
        )
    html = (
        '<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8">'
        '<title>Mizan Kontrol Raporu</title><style>'
        'body{font-family:"Segoe UI",sans-serif;background:#0f1023;color:#e9ecf5;padding:40px;max-width:800px;margin:auto;}'
        'h1{color:#7c3aed;} .durum{display:inline-block;padding:4px 14px;border-radius:8px;font-weight:800;color:#fff;margin:10px 0;}'
        '.bilgi{background:rgba(255,255,255,0.05);padding:10px 16px;border-radius:8px;margin:6px 0;}'
        '</style></head><body>'
        f'<h1>&#128202; Mizan Kontrol Raporu</h1>'
        f'<span class="durum" style="background:{renk};">{sonuc.durum}</span>'
        f'<div class="bilgi"><strong>Dosya:</strong> {sonuc.dosya_adi}</div>'
        f'<div class="bilgi"><strong>Firma:</strong> {sonuc.firma_adi}</div>'
        f'<div class="bilgi"><strong>D&#246;nem:</strong> {sonuc.donem}</div>'
        f'<div class="bilgi"><strong>Sat&#305;r Say&#305;s&#305;:</strong> {sonuc.satir_sayisi}</div>'
        f'<div class="bilgi"><strong>&#214;z:</strong> {sonuc.ozet}</div>'
        f'<div class="bilgi"><strong>Hata:</strong> {sonuc.hata_sayisi} &nbsp; <strong>Uyar&#305;:</strong> {sonuc.uyari_sayisi}</div>'
        '<h2>Kural İhlalleri</h2>'
        f'{ihlaller_html if ihlaller_html else "<p>İhlal yok.</p>"}'
        '</body></html>'
    )
    with open(hedef, "w", encoding="utf-8") as f:
        f.write(html)
    return hedef


def kontrol_txt_yaz(sonuc: KontrolSonucu, hedef: Path) -> Path:
    """Kontrol sonucunu metin dosyasi olarak yazar."""
    satirlar = [
        "=" * 60,
        "  MIZAN KONTROL RAPORU",
        "=" * 60,
        f"  Dosya:  {sonuc.dosya_adi}",
        f"  Firma:  {sonuc.firma_adi}",
        f"  Donem:  {sonuc.donem}",
        f"  Satir:  {sonuc.satir_sayisi}",
        f"  Durum:  {sonuc.durum} ({sonuc.ozet})",
        f"  Hata:   {sonuc.hata_sayisi}",
        f"  Uyari:  {sonuc.uyari_sayisi}",
        "-" * 60,
        "  Kural Ihlalleri:",
        "-" * 60,
    ]
    for i in sonuc.ihlaller:
        satirlar.append(f"  [{i.kural_id}] {i.hesap_kodu} {i.hesap_adi}: {i.mesaj} [{i.seviye}]")
    if not sonuc.ihlaller:
        satirlar.append("  (Ihlal yok)")
    satirlar.append("=" * 60)
    with open(hedef, "w", encoding="utf-8") as f:
        f.write("\n".join(satirlar) + "\n")
    return hedef


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    for p in sys.argv[1:] or ["raporlar"]:
        yol = Path(p)
        if yol.is_dir():
            for f in sorted(yol.glob("*.xlsx")):
                if "_KONTROL" in f.name:
                    continue
                s = mizan_kontrol(f)
                print(f.name + ": " + s.durum + " - " + s.ozet)
                for i in s.ihlaller:
                    print("   [" + i.seviye + "] " + i.hesap_kodu + " " + i.hesap_adi + ": " + i.mesaj)
        elif yol.is_file():
            s = mizan_kontrol(yol)
            print(yol.name + ": " + s.durum + " - " + s.ozet)
            for i in s.ihlaller:
                print("   [" + i.seviye + "] " + i.hesap_kodu + " " + i.hesap_adi + ": " + i.mesaj)