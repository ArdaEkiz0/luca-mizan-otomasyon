#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# mizan_kontrol - Luca mizan kontrol motoru (ASCII kaynak)

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import openpyxl
from openpyxl.styles import Font, PatternFill

KURALLAR = [
    {"id": "K1", "tip": "ana_hesap", "kodlar": ["100"], "hedef_kolon": "alacak_bakiye",
     "kosul": "100 ana hesap ALACAK bakiyeli olmamali (negatif olmamali)"},
    {"id": "K2", "tip": "borc_limit", "kodlar": ["100"], "limit": 3000000,
     "kosul": "100 ana hesap borc tutari 3.000.000 TL yi gecmemeli"},
    {"id": "K3", "tip": "ana_hesap", "kodlar": ["103"], "hedef_kolon": "borc_bakiye",
     "kosul": "103 ana hesap BORC bakiyeli olmamali"},
    {"id": "K4", "tip": "ana_hesap", "kodlar": ["101"], "hedef_kolon": "alacak_bakiye",
     "kosul": "101 ana hesap ALACAK bakiyeli olmamali"},
    {"id": "K5", "tip": "ana_hesap", "kodlar": ["300"], "hedef_kolon": "borc_bakiye",
     "kosul": "300 ana hesap BORC bakiyeli olmamali"},
    {"id": "K6", "tip": "ana_hesap", "kodlar": ["120"], "hedef_kolon": "alacak_bakiye",
     "kosul": "120 ana hesap ALACAK bakiyeli olmamali"},
    {"id": "K7", "tip": "ana_hesap", "kodlar": ["320"], "hedef_kolon": "borc_bakiye",
     "kosul": "320 ana hesap BORC bakiyeli olmamali"},
    {"id": "K8", "tip": "ana_hesap", "kodlar": ["360"], "hedef_kolon": "borc_bakiye",
     "kosul": "360 ana hesap BORC bakiyeli olmamali"},
    {"id": "K9", "tip": "ana_hesap", "kodlar": ["361"], "hedef_kolon": "borc_bakiye",
     "kosul": "361 ana hesap BORC bakiyeli olmamali"},
    {"id": "K10", "tip": "on_ek_borc", "kodlar": ["600"],
     "kosul": "600 ile baslayan tum hesaplarin BORCU 0 olmali"},
    {"id": "K11", "tip": "on_ek_alacak", "kodlar": ["760", "770", "780"],
     "kosul": "760/770/780 ile baslayan tum hesaplarin ALACAGI 0 olmali"},
    {"id": "K12", "tip": "bakiye_yok", "kodlar": ["191", "391"],
     "kosul": "191 ve 391 hesaplarin bakiyesi olmamali"},
]


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


def _dosya_oku(dosya_yolu: Path):
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
        ilk_ust = ilk.upper().replace("\u0130", "I").replace("\u00d6", "O").replace("\u00dc", "U")
        ilk_ust = ilk_ust.replace("\u00c7", "C").replace("\u015e", "S").replace("\u011e", "G")

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


def mizan_kontrol(dosya_yolu: Path) -> KontrolSonucu:
    satirlar, firma, donem = _dosya_oku(dosya_yolu)
    sonuc = KontrolSonucu(
        dosya_adi=dosya_yolu.name,
        firma_adi=firma,
        donem=donem,
        satir_sayisi=len(satirlar),
    )

    for kural in KURALLAR:
        tip = kural["tip"]
        kodlar = kural.get("kodlar", [])
        for satir in satirlar:
            kod = satir["kod"]
            ad = satir["ad"]

            if tip in ("ana_hesap", "borc_limit", "bakiye_yok"):
                eslesen = any(_kod_esles(kod, h) for h in kodlar)
            else:
                eslesen = any(kod.startswith(h) for h in kodlar)

            if not eslesen:
                continue

            ihlal = _kural_uygula(kural, kod, ad, satir)
            if ihlal is not None:
                sonuc.ihlaller.append(ihlal)

    sonuc.hata_sayisi = sum(1 for i in sonuc.ihlaller if i.seviye == "HATA")
    sonuc.uyari_sayisi = sum(1 for i in sonuc.ihlaller if i.seviye == "UYARI")
    return sonuc


