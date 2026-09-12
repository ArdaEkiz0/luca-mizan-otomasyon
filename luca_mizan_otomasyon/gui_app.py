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

# NOT: Uygulama beklenmedik şekilde kapanırsa (ör. bir çökme), ekrandaki log
# kutusu da onunla birlikte kaybolur ve neyin yanlış gittiğini görmek
# imkansız hale gelir. Bu yüzden her log satırı, ekranın yanında bir dosyaya
# da (kalıcı olarak) yazılıyor — uygulama kapansa bile bu dosya kalır ve
# sorunu teşhis etmek için paylaşılabilir.
LOG_DOSYASI = Path(__file__).parent / "otomasyon_log.txt"


def _dosyaya_log_yaz(mesaj: str) -> None:
    try:
        zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_DOSYASI, "a", encoding="utf-8") as f:
            f.write(f"[{zaman}] {mesaj}\n")
    except Exception:
        pass  # Log dosyasına yazamamak akışı bozmasın.


def _beklenmedik_hata_yakala(exc_type, exc_value, exc_tb) -> None:
    """Tkinter/ana thread'de yakalanmamış herhangi bir hatayı da (uygulama
    çökmeden hemen önceki son an dahil) log dosyasına kaydeder."""
    ayrinti = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    _dosyaya_log_yaz("BEKLENMEDİK HATA (uygulama kapanıyor olabilir):\n" + ayrinti)
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _beklenmedik_hata_yakala


def _thread_hata_yakala(args) -> None:
    """Arka plan iş parçacıklarında (thread) beklenmedik bir hata olursa
    (normalde is_parcasi() fonksiyonları kendi try/except'leriyle bunu
    yakalayıp kuyruğa gönderiyor, ama olur da bir şey o yakalamanın dışında
    kalırsa) yine de log dosyasına kaydedilsin."""
    ayrinti = "".join(
        traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
    )
    _dosyaya_log_yaz(f"BEKLENMEDİK THREAD HATASI ({args.thread.name}):\n" + ayrinti)


threading.excepthook = _thread_hata_yakala

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

