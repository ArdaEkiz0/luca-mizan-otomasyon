#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Luca Mizan Raporu Otomasyonu - Modern Web Arayüzü (Backend)
============================================================

Aynı LucaOtomasyonCore motorunu kullanan, tarayıcıda açılan modern ve
animasyonlu bir arayüz sunar. Frontend (index.html / style.css / app.js)
bu sunucudan servis edilir ve /api/durum uç noktasını polling ederek
ilerleme/logları canlı gösterir.

Güvenlik: Kimlik bilgileri yalnızca bu bilgisayardaki ".env" dosyasında
saklanır; sunucu yalnızca 127.0.0.1 adresine bağlanır (dış ağa açık değildir).
"""

from __future__ import annotations

import datetime
import json
import mimetypes
import os
import queue
import subprocess
import sys
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dotenv import load_dotenv, set_key

from luca_otomasyon_core import LucaOtomasyonCore, SINIF_ETIKETLERI

try:
    from veri_tabani import (
        kontrol_sonuc_kaydet, kontrol_sonuclari_getir, istatistik_getir,
        ayar_getir, ayar_kaydet, kural_istatistik_guncelle,
        rapor_gecmis_kaydet, rapor_gecmis_getir, grafik_verisi_getir,
    )
except Exception:
    pass

# --- Yol yönetimi (PyInstaller uyumlu) ---
# Statik arayüz dosyaları (html/css/js/svg/ico) .exe içinde paketlenir;
# _MEIPASS geçici klasöründe açılır. Kullanıcı verisi (.env, raporlar, log)
# ise exe'nin YANINDAKİ çalışma dizininde kalıcı olarak tutulur.
def _kaynak_kok() -> Path:
    """Paketli statik dosyaların bulunduğu kök (PyInstaller _MEIPASS veya kaynak)."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def _veri_kok() -> Path:
    """Kullanıcı verilerinin kalıcı tutulacağı dizin (exe'nin yanı)."""
    return Path(os.getcwd()).resolve()


KAYNAK_KOK = _kaynak_kok()
VERI_KOK = _veri_kok()

BASE_DIR = VERI_KOK
WEB_DIR = KAYNAK_KOK / "web_ui"
ENV_PATH = VERI_KOK / ".env"
ENV_EXAMPLE_PATH = KAYNAK_KOK / ".env.example"
LOG_DOSYASI = VERI_KOK / "otomasyon_log.txt"
RAPORLAR_DIR = VERI_KOK / "raporlar"

SUNUCU_HOST = "127.0.0.1"
SUNUCU_PORT = 8765

YILLAR = [str(y) for y in range(2026, 2010, -1)]
SINIFLAR = [
    ("", "Tumu"),
    ("1", "1.Sinif"),
    ("2", "2.Sinif"),
    ("3", "Isletme Defteri"),
    ("4", "Serbest Meslek Defteri"),
    ("5", "Basit Usul"),
]


def _dosyaya_log_yaz(mesaj: str) -> None:
    try:
        zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_DOSYASI, "a", encoding="utf-8") as f:
            f.write(f"[{zaman}] {mesaj}\n")
    except Exception:
        pass