def _kural_uygula(kural: dict, kod: str, ad: str, satir: dict) -> Optional[KuralIhlali]:
    tip = kural["tip"]
    kosul = kural.get("kosul", "")

    if tip == "ana_hesap":
        kolon = kural["hedef_kolon"]
        deger = satir.get(kolon, 0)
        if deger != 0:
            return KuralIhlali(
                kural_id=kural["id"], hesap_kodu=kod, hesap_adi=ad,
                mesaj=f"{kosul} (mevcut: {deger:,.2f})",
                seviye="HATA", deger=f"{deger:,.2f}",
            )

    elif tip == "borc_limit":
        borc = satir["borc"]
        if borc > kural["limit"]:
            return KuralIhlali(
                kural_id=kural["id"], hesap_kodu=kod, hesap_adi=ad,
                mesaj=f"{kosul} (borc: {borc:,.2f})",
                seviye="HATA", deger=f"{borc:,.2f}",
            )

    elif tip == "on_ek_borc":
        borc = satir["borc"]
        if borc != 0:
            return KuralIhlali(
                kural_id=kural["id"], hesap_kodu=kod, hesap_adi=ad,
                mesaj=f"{kosul} (borc: {borc:,.2f})",
                seviye="HATA", deger=f"{borc:,.2f}",
            )

    elif tip == "on_ek_alacak":
        alacak = satir["alacak"]
        if alacak != 0:
            return KuralIhlali(
                kural_id=kural["id"], hesap_kodu=kod, hesap_adi=ad,
                mesaj=f"{kosul} (alacak: {alacak:,.2f})",
                seviye="HATA", deger=f"{alacak:,.2f}",
            )

    elif tip == "bakiye_yok":
        bb = satir["borc_bakiye"]
        ab = satir["alacak_bakiye"]
        if bb != 0 or ab != 0:
            return KuralIhlali(
                kural_id=kural["id"], hesap_kodu=kod, hesap_adi=ad,
                mesaj=f"{kosul} (bb: {bb:,.2f}, ab: {ab:,.2f})",
                seviye="HATA", deger=f"{bb:,.2f}/{ab:,.2f}",
            )

    return None


def kontrol_raporu_yaz(sonuc: KontrolSonucu, hedef: Path) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Kontrol Raporu"

    kalin = Font(bold=True, size=14)
    ws["A1"] = "\u004d\u00b0IZAN KONTROL RAPORU"
    ws["A1"].font = kalin
    ws["A2"] = "Firma: " + sonuc.firma_adi
    ws["A3"] = "Donem: " + sonuc.donem
    ws["A4"] = "Dosya: " + sonuc.dosya_adi

    basliklar = ["Durum", "Kural", "Hesap kodu", "Hesap adi", "Seviye", "Deger", "Mesaj"]
    for i, b in enumerate(basliklar):
        h = ws.cell(row=6, column=i + 1, value=b)
        h.font = Font(bold=True)

    satir = 7
    yesil = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    kirmizi = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    sari = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")

    if not sonuc.ihlaller:
        ws.cell(row=satir, column=1, value="OK").fill = yesil
    else:
        for i in sonuc.ihlaller:
            ws.cell(row=satir, column=1, value=i.seviye)
            ws.cell(row=satir, column=2, value=i.kural_id)
            ws.cell(row=satir, column=3, value=i.hesap_kodu)
            ws.cell(row=satir, column=4, value=i.hesap_adi)
            ws.cell(row=satir, column=5, value=i.seviye)
            ws.cell(row=satir, column=6, value=i.deger)
            ws.cell(row=satir, column=7, value=i.mesaj)
            fmt = kirmizi if i.seviye == "HATA" else sari
            ws.cell(row=satir, column=1).fill = fmt
            ws.cell(row=satir, column=5).fill = fmt
            satir += 1

    for kolon, g in zip("ABCDEFG", [16, 8, 14, 26, 8, 22, 55]):
        ws.column_dimensions[kolon].width = g

    wb.save(hedef)
    return hedef


if __name__ == "__main__":
    import sys

    for p in sys.argv[1:] or ["raporlar"]:
        yol = Path(p)
        if yol.is_dir():
            for f in sorted(yol.glob("*.xlsx")):
                s = mizan_kontrol(f)
                print(f.name + ": " + s.durum + " - " + s.ozet)
        elif yol.is_file():
            s = mizan_kontrol(yol)
            print(yol.name + ": " + s.durum + " - " + s.ozet)
            for i in s.ihlaller:
                print("   [" + i.seviye + "] " + i.hesap_kodu + " " + i.hesap_adi + ": " + i.mesaj)