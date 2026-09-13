#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Luca Mizan Raporu Otomasyonu - Masaüstü Arayüz
================================================

luca_otomasyon_core.py içindeki motoru kullanan, CustomTkinter tabanlı
basit bir masaüstü uygulaması. Tüm Playwright işlemleri arayüzü
kilitlememesi için ayrı bir arka plan iş parçacığında (thread) çalışır;
ilerleme mesajları ve sonuçlar bir kuyruk (queue) üzerinden ana pencereye
aktarılır.

Kimlik bilgileriniz yalnızca bu bilgisayardaki ".env" dosyasında saklanır.
"""

from __future__ import annotations

import datetime
import importlib
import os
import queue
import subprocess
import sys
import threading
import traceback
from pathlib import Path

import customtkinter as ctk
from dotenv import load_dotenv, set_key
from tkinter import ttk, messagebox

from luca_otomasyon_core import LucaOtomasyonCore, SINIF_ETIKETLERI

try:
    from veri_tabani import (
        kontrol_sonuc_kaydet, kontrol_sonuclari_getir, istatistik_getir,
        ayar_getir, ayar_kaydet,
    )
except Exception:
    kontrol_sonuc_kaydet = None
    kontrol_sonuclari_getir = None
    istatistik_getir = None
    ayar_getir = None
    ayar_kaydet = None

try:
    import guncelleme_kontrolu as gc
except Exception:
    gc = None

try:
    from hata_onerileri import hata_onusu_ara, ihlaller_ozeti_ihlaller
except Exception:
    hata_onusu_ara = None
    ihlaller_ozeti_ihlaller = None

ENV_PATH = Path(__file__).parent / ".env"
ENV_EXAMPLE_PATH = Path(__file__).parent / ".env.example"

LOG_DOSYASI = Path(__file__).parent / "otomasyon_log.txt"


def _dosyaya_log_yaz(mesaj: str) -> None:
    try:
        zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_DOSYASI, "a", encoding="utf-8") as f:
            f.write(f"[{zaman}] {mesaj}\n")
    except Exception:
        pass


def _beklenmedik_hata_yakala(exc_type, exc_value, exc_tb) -> None:
    ayrinti = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    _dosyaya_log_yaz("BEKLENMEDIK HATA (uygulama kapaniyor olabilir):\n" + ayrinti)
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _beklenmedik_hata_yakala


def _thread_hata_yakala(args) -> None:
    ayrinti = "".join(
        traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
    )
    _dosyaya_log_yaz(f"BEKLENMEDIK THREAD HATASI ({args.thread.name}):\n" + ayrinti)


threading.excepthook = _thread_hata_yakala

_islem_hata_kodlari: dict[str, str] = {
    "BAGLANTI": "Luca sunucusina baglanamadi",
    "FRAME": "Sayfa frame bulunamadi",
    "ROPOR": "Rapor olusturulamadi",
    "KONTROL": "Kontrol islemi basarisiz",
    "DOSYA": "Dosya hatasi",
}

# Tema ve renk paleti
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

YILLAR = [str(y) for y in range(2026, 2010, -1)]
SINIFLAR = [
    ("", "Tumu"),
    ("1", "1.Sinif"),
    ("2", "2.Sinif"),
    ("3", "Isletme Defteri"),
    ("4", "Serbest Meslek Defteri"),
    ("5", "Basit Usul"),
]

# Renk sabitleri
RENKLER = {
    "baslik": "#1a8cff",
    "baslik_yazi": "#ffffff",
    "panel_arka": "#2b2b2b",
    "panel_baslik": "#3d3d3d",
    "buton_baslat": "#28a745",
    "buton_baslat_hover": "#218838",
    "buton_rapor": "#17a2b8",
    "buton_rapor_hover": "#138496",
    "buton_toplu": "#6f42c1",
    "buton_toplu_hover": "#5a32a3",
    "buton_kapat": "#dc3545",
    "buton_kapat_hover": "#c82333",
    "durum_bekleme": "#ffc107",
    "durum_calisiyor": "#17a2b8",
    "durum_basarili": "#28a745",
    "durum_hata": "#dc3545",
    "log_arka": "#1e1e1e",
    "log_yazi": "#d4d4d4",
}


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


class LucaGUI(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        _dosyaya_log_yaz("=" * 20 + " Uygulama baslatildi " + "=" * 20)

        self.title("Luca Mizan Raporu Otomasyonu")
        self.geometry("1050x750")
        self.minsize(900, 650)
        self.configure(fg_color="#1a1a2e")

        self.olay_kuyrugu: "queue.Queue[tuple]" = queue.Queue()
        self.core: LucaOtomasyonCore | None = None
        self.secili_kisa_ad: str | None = None
        self.calisiyor = False
        self._dashboard_pencere: ctk.CTkToplevel | None = None

        self._is_kuyrugu: "queue.Queue" = queue.Queue()
        threading.Thread(target=self._is_parcasi_dongusu, daemon=True, name="OtomasyonWorker").start()

        ayar = _env_yukle()
        self._arayuzu_olustur(ayar)
        self.after(120, self._kuyrugu_dinle)
        self.after(5000, self._guncelleme_kontrol)
        self.protocol("WM_DELETE_WINDOW", self._kapatirken)

    def _is_parcasi_dongusu(self) -> None:
        while True:
            is_ = self._is_kuyrugu.get()
            try:
                is_()
            except Exception:
                _dosyaya_log_yaz("IS KUYRUGU HATASI:\n" + traceback.format_exc())

    def _arayuzu_olustur(self, ayar: dict) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        # --- Baslik ---
        baslik_frame = ctk.CTkFrame(self, fg_color=RENKLER["baslik"], corner_radius=0, height=50)
        baslik_frame.grid(row=0, column=0, sticky="ew")
        baslik_frame.grid_columnconfigure(0, weight=1)

        baslik = ctk.CTkLabel(
            baslik_frame,
            text="Luca Mizan Raporu Otomasyonu",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=RENKLER["baslik_yazi"],
        )
        baslik.grid(row=0, column=0, padx=20, pady=12, sticky="w")

        surum = ctk.CTkLabel(
            baslik_frame,
            text="v2.0",
            font=ctk.CTkFont(size=12),
            text_color="#a0c4ff",
        )
        surum.grid(row=0, column=1, padx=20, pady=12, sticky="e")

        self.guncelle_btn = ctk.CTkButton(
            baslik_frame, text="🔄 Güncelle", width=100, height=28,
            font=ctk.CTkFont(size=11),
            fg_color="#28a745", hover_color="#218838",
            command=self._guncelle_kontrol,
        )
        self.guncelle_btn.grid(row=0, column=2, padx=0, pady=12, sticky="e")

        self.guncelle_durum = ctk.CTkLabel(
            baslik_frame, text="",
            font=ctk.CTkFont(size=10),
            text_color="#888888",
        )
        self.guncelle_durum.grid(row=0, column=3, padx=(0, 10), pady=12, sticky="e")

        self.dashboard_btn = ctk.CTkButton(
            baslik_frame, text="📊 Dashboard", width=110, height=28,
            font=ctk.CTkFont(size=11),
            fg_color="#6f42c1", hover_color="#5a32a3",
            command=self._dashboard_ac,
        )
        self.dashboard_btn.grid(row=0, column=4, padx=0, pady=12, sticky="e")

        # --- Giris bilgileri ---
        giris_frame = ctk.CTkFrame(self, fg_color=RENKLER["panel_arka"], corner_radius=10)
        giris_frame.grid(row=1, column=0, padx=20, pady=(10, 5), sticky="ew")
        for c in range(7):
            giris_frame.grid_columnconfigure(c, weight=1)

        giris_baslik = ctk.CTkLabel(
            giris_frame,
            text="Giris Bilgileri",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=RENKLER["baslik"],
        )
        giris_baslik.grid(row=0, column=0, columnspan=7, padx=15, pady=(10, 5), sticky="w")

        ctk.CTkLabel(giris_frame, text="Uye No:", text_color="#cccccc").grid(
            row=1, column=0, padx=(15, 5), pady=5, sticky="w"
        )
        self.uye_no_var = ctk.StringVar(value=ayar["uye_no"])
        ctk.CTkEntry(
            giris_frame, textvariable=self.uye_no_var, width=120,
            fg_color="#3d3d3d", border_color="#555555"
        ).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ctk.CTkLabel(giris_frame, text="Kullanici Adi:", text_color="#cccccc").grid(
            row=1, column=2, padx=(15, 5), pady=5, sticky="w"
        )
        self.kullanici_var = ctk.StringVar(value=ayar["kullanici_adi"])
        ctk.CTkEntry(
            giris_frame, textvariable=self.kullanici_var, width=160,
            fg_color="#3d3d3d", border_color="#555555"
        ).grid(row=1, column=3, padx=5, pady=5, sticky="w")

        ctk.CTkLabel(giris_frame, text="Parola:", text_color="#cccccc").grid(
            row=1, column=4, padx=(15, 5), pady=5, sticky="w"
        )
        self.parola_var = ctk.StringVar(value=ayar["parola"])
        self.parola_entry = ctk.CTkEntry(
            giris_frame, textvariable=self.parola_var, width=140, show="*",
            fg_color="#3d3d3d", border_color="#555555"
        )
        self.parola_entry.grid(row=1, column=5, padx=5, pady=5, sticky="w")

        self.goster_btn = ctk.CTkButton(
            giris_frame, text="Goster", width=60,
            fg_color="#555555", hover_color="#666666",
            command=self._parola_goster_gizle,
        )
        self.goster_btn.grid(row=1, column=6, padx=(5, 15), pady=5, sticky="w")

        self.kaydet_btn = ctk.CTkButton(
            giris_frame, text="Bilgileri Kaydet",
            fg_color="#28a745", hover_color="#218838",
            command=self._bilgileri_kaydet,
        )
        self.kaydet_btn.grid(row=2, column=0, columnspan=2, padx=15, pady=(0, 10), sticky="w")

        # --- Filtre + musteri listesi ---
        filtre_frame = ctk.CTkFrame(self, fg_color=RENKLER["panel_arka"], corner_radius=10)
        filtre_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        for c in range(6):
            filtre_frame.grid_columnconfigure(c, weight=1)

        filtre_baslik = ctk.CTkLabel(
            filtre_frame,
            text="Filtre ve Musteri Secimi",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=RENKLER["baslik"],
        )
        filtre_baslik.grid(row=0, column=0, columnspan=6, padx=15, pady=(10, 5), sticky="w")

        ctk.CTkLabel(filtre_frame, text="Yil:", text_color="#cccccc").grid(
            row=1, column=0, padx=(15, 5), pady=5, sticky="w"
        )
        self.yil_var = ctk.StringVar(value=ayar["yil"] if ayar["yil"] in YILLAR else YILLAR[0])
        ctk.CTkOptionMenu(
            filtre_frame, values=YILLAR, variable=self.yil_var, width=100,
            fg_color="#3d3d3d", button_color="#555555",
        ).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ctk.CTkLabel(filtre_frame, text="Sinif:", text_color="#cccccc").grid(
            row=1, column=2, padx=(15, 5), pady=5, sticky="w"
        )
        self.sinif_etiket_var = ctk.StringVar(
            value=next((e for k, e in SINIFLAR if k == ayar["sinif"]), "1.Sinif")
        )
        ctk.CTkOptionMenu(
            filtre_frame, values=[e for _, e in SINIFLAR], variable=self.sinif_etiket_var, width=180,
            fg_color="#3d3d3d", button_color="#555555",
        ).grid(row=1, column=3, padx=5, pady=5, sticky="w")

        self.getir_btn = ctk.CTkButton(
            filtre_frame, text="Musterileri Getir",
            fg_color=RENKLER["buton_baslat"], hover_color=RENKLER["buton_baslat_hover"],
            command=self._musterileri_getir,
        )
        self.getir_btn.grid(row=1, column=4, padx=15, pady=5, sticky="w")

        # --- Tarih araligi (opsiyonel) ---
        tarih_satiri = ctk.CTkFrame(filtre_frame, fg_color="transparent")
        tarih_satiri.grid(row=3, column=0, columnspan=6, padx=15, pady=(5, 5), sticky="ew")

        ctk.CTkLabel(tarih_satiri, text="Tarih Araligi (bos = tum yil):", text_color="#cccccc").pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkLabel(tarih_satiri, text="Baslangic (8 rakam):", text_color="#999999").pack(side="left", padx=(0, 4))
        self.baslangic_entry = ctk.CTkEntry(
            tarih_satiri, width=110, placeholder_text="01012026",
            fg_color="#2b2b2b", border_color="#555555",
        )
        self.baslangic_entry.bind("<KeyRelease>", self._tarih_otomatik_format)
        self.baslangic_entry.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(tarih_satiri, text="Bitis (8 rakam):", text_color="#999999").pack(side="left", padx=(0, 4))
        self.bitis_entry = ctk.CTkEntry(
            tarih_satiri, width=110, placeholder_text="31122026",
            fg_color="#2b2b2b", border_color="#555555",
        )
        self.bitis_entry.bind("<KeyRelease>", self._tarih_otomatik_format)
        self.bitis_entry.pack(side="left")

        # Musteri tablosu
        tablo_cercevesi = ctk.CTkFrame(filtre_frame, fg_color="transparent")
        tablo_cercevesi.grid(row=2, column=0, columnspan=6, padx=15, pady=(5, 15), sticky="nsew")
        filtre_frame.grid_rowconfigure(2, weight=1)

        stil = ttk.Style()
        stil.theme_use("default")
        stil.configure("Treeview",
                       background="#2b2b2b",
                       foreground="#ffffff",
                       fieldbackground="#2b2b2b",
                       rowheight=28,
                       font=("Segoe UI", 10))
        stil.configure("Treeview.Heading",
                       background="#3d3d3d",
                       foreground="#ffffff",
                       font=("Segoe UI", 10, "bold"))
        stil.map("Treeview", background=[("selected", "#1a8cff")])

        kolonlar = ("kisa_ad", "uzun_ad", "vergi_dairesi", "vergi_no")
        self.tablo = ttk.Treeview(
            tablo_cercevesi, columns=kolonlar, show="headings", height=8, selectmode="extended"
        )
        self.tablo.heading("kisa_ad", text="Kisa Ad")
        self.tablo.heading("uzun_ad", text="Uzun Ad")
        self.tablo.heading("vergi_dairesi", text="Vergi Dairesi")
        self.tablo.heading("vergi_no", text="Vergi No")
        self.tablo.column("kisa_ad", width=120)
        self.tablo.column("uzun_ad", width=340)
        self.tablo.column("vergi_dairesi", width=180)
        self.tablo.column("vergi_no", width=110)
        self.tablo.pack(side="left", fill="both", expand=True)
        self.tablo.bind("<<TreeviewSelect>>", self._tablo_secim_degisti)

        kaydirma = ttk.Scrollbar(tablo_cercevesi, orient="vertical", command=self.tablo.yview)
        self.tablo.configure(yscrollcommand=kaydirma.set)
        kaydirma.pack(side="right", fill="y")

        # --- Aksiyon butonlari ---
        aksiyon_frame = ctk.CTkFrame(self, fg_color=RENKLER["panel_arka"], corner_radius=10)
        aksiyon_frame.grid(row=3, column=0, padx=20, pady=5, sticky="ew")
        aksiyon_frame.grid_columnconfigure(0, weight=1)

        buton_satiri = ctk.CTkFrame(aksiyon_frame, fg_color="transparent")
        buton_satiri.grid(row=0, column=0, sticky="w", padx=15, pady=(10, 4))

        self.rapor_btn = ctk.CTkButton(
            buton_satiri, text="Mizan Raporu Olustur", state="disabled",
            fg_color=RENKLER["buton_rapor"], hover_color=RENKLER["buton_rapor_hover"],
            command=self._rapor_olustur,
        )
        self.rapor_btn.pack(side="left", padx=(0, 8), pady=2)

        self.toplu_rapor_btn = ctk.CTkButton(
            buton_satiri, text="Tum Musteriler Icin Rapor", state="disabled",
            fg_color=RENKLER["buton_toplu"], hover_color=RENKLER["buton_toplu_hover"],
            command=self._toplu_rapor_olustur,
        )
        self.toplu_rapor_btn.pack(side="left", padx=(0, 8), pady=2)

        self.kapat_btn = ctk.CTkButton(
            buton_satiri, text="Tarayiciyi Kapat", state="disabled",
            fg_color=RENKLER["buton_kapat"], hover_color=RENKLER["buton_kapat_hover"],
            command=self._tarayiciyi_kapat,
        )
        self.kapat_btn.pack(side="left", pady=2)

        durum_satiri = ctk.CTkFrame(aksiyon_frame, fg_color="transparent")
        durum_satiri.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 10))
        durum_satiri.grid_columnconfigure(0, weight=1)

        self.durum_var = ctk.StringVar(value="Hazir")
        self.durum_label = ctk.CTkLabel(
            durum_satiri, textvariable=self.durum_var, anchor="w", justify="left",
            text_color=RENKLER["durum_bekleme"],
            font=ctk.CTkFont(size=12),
        )
        self.durum_label.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.ilerleme = ctk.CTkProgressBar(durum_satiri, mode="indeterminate", width=220)
        self.ilerleme.grid(row=0, column=1, sticky="e")

        # --- Indirilen Raporlar ---
        rapor_frame = ctk.CTkFrame(self, fg_color=RENKLER["panel_arka"], corner_radius=10)
        rapor_frame.grid(row=4, column=0, padx=20, pady=(5, 5), sticky="ew")

        rapor_baslik_frame = ctk.CTkFrame(rapor_frame, fg_color="transparent")
        rapor_baslik_frame.pack(fill="x", padx=15, pady=(10, 5))

        rapor_baslik = ctk.CTkLabel(
            rapor_baslik_frame,
            text="Indirilen Raporlar",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=RENKLER["baslik"],
        )
        rapor_baslik.pack(side="left")

        self.rapor_sayisi_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            rapor_baslik_frame,
            textvariable=self.rapor_sayisi_var,
            font=ctk.CTkFont(size=11),
            text_color="#888888",
        ).pack(side="left", padx=(10, 0))

        butonlar_frame = ctk.CTkFrame(rapor_frame, fg_color="transparent")
        butonlar_frame.pack(fill="x", padx=15, pady=(0, 10))

        self.ac_btn = ctk.CTkButton(
            butonlar_frame, text="Raporu Ac", state="disabled", width=100,
            fg_color="#28a745", hover_color="#218838",
            command=self._secili_raporu_ac,
        )
        self.ac_btn.pack(side="left", padx=(0, 8))

        self.klasor_btn = ctk.CTkButton(
            butonlar_frame, text="Klasoru Ac", state="disabled", width=100,
            fg_color="#6c757d", hover_color="#5a6268",
            command=self._rapor_klasorunu_ac,
        )
        self.klasor_btn.pack(side="left", padx=(0, 8))

        self.temizle_btn = ctk.CTkButton(
            butonlar_frame, text="Listeyi Temizle", width=110,
            fg_color="#555555", hover_color="#666666",
            command=self._rapor_listesini_temizle,
        )
        self.temizle_btn.pack(side="left")

        # Rapor tablosu
        rapor_tablo_frame = ctk.CTkFrame(rapor_frame, fg_color="transparent")
        rapor_tablo_frame.pack(fill="x", padx=15, pady=(0, 10))

        stil2 = ttk.Style()
        stil2.configure("Rapor.Treeview",
                       background="#1e1e1e",
                       foreground="#4fc3f7",
                       fieldbackground="#1e1e1e",
                       rowheight=24,
                       font=("Consolas", 10))
        stil2.configure("Rapor.Treeview.Heading",
                       background="#3d3d3d",
                       foreground="#ffffff",
                       font=("Segoe UI", 9, "bold"))
        stil2.map("Rapor.Treeview", background=[("selected", "#1a8cff")])

        rapor_kolonlar = ("dosya", "boyut", "tarih")
        self.rapor_tablo = ttk.Treeview(
            rapor_tablo_frame, columns=rapor_kolonlar, show="headings",
            height=4, selectmode="browse", style="Rapor.Treeview",
        )
        self.rapor_tablo.heading("dosya", text="Dosya Adi")
        self.rapor_tablo.heading("boyut", text="Boyut")
        self.rapor_tablo.heading("tarih", text="Tarih")
        self.rapor_tablo.column("dosya", width=350)
        self.rapor_tablo.column("boyut", width=80)
        self.rapor_tablo.column("tarih", width=140)
        self.rapor_tablo.pack(side="left", fill="x", expand=True)
        self.rapor_tablo.bind("<Double-1>", lambda e: self._secili_raporu_ac())

        rapor_kaydirma = ttk.Scrollbar(rapor_tablo_frame, orient="vertical", command=self.rapor_tablo.yview)
        self.rapor_tablo.configure(yscrollcommand=rapor_kaydirma.set)
        rapor_kaydirma.pack(side="right", fill="y")

        self.indirilen_raporlar: list[dict] = []

        # --- Mizan Kontrol ---
        kontrol_frame = ctk.CTkFrame(self, fg_color="#1a0f0f", corner_radius=10)
        kontrol_frame.grid(row=5, column=0, padx=20, y=(5, 5), sticky="nsew")
        self.grid_rowconfigure(5, weight=1)

        kontrol_aciklama = ctk.CTkLabel(
            kontrol_frame,
            text="İki mizan yükleyin — hangi hatada hangisi gösteriliyor ↓",
            font=ctk.CTkFont(size=10, italic=True),
            text_color="#888888",
        )
        kontrol_aciklama.pack(fill="x", padx=15, pady=(8, 0))

        kontrol_baslik_frame = ctk.CTkFrame(kontrol_frame, fg_color="transparent")
        kontrol_baslik_frame.pack(fill="x", padx=15, pady=(10, 5))

        ctk.CTkLabel(
            kontrol_baslik_frame, text="🔴 Mizan Kontrolü",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#ef4444",
        ).pack(side="left")

        self.kontrol_butonlar = ctk.CTkFrame(kontrol_frame, fg_color="transparent")
        self.kontrol_butonlar.pack(fill="x", padx=15, pady=(0, 5))

        self.kontrol_btn = ctk.CTkButton(
            self.kontrol_butonlar, text="🔍 Raporlari Kontrol Et", width=200,
            fg_color="#dc2626", hover_color="#b91c1c",
            command=self._kontrol_raporlari, state="disabled",
        )
        self.kontrol_btn.pack(side="left", padx=(0, 8))

        self.toplu_kontrol_btn = ctk.CTkButton(
            self.kontrol_butonlar, text="📦 Tum Raporlari Kontrol Et", width=220,
            fg_color="#7c3aed", hover_color="#6d28d9",
            command=self._toplu_kontrol_raporlari, state="disabled",
        )
        self.toplu_kontrol_btn.pack(side="left", padx=(0, 8))

        # Istatistik
        ist_frame = ctk.CTkFrame(kontrol_frame, fg_color="#0f0f0f", corner_radius=8)
        ist_frame.pack(fill="x", padx=15, pady=(0, 5))

        self.ist_baslık = ctk.CTkLabel(ist_frame, text="📊 SONUÇ",
                                        font=ctk.CTkFont(size=10, weight="bold"),
                                        text_color="#888888")
        self.ist_baslık.pack(padx=10, pady=(6, 0), anchor="w")

        ist_bar = ctk.CTkFrame(ist_frame, fg_color="transparent")
        ist_bar.pack(fill="x", padx=10, pady=(0, 6))

        self.ist_toplam = ctk.CTkLabel(ist_bar, text="TOPLAM: 0",
                                        font=ctk.CTkFont(size=13, weight="bold"),
                                        text_color="#ffffff")
        self.ist_toplam.pack(side="left", padx=10, pady=4)
        self.ist_ok = ctk.CTkLabel(ist_bar, text="✅ OK: 0",
                                    font=ctk.CTkFont(size=13, weight="bold"),
                                    text_color="#22c55e")
        self.ist_ok.pack(side="left", padx=10)
        self.ist_hata = ctk.CTkLabel(ist_bar, text="❌ HATA: 0",
                                       font=ctk.CTkFont(size=13, weight="bold"),
                                       text_color="#ef4444")
        self.ist_hata.pack(side="left", padx=10)
        self.ist_uyari = ctk.CTkLabel(ist_bar, text="⚠️ UYARI: 0",
                                       font=ctk.CTkFont(size=13, weight="bold"),
                                       text_color="#facc15")
        self.ist_uyari.pack(side="left", padx=10)

        # Filtre
        filtre_bar = ctk.CTkFrame(kontrol_frame, fg_color="transparent")
        filtre_bar.pack(fill="x", padx=15, pady=(0, 5))

        ctk.CTkLabel(filtre_bar, text="🔎 Filtre:", text_color="#888888",
                      font=ctk.CTkFont(size=10)).pack(side="left")
        self.kontrol_filtre = ctk.StringVar(value="tum")
        for txt, val in [("Tümü", "tum"), ("✅ OK", "OK"), ("❌ HATA", "HATA"), ("⚠️ UYARI", "UYARI")]:
            btn = ctk.CTkButton(
                filtre_bar, text=txt, width=80, height=26,
                fg_color="#2a2a2a" if val != "tum" else "#dc2626",
                text_color="#ffffff" if val != "tum" else "#cccccc",
                hover_color="#3a3a3a",
                command=lambda v=val: self._kontrol_filtrele(v),
            )
            btn.pack(side="left", padx=2)

        ctk.CTkLabel(filtre_bar, text="Firma:", text_color="#888888", font=ctk.CTkFont(size=10)).pack(side="left", padx=(12, 4))
        self.kontrol_arama = ctk.CTkEntry(filtre_bar, width=150, height=24, placeholder_text="Firma ara...")
        self.kontrol_arama.bind("<KeyRelease>", lambda e: self._kontrol_filtrele(self.kontrol_filtre.get()))
        self.kontrol_arama.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(filtre_bar, text="Tarix:", text_color="#888888", font=ctk.CTkFont(size=10)).pack(side="left")
        self.kontrol_tarix_entry = ctk.CTkEntry(filtre_bar, width=130, height=24, placeholder_text="GGGG (yil)")
        self.kontrol_tarix_entry.bind("<KeyRelease>", lambda e: self._kontrol_filtrele(self.kontrol_filtre.get()))
        self.kontrol_tarix_entry.pack(side="left", padx=(4, 8))

        # Export butonlari
        export_bar = ctk.CTkFrame(kontrol_frame, fg_color="transparent")
        export_bar.pack(fill="x", padx=15, pady=(0, 5))

        ctk.CTkButton(export_bar, text="📄 JSON İndir", width=120, height=26,
                       fg_color="#16a34a", hover_color="#15803d",
                       command=self._kontrol_export_json).pack(side="left", padx=(0, 4))
        ctk.CTkButton(export_bar, text="📊 CSV İndir", width=120, height=26,
                       fg_color="#0891b2", hover_color="#0e7490",
                       command=self._kontrol_export_csv).pack(side="left", padx=(0, 4))
        ctk.CTkButton(export_bar, text="📑 PDF İndir", width=120, height=26,
                       fg_color="#dc2626", hover_color="#b91c1c",
                       command=self._kontrol_export_pdf).pack(side="left", padx=(0, 4))

        # Sonuclar tablosu
        kontrol_tablo_frame = ctk.CTkFrame(kontrol_frame, fg_color="transparent")
        kontrol_tablo_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        stil3 = ttk.Style()
        stil3.configure("Kontrol.Treeview",
                        background="#0f0f0f", foreground="#d4d4d4",
                        fieldbackground="#0f0f0f", rowheight=28,
                        font=("Segoe UI", 10))
        stil3.configure("Kontrol.Treeview.Heading",
                        background="#1f1f1f", foreground="#ef4444",
                        font=("Segoe UI", 10, "bold"))
        stil3.map("Kontrol.Treeview", background=[("selected", "#1a8cff")])

        kontrol_kolonlar = ("dosya", "durum", "ozet", "hata", "uyari", "firma")
        self.kontrol_tablo = ttk.Treeview(
            kontrol_tablo_frame, columns=kontrol_kolonlar, show="headings",
            height=6, selectmode="browse", style="Kontrol.Treeview",
        )
        self.kontrol_tablo.heading("durum", text="Durum")
        self.kontrol_tablo.heading("ozet", text="Özet")
        self.kontrol_tablo.heading("hata", text="Hata")
        self.kontrol_tablo.heading("uyari", text="Uyari")
        self.kontrol_tablo.column("durum", width=70)
        self.kontrol_tablo.column("ozet", width=220)
        self.kontrol_tablo.column("hata", width=40)
        self.kontrol_tablo.column("uyari", width=40)
        self.kontrol_tablo.column("firma", width=130)
        self.kontrol_tablo.pack(side="left", fill="both", expand=True)
        self.kontrol_tablo.bind("<Double-1>", lambda e: self._kontrol_detay_goster())

        kaydirma3 = ttk.Scrollbar(kontrol_tablo_frame, orient="vertical", command=self.kontrol_tablo.yview)
        self.kontrol_tablo.configure(yscrollcommand=kaydirma3.set)
        kaydirma3.pack(side="right", fill="y")

        self.kontrol_tablo.tag_configure("ok", foreground="#22c55e", background="#0a1a0a")
        self.kontrol_tablo.tag_configure("hata", foreground="#ef4444", background="#1a0a0a")
        self.kontrol_tablo.tag_configure("uyari", foreground="#facc15", background="#1a1a0a")

        self.kontrol_sonuclari: list[dict] = []
        self.kontrol_filtreli = "tum"

        # --- Log alani ---
        log_frame = ctk.CTkFrame(self, fg_color=RENKLER["panel_arka"], corner_radius=10)
        log_frame.grid(row=6, column=0, padx=20, y=(5, 16), sticky="nsew")
        self.grid_rowconfigure(6, weight=1)

        log_baslik = ctk.CTkLabel(
            log_frame,
            text="Islem Logu",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=RENKLER["baslik"],
        )
        log_baslik.pack(padx=15, pady=(8, 2), anchor="w")

        self.log_kutusu = ctk.CTkTextbox(
            log_frame,
            height=140,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=RENKLER["log_arka"],
            text_color=RENKLER["log_yazi"],
            corner_radius=6,
        )
        self.log_kutusu.pack(padx=10, pady=(0, 10), fill="both", expand=True)
        self.log_kutusu.configure(state="disabled")

    def _parola_goster_gizle(self) -> None:
        yeni = "" if self.parola_entry.cget("show") == "*" else "*"
        self.parola_entry.configure(show=yeni)
        self.goster_btn.configure(text="Gizle" if yeni == "" else "Goster")

    def _bilgileri_kaydet(self) -> None:
        sinif_kodu = next((k for k, e in SINIFLAR if e == self.sinif_etiket_var.get()), "1")
        _env_kaydet(
            self.uye_no_var.get().strip(),
            self.kullanici_var.get().strip(),
            self.parola_var.get(),
            self.yil_var.get(),
            sinif_kodu,
        )
        self._log("Bilgiler .env dosyasina kaydedildi.")

    def _log(self, mesaj: str) -> None:
        _dosyaya_log_yaz(mesaj)
        self.log_kutusu.configure(state="normal")
        self.log_kutusu.insert("end", mesaj + "\n")
        self.log_kutusu.see("end")
        self.log_kutusu.configure(state="disabled")

    def _mesgul_baslat(self, durum: str) -> None:
        self.calisiyor = True
        self.durum_var.set(durum)
        self.durum_label.configure(text_color=RENKLER["durum_calisiyor"])
        self.ilerleme.start()
        self.getir_btn.configure(state="disabled")
        self.rapor_btn.configure(state="disabled")
        self.toplu_rapor_btn.configure(state="disabled")
        self.kontrol_btn.configure(state="disabled")
        self.toplu_kontrol_btn.configure(state="disabled")

    def _mesgul_bitir(self, durum: str = "Hazir") -> None:
        self.calisiyor = False
        self.durum_var.set(durum)
        self.ilerleme.stop()
        self.getir_btn.configure(state="normal")
        if self.core is not None:
            self.kapat_btn.configure(state="normal")
            if self.tablo.get_children():
                self.toplu_rapor_btn.configure(state="normal")
                self.rapor_btn.configure(state="normal")
            self._kontrol_guncelle_butonlar()

        if "hata" in durum.lower():
            self.durum_label.configure(text_color=RENKLER["durum_hata"])
        elif "basarili" in durum.lower() or "tamamlandi" in durum.lower():
            self.durum_label.configure(text_color=RENKLER["durum_basarili"])
        else:
            self.durum_label.configure(text_color=RENKLER["durum_bekleme"])

    def _musterileri_getir(self) -> None:
        if self.calisiyor:
            return
        uye_no = self.uye_no_var.get().strip()
        kullanici_adi = self.kullanici_var.get().strip()
        parola = self.parola_var.get()
        if not uye_no or not kullanici_adi or not parola:
            messagebox.showwarning("Eksik bilgi", "Lutfen Uye Numarisi, Kullanici Adi ve Parola alanlarini doldurun.")
            return

        yil = self.yil_var.get()
        sinif_kodu = next((k for k, e in SINIFLAR if e == self.sinif_etiket_var.get()), "1")

        if self.core is not None:
            self._tarayiciyi_kapat(sessiz=True)

        for satir in self.tablo.get_children():
            self.tablo.delete(satir)
        self.secili_kisa_ad = None

        self._mesgul_baslat("Giris yapiliyor ve musteri listesi getiriliyor...")

        def is_parcasi():
            core = LucaOtomasyonCore(uye_no, kullanici_adi, parola, cikti_klasoru="raporlar")
            try:
                musteriler = core.baslat_ve_filtrele(
                    yil, sinif_kodu, log=lambda m: self.olay_kuyrugu.put(("log", m))
                )
                self.olay_kuyrugu.put(("musteriler_hazir", core, musteriler))
            except Exception as e:
                self.olay_kuyrugu.put(("hata", str(e), traceback.format_exc()))
                try:
                    core.kapat()
                except Exception:
                    pass

        self._is_kuyrugu.put(is_parcasi)

    def _tablo_secim_degisti(self, _event=None) -> None:
        secim = self.tablo.selection()
        if not secim:
            self.secili_kisa_ad = None
            self.rapor_btn.configure(state="disabled")
            return
        degerler = self.tablo.item(secim[0], "values")
        self.secili_kisa_ad = degerler[0]
        if not self.calisiyor:
            self.rapor_btn.configure(state="normal")

    def _tarih_otomatik_format(self, _event=None) -> None:
        """Kullanıcı sadece 8 rakam yazar; noktalar otomatik eklenir.

        Örn: '01012026' yazarken ekranda '01.01.2026' görünür.
        """
        for entry in (self.baslangic_entry, self.bitis_entry):
            try:
                rakamlar = "".join(ch for ch in entry.get() if ch.isdigit())[:8]
                parcalar = []
                if len(rakamlar) >= 1:
                    parcalar.append(rakamlar[0:2])
                if len(rakamlar) >= 3:
                    parcalar.append(rakamlar[2:4])
                if len(rakamlar) >= 5:
                    parcalar.append(rakamlar[4:8])
                yeni = ".".join(parcalar)
                if entry.get() != yeni:
                    imlec = len(yeni)
                    entry.delete(0, "end")
                    entry.insert(0, yeni)
                    try:
                        entry.icursor(imlec)
                    except Exception:
                        pass
            except Exception:
                pass

    @staticmethod
    def _tarih_temizle(deger: str) -> str:
        """Girdiden ayraçları kaldırıp düz 8 rakam (GGAAYYYY) döndürür.

        '01.01.2026' -> '01012026'. Core tarafı bunu GG/AA/YYYY'e çevirir.
        """
        return "".join(ch for ch in deger if ch.isdigit())[:8]

    def _rapor_olustur(self) -> None:
        if self.calisiyor or self.core is None:
            return
        if not self.secili_kisa_ad:
            secim = self.tablo.selection()
            if secim:
                degerler = self.tablo.item(secim[0], "values")
                self.secili_kisa_ad = degerler[0]
            else:
                messagebox.showwarning("Müşteri Seçilmedi", "Lütfen listeden bir müşteri seçin.")
                return
        kisa_ad = self.secili_kisa_ad
        baslangic = self._tarih_temizle(self.baslangic_entry.get()) if hasattr(self, "baslangic_entry") else ""
        bitis = self._tarih_temizle(self.bitis_entry.get()) if hasattr(self, "bitis_entry") else ""
        self._mesgul_baslat(f"'{kisa_ad}' icin Mizan raporu olusturuluyor...")

        def is_parcasi():
            try:
                self.core.musteri_sec(kisa_ad, log=lambda m: self.olay_kuyrugu.put(("log", m)))
                dosya = self.core.mizan_raporu_olustur(
                    kisa_ad,
                    log=lambda m: self.olay_kuyrugu.put(("log", m)),
                    baslangic=baslangic,
                    bitis=bitis,
                )
                self.core.musteri_kartina_don(log=lambda m: self.olay_kuyrugu.put(("log", m)))
                self.olay_kuyrugu.put(("rapor_tamam", dosya))
            except Exception as e:
                self.olay_kuyrugu.put(("hata", str(e), traceback.format_exc()))

        self._is_kuyrugu.put(is_parcasi)

    def _toplu_rapor_olustur(self) -> None:
        if self.calisiyor or self.core is None:
            return
        tum_musteriler = []
        for cocuk in self.tablo.get_children():
            degerler = self.tablo.item(cocuk, "values")
            tum_musteriler.append({
                "kisa_ad": degerler[0],
                "uzun_ad": degerler[1],
                "vergi_dairesi": degerler[2],
                "vergi_no": degerler[3],
            })
        if not tum_musteriler:
            messagebox.showwarning("Musteri yok", "Once musteri listesini getirin.")
            return

        onay = messagebox.askyesno(
            "Toplu Rapor Onayi",
            f"{len(tum_musteriler)} musteri icin Mizan raporu olusturulacak.\n\n"
            "Bu islem biraz surebilir. Devam etmek istiyor musunuz?",
        )
        if not onay:
            return

        self._mesgul_baslat(f"{len(tum_musteriler)} musteri icin toplu rapor olusturuluyor...")
        baslangic = self._tarih_temizle(self.baslangic_entry.get()) if hasattr(self, "baslangic_entry") else ""
        bitis = self._tarih_temizle(self.bitis_entry.get()) if hasattr(self, "bitis_entry") else ""

        def is_parcasi():
            try:
                sonuclar = self.core.toplu_mizan_raporu(
                    tum_musteriler,
                    log=lambda m: self.olay_kuyrugu.put(("log", m)),
                    baslangic=baslangic,
                    bitis=bitis,
                )
                self.olay_kuyrugu.put(("toplu_rapor_tamam", sonuclar))
            except Exception as e:
                self.olay_kuyrugu.put(("hata", str(e), traceback.format_exc()))

        self._is_kuyrugu.put(is_parcasi)

    def _tarayiciyi_kapat(self, sessiz: bool = False) -> None:
        core_kapatilacak = self.core
        self.core = None
        self.secili_kisa_ad = None
        self.rapor_btn.configure(state="disabled")
        self.toplu_rapor_btn.configure(state="disabled")
        self.kapat_btn.configure(state="disabled")
        if not sessiz:
            self._log("Tarayici kapatiliyor...")
            self.durum_var.set("Hazir")
            self.durum_label.configure(text_color=RENKLER["durum_bekleme"])

        if core_kapatilacak is not None:
            def is_parcasi():
                try:
                    core_kapatilacak.kapat()
                except Exception:
                    pass

            self._is_kuyrugu.put(is_parcasi)

    def _kapatirken(self) -> None:
        _dosyaya_log_yaz("Uygulama penceresi kapatiliyor.")
        if self._dashboard_pencere is not None:
            try:
                self._dashboard_pencere.destroy()
            except Exception:
                pass
            self._dashboard_pencere = None
        self._tarayiciyi_kapat(sessiz=True)
        self.destroy()

    def _rapor_ekle(self, dosya_yolu) -> None:
        """Indirilen raporu listeye ekle."""
        if dosya_yolu is None:
            return
        dosya = Path(dosya_yolu)
        if not dosya.exists():
            return

        boyut = dosya.stat().st_size
        if boyut > 1024 * 1024:
            boyut_str = f"{boyut / (1024 * 1024):.1f} MB"
        elif boyut > 1024:
            boyut_str = f"{boyut / 1024:.1f} KB"
        else:
            boyut_str = f"{boyut} B"

        tarih = datetime.datetime.fromtimestamp(dosya.stat().st_mtime).strftime("%d.%m.%Y %H:%M")

        self.rapor_tablo.insert("", "end", values=(dosya.name, boyut_str, tarih))
        self.indirilen_raporlar.append({"dosya": dosya, "boyut": boyut_str, "tarih": tarih})

        sayi = len(self.indirilen_raporlar)
        self.rapor_sayisi_var.set(f"({sayi} dosya)")
        self.ac_btn.configure(state="normal")
        self.klasor_btn.configure(state="normal")

    def _secili_raporu_ac(self) -> None:
        """Secili rapor dosyasini varsayilan uygulama ile ac."""
        secim = self.rapor_tablo.selection()
        if not secim:
            return
        degerler = self.rapor_tablo.item(secim[0], "values")
        dosya_adi = degerler[0]

        for rapor in self.indirilen_raporlar:
            if rapor["dosya"].name == dosya_adi:
                try:
                    os.startfile(str(rapor["dosya"]))
                    self._log(f"Dosya aciliyor: {rapor['dosya'].name}")
                except Exception as e:
                    self._log(f"Dosya acilamadi: {e}")
                    try:
                        subprocess.Popen(["explorer", str(rapor["dosya"])])
                    except Exception:
                        pass
                return

    def _rapor_klasorunu_ac(self) -> None:
        """Raporlar klasorunu ac."""
        klasor = Path("raporlar")
        if not klasor.exists():
            klasor.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(klasor.resolve()))
        except Exception:
            try:
                subprocess.Popen(["explorer", str(klasor.resolve())])
            except Exception as e:
                self._log(f"Klasor acilamadi: {e}")

    def _rapor_listesini_temizle(self) -> None:
        """Rapor listesini temizle."""
        for cocuk in self.rapor_tablo.get_children():
            self.rapor_tablo.delete(cocuk)
        self.indirilen_raporlar.clear()
        self.rapor_sayisi_var.set("")
        self.ac_btn.configure(state="disabled")
        self.klasor_btn.configure(state="disabled")

    def _kontrol_guncelle_butonlar(self) -> None:
        """Kontrol butonlarini rapor varligina gore gunceller."""
        rapor_klasor = Path("raporlar")
        if rapor_klasor.exists():
            xlsx_sayisi = len(list(rapor_klasor.glob("*.xlsx")))
            self.kontrol_btn.configure(state="normal" if xlsx_sayisi > 0 else "disabled")
            self.toplu_kontrol_btn.configure(state="normal" if xlsx_sayisi > 0 else "disabled")
        else:
            self.kontrol_btn.configure(state="disabled")
            self.toplu_kontrol_btn.configure(state="disabled")

    def _kontrol_raporlari(self) -> None:
        """Indirilen tum mizan raporlarini kontrol eder."""
        if self.calisiyor:
            return
        rapor_klasor = Path("raporlar")
        if not rapor_klasor.exists():
            messagebox.showwarning("Uyari", "Raporlar klasoru bulunamadi.")
            return
        dosyalar = sorted(f for f in rapor_klasor.glob("*.xlsx") if "_KONTROL" not in f.name)
        if not dosyalar:
            messagebox.showinfo("Bilgi", "Kontrol edilecek rapor yok.")
            return

        self._mesgul_baslat("Mizan raporlari kontrol ediliyor...")
        self.kontrol_sonuclari = []
        self.kontrol_filtreli = "tum"
        self._kontrol_tablosu_yenile()

        def is_parcasi():
            for dosya in dosyalar:
                try:
                    s = _mizan_mod.retry_islem(
                        lambda d=dosya: _mizan_mod.mizan_kontrol(d),
                        deneme_sayisi=3,
                        bekleme_saniye=0.5,
                    )
                    self.olay_kuyrugu.put(("kontrol_sonuc", {
                        "dosya": dosya.name,
                        "durum": s.durum,
                        "ozet": s.ozet,
                        "hata_sayisi": s.hata_sayisi,
                        "uyari_sayisi": s.uyari_sayisi,
                        "firma": s.firma_adi,
                        "ihlaller": [{"kural": i.kural_id, "hesap": i.hesap_kodu,
                                       "ad": i.hesap_adi, "seviye": i.seviye, "mesaj": i.mesaj}
                                      for i in s.ihlaller],
                        "yol": str(dosya),
                    }))
                except Exception as e:
                    hata_kodu = "KONTROL"
                    mesaj = str(e)
                    if "Dosya bulunamadi" in mesaj:
                        hata_kodu = "DOSYA"
                    elif "Baglant" in mesaj or "sunucu" in mesaj.lower():
                        hata_kodu = "BAGLANTI"
                    self.olay_kuyrugu.put(("kontrol_sonuc", {
                        "dosya": dosya.name, "durum": "HATA",
                        "ozet": f"{hata_kodu}: {mesaj}",
                        "hata_sayisi": 1, "uyari_sayisi": 0, "firma": "", "ihlaller": [],
                        "yol": str(dosya),
                    }))
            self.olay_kuyrugu.put(("kontrol_tamam"))

        self._is_kuyrugu.put(is_parcasi)

    def _toplu_kontrol_raporlari(self) -> None:
        """Tum raporlari kontrol et onayi."""
        self._kontrol_raporlari()

    def _kontrol_tamamlandi(self) -> None:
        """Kontrol tamamlandi istatistikleri gunceller."""
        toplam = len(self.kontrol_sonuclari)
        ok = sum(1 for s in self.kontrol_sonuclari if s["durum"] == "OK")
        hata = sum(1 for s in self.kontrol_sonuclari if s["durum"] == "HATA")
        uyari = sum(1 for s in self.kontrol_sonuclari if s["durum"] == "UYARI")
        self.ist_toplam.configure(text=f"TOPLAM: {toplam}")
        self.ist_ok.configure(text=f"✅ OK: {ok}")
        self.ist_hata.configure(text=f"❌ HATA: {hata}")
        self.ist_uyari.configure(text=f"⚠️ UYARI: {uyari}")
        self._mesgul_bitir(f"Kontrol tamamlandi ({toplam} dosya)")
        self._kontrol_filtrele(self.kontrol_filtreli)

        # SQLite kaydet
        if kontrol_sonuc_kaydet is not None:
            try:
                for s in self.kontrol_sonuclari:
                    ihlaller = s.get("ihlaller", [])
                    kontrol_sonuc_kaydet(
                        dosya_adi=s["dosya"],
                        firma_adi=s.get("firma", ""),
                        durum=s["durum"],
                        hata_sayisi=s.get("hata_sayisi", 0),
                        uyari_sayisi=s.get("uyari_sayisi", 0),
                        ihlaller=ihlaller,
                    )
            except Exception:
                pass

        # Dashboard güncelle
        self._dashboard_guncelle()

        # Belirgi bildirim
        if hata > 0:
            hatali_dosyalar = [s["dosya"] for s in self.kontrol_sonuclari if s["durum"] == "HATA"]
            mesaj = f"❌ {hata} DOSYA HATALI!\n\n" + "\n".join(f"  • {d}" for d in hatali_dosyalar)
            messagebox.showerror("HATA Tespit Edildi", mesaj)
            # Istatistik etiketini kirmizi yap
            self.ist_hata.configure(text=f"❌ HATA: {hata}", text_color="#ef4444")
            self.ist_toplam.configure(text=f"🚨 TOPLAM: {toplam}", text_color="#ef4444")
        elif uyari > 0:
            messagebox.showwarning("UYARI", f"⚠️ {uyari} dosyada uyarı var.")
            self.ist_hata.configure(text=f"⚠️ HATA: {hata}", text_color="#facc15")
            self.ist_uyari.configure(text=f"⚠️ UYARI: {uyari}", text_color="#facc15")
        else:
            messagebox.showinfo("Kontrol Tamamlandı", f"✅ Tüm {toplam} dosya OK.")
            self.ist_hata.configure(text=f"❌ HATA: 0", text_color="#ef4444")
            self.ist_uyari.configure(text=f"⚠️ UYARI: 0", text_color="#facc15")
            self.ist_toplam.configure(text=f"TOPLAM: {toplam}", text_color="#ffffff")

    def _kontrol_sonuc_ekle(self, sonuc: dict) -> None:
        """Tek bir kontrol sonucunu ekler."""
        self.kontrol_sonuclari.append(sonuc)

    def _kontrol_tablosu_yenile(self) -> None:
        """Filtreli tabloyu gunceller."""
        for cocuk in self.kontrol_tablo.get_children():
            self.kontrol_tablo.delete(cocuk)

        filtre = self.kontrol_filtreli
        arama = self.kontrol_arama.get().strip().lower() if hasattr(self, 'kontrol_arama') else ""
        tarix = self.kontrol_tarix_entry.get().strip() if hasattr(self, 'kontrol_tarix_entry') else ""

        filtrelenen = self.kontrol_sonuclari
        if filtre != "tum":
            filtrelenen = [s for s in filtrelenen if s["durum"] == filtre]
        if arama:
            filtrelenen = [s for s in filtrelenen if arama in s.get("firma", "").lower() or arama in s["dosya"].lower()]
        if tarix:
            filtrelenen = [s for s in filtrelenen if tarix in s["dosya"]]

        for s in filtrelenen:
            tag = "ok" if s["durum"] == "OK" else ("uyari" if s["durum"] == "UYARI" else "hata")
            self.kontrol_tablo.insert("", "end", values=(
                s["dosya"], s["durum"], s["ozet"], s["hata_sayisi"], s["uyari_sayisi"], s.get("firma", ""),
            ), tags=(tag,))

        if not filtrelenen:
            self.kontrol_tablo.insert("", "end", values=("--", "--", "Filtreye eslesen kayit yok", "", "", ""))

    def _kontrol_filtrele(self, filtre: str) -> None:
        """Filtre uygular."""
        self.kontrol_filtreli = filtre
        self._kontrol_tablosu_yenile()

    def _kontrol_detay_goster(self) -> None:
        """Secili dosyanin detaylarini gosterir (messagebox)."""
        secim = self.kontrol_tablo.selection()
        if not secim:
            return
        degerler = self.kontrol_tablo.item(secim[0], "values")
        dosya = degerler[0]
        for s in self.kontrol_sonuclari:
            if s["dosya"] == dosya and s.get("ihlaller"):
                mesaj = f"=== {dosya} ===\n\n"
                for ihlal in s["ihlaller"]:
                    mesaj += f"[{ihlal['kural']}] {ihlal['hesap']} {ihlal['ad']}: {ihlal['mesaj']}\n"

                # Hata önerileri
                if hata_onusu_ara is not None:
                    oneriler = []
                    for ihlal in s["ihlaller"]:
                        if ihlal.get("seviye") == "HATA":
                            oner = hata_onusu_ara(ihlal.get("kural", ""))
                            if oner:
                                oneriler.append(f"[{ihlal['kural']}] {ihlal['hesap_kodu']}: {oner}")
                    if oneriler:
                        mesaj += "\n--- ÖNERİLER ---\n" + "\n".join(oneriler)

                messagebox.showinfo("Kontrol Detay", mesaj)
                return
        messagebox.showinfo("Kontrol Detay", f"{dosya}: Ihlal bulunamadi.")

    def _kontrol_export(self, format: str) -> None:
        """Filtreli sonuclari export eder."""
        import mizan_kontrol as mk
        from pathlib import Path as Path2

        filtrelenen = [s for s in self.kontrol_sonuclari if s["durum"] != "OK" or self.kontrol_filtreli == "tum"]
        if self.kontrol_filtreli != "tum":
            filtrelenen = [s for s in self.kontrol_sonuclari if s["durum"] == self.kontrol_filtreli]
        if not filtrelenen:
            messagebox.showwarning("Uyari", "Export edilecek kayit yok.")
            return

        try:
            rapor_klasor = Path2("raporlar")
            for s in filtrelenen:
                dosya_yol = None
                for f in rapor_klasor.glob("*.xlsx"):
                    if f.name == s["dosya"] and "_KONTROL" not in f.name:
                        dosya_yol = f
                        break
                if dosya_yol is None:
                    continue
                s_obj = mk.mizan_kontrol(dosya_yol)
                if format == "json":
                    hedef = dosya_yol.with_suffix(".json")
                    mk.kontrol_json_yaz(s_obj, hedef)
                elif format == "csv":
                    hedef = dosya_yol.with_suffix(".csv")
                    mk.kontrol_csv_yaz(s_obj, hedef)
                elif format == "pdf":
                    hedef = dosya_yol.with_suffix("_KONTROL.pdf")
                    mk.kontrol_pdf_yaz(s_obj, hedef)
            messagebox.showinfo("Basarili", f"Export tamamlandi ({len(filtrelenen)} dosya).")
        except Exception as e:
            messagebox.showerror("Hata", f"Export basarisiz: {e}")

    def _kontrol_export_json(self) -> None:
        self._kontrol_export("json")

    def _kontrol_export_csv(self) -> None:
        self._kontrol_export("csv")

    def _kontrol_export_pdf(self) -> None:
        self._kontrol_export("pdf")

    # --- Güncelleme ---
    def _guncelleme_kontrol(self) -> None:
        if gc is None:
            self.guncelle_durum.configure(text="")
            return
        try:
            son = gc.guncellememi_kontrol_et()
            if son.get("guncellememevcut"):
                self.guncelle_durum.configure(text="✅ Güncel", text_color="#22c55e")
            else:
                self.guncelle_durum.configure(text="🔄 Güncelle mevcut!", text_color="#facc15")
        except Exception:
            self.guncelle_durum.configure(text="")

    def _guncelle(self) -> None:
        if gc is None:
            messagebox.showwarning("Güncelleme", "Güncelleme modülü yüklü değil.")
            return
        try:
            son = gc.guncelle()
            if son.get("ok"):
                if son.get("guncellendi"):
                    messagebox.showinfo("Güncelleme", son.get("mesaj", "Güncelleme başarılı!"))
                    self._guncelleme_kontrol()
                else:
                    messagebox.showinfo("Güncelleme", son.get("mesaj", "Zaten en güncel sürüm."))
            else:
                messagebox.showerror("Güncelleme", son.get("mesaj", "Güncelleme başarısız."))
        except Exception as e:
            messagebox.showerror("Güncelleme", f"Hata: {e}")

    def _guncelle_kontrol(self) -> None:
        self._guncelleme_kontrol()
        if gc is not None:
            son = gc.guncellememi_kontrol_et()
            if not son.get("guncellememevcut"):
                self._guncelle()

    # --- Dashboard ---
    def _dashboard_ac(self) -> None:
        if self._dashboard_pencere is not None:
            try:
                self._dashboard_pencere.lift()
                self._dashboard_pencere.focus_force()
            except Exception:
                pass
            return
        self._dashboard_pencere = ctk.CTkToplevel(self)
        self._dashboard_pencere.title("📊 Dashboard")
        self._dashboard_pencere.geometry("650x450")
        self._dashboard_pencere.minsize(500, 350)
        self._dashboard_pencere.transient(self)
        self._dashboard_pencere.protocol("WM_DELETE_WINDOW", self._dashboard_kapat)

        ctk.CTkLabel(
            self._dashboard_pencere, text="📊 Dashboard",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=RENKLER["baslik"],
        ).pack(padx=20, pady=(15, 5), anchor="w")

        self.dash_ist = ctk.CTkFrame(self._dashboard_pencere, corner_radius=8)
        self.dash_ist.pack(fill="x", padx=20, pady=5)

        self.dash_toplam = ctk.CTkLabel(self.dash_ist, text="TOPLAM: 0",
                                         font=ctk.CTkFont(size=16, weight="bold"), text_color="#fff")
        self.dash_toplam.pack(side="left", padx=15, pady=10)
        self.dash_ok = ctk.CTkLabel(self.dash_ist, text="✅ OK: 0",
                                     font=ctk.CTkFont(size=14), text_color="#22c55e")
        self.dash_ok.pack(side="left", padx=15, pady=10)
        self.dash_hata = ctk.CTkLabel(self.dash_ist, text="❌ HATA: 0",
                                       font=ctk.CTkFont(size=14), text_color="#ef4444")
        self.dash_hata.pack(side="left", padx=15, pady=10)
        self.dash_uyari = ctk.CTkLabel(self.dash_ist, text="⚠️ UYARI: 0",
                                        font=ctk.CTkFont(size=14), text_color="#facc15")
        self.dash_uyari.pack(side="left", padx=15, pady=10)

        self.dash_surum = ctk.CTkLabel(
            self._dashboard_pencere, text="",
            font=ctk.CTkFont(size=11), text_color="#888888",
        )
        self.dash_surum.pack(padx=20, pady=(10, 5), anchor="w")

        self.dash_grafik = ctk.CTkFrame(self._dashboard_pencere, corner_radius=8)
        self.dash_grafik.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(self.dash_grafik, text="HATA Durumu — Son Kontroller",
                      font=ctk.CTkFont(size=12, weight="bold")).pack(padx=10, pady=(10, 5), anchor="w")
        self.dash_barlar = ctk.CTkFrame(self.dash_grafik, fg_color="transparent")
        self.dash_barlar.pack(fill="x", padx=10, pady=(0, 10))

        self.dash_tablo_frame = ctk.CTkFrame(self._dashboard_pencere)
        self.dash_tablo_frame.pack(fill="both", expand=True, padx=20, pady=(5, 15))
        self.dash_tablo = ttk.Treeview(
            self.dash_tablo_frame,
            columns=("dosya", "durum", "ozet", "tarih"),
            show="headings", height=5, selectmode="browse",
        )
        self.dash_tablo.heading("dosya", text="Dosya")
        self.dash_tablo.heading("durum", text="Durum")
        self.dash_tablo.heading("ozet", text="Özet")
        self.dash_tablo.heading("tarih", text="Tarih")
        self.dash_tablo.column("dosya", width=150)
        self.dash_tablo.column("durum", width=70)
        self.dash_tablo.column("ozet", width=300)
        self.dash_tablo.column("tarih", width=120)
        scroll = ttk.Scrollbar(self.dash_tablo_frame, orient="vertical", command=self.dash_tablo.yview)
        self.dash_tablo.configure(yscrollcommand=scroll.set)
        self.dash_tablo.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.dash_tablo.tag_configure("ok", foreground="#22c55e")
        self.dash_tablo.tag_configure("hata", foreground="#ef4444")
        self.dash_tablo.tag_configure("uyari", foreground="#facc15")

        ctk.CTkButton(
            self._dashboard_pencere, text="🔄 Yenile", width=100,
            fg_color="#555555", hover_color="#444444",
            command=self._dashboard_guncelle,
        ).pack(pady=(0, 15))

        self.after(200, self._dashboard_guncelle)

    def _dashboard_kapat(self) -> None:
        if self._dashboard_pencere is not None:
            self._dashboard_pencere.destroy()
            self._dashboard_pencere = None

    def _dashboard_guncelle(self) -> None:
        if self._dashboard_pencere is None:
            return
        try:
            if istatistik_getir is not None:
                ist = istatistik_getir()
                toplam = ist.get("toplam", 0)
                ok = ist.get("ok", 0)
                hata = ist.get("hata", 0)
                uyari = ist.get("uyari", 0)
                self.dash_toplam.configure(text=f"TOPLAM: {toplam}")
                self.dash_ok.configure(text=f"✅ OK: {ok}")
                self.dash_hata.configure(text=f"❌ HATA: {hata}")
                self.dash_uyari.configure(text=f"⚠️ UYARI: {uyari}")

            if gc is not None:
                surum = gc.simdiki_surum()
                self.dash_surum.configure(text=f"v{surum}")

            if kontrol_sonuclari_getir is not None:
                for cocuk in self.dash_tablo.get_children():
                    self.dash_tablo.delete(cocuk)
                sonuclar = kontrol_sonuclari_getir(limit=50)
                for s in sonuclar:
                    tag = "ok" if s["durum"] == "OK" else ("uyari" if s["durum"] == "UYARI" else "hata")
                    self.dash_tablo.insert("", "end", values=(
                        s.get("dosya", ""), s.get("durum", ""), s.get("ozet", ""), s.get("kayit_tarihi", ""),
                    ), tags=(tag,))
        except Exception:
            pass

    # --- Queue listener ---
    def _kuyrugu_dinle(self) -> None:
        try:
            while True:
                olay = self.olay_kuyrugu.get_nowait()
                tur = olay[0]

                if tur == "log":
                    self._log(olay[1])

                elif tur == "musteriler_hazir":
                    self.core, musteriler = olay[1], olay[2]
                    for m in musteriler:
                        self.tablo.insert("", "end", values=(
                            m["kisa_ad"], m["uzun_ad"], m["vergi_dairesi"], m["vergi_no"]
                        ))
                    if not musteriler:
                        self._log("UYARI: Filtreyle eslesen musteri bulunamadi.")
                    else:
                        self.toplu_rapor_btn.configure(state="normal")
                    self._mesgul_bitir(f"{len(musteriler)} musteri listelendi.")
                    self._kontrol_guncelle_butonlar()

                elif tur == "rapor_tamam":
                    dosya = olay[1]
                    if dosya:
                        self._log(f"BASARILI: Rapor kaydedildi -> {dosya}")
                        self._rapor_ekle(dosya)
                        self._mesgul_bitir("Rapor olusturuldu.")
                        self._kontrol_guncelle_butonlar()
                    else:
                        self._mesgul_bitir("Rapor kuyruga alindi (Rapor Takip'ten indirin).")

                elif tur == "toplu_rapor_tamam":
                    sonuclar = olay[1]
                    basarili = sum(1 for s in sonuclar if s["durum"] in ("basarili", "kuyruga alindi"))
                    basarisiz = sum(1 for s in sonuclar if s["durum"] == "hatali")
                    self._log(f"\nTOPLU RAPOR SONUCU: {basarili} basarili, {basarisiz} hatali")
                    for s in sonuclar:
                        if s["durum"] == "hatali":
                            self._log(f"  X {s['kisa_ad']}: {s['hata']}")
                        else:
                            self._log(f"  OK {s['kisa_ad']}: {s['dosya_yolu'] or 'kuyruka alindi'}")
                            if s.get("dosya_yolu"):
                                self._rapor_ekle(s["dosya_yolu"])
                    self._mesgul_bitir(f"Toplu rapor tamamlandi ({basarili} basarili, {basarisiz} hatali)")
                    self._kontrol_guncelle_butonlar()

                elif tur == "kontrol_sonuc":
                    self._kontrol_sonuc_ekle(olay[1])

                elif tur == "kontrol_tamam":
                    self._kontrol_tamamlandi()

                elif tur == "hata":
                    mesaj, ayrinti = olay[1], olay[2]
                    self._log(f"HATA: {mesaj}")
                    self._log(ayrinti)
                    self._mesgul_bitir("Hata olustu.")
                    try:
                        messagebox.showerror("Hata", mesaj)
                    except Exception:
                        pass

        except queue.Empty:
            pass
        except Exception as e:
            _dosyaya_log_yaz(f"KUYRUG ISLEME HATASI: {e}\n{traceback.format_exc()}")
        finally:
            self.after(120, self._kuyrugu_dinle)


def main() -> None:
    uygulama = LucaGUI()
    uygulama.mainloop()


if __name__ == "__main__":
    main()