def _env_yukle() -> dict:
    if not ENV_PATH.exists() and ENV_EXAMPLE_PATH.exists():
        ENV_PATH.write_text(ENV_EXAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    load_dotenv(ENV_PATH, override=True)
    return {
        "uye_no": os.getenv("LUCA_UYE_NO", ""),
        "kullanici_adi": os.getenv("LUCA_KULLANICI_ADI", ""),
        "parola": os.getenv("LUCA_PAROLA", ""),
        "yil": os.getenv("MIZAN_YIL", "2026"),
        "sinif": os.getenv("MIZAN_SINIF", "1"),
        "cikti_klasoru": os.getenv("CIKTI_KLASORU", "raporlar"),
    }


def _env_kaydet(uye_no: str, kullanici_adi: str, parola: str, yil: str, sinif: str) -> None:
    if not ENV_PATH.exists():
        ENV_PATH.write_text("", encoding="utf-8")
    set_key(str(ENV_PATH), "LUCA_UYE_NO", uye_no)
    set_key(str(ENV_PATH), "LUCA_KULLANICI_ADI", kullanici_adi)
    set_key(str(ENV_PATH), "LUCA_PAROLA", parola)
    set_key(str(ENV_PATH), "MIZAN_YIL", yil)
    set_key(str(ENV_PATH), "MIZAN_SINIF", sinif)


def _boyut_formatla(boyut: int) -> str:
    if boyut > 1024 * 1024:
        return f"{boyut / (1024 * 1024):.1f} MB"
    if boyut > 1024:
        return f"{boyut / 1024:.1f} KB"
    return f"{boyut} B"


class UygulamaDurumu:
    """Arka plan iş parçacığı ile frontend arasında paylaşılan durum."""

    def __init__(self) -> None:
        self.kilit = threading.Lock()
        self.loglar: list[dict] = []
        self.log_sayaci = 0
        self.calisiyor = False
        self.durum_metni = "Hazir"
        self.durum_seviye = "bekleme"  # bekleme | calisiyor | basarili | hata
        self.core: LucaOtomasyonCore | None = None
        self.musteriler: list[dict] = []
        self.raporlar: list[dict] = []
        self.secili_kisa_ad: str | None = None
        self._rapor_dosyalari: list[Path] = []
        self.toplu_sonuc: list[dict] = []

    def log_ekle(self, mesaj: str) -> None:
        seviye = "bilgi"
        if mesaj.startswith("HATA") or "HATA:" in mesaj[:20]:
            seviye = "hata"
        elif mesaj.startswith("BAŞARILI") or mesaj.startswith("BASARILI") or "OK " in mesaj[:4]:
            seviye = "basarili"
        elif mesaj.startswith("UYARI"):
            seviye = "uyari"
        with self.kilit:
            self.log_sayaci += 1
            self.loglar.append({"id": self.log_sayaci, "seviye": seviye, "mesaj": mesaj})
        _dosyaya_log_yaz(mesaj)

    def rapor_ekle(self, dosya_yolu: Path | str) -> None:
        dosya = Path(dosya_yolu)
        if not dosya.exists():
            return
        with self.kilit:
            self._rapor_dosyalari.append(dosya)
            self.raporlar = [{
                "dosya": d.name,
                "boyut": _boyut_formatla(d.stat().st_size),
                "tarih": datetime.datetime.fromtimestamp(d.stat().st_mtime).strftime("%d.%m.%Y %H:%M"),
                "yol": str(d),
            } for d in self._rapor_dosyalari]

    def durum_baslat(self, metin: str) -> bool:
        with self.kilit:
            if self.calisiyor:
                return False
            self.calisiyor = True
            self.durum_metni = metin
            self.durum_seviye = "calisiyor"
            return True

    def durum_bitir(self, metin: str, seviye: str = "basarili") -> None:
        with self.kilit:
            self.calisiyor = False
            self.durum_metni = metin
            self.durum_seviye = seviye


DURUM = UygulamaDurumu()


class Isci:
    """Playwright (senkron) motorunu yalnızca TEK bir iş parçacığında çalıştırır.

    Playwright sync API aynı thread'de kullanılmalıdır; HTTP handler
    thread'lerinden doğrudan çağırmak çökmelere yol açar. Bu yüzden tüm
    komutlar buradaki kuyruğa konur ve tek işçi tarafından işlenir.
    """

    def __init__(self) -> None:
        self.kuyruk: "queue.Queue" = queue.Queue()
        self.thread = threading.Thread(target=self._dongu, daemon=True, name="OtomasyonWorker")
        self.thread.start()

    def _dongu(self) -> None:
        while True:
            is_ = self.kuyruk.get()
            try:
                is_()
            except Exception:
                DURUM.log_ekle("IS KUYRUGU HATASI:\n" + traceback.format_exc())
                DURUM.durum_bitir("Hata olustu.", "hata")

    def gonder(self, is_) -> None:
        self.kuyruk.put(is_)


ISCI = Isci()


def _sinif_kod_bul(sinif_girdi: str) -> str:
    """Kullanıcının seçtiği sınıfı Luca'nın beklediği koda çevirir.

    Frontend'ten '1.Sinif' (etiket) veya '1' (kod) gelebilir. Luca'nın
    #SINIF select'i KOD bekler ('1','2',...), etiket beklenmez.
    """
    girdi = str(sinif_girdi or "").strip()
    for kod, etiket in SINIFLAR:
        if kod == girdi or etiket == girdi:
            return kod
    return girdi


class ApiHandler(BaseHTTPRequestHandler):
    def _json(self, veri: dict, durum: int = 200) -> None:
        govde = json.dumps(veri, ensure_ascii=False).encode("utf-8")
        self.send_response(durum)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(govde)

    def _giris_kontrol(self) -> None:
        if not self.path.startswith("/api/"):
            return
        if self.path.startswith("/api/ayarlar"):
            return

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        yol = self.path.split("?", 1)[0]

        if yol == "/api/durum":
            self._api_durum()
            return
        if yol == "/api/ayarlar":
            self._json(_env_yukle())
            return
        if yol == "/api/kontrol/dashboard":
            self._kontrol_dashboard()
            return
        if yol == "/api/docs":
            self._api_docs()
            return

        # Statik dosyalar
        if yol in ("/", "/index.html"):
            dosya = WEB_DIR / "index.html"
        elif yol == "/style.css":
            dosya = WEB_DIR / "style.css"
        elif yol == "/app.js":
            dosya = WEB_DIR / "app.js"
        elif yol == "/favicon.svg":
            dosya = WEB_DIR / "favicon.svg"
        elif yol == "/logo.svg":
            dosya = WEB_DIR / "logo.svg"
        else:
            self._json({"hata": "Bulunamadi"}, 404)
            return

        if not dosya.exists():
            self._json({"hata": "Dosya bulunamadi"}, 404)
            return

        govde = dosya.read_bytes()
        tip = mimetypes.guess_type(dosya.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", tip + ("; charset=utf-8" if "text" in tip else ""))
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(govde)

    def do_POST(self) -> None:
        yol = self.path.split("?", 1)[0]
        uzunluk = int(self.headers.get("Content-Length") or 0)
        veri = {}
        if uzunluk:
            try:
                veri = json.loads(self.rfile.read(uzunluk).decode("utf-8"))
            except Exception:
                veri = {}

        if yol == "/api/musterileri_getir":
            self._musterileri_getir(veri)
        elif yol == "/api/rapor_olustur":
            self._rapor_olustur(veri)
        elif yol == "/api/toplu_rapor":
            self._toplu_rapor(veri)
        elif yol == "/api/rapor_gecmis":
            self._rapor_gemis(veri)
        elif yol == "/api/rapor_karistirma":
            self._rapor_karistirma(veri)
        elif yol == "/api/tarayici_kapat":
            self._tarayiciyi_kapat()
        elif yol == "/api/ayar_kaydet":
            self._ayar_kaydet(veri)
        elif yol == "/api/dosya_ac":
            self._dosya_ac(veri)
        elif yol == "/api/klasor_ac":
            self._klasor_ac()
        elif yol == "/api/liste_temizle":
            with DURUM.kilit:
                DURUM.raporlar = []
                DURUM._rapor_dosyalari = []
            self._json({"ok": True})
        elif yol == "/api/kontrol":
            self._kontrol_raporlari()
        elif yol == "/api/kontrol/istatistik":
            self._kontrol_istatistik()
        elif yol == "/api/kontrol/export/json":
            self._kontrol_export_json(veri)
        elif yol == "/api/kontrol/export/csv":
            self._kontrol_export_csv(veri)
        elif yol == "/api/kontrol/export/pdf":
            self._kontrol_export_pdf(veri)
        elif yol == "/api/kontrol/export/html":
            self._kontrol_export_html(veri)
        elif yol == "/api/kontrol/export/txt":
            self._kontrol_export_txt(veri)
        elif yol == "/api/guncelleme":
            self._guncelleme_kontrol()
        elif yol == "/api/guncelleme/guncelle":
            self._guncelleme_yap()
        elif yol == "/api/kontrol/dashboard":
            self._kontrol_dashboard()
        elif yol == "/api/kontrol/arama":
            self._kontrol_arama(veri)
        elif yol == "/api/ayar_dil":
            self._ayar_dil(veri)
        else:
            self._json({"hata": "Bilinmeyen istek"}, 404)

    def _api_durum(self) -> None:
        with DURUM.kilit:
            yeni_loglar = DURUM.loglar
            DURUM.loglar = []
            cevap = {
                "loglar": yeni_loglar,
                "durum_metni": DURUM.durum_metni,
                "durum_seviye": DURUM.durum_seviye,
                "calisiyor": DURUM.calisiyor,
                "musteriler": DURUM.musteriler,
                "raporlar": DURUM.raporlar,
                "secili_kisa_ad": DURUM.secili_kisa_ad,
            }
        self._json(cevap)

    def _musterileri_getir(self, veri: dict) -> None:
        if not DURUM.durum_baslat("Giris yapiliyor ve musteri listesi getiriliyor..."):
            self._json({"ok": False, "hata": "Bir islem zaten suruyor."})
            return

        uye_no = str(veri.get("uye_no", "")).strip()
        kullanici_adi = str(veri.get("kullanici_adi", "")).strip()
        parola = str(veri.get("parola", ""))
        yil = str(veri.get("yil", "2026"))
        sinif = _sinif_kod_bul(veri.get("sinif", "1"))

        if not uye_no or not kullanici_adi or not parola:
            DURUM.durum_bitir("Eksik giris bilgisi.", "hata")
            self._json({"ok": False, "hata": "Uye No, Kullanici Adi ve Parola zorunludur."})
            return

        # Önce eski oturumu kapat
        eski_core = DURUM.core
        with DURUM.kilit:
            DURUM.core = None
            DURUM.musteriler = []
            DURUM.secili_kisa_ad = None
        if eski_core is not None:
            try:
                eski_core.kapat()
            except Exception:
                pass

        def is_():
            core = LucaOtomasyonCore(uye_no, kullanici_adi, parola, cikti_klasoru="raporlar")
            try:
                musteriler = core.baslat_ve_filtrele(yil, sinif, log=DURUM.log_ekle)
                with DURUM.kilit:
                    DURUM.core = core
                    DURUM.musteriler = musteriler
                if not musteriler:
                    DURUM.log_ekle("UYARI: Filtreyle eslesen musteri bulunamadi.")
                DURUM.durum_bitir(f"{len(musteriler)} musteri listelendi.")
            except Exception as e:
                DURUM.log_ekle(f"HATA: {e}")
                DURUM.log_ekle(traceback.format_exc())
                DURUM.durum_bitir("Hata olustu.", "hata")
                try:
                    core.kapat()
                except Exception:
                    pass

        ISCI.gonder(is_)
        self._json({"ok": True})

    def _rapor_olustur(self, veri: dict) -> None:
        if not DURUM.durum_baslat("Mizan raporu olusturuluyor..."):
            self._json({"ok": False, "hata": "Bir islem zaten suruyor."})
            return

        kisa_ad = str(veri.get("kisa_ad", "")).strip()
        baslangic = str(veri.get("baslangic", "")).strip()
        bitis = str(veri.get("bitis", "")).strip()
        if not kisa_ad:
            DURUM.durum_bitir("Musteri secilmedi.", "hata")
            self._json({"ok": False, "hata": "Musteri secilmedi."})
            return

        with DURUM.kilit:
            core = DURUM.core
        if core is None:
            DURUM.durum_bitir("Once musteri listesini getirin.", "hata")
            self._json({"ok": False, "hata": "Once musteri listesini getirin."})
            return

        DURUM.durum_baslat(f"'{kisa_ad}' icin Mizan raporu olusturuluyor...")

        def is_():
            try:
                core.musteri_sec(kisa_ad, log=DURUM.log_ekle)
                dosya = core.mizan_raporu_olustur(
                    kisa_ad, log=DURUM.log_ekle,
                    baslangic=baslangic, bitis=bitis,
                )
                core.musteri_kartina_don(log=DURUM.log_ekle)
                if dosya:
                    DURUM.log_ekle(f"BAŞARILI: Rapor kaydedildi -> {dosya}")
                    DURUM.rapor_ekle(dosya)
                    DURUM.durum_bitir("Rapor olusturuldu.")
                else:
                    DURUM.durum_bitir("Rapor kuyruga alindi (Rapor Takip'ten indirin).")
            except Exception as e:
                DURUM.log_ekle(f"HATA: {e}")
                DURUM.log_ekle(traceback.format_exc())
                DURUM.durum_bitir("Hata olustu.", "hata")

        ISCI.gonder(is_)
        self._json({"ok": True})

    def _toplu_rapor(self, veri: dict) -> None:
        if not DURUM.durum_baslat("Toplu rapor olusturuluyor..."):
            self._json({"ok": False, "hata": "Bir islem zaten suruyor."})
            return

        baslangic = str(veri.get("baslangic", "")).strip()
        bitis = str(veri.get("bitis", "")).strip()

        with DURUM.kilit:
            core = DURUM.core
            musteriler = list(DURUM.musteriler)
        if core is None or not musteriler:
            DURUM.durum_bitir("Once musteri listesini getirin.", "hata")
            self._json({"ok": False, "hata": "Once musteri listesini getirin."})
            return

        DURUM.durum_baslat(f"{len(musteriler)} musteri icin toplu rapor olusturuluyor...")

        def is_():
            try:
                sonuclar = core.toplu_mizan_raporu(
                    musteriler,
                    log=DURUM.log_ekle,
                    baslangic=baslangic,
                    bitis=bitis,
                )
                basarili = sum(1 for s in sonuclar if s["durum"] in ("basarili", "kuyruga alindi"))
                basarisiz = sum(1 for s in sonuclar if s["durum"] == "hatali")
                DURUM.log_ekle(f"TOPLU RAPOR SONUCU: {basarili} basarili, {basarisiz} hatali")
                tarih = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for s in sonuclar:
                    kisa = s.get("kisa_ad", "")
                    hata = s.get("hata", "")
                    dosya = s.get("dosya_yolu", "")
                    if s["durum"] == "hatali":
                        DURUM.log_ekle(f"  X {kisa}: {hata}")
                        rapor_gecmis_kaydet(
                            kisa_ad=kisa, rapor_tipi="Toplu",
                            rapor_dosyasi=hata, durum="HATA", tarih=tarih,
                        )
                    else:
                        DURUM.log_ekle(f"  OK {kisa}: {dosya or 'kuyruga alindi'}")
                        if s.get("dosya_yolu"):
                            DURUM.rapor_ekle(s["dosya_yolu"])
                        rapor_gecmis_kaydet(
                            kisa_ad=kisa, rapor_tipi="Toplu",
                            rapor_dosyasi=dosya or "", durum="OK", tarih=tarih,
                        )
                DURUM.durum_bitir(f"Toplu rapor tamamlandi ({basarili} basarili, {basarisiz} hatali)")
                DURUM.toplu_sonuc = sonuclar
            except Exception as e:
                DURUM.log_ekle(f"HATA: {e}")
                DURUM.log_ekle(traceback.format_exc())
                DURUM.durum_bitir("Hata olustu.", "hata")

        ISCI.gonder(is_)
        self._json({"ok": True})

    def _rapor_gemis(self, veri: dict) -> None:
        try:
            from urllib.parse import parse_qs
            if self.path and "?" in self.path:
                qs = parse_qs(self.path.split("?", 1)[1])
                for key, val in qs.items():
                    if key not in veri or not veri[key]:
                        veri[key] = val[0]
            limit = int(veri.get("limit", 50))
            kisi_no = str(veri.get("kisi_no", ""))
            tarih_baslangic = str(veri.get("tarih_baslangic", ""))
            tarih_bitis = str(veri.get("tarih_bitis", ""))
            durum = str(veri.get("durum", ""))
            kayitlar = rapor_gecmis_getir(
                limit=limit, kisi_no=kisi_no or None,
                tarih_baslangic=tarih_baslangic or None,
                tarih_bitis=tarih_bitis or None,
                durum=durum or None,
            )
            self._json({"ok": True, "kayitlar": kayitlar})
        except Exception as e:
            self._json({"ok": False, "hata": str(e)})

    def _rapor_karistirma(self, veri: dict) -> None:
        try:
            with DURUM.kilit:
                sonuclar = list(DURUM.toplu_sonuc)
            if not sonuclar:
                self._json({"ok": False, "hata": "Henuz toplu rapor yapilmedi."})
                return
            karistirma = {
                "toplam": len(sonuclar),
                "basarili": sum(1 for s in sonuclar if s["durum"] in ("basarili", "kuyruga alindi")),
                "hatali": sum(1 for s in sonuclar if s["durum"] == "hatali"),
                "sure_saniye": sum(s.get("sure_saniye", 0) for s in sonuclar),
                "ortalama_sure": 0,
                "kisiler": [],
            }
            if karistirma["toplam"] > 0:
                karistirma["ortalama_sure"] = round(
                    karistirma["sure_saniye"] / karistirma["toplam"], 2
                )
            for s in sonuclar:
                karistirma["kisiler"].append({
                    "kisa_ad": s.get("kisa_ad", ""),
                    "urun_adi": s.get("urun_adi", ""),
                    "urun_kodu": s.get("urun_kodu", ""),
                    "musteri_kodu": s.get("musteri_kodu", ""),
                    "urun_hafi": s.get("urun_hafi", ""),
                    "rapor_tipi": s.get("rapor_tipi", ""),
                    "sorgu_sayisi": s.get("sorgu_sayisi", 0),
                    "sure_saniye": s.get("sure_saniye", 0),
                    "durum": s.get("durum", ""),
                    "hata": s.get("hata", ""),
                })
            self._json({"ok": True, "karistirma": karistirma})
        except Exception as e:
            self._json({"ok": False, "hata": str(e)})

    def _tarayiciyi_kapat(self) -> None:
        with DURUM.kilit:
            core = DURUM.core
            DURUM.core = None
            DURUM.musteriler = []
            DURUM.secili_kisa_ad = None

        if core is not None:
            def is_():
                try:
                    core.kapat()
                except Exception:
                    pass
                DURUM.log_ekle("Tarayici kapatildi.")
            ISCI.gonder(is_)
        DURUM.durum_bitir("Hazir")
        self._json({"ok": True})

    def _ayar_kaydet(self, veri: dict) -> None:
        sinif_kodu = _sinif_kod_bul(veri.get("sinif", "1.Sinif"))
        _env_kaydet(
            str(veri.get("uye_no", "")).strip(),
            str(veri.get("kullanici_adi", "")).strip(),
            str(veri.get("parola", "")),
            str(veri.get("yil", "2026")),
            sinif_kodu,
        )
        DURUM.log_ekle("Bilgiler .env dosyasina kaydedildi.")
        self._json({"ok": True})

    def _dosya_ac(self, veri: dict) -> None:
        yol = str(veri.get("yol", ""))
        dosya = Path(yol)
        if not dosya.exists():
            self._json({"ok": False, "hata": "Dosya bulunamadi."})
            return
        try:
            os.startfile(str(dosya))
            DURUM.log_ekle(f"Dosya aciliyor: {dosya.name}")
            self._json({"ok": True})
        except Exception as e:
            try:
                subprocess.Popen(["explorer", str(dosya)])
                self._json({"ok": True})
            except Exception:
                self._json({"ok": False, "hata": str(e)})

    def _klasor_ac(self) -> None:
        klasor = BASE_DIR / "raporlar"
        klasor.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(klasor.resolve()))
        except Exception:
            try:
                subprocess.Popen(["explorer", str(klasor.resolve())])
            except Exception as e:
                self._json({"ok": False, "hata": str(e)})
                return
        self._json({"ok": True})

    def _kontrol_raporlari(self) -> None:
        """İndirilen tüm mizanları kontrol eder, istatistiklerle sonucu JSON verir."""
        try:
            from mizan_kontrol import mizan_kontrol, kontrol_raporu_yaz, MizanKontrolMotoru, kural_istatistikleri
        except Exception as e:
            self._json({"ok": False, "hata": f"mizan_kontrol yüklenemedi: {e}"})
            return

        with DURUM.kilit:
            dosyalar = [Path(p) for p in DURUM._rapor_dosyalari if "_KONTROL" not in Path(p).name]
            if not dosyalar:
                klasor = BASE_DIR / "raporlar"
                if klasor.exists():
                    dosyalar = sorted(
                        f for f in klasor.glob("*.xlsx")
                        if "_KONTROL" not in f.name
                    )

        sonuclar = []
        toplam_hata = 0
        toplam_uyari = 0
        toplam_ok = 0

        for f in dosyalar:
            try:
                s = mizan_kontrol(f)

                if s.durum == "OK":
                    toplam_ok += 1
                elif s.durum == "HATA":
                    toplam_hata += 1
                else:
                    toplam_uyari += 1

                kontrol_dosya = f.with_name(f.stem + "_KONTROL.xlsx")
                try:
                    kontrol_raporu_yaz(s, kontrol_dosya)
                except Exception:
                    kontrol_dosya = None

                sonuclar.append({
                    "dosya": f.name,
                    "firma": s.firma_adi,
                    "donem": s.donem,
                    "satir_sayisi": s.satir_sayisi,
                    "durum": s.durum,
                    "ozet": s.ozet,
                    "hata_sayisi": s.hata_sayisi,
                    "uyari_sayisi": s.uyari_sayisi,
                    "kontrol_dosyasi": str(kontrol_dosya) if kontrol_dosya else None,
                    "ihlaller": [
                        {"kural": i.kural_id, "hesap": i.hesap_kodu,
                         "ad": i.hesap_adi, "seviye": i.seviye,
                         "mesaj": i.mesaj}
                        for i in s.ihlaller
                    ],
                })
            except Exception as e:
                sonuclar.append({
                    "dosya": f.name, "durum": "HATA",
                    "ozet": f"Okunamadi: {e}", "ihlaller": [],
                    "hata_sayisi": 1, "uyari_sayisi": 0,
                })
                toplam_hata += 1

        istatistik = kural_istatistikleri()
        istatistik_sonuc = {}
        for kid, ist in istatistik.items():
            istatistik_sonuc[kid] = {
                "toplam": ist.toplam, "hata": ist.hata, "uyari": ist.uyari,
            }

        self._json({
            "ok": True,
            "sonuclar": sonuclar,
            "istatistik": {
                "toplam": len(sonuclar),
                "ok": toplam_ok,
                "hata": toplam_hata,
                "uyari": toplam_uyari,
            },
            "kural_istatistik": istatistik_sonuc,
        })

        try:
            for s in sonuclar:
                kontrol_sonuc_kaydet(
                    dosya_adi=s["dosya"],
                    firma_adi=s.get("firma", ""),
                    donem=s.get("donem", ""),
                    satir_sayisi=s.get("satir_sayisi", 0),
                    durum=s["durum"],
                    hata_sayisi=s.get("hata_sayisi", 0),
                    uyari_sayisi=s.get("uyari_sayisi", 0),
                    ihlaller=s.get("ihlaller", []),
                )
                for i in s.get("ihlaller", []):
                    kural_istatistik_guncelle(i.get("kural", ""), i.get("seviye", ""))
        except Exception:
            pass

    def _kontrol_istatistik(self) -> None:
        """Kural istatistiklerini JSON olarak verir."""
        try:
            from mizan_kontrol import kural_istatistikleri
        except Exception as e:
            self._json({"ok": False, "hata": str(e)})
            return

        istatistik = kural_istatistikleri()
        sonuc = {}
        for kid, ist in istatistik.items():
            sonuc[kid] = {
                "kural_id": kid,
                "toplam": ist.toplam,
                "hata": ist.hata,
                "uyari": ist.uyari,
                "hesaplar": ist.hesaplar,
            }
        self._json({"ok": True, "istatistik": sonuc})

    def _kontrol_export_json(self, veri: dict) -> None:
        """Kontrol sonuclarini JSON olarak indir."""
        try:
            from mizan_kontrol import mizan_kontrol, kontrol_json_yaz
        except Exception as e:
            self._json({"ok": False, "hata": str(e)})
            return
        try:
            dosya_adi = str(veri.get("dosya", ""))
            if not dosya_adi:
                self._json({"ok": False, "hata": "Dosya belirtilmedi"})
                return
            rapor_klasor = BASE_DIR / "raporlar"
            dosya = None
            for f in sorted(rapor_klasor.glob("*.xlsx")):
                if f.name == dosya_adi and "_KONTROL" not in f.name:
                    dosya = f
                    break
            if dosya is None:
                self._json({"ok": False, "hata": "Dosya bulunamadi"})
                return
            s = mizan_kontrol(dosya)
            hedef = dosya.with_suffix(".json")
            kontrol_json_yaz(s, hedef)
            govde = hedef.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Disposition", f'attachment; filename="{hedef.name}"')
            self.send_header("Content-Length", str(len(govde)))
            self.end_headers()
            self.wfile.write(govde)
        except Exception as e:
            self._json({"ok": False, "hata": str(e)})

    def _kontrol_export_csv(self, veri: dict) -> None:
        """Kontrol sonuclarini CSV olarak indir."""
        try:
            from mizan_kontrol import mizan_kontrol, kontrol_csv_yaz
        except Exception as e:
            self._json({"ok": False, "hata": str(e)})
            return
        try:
            dosya_adi = str(veri.get("dosya", ""))
            if not dosya_adi:
                self._json({"ok": False, "hata": "Dosya belirtilmedi"})
                return
            rapor_klasor = BASE_DIR / "raporlar"
            dosya = None
            for f in sorted(rapor_klasor.glob("*.xlsx")):
                if f.name == dosya_adi and "_KONTROL" not in f.name:
                    dosya = f
                    break
            if dosya is None:
                self._json({"ok": False, "hata": "Dosya bulunamadi"})
                return
            s = mizan_kontrol(dosya)
            hedef = dosya.with_suffix(".csv")
            kontrol_csv_yaz(s, hedef)
            govde = hedef.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{hedef.name}"')
            self.send_header("Content-Length", str(len(govde)))
            self.end_headers()
            self.wfile.write(govde)
        except Exception as e:
            self._json({"ok": False, "hata": str(e)})

    def _kontrol_export_pdf(self, veri: dict) -> None:
        """Kontrol sonuclarini PDF olarak indir."""
        try:
            from mizan_kontrol import mizan_kontrol, kontrol_pdf_yaz
        except Exception as e:
            self._json({"ok": False, "hata": str(e)})
            return
        try:
            dosya_adi = str(veri.get("dosya", ""))
            if not dosya_adi:
                self._json({"ok": False, "hata": "Dosya belirtilmedi"})
                return
            rapor_klasor = BASE_DIR / "raporlar"
            dosya = None
            for f in sorted(rapor_klasor.glob("*.xlsx")):
                if f.name == dosya_adi and "_KONTROL" not in f.name:
                    dosya = f
                    break
            if dosya is None:
                self._json({"ok": False, "hata": "Dosya bulunamadi"})
                return
            s = mizan_kontrol(dosya)
            hedef = dosya.with_suffix("_KONTROL.pdf")
            kontrol_pdf_yaz(s, hedef)
            govde = hedef.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f'attachment; filename="{hedef.name}"')
            self.send_header("Content-Length", str(len(govde)))
            self.end_headers()
            self.wfile.write(govde)
        except Exception as e:
            self._json({"ok": False, "hata": str(e)})

    def _kontrol_export_html(self, veri: dict) -> None:
        try:
            from mizan_kontrol import mizan_kontrol, kontrol_html_yaz
        except Exception as e:
            self._json({"ok": False, "hata": str(e)})
            return
        try:
            dosya_adi = str(veri.get("dosya", ""))
            if not dosya_adi:
                self._json({"ok": False, "hata": "Dosya belirtilmedi"})
                return
            rapor_klasor = BASE_DIR / "raporlar"
            dosya = None
            for f in sorted(rapor_klasor.glob("*.xlsx")):
                if f.name == dosya_adi and "_KONTROL" not in f.name:
                    dosya = f
                    break
            if dosya is None:
                self._json({"ok": False, "hata": "Dosya bulunamadi"})
                return
            s = mizan_kontrol(dosya)
            hedef = dosya.with_suffix(".html")
            kontrol_html_yaz(s, hedef)
            govde = hedef.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{hedef.name}"')
            self.send_header("Content-Length", str(len(govde)))
            self.end_headers()
            self.wfile.write(govde)
        except Exception as e:
            self._json({"ok": False, "hata": str(e)})

    def _kontrol_export_txt(self, veri: dict) -> None:
        try:
            from mizan_kontrol import mizan_kontrol, kontrol_txt_yaz
        except Exception as e:
            self._json({"ok": False, "hata": str(e)})
            return
        try:
            dosya_adi = str(veri.get("dosya", ""))
            if not dosya_adi:
                self._json({"ok": False, "hata": "Dosya belirtilmedi"})
                return
            rapor_klasor = BASE_DIR / "raporlar"
            dosya = None
            for f in sorted(rapor_klasor.glob("*.xlsx")):
                if f.name == dosya_adi and "_KONTROL" not in f.name:
                    dosya = f
                    break
            if dosya is None:
                self._json({"ok": False, "hata": "Dosya bulunamadi"})
                return
            s = mizan_kontrol(dosya)
            hedef = dosya.with_suffix("_KONTROL.txt")
            kontrol_txt_yaz(s, hedef)
            govde = hedef.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{hedef.name}"')
            self.send_header("Content-Length", str(len(govde)))
            self.end_headers()
            self.wfile.write(govde)
        except Exception as e:
            self._json({"ok": False, "hata": str(e)})

    def _api_docs(self) -> None:
        endpointler = [
            {"yol": "GET  /api/durum", "aciklama": "Canlı durum, loglar, müşteri listesi"},
            {"yol": "GET  /api/ayarlar", "aciklama": "Ortam ayarları"},
            {"yol": "GET  /api/kontrol/dashboard", "aciklama": "Dashboard verisi (istatistik, grafik, tablo)"},
            {"yol": "GET  /api/docs", "aciklama": "Bu API dokümantasyonu"},
            {"yol": "POST /api/musterileri_getir", "aciklama": "Müşteri listesi getir"},
            {"yol": "POST /api/rapor_olustur", "aciklama": "Tek müşteri raporu"},
            {"yol": "POST /api/toplu_rapor", "aciklama": "Toplu rapor"},
            {"yol": "POST /api/rapor_gecmis", "aciklama": "Rapor geçmişi"},
            {"yol": "POST /api/rapor_karistirma", "aciklama": "Toplu rapor karşılaştırma"},
            {"yol": "POST /api/tarayici_kapat", "aciklama": "Tarayıcıyı kapat"},
            {"yol": "POST /api/ayar_kaydet", "aciklama": "Ayarları kaydet"},
            {"yol": "POST /api/dosya_ac", "aciklama": "Dosya aç"},
            {"yol": "POST /api/klasor_ac", "aciklama": "Klasör aç"},
            {"yol": "POST /api/liste_temizle", "aciklama": "Rapor listesini temizle"},
            {"yol": "POST /api/kontrol", "aciklama": "Mizan kontrolü"},
            {"yol": "POST /api/kontrol/export/{json,csv,pdf,html,txt}", "aciklama": "Rapor export"},
            {"yol": "GET  /api/ayar_dil", "aciklama": "Dil ayarı"},
            {"yol": "POST /api/guncelleme", "aciklama": "Sürüm kontrolü"},
            {"yol": "POST /api/guncelleme/guncelle", "aciklama": "Güncelle"},
        ]
        try:
            from guncelleme_kontrolu import simdiki_surum
            surum = simdiki_surum()
        except Exception:
            surum = "0.1.1"
        self._json({"ok": True, "endpoints": endpointler, "surum": surum})

    def _guncelleme_kontrol(self) -> None:
        try:
            from guncelleme_kontrolu import guncellememi_kontrol_et, simdiki_surum
            sonuc = guncellememi_kontrol_et()
            self._json({"ok": True, "guncelleme": sonuc, "surum": simdiki_surum()})
        except Exception as e:
            self._json({"ok": False, "hata": str(e)})

    def _guncelleme_yap(self) -> None:
        try:
            from guncelleme_kontrolu import guncelle
            sonuc = guncelle()
            self._json(sonuc)
        except Exception as e:
            self._json({"ok": False, "hata": str(e)})

    def _kontrol_dashboard(self) -> None:
        try:
            from veri_tabani import istatistik_getir, kontrol_sonuclari_getir, grafik_verisi_getir
            from mizan_kontrol import mizan_kontrol as _mk
            import guncelleme_kontrolu as gc
            ist = istatistik_getir()
            sonuclar = kontrol_sonuclari_getir(limit=50)
            kural_ist = ist.get("kurallar", {})
            en_cok_hata_kural = sorted(kural_ist.items(), key=lambda x: x[1].get("hata", 0), reverse=True)[:5]
            son_kontrol = None
            if sonuclar:
                sk = sonuclar[0]
                son_kontrol = {
                    "dosya_adi": sk.get("dosya_adi", ""),
                    "durum": sk.get("durum", ""),
                    "kontrol_tarihi": sk.get("kontrol_tarihi", ""),
                }
            grafik = grafik_verisi_getir(7)
            self._json({"ok": True, "istatistik": ist, "sonuclar": sonuclar,
                        "surum": gc.simdiki_surum(), "guncelleme": gc.guncellememi_kontrol_et(),
                        "kural_ist": en_cok_hata_kural, "son_kontrol": son_kontrol,
                        "grafik": grafik})
        except Exception as e:
            self._json({"ok": False, "hata": str(e)})

    def _kontrol_arama(self, veri: dict) -> None:
        try:
            from veri_tabani import kontrol_sonuclari_getir
            firma = str(veri.get("firma", ""))
            durum = str(veri.get("durum", ""))
            if not firma and not durum:
                self._json({"ok": True, "sonuclar": []})
                return
            sonuclar = kontrol_sonuclari_getir(firma=firma or None, durum=durum or None or None)
            self._json({"ok": True, "sonuclar": sonuclar})
        except Exception as e:
            self._json({"ok": False, "hata": str(e)})

    def _ayar_dil(self, veri: dict) -> None:
        try:
            dil = str(veri.get("dil", "tr"))
            ayar_kaydet("dil", dil)
            self._json({"ok": True, "dil": dil})
        except Exception as e:
            self._json({"ok": False, "hata": str(e)})

    def log_message(self, format, *args) -> None:
        pass


