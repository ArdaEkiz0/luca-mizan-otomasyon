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

        self._is_kuyrugu: "queue.Queue" = queue.Queue()
        threading.Thread(target=self._is_parcasi_dongusu, daemon=True, name="OtomasyonWorker").start()

        ayar = _env_yukle()
        self._arayuzu_olustur(ayar)
        self.after(120, self._kuyrugu_dinle)
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
        self.grid_rowconfigure(3, weight=1)

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
        aksiyon_frame = ctk.CTkFrame(self, fg_color="transparent")
        aksiyon_frame.grid(row=3, column=0, padx=20, pady=(0, 4), sticky="ew")
        aksiyon_frame.grid_columnconfigure(0, weight=1)

        buton_satiri = ctk.CTkFrame(aksiyon_frame, fg_color="transparent")
        buton_satiri.grid(row=0, column=0, sticky="w", pady=(0, 6))

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
        durum_satiri.grid(row=1, column=0, sticky="ew")
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

        # --- Log alani ---
        log_frame = ctk.CTkFrame(self, fg_color=RENKLER["panel_arka"], corner_radius=10)
        log_frame.grid(row=5, column=0, padx=20, pady=(5, 16), sticky="nsew")
        self.grid_rowconfigure(5, weight=1)

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
        self._mesgul_baslat(f"'{kisa_ad}' icin Mizan raporu olusturuluyor...")

        def is_parcasi():
            try:
                self.core.musteri_sec(kisa_ad, log=lambda m: self.olay_kuyrugu.put(("log", m)))
                dosya = self.core.mizan_raporu_olustur(kisa_ad, log=lambda m: self.olay_kuyrugu.put(("log", m)))
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

        def is_parcasi():
            try:
                sonuclar = self.core.toplu_mizan_raporu(
                    tum_musteriler,
                    log=lambda m: self.olay_kuyrugu.put(("log", m)),
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

                elif tur == "rapor_tamam":
                    dosya = olay[1]
                    if dosya:
                        self._log(f"BASARILI: Rapor kaydedildi -> {dosya}")
                        self._rapor_ekle(dosya)
                        self._mesgul_bitir("Rapor olusturuldu.")
                    else:
                        self._mesgul_bitir("Rapor kuyruka alindi (Rapor Takip'ten indirin).")

                elif tur == "toplu_rapor_tamam":
                    sonuclar = olay[1]
                    basarili = sum(1 for s in sonuclar if s["durum"] in ("basarili", "kuyruka alindi"))
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
            _dosyaya_log_yaz(f"KUYRUK ISLEME HATASI: {e}\n{traceback.format_exc()}")
        finally:
            self.after(120, self._kuyrugu_dinle)


def main() -> None:
    uygulama = LucaGUI()
    uygulama.mainloop()


if __name__ == "__main__":
    main()