YILLAR = [str(y) for y in range(2026, 2010, -1)]
SINIFLAR = [("", "Tümü"), ("1", "1.Sınıf"), ("2", "2.Sınıf"), ("3", "İşletme Defteri"), ("4", "Serbest Meslek Defteri"), ("5", "Basit Usül")]


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

        _dosyaya_log_yaz("=" * 20 + " Uygulama başlatıldı " + "=" * 20)

        self.title("Luca Mizan Raporu Otomasyonu")
        self.geometry("980x700")
        self.minsize(860, 600)

        self.olay_kuyrugu: "queue.Queue[tuple]" = queue.Queue()
        self.core: LucaOtomasyonCore | None = None
        self.secili_kisa_ad: str | None = None
        self.calisiyor = False

        # NOT: Playwright'ın senkron (sync) API'si thread-safe DEĞİLDİR — bir
        # tarayıcı/sayfa nesnesi hangi thread'de oluşturulduysa SADECE o
        # thread'den kullanılabilir. Eskiden her buton tıklamasında
        # (Müşterileri Getir / Mizan Raporu Oluştur / Toplu Rapor / Tarayıcıyı
        # Kapat) AYRI bir thread açılıyordu; "Müşterileri Getir" işi biten
        # thread kapandıktan (exited) sonra "Mizan Raporu Oluştur" gibi bir
        # sonraki işlem FARKLI bir thread'den aynı tarayıcı nesnesine erişmeye
        # çalışıyor, bu da "greenlet.error: cannot switch to a different
        # thread (which happens to have exited)" hatasına yol açıyordu. Şimdi
        # TÜM otomasyon işleri, uygulama boyunca yaşayan TEK bir arka plan
        # thread'inde sırayla kuyruklanıp işleniyor.
        self._is_kuyrugu: "queue.Queue" = queue.Queue()
        threading.Thread(target=self._is_parcasi_dongusu, daemon=True, name="OtomasyonWorker").start()

        ayar = _env_yukle()
        self._arayuzu_olustur(ayar)
        self.after(120, self._kuyrugu_dinle)
        self.protocol("WM_DELETE_WINDOW", self._kapatirken)

    def _is_parcasi_dongusu(self) -> None:
        """TÜM Playwright/otomasyon işlerinin çalıştığı, uygulama boyunca
        yaşayan TEK arka plan thread'i. Yukarıdaki NOT'ta açıklandığı gibi,
        bu, Playwright nesnelerinin her zaman aynı thread'den kullanılmasını
        garanti eder."""
        while True:
            is_ = self._is_kuyrugu.get()
            try:
                is_()
            except Exception:
                # is_ fonksiyonları kendi içinde zaten try/except ile
                # hataları olay kuyruğuna gönderiyor; yine de beklenmedik bir
                # şey patlarsa döngü burada ölmesin, sadece dosyaya kaydedilsin.
                _dosyaya_log_yaz("İŞ KUYRUĞU HATASI:\n" + traceback.format_exc())

    # ------------------------------------------------------------------
    # Arayüz kurulumu
    # ------------------------------------------------------------------

    def _arayuzu_olustur(self, ayar: dict) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        baslik = ctk.CTkLabel(
            self, text="Luca Mizan Raporu Otomasyonu",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        baslik.grid(row=0, column=0, padx=20, pady=(18, 6), sticky="w")

        # --- Giriş bilgileri ------------------------------------------------
        giris_frame = ctk.CTkFrame(self, corner_radius=12)
        giris_frame.grid(row=1, column=0, padx=20, pady=8, sticky="ew")
        for c in range(6):
            giris_frame.grid_columnconfigure(c, weight=1)

        ctk.CTkLabel(giris_frame, text="Giriş Bilgileri", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, columnspan=6, padx=14, pady=(12, 4), sticky="w"
        )

        ctk.CTkLabel(giris_frame, text="Üye Numarası").grid(row=1, column=0, padx=(14, 4), pady=6, sticky="w")
        self.uye_no_var = ctk.StringVar(value=ayar["uye_no"])
        ctk.CTkEntry(giris_frame, textvariable=self.uye_no_var, width=140).grid(row=1, column=1, padx=4, pady=6, sticky="w")

        ctk.CTkLabel(giris_frame, text="Kullanıcı Adı").grid(row=1, column=2, padx=(14, 4), pady=6, sticky="w")
        self.kullanici_var = ctk.StringVar(value=ayar["kullanici_adi"])
        ctk.CTkEntry(giris_frame, textvariable=self.kullanici_var, width=140).grid(row=1, column=3, padx=4, pady=6, sticky="w")

        ctk.CTkLabel(giris_frame, text="Parola").grid(row=1, column=4, padx=(14, 4), pady=6, sticky="w")
        self.parola_var = ctk.StringVar(value=ayar["parola"])
        self.parola_entry = ctk.CTkEntry(giris_frame, textvariable=self.parola_var, width=140, show="*")
        self.parola_entry.grid(row=1, column=5, padx=(4, 6), pady=6, sticky="w")

        self.goster_btn = ctk.CTkButton(giris_frame, text="Göster", width=64, command=self._parola_goster_gizle)
        self.goster_btn.grid(row=1, column=6, padx=(0, 14), pady=6, sticky="w")

        self.kaydet_btn = ctk.CTkButton(giris_frame, text="Bilgileri Kaydet (.env)", command=self._bilgileri_kaydet)
        self.kaydet_btn.grid(row=2, column=0, columnspan=2, padx=14, pady=(0, 12), sticky="w")

        # --- Filtre + müşteri listesi ---------------------------------------
        filtre_frame = ctk.CTkFrame(self, corner_radius=12)
        filtre_frame.grid(row=2, column=0, padx=20, pady=8, sticky="ew")

        ctk.CTkLabel(filtre_frame, text="Filtre ve Müşteri Seçimi", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, columnspan=6, padx=14, pady=(12, 4), sticky="w"
        )

        ctk.CTkLabel(filtre_frame, text="Yıl").grid(row=1, column=0, padx=(14, 4), pady=6, sticky="w")
        self.yil_var = ctk.StringVar(value=ayar["yil"] if ayar["yil"] in YILLAR else YILLAR[0])
        ctk.CTkOptionMenu(filtre_frame, values=YILLAR, variable=self.yil_var, width=100).grid(row=1, column=1, padx=4, pady=6, sticky="w")

        ctk.CTkLabel(filtre_frame, text="Sınıf").grid(row=1, column=2, padx=(14, 4), pady=6, sticky="w")
        self.sinif_etiket_var = ctk.StringVar(
            value=next((e for k, e in SINIFLAR if k == ayar["sinif"]), "1.Sınıf")
        )
        ctk.CTkOptionMenu(
            filtre_frame, values=[e for _, e in SINIFLAR], variable=self.sinif_etiket_var, width=180
        ).grid(row=1, column=3, padx=4, pady=6, sticky="w")

        self.getir_btn = ctk.CTkButton(filtre_frame, text="Müşterileri Getir", command=self._musterileri_getir)
        self.getir_btn.grid(row=1, column=4, padx=14, pady=6, sticky="w")

        # Müşteri tablosu (ttk.Treeview - CustomTkinter'da yerleşik tablo yok)
        tablo_cercevesi = ctk.CTkFrame(filtre_frame, fg_color="transparent")
        tablo_cercevesi.grid(row=2, column=0, columnspan=6, padx=14, pady=(6, 14), sticky="nsew")
        filtre_frame.grid_columnconfigure(5, weight=1)

        stil = ttk.Style()
        stil.theme_use("default")
        stil.configure("Treeview", rowheight=26, font=("Segoe UI", 10))
        stil.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        kolonlar = ("kisa_ad", "uzun_ad", "vergi_dairesi", "vergi_no")
        self.tablo = ttk.Treeview(tablo_cercevesi, columns=kolonlar, show="headings", height=8, selectmode="extended")
        self.tablo.heading("kisa_ad", text="Kısa Ad")
        self.tablo.heading("uzun_ad", text="Uzun Ad")
        self.tablo.heading("vergi_dairesi", text="Vergi Dairesi")
        self.tablo.heading("vergi_no", text="Vergi No")
        self.tablo.column("kisa_ad", width=110)
        self.tablo.column("uzun_ad", width=320)
        self.tablo.column("vergi_dairesi", width=180)
        self.tablo.column("vergi_no", width=100)
        self.tablo.pack(side="left", fill="both", expand=True)
        self.tablo.bind("<<TreeviewSelect>>", self._tablo_secim_degisti)

        kaydirma = ttk.Scrollbar(tablo_cercevesi, orient="vertical", command=self.tablo.yview)
        self.tablo.configure(yscrollcommand=kaydirma.set)
        kaydirma.pack(side="right", fill="y")

        # --- Aksiyon butonları ------------------------------------------------
        # NOT: Butonlar ile durum yazısı/ilerleme çubuğu BİLEREK iki AYRI
        # satıra (alt alta) yerleştiriliyor. Daha önce hepsi aynı satırda
        # (bazıları sola, bazıları sağa yaslı) pack() ile diziliyordu; pencere
        # genişliği hepsini yan yana sığdırmaya yetmeyince araya girmeden
        # üst üste binip birbirine karışıyorlardı. İki ayrı satır olunca bu
        # çakışma pencere genişliğinden bağımsız olarak imkansız hale geliyor.
        aksiyon_frame = ctk.CTkFrame(self, fg_color="transparent")
        aksiyon_frame.grid(row=3, column=0, padx=20, pady=(0, 4), sticky="ew")
        aksiyon_frame.grid_columnconfigure(0, weight=1)

        buton_satiri = ctk.CTkFrame(aksiyon_frame, fg_color="transparent")
        buton_satiri.grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.rapor_btn = ctk.CTkButton(
            buton_satiri, text="Mizan Raporu Oluştur", state="disabled",
            fg_color="#1f8f4e", hover_color="#166b3b", command=self._rapor_olustur,
        )
        self.rapor_btn.pack(side="left", padx=(0, 8), pady=2)

        self.toplu_rapor_btn = ctk.CTkButton(
            buton_satiri, text="Tüm Müşteriler İçin Rapor", state="disabled",
            fg_color="#1f6f8f", hover_color="#166b8b", command=self._toplu_rapor_olustur,
        )
        self.toplu_rapor_btn.pack(side="left", padx=(0, 8), pady=2)

        self.kapat_btn = ctk.CTkButton(
            buton_satiri, text="Tarayıcıyı Kapat", state="disabled",
            fg_color="#8f1f1f", hover_color="#6b1616", command=self._tarayiciyi_kapat,
        )
        self.kapat_btn.pack(side="left", pady=2)

        durum_satiri = ctk.CTkFrame(aksiyon_frame, fg_color="transparent")
        durum_satiri.grid(row=1, column=0, sticky="ew")
        durum_satiri.grid_columnconfigure(0, weight=1)

        self.durum_var = ctk.StringVar(value="Hazır")
        ctk.CTkLabel(durum_satiri, textvariable=self.durum_var, anchor="w", justify="left").grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )

        self.ilerleme = ctk.CTkProgressBar(durum_satiri, mode="indeterminate", width=220)
        self.ilerleme.grid(row=0, column=1, sticky="e")

        # --- Log alanı ------------------------------------------------------
        self.log_kutusu = ctk.CTkTextbox(self, height=180, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_kutusu.grid(row=4, column=0, padx=20, pady=(6, 16), sticky="nsew")
        self.grid_rowconfigure(4, weight=1)
        self.log_kutusu.configure(state="disabled")

    # ------------------------------------------------------------------
    # Yardımcı: UI durum yönetimi
    # ------------------------------------------------------------------

    def _parola_goster_gizle(self) -> None:
        yeni = "" if self.parola_entry.cget("show") == "*" else "*"
        self.parola_entry.configure(show=yeni)
        self.goster_btn.configure(text="Gizle" if yeni == "" else "Göster")

    def _bilgileri_kaydet(self) -> None:
        sinif_kodu = next((k for k, e in SINIFLAR if e == self.sinif_etiket_var.get()), "1")
        _env_kaydet(
            self.uye_no_var.get().strip(),
            self.kullanici_var.get().strip(),
            self.parola_var.get(),
            self.yil_var.get(),
            sinif_kodu,
        )
        self._log("Bilgiler .env dosyasına kaydedildi.")

    def _log(self, mesaj: str) -> None:
        _dosyaya_log_yaz(mesaj)
        self.log_kutusu.configure(state="normal")
        self.log_kutusu.insert("end", mesaj + "\n")
        self.log_kutusu.see("end")
        self.log_kutusu.configure(state="disabled")

    def _mesgul_baslat(self, durum: str) -> None:
        self.calisiyor = True
        self.durum_var.set(durum)
        self.ilerleme.start()
        self.getir_btn.configure(state="disabled")
        self.rapor_btn.configure(state="disabled")

    def _mesgul_bitir(self, durum: str = "Hazır") -> None:
        self.calisiyor = False
        self.durum_var.set(durum)
        self.ilerleme.stop()
        self.getir_btn.configure(state="normal")
        if self.core is not None:
            self.kapat_btn.configure(state="normal")
            if self.tablo.get_children():
                self.toplu_rapor_btn.configure(state="normal")
        if self.secili_kisa_ad is not None:
            self.rapor_btn.configure(state="normal")

    # ------------------------------------------------------------------
    # Aksiyon: Müşterileri getir (arka plan thread)
    # ------------------------------------------------------------------

    def _musterileri_getir(self) -> None:
        if self.calisiyor:
            return
        uye_no = self.uye_no_var.get().strip()
        kullanici_adi = self.kullanici_var.get().strip()
        parola = self.parola_var.get()
        if not uye_no or not kullanici_adi or not parola:
            messagebox.showwarning("Eksik bilgi", "Lütfen Üye Numarası, Kullanıcı Adı ve Parola alanlarını doldurun.")
            return

        yil = self.yil_var.get()
        sinif_kodu = next((k for k, e in SINIFLAR if e == self.sinif_etiket_var.get()), "1")

        # Önceki oturum açıksa kapat, temiz başla.
        if self.core is not None:
            self._tarayiciyi_kapat(sessiz=True)

        for satir in self.tablo.get_children():
            self.tablo.delete(satir)
        self.secili_kisa_ad = None

        self._mesgul_baslat("Giriş yapılıyor ve müşteri listesi getiriliyor...")

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

    # ------------------------------------------------------------------
    # Aksiyon: Mizan raporu oluştur (arka plan thread)
    # ------------------------------------------------------------------

    def _rapor_olustur(self) -> None:
        if self.calisiyor or self.core is None or not self.secili_kisa_ad:
            return
        kisa_ad = self.secili_kisa_ad
        self._mesgul_baslat(f"'{kisa_ad}' için Mizan raporu oluşturuluyor...")

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
            messagebox.showwarning("Müşteri yok", "Önce müşteri listesini getirin.")
            return

        onay = messagebox.askyesno(
            "Toplu Rapor Onayı",
            f"{len(tum_musteriler)} müşteri için Mizan raporu oluşturulacak.\n\n"
            "Bu işlem biraz sürebilir. Devam etmek istiyor musunuz?",
        )
        if not onay:
            return

        self._mesgul_baslat(f"{len(tum_musteriler)} müşteri için toplu rapor oluşturuluyor...")

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

    # ------------------------------------------------------------------
    # Tarayıcıyı kapat
    # ------------------------------------------------------------------

    def _tarayiciyi_kapat(self, sessiz: bool = False) -> None:
        # NOT: self.core.kapat() (Playwright çağrısı) BURADA (ana/Tkinter
        # thread'inde) DOĞRUDAN çağrılMIYOR — Playwright nesnesi
        # OtomasyonWorker thread'inde oluşturulduğu için, aynı "cannot
        # switch to a different thread" hatasına düşmemek adına kapatma
        # işi de o thread'e kuyruklanıyor. self.core hemen (senkron olarak)
        # None yapılıyor ki arayüz durumu doğru yansısın.
        core_kapatilacak = self.core
        self.core = None
        self.secili_kisa_ad = None
        self.rapor_btn.configure(state="disabled")
        self.toplu_rapor_btn.configure(state="disabled")
        self.kapat_btn.configure(state="disabled")
        if not sessiz:
            self._log("Tarayıcı kapatılıyor...")
            self.durum_var.set("Hazır")

        if core_kapatilacak is not None:
            def is_parcasi():
                try:
                    core_kapatilacak.kapat()
                except Exception:
                    pass

            self._is_kuyrugu.put(is_parcasi)

    def _kapatirken(self) -> None:
        _dosyaya_log_yaz("Uygulama penceresi kapatılıyor (kullanıcı tarafından ya da normal çıkış).")
        self._tarayiciyi_kapat(sessiz=True)
        self.destroy()

    # ------------------------------------------------------------------
    # Kuyruk dinleyici (ana thread'de çalışır, Tkinter'a güvenle dokunur)
    # ------------------------------------------------------------------

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
                        self.tablo.insert("", "end", values=(m["kisa_ad"], m["uzun_ad"], m["vergi_dairesi"], m["vergi_no"]))
                    if not musteriler:
                        self._log("UYARI: Filtreyle eşleşen müşteri bulunamadı.")
                    else:
                        self.toplu_rapor_btn.configure(state="normal")
                    self._mesgul_bitir(f"{len(musteriler)} müşteri listelendi. Birini seçip rapor oluşturabilirsiniz.")

                elif tur == "rapor_tamam":
                    dosya = olay[1]
                    if dosya:
                        self._log(f"BAŞARILI: Rapor kaydedildi -> {dosya}")
                        self._mesgul_bitir("Rapor oluşturuldu.")
                    else:
                        self._mesgul_bitir("Rapor kuyruğa alındı (Rapor Takip'ten indirin).")

                elif tur == "toplu_rapor_tamam":
                    sonuclar = olay[1]
                    basarili = sum(1 for s in sonuclar if s["durum"] in ("başarılı", "kuyruğa alındı"))
                    basarisiz = sum(1 for s in sonuclar if s["durum"] == "hatalı")
                    self._log(f"\nTOPLU RAPOR SONUCU: {basarili} başarılı, {basarisiz} hatalı")
                    for s in sonuclar:
                        if s["durum"] == "hatalı":
                            self._log(f"  X {s['kisa_ad']}: {s['hata']}")
                        else:
                            self._log(f"  OK {s['kisa_ad']}: {s['dosya_yolu'] or 'kuyruğa alındı'}")
                    self._mesgul_bitir(f"Toplu rapor tamamlandı ({basarili} başarılı, {basarisiz} hatalı)")

                elif tur == "hata":
                    mesaj, ayrinti = olay[1], olay[2]
                    self._log(f"HATA: {mesaj}")
                    self._log(ayrinti)
                    self._mesgul_bitir("Hata oluştu.")
                    try:
                        messagebox.showerror("Hata", mesaj)
                    except Exception:
                        pass

        except queue.Empty:
            pass
        except Exception as e:
            # Burada beklenmeyen bir şey patlarsa bile (ör. bir widget'a artık
            # erişilemiyor olması) sessizce yutmak yerine dosyaya kaydediyoruz
            # ki pencere kapansa bile sebebi görebilelim; ayrıca "finally"
            # sayesinde döngü yine de devam eder, uygulama burada donmaz.
            _dosyaya_log_yaz(f"KUYRUK İŞLEME HATASI: {e}\n{traceback.format_exc()}")
        finally:
            self.after(120, self._kuyrugu_dinle)


def main() -> None:
    uygulama = LucaGUI()
    uygulama.mainloop()


if __name__ == "__main__":
    main()