def _temiz_kapat(sunucu=None) -> None:
    """Uygulama kapanırken tarayıcı/core'u temiz kapat."""
    with DURUM.kilit:
        core = DURUM.core
        DURUM.core = None
    if core is not None:
        try:
            core.kapat()
        except Exception:
            pass
    if sunucu is not None:
        try:
            sunucu.server_close()
        except Exception:
            pass


def sunucu_baslat(port: int | None = None) -> "tuple[str, ThreadingHTTPServer]":
    """HTTP sunucusunu arka plan iş parçacığında başlatır.

    Pencere (masaüstü uygulama) modu için kullanılır: bu fonksiyon adresi
    ve sunucu nesnesini döndürür; arayüz tarafı ana thread'de kalır.
    """
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    kullanilacak_port = port or SUNUCU_PORT
    sunucu = ThreadingHTTPServer((SUNUCU_HOST, kullanilacak_port), ApiHandler)
    threading.Thread(target=sunucu.serve_forever, daemon=True).start()
    adres = f"http://{SUNUCU_HOST}:{kullanilacak_port}"
    return adres, sunucu


def main() -> None:
    _dosyaya_log_yaz("=" * 20 + " Uygulama baslatildi (web arayüz) " + "=" * 20)
    WEB_DIR.mkdir(parents=True, exist_ok=True)

    try:
        sunucu = ThreadingHTTPServer((SUNUCU_HOST, SUNUCU_PORT), ApiHandler)
    except OSError as e:
        # Port meşgul — dışarıdan bir örnek zaten çalışıyor olabilir.
        print(f"[HATA] {SUNUCU_HOST}:{SUNUCU_PORT} adresine baglanilamiyor: {e}")
        print("Sunucu zaten calisiyor olabilir. Tarayicidan adrese ulasmayi deneyin:")
        print(f"  http://{SUNUCU_HOST}:{SUNUCU_PORT}")
        return

    adres = f"http://{SUNUCU_HOST}:{SUNUCU_PORT}"
    print(f"Luca Mizan Otomasyonu calisiyor: {adres}")
    print("Tarayici otomatik aciliyor... (acilmazsa adresi elle girin)")

    try:
        webbrowser.open(adres)
    except Exception:
        pass

    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _temiz_kapat(sunucu)


if __name__ == "__main__":
    main()