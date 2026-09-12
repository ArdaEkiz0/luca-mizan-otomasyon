#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Luca Mizan Otomasyon - Kapsamli Testler
=========================================
Gercek siteye baglanmadan kod mantigini test eder.
Playwright nesneleri taklit edilir (mock).
"""

import sys
import os
import unittest
import shutil
import tempfile
from unittest.mock import MagicMock, patch, PropertyMock, call, ANY
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from luca_otomasyon_core import LucaOtomasyonCore, SINIF_ETIKETLERI
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


# ============================================================
# MOCK SINIFLARI
# ============================================================

class MockLocator:
    """Mock locator that supports chaining, .count(), .first, .nth(), etc."""
    def __init__(self, count=1, items=None):
        self._count = count
        self._items = items or []
        self.count = MagicMock(return_value=count)
        self.first = MagicMock()
        self.first.click = MagicMock()
        self.first.get_attribute = MagicMock(return_value="")
        self.first.inner_text = MagicMock(return_value="")
        self.first.evaluate = MagicMock(return_value=0)
        self._nth_mocks = {}

    def nth(self, i):
        if i not in self._nth_mocks:
            m = MagicMock()
            m.inner_text = MagicMock(return_value="")
            m.locator.return_value = MockLocator(count=0)
            self._nth_mocks[i] = m
        return self._nth_mocks[i]

    def __getattr__(self, name):
        return MagicMock()


class MockFrame:
    """Mock Playwright Frame. locator(), get_by_text() are MagicMocks
    so tests can set return_value freely."""
    def __init__(self, url="https://test.luca.com.tr/test"):
        self.url = url
        self.locator = MagicMock()
        self.get_by_text = MagicMock()
        self.get_by_role = MagicMock()
        self.wait_for_selector = MagicMock(return_value=True)
        self.wait_for_load_state = MagicMock(return_value=True)
        self.wait_for_timeout = MagicMock(return_value=True)
        self.evaluate = MagicMock(return_value={"bulundu": True, "tag": "button"})
        self.goto = MagicMock(return_value=True)
        self.select_option = MagicMock(return_value=True)

    def _setup_tablo(self, satir_sayisi=3, isimler=None):
        """Test kolaylığı: tablo satırlarını mock'la."""
        if isimler is None:
            isimler = [f"MÜŞTERİ_{i}" for i in range(satir_sayisi)]
        tablo = MagicMock()
        tablo.count.return_value = satir_sayisi
        tablo.first = MagicMock()
        tablo.first.evaluate.return_value = 0
        tablo.first.get_attribute.return_value = ""
        tablo.first.dblclick = MagicMock()
        tablo.first.click = MagicMock()
        for i, isim in enumerate(isimler):
            nth = MagicMock()
            nth.locator.return_value.nth.return_value.inner_text.return_value = isim
            nth.get_attribute.return_value = ""
            tablo.nth = MagicMock(side_effect=lambda i, _n=nth: _n)
        self.locator.return_value = tablo
        return tablo


class MockPage:
    def __init__(self, url="https://test.luca.com.tr/main.erp"):
        self.url = url
        self.frames = []
        self._closed = False

    def goto(self, url, wait_until="domcontentloaded", timeout=30000):
        self.url = url
        return True

    def wait_for_url(self, pattern, timeout=30000):
        return True

    def wait_for_load_state(self, state):
        return True

    def wait_for_timeout(self, ms):
        return True

    def wait_for_function(self, func, timeout=5000):
        return True

    def bring_to_front(self):
        return True

    def go_back(self):
        return True

    def is_closed(self):
        return self._closed

    def content(self):
        return "TEST FİRMA - Müşteri Bilgileri"

    def locator(self, selector):
        mock = MagicMock()
        mock.count.return_value = 1
        mock.first = MagicMock()
        mock.fill = MagicMock()
        return mock

    def get_by_text(self, text, exact=False):
        mock = MagicMock()
        mock.first = MagicMock()
        mock.count.return_value = 1
        return mock

    def evaluate(self, code, *args):
        return {"bulundu": True, "tag": "button"}

    def expect_download(self, timeout=20000):
        mock = MagicMock()
        mock.__enter__ = MagicMock(return_value=mock)
        mock.__exit__ = MagicMock(return_value=False)
        mock.value = MagicMock()
        mock.value.save_as = MagicMock()
        return mock

    def on(self, event, handler):
        pass


class MockBrowser:
    def __init__(self):
        self._closed = False

    def new_context(self, accept_downloads=True):
        return MockContext()

    def close(self):
        self._closed = True


class MockContext:
    def __init__(self):
        self.pages = []
        self._page = MockPage()

    def new_page(self):
        page = MockPage()
        self.pages.append(page)
        return page


class MockPlaywright:
    def __init__(self):
        self.chromium = MagicMock()
        self.chromium.launch.return_value = MockBrowser()

    def start(self):
        return self

    def stop(self):
        pass


# ============================================================
# CORE TESTLERI
# ============================================================

class TestLucaOtomasyonCore(unittest.TestCase):

    def setUp(self):
        self.core = LucaOtomasyonCore(
            uye_no="12345",
            kullanici_adi="test@test.com",
            parola="sifre123",
            cikti_klasoru="test_raporlar",
            headless=True,
        )

    def tearDown(self):
        try:
            self.core.kapat()
        except Exception:
            pass

    def test_sinif_etiketleri_dogru_mu(self):
        self.assertEqual(SINIF_ETIKETLERI[""], "Tümü")
        self.assertEqual(SINIF_ETIKETLERI["1"], "1.Sınıf")
        self.assertEqual(SINIF_ETIKETLERI["2"], "2.Sınıf")
        self.assertEqual(SINIF_ETIKETLERI["3"], "İşletme Defteri")
        self.assertEqual(SINIF_ETIKETLERI["4"], "Serbest Meslek Defteri")
        self.assertEqual(SINIF_ETIKETLERI["5"], "Basit Usül")

    def test_core_baslangic_durumu(self):
        self.assertEqual(self.core.uye_no, "12345")
        self.assertEqual(self.core.kullanici_adi, "test@test.com")
        self.assertEqual(self.core.parola, "sifre123")
        self.assertIsNone(self.core.dashboard)
        self.assertIsNone(self.core.liste_frame)

    def test_cikti_klasoru_olusturma(self):
        self.assertEqual(self.core.cikti_klasoru, Path("test_raporlar"))

    def test_cikti_klasoru_string_path(self):
        core = LucaOtomasyonCore("1", "a", "b", cikti_klasoru="/tmp/test_output")
        self.assertEqual(core.cikti_klasoru, Path("/tmp/test_output"))

    def test_bos_bilgilerle_baslat(self):
        core = LucaOtomasyonCore("", "", "", cikti_klasoru="test")
        self.assertEqual(core.uye_no, "")
        self.assertEqual(core.kullanici_adi, "")
        self.assertEqual(core.parola, "")


# ============================================================
# musteri_sec TESTLERI (yeni sec() + gonder() mekanizması)
# ============================================================

class TestMusteriSec(unittest.TestCase):
    """musteri_sec fonksiyonunun detaylı testleri."""

    def setUp(self):
        self.core = LucaOtomasyonCore(
            uye_no="12345",
            kullanici_adi="test@test.com",
            parola="sifre123",
            cikti_klasoru="test_raporlar",
            headless=True,
        )
        self.mock_page = MockPage()
        self.mock_frame = MockFrame()
        self.mock_page.frames = [self.mock_frame]
        self.core.dashboard = self.mock_page
        self.core._context = MockContext()
        self.core._context.pages = [self.mock_page]
        self.core._musteri_listesi_sayfasi = self.mock_page
        self.core._son_yil = "2026"
        self.core._son_sinif = "1"
        self.core.liste_frame = self.mock_frame
        self.core._frame_bul = MagicMock(return_value=self.mock_frame)

    def _setup_tablo(self, satir_sayisi, eslesme_sayisi=1, satir_ontcik=""):
        """Tabloyu mock'la. locator() iki kez çağrılır: count ve has_text."""
        tablo = MagicMock()
        tablo.count.return_value = satir_sayisi

        satir = MagicMock()
        satir.get_attribute.return_value = satir_ontcik
        satir.evaluate.return_value = 0  # satır index

        eslesme = MagicMock()
        eslesme.count.return_value = eslesme_sayisi
        eslesme.first = satir

        call_sayac = [0]
        def locator_side_effect(selector, **kwargs):
            call_sayac[0] += 1
            if call_sayac[0] == 1:
                return tablo  # İlk çağrı: count için
            return eslesme  # Sonraki çağrılar: has_text için

        self.mock_frame.locator = MagicMock(side_effect=locator_side_effect)
        return tablo, eslesme, satir

    def test_musteri_sec_basarili_sec_gonder_akisi(self):
        """sec() + gonder('guncelle') akışının doğru çağrılmasını test et."""
        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        _, _, satir = self._setup_tablo(3, 1, "sec(this, '111', 'TEST FİRMA', '222', '333', '');")

        def mock_evaluate(code, *args):
            if "sec(" in code:
                return {"ok": True, "onclick": "sec(this, '111', 'TEST FİRMA', '222', '333', '');"}
            if "gonder" in code:
                return {"ok": True}
            return {"ok": True}
        self.mock_frame.evaluate = mock_evaluate

        self.core.musteri_sec("TEST FİRMA", log=log_fn)

        self.assertTrue(any("sec()" in m for m in log_messages),
                        f"sec() log'u bulunamadı. Loglar: {log_messages}")
        self.assertTrue(any("gonder" in m for m in log_messages),
                        f"gonder() log'u bulunamadı. Loglar: {log_messages}")

    def test_musteri_sec_tablo_bos_hata(self):
        """Tablo boşsa hata fırlatmalı."""
        self._setup_tablo(0, 0)

        with self.assertRaises(RuntimeError) as ctx:
            self.core.musteri_sec("OLMAYAN FİRMA", log=lambda m: None)
        self.assertIn("hiç satır yok", str(ctx.exception))

    def test_musteri_sec_musteri_bulunamadi_hata(self):
        """Tabloda müşteri yoksa hata fırlatmalı."""
        isimler = ["FİRMA A", "FİRMA B", "FİRMA C", "FİRMA D", "FİRMA E"]

        # locator() çağrısı: ilki count için (satir_sayisi=5), ikincisi has_text için (0)
        call_sayac = [0]
        tablo_mock = MagicMock()
        tablo_mock.count.return_value = 5

        eslesme_mock = MagicMock()
        eslesme_mock.count.return_value = 0  # eşleşme yok!

        def mock_locator(selector, **kwargs):
            call_sayac[0] += 1
            if "has_text" in kwargs or call_sayac[0] > 1:
                return eslesme_mock
            return tablo_mock
        self.mock_frame.locator = MagicMock(side_effect=mock_locator)

        def mock_evaluate(code, *args):
            if "indexOf" in code:
                return 0
            return isimler
        self.mock_frame.evaluate = mock_evaluate

        with self.assertRaises(RuntimeError) as ctx:
            self.core.musteri_sec("OLMAYAN", log=lambda m: None)
        self.assertIn("OLMAYAN", str(ctx.exception))

    def test_musteri_sec_double_click_fallback(self):
        """sec() fonksiyonu bulunamazsa double-click denenmeli."""
        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        _, _, satir = self._setup_tablo(3, 1, "")

        self.core.musteri_sec("TEST FİRMA", log=log_fn)
        satir.dblclick.assert_called()

    def test_musteri_sec_tum_yontemler_basarisiz_hata(self):
        """Hiçbir tıklama yöntemi çalışmazsa hata fırlatmalı."""
        _, _, satir = self._setup_tablo(3, 1, "")
        satir.dblclick.side_effect = Exception("dblclick failed")
        satir.click.side_effect = Exception("click failed")

        with self.assertRaises(RuntimeError) as ctx:
            self.core.musteri_sec("TEST FİRMA", log=lambda m: None)
        self.assertIn("hiç bir tıklama yöntemi çalışmadı", str(ctx.exception))

    def test_musteri_sec_dogrulama_basarisiz_uyari(self):
        """Doğrulama başarısızsa uyarı loglanmalı."""
        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        self._setup_tablo(3, 1, "sec(this, '111', 'TEST', '222', '333', '');")
        self.mock_page.frames = []
        self.mock_page.content = MagicMock(return_value="Boş sayfa")

        def mock_evaluate(code, *args):
            if "sec(" in code:
                return {"ok": True}
            if "gonder" in code:
                return {"ok": True}
            return {"ok": True}
        self.mock_frame.evaluate = mock_evaluate

        self.core.musteri_sec("TEST", log=log_fn)
        self.assertTrue(any("UYARI" in m and "doğrulanamadı" in m for m in log_messages),
                        f"Doğrulama uyarısı bulunamadı. Loglar: {log_messages}")

    def test_musteri_sec_url_degisikligi_bekleme(self):
        """URL değişikliği sonrası bekleme ve kontrol."""
        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        self._setup_tablo(3, 1, "sec(this, '111', 'TEST', '222', '333', '');")
        self.mock_page.url = "https://test.luca.com.tr/Luca/musteriListesi.do"

        def mock_evaluate(code, *args):
            if "sec(" in code:
                return {"ok": True}
            if "gonder" in code:
                return {"ok": True}
            return {"ok": True}
        self.mock_frame.evaluate = mock_evaluate

        self.core.musteri_sec("TEST", log=log_fn)
        self.assertTrue(any("Sayfa yönlendirildi" in m or "musteriBilgileri" in m
                            or "sayfa içeriğinde" in m or "UYARI" in m
                            for m in log_messages),
                        f"URL/değişiklik log'u bulunamadı. Loglar: {log_messages}")

    def test_musteri_sec_redirect_sonrasi_basarili(self):
        """URL değişikliği olduktan sonra başarılı doğrulama."""
        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        self._setup_tablo(3, 1, "sec(this, '111', 'TEST', '222', '333', '');")

        # sec()+gonder() çağrıldığında URL değişsin diye evaluate side_effect
        baslangic_url = self.mock_page.url
        def mock_evaluate(code, *args):
            if "sec(" in code:
                return {"ok": True}
            if "gonder" in code:
                # gonder() çağrıldığında URL'i değiştir
                self.mock_page.url = "https://test.luca.com.tr/Luca/musteriBilgileri.do?something"
                return {"ok": True}
            return {"ok": True}
        self.mock_frame.evaluate = mock_evaluate

        self.core.musteri_sec("TEST", log=log_fn)
        # URL değiştiği için "Sayfa yönlendirildi" log'u olmalı
        self.assertTrue(any("Sayfa yönlendirildi" in m for m in log_messages),
                        f"Sayfa yönlendirildi log'u bulunamadı. Loglar: {log_messages}")

    def test_musteri_sec_uzun_ad_secimi(self):
        """Uzun müşteri adlarıyla çalışma testi."""
        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        uzun_ad = "ÇOK UZUN MÜŞTERİ ADI A.Ş. SANAYİ VE TİCARET LİMİTED ŞİRKETİ"
        self._setup_tablo(1, 1, f"sec(this, '999', '{uzun_ad}', '111', '222', '');")

        def mock_evaluate(code, *args):
            if "sec(" in code:
                return {"ok": True}
            if "gonder" in code:
                return {"ok": True}
            return {"ok": True}
        self.mock_frame.evaluate = mock_evaluate

        self.core.musteri_sec(uzun_ad, log=log_fn)
        self.assertTrue(any("sec()" in m for m in log_messages))


# ============================================================
# musteri_kartina_don TESTLERI
# ============================================================

class TestMusteriKartinaDon(unittest.TestCase):

    def setUp(self):
        self.core = LucaOtomasyonCore(
            uye_no="12345",
            kullanici_adi="test@test.com",
            parola="sifre123",
            cikti_klasoru="test_raporlar",
            headless=True,
        )
        self.mock_page = MockPage()
        mock_frame = MockFrame()
        self.mock_page.frames = [mock_frame]
        self.core.dashboard = self.mock_page
        self.core._context = MockContext()
        self.core._context.pages = [self.mock_page]
        self.core._musteri_listesi_sayfasi = self.mock_page
        self.core._son_yil = "2026"
        self.core._son_sinif = "1"
        self.core.liste_frame = mock_frame
        self.core._frame_bul = MagicMock(return_value=mock_frame)
        self.core._rol_buton_tikla = MagicMock()

    @patch('luca_otomasyon_core.sync_playwright')
    def test_musteri_kartina_don_url_ile_donme(self, mock_pw):
        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        self.core._filtreleri_uygula = MagicMock()
        self.core.musteri_kartina_don(log=log_fn)

        self.assertTrue(any("Doğrudan URL ile müşteri listesine dönüldü" in m for m in log_messages))
        self.core._filtreleri_uygula.assert_called_once()

    @patch('luca_otomasyon_core.sync_playwright')
    def test_musteri_kartina_don_filtre_uygulama(self, mock_pw):
        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        self.core._filtreleri_uygula = MagicMock()
        self.core.musteri_kartina_don(log=log_fn)

        self.core._filtreleri_uygula.assert_called_once_with(log_fn)

    def test_musteri_kartina_don_dashboard_yoksa(self):
        core = LucaOtomasyonCore("1", "a", "b")
        with self.assertRaises(RuntimeError):
            core.musteri_kartina_don()

    def test_musteri_kartina_don_url_dogru_mu(self):
        """Navigasyon URL'sinin doğru olduğunu doğrula."""
        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        self.core._filtreleri_uygula = MagicMock()
        self.core.musteri_kartina_don(log=log_fn)

        # URL'nin listSirketAction.do içermesi gerekir
        self.assertIn("listSirketAction.do", self.mock_page.url)

    def test_musteri_kartina_don_filtre_sonrasi_frame(self):
        """Filtre uygulandıktan sonra frame'in bulunduğunu doğrula."""
        self.core._filtreleri_uygula = MagicMock()
        self.core.musteri_kartina_don(log=lambda m: None)

        self.core._filtreleri_uygula.assert_called_once()


# ============================================================
# _filtreleri_uygula TESTLERI
# ============================================================

class TestFiltreleriUygula(unittest.TestCase):

    def setUp(self):
        self.core = LucaOtomasyonCore(
            uye_no="12345",
            kullanici_adi="test@test.com",
            parola="sifre123",
            cikti_klasoru="test_raporlar",
            headless=True,
        )
        self.mock_frame = MockFrame()
        self.core.liste_frame = self.mock_frame
        self.core._son_yil = "2026"
        self.core._son_sinif = "1"
        self.core.dashboard = MockPage()

    def test_filtre_yil_sinif_uygulama(self):
        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        self.core._rol_buton_tikla = MagicMock()
        self.core._frame_bul = MagicMock(return_value=self.mock_frame)

        self.core._filtreleri_uygula(log_fn)

        self.assertIn("Filtre uygulanıyor", log_messages[0])
        self.assertIn("2026", log_messages[0])

    def test_filtre_farkli_yil(self):
        self.core._son_yil = "2025"
        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        self.core._rol_buton_tikla = MagicMock()
        self.core._frame_bul = MagicMock(return_value=self.mock_frame)

        self.core._filtreleri_uygula(log_fn)

        self.assertIn("2025", log_messages[0])

    def test_filtre_frame_bulunamaz_hata(self):
        """Frame bulunamazsa hata loglanmalı."""
        self.core._frame_bul = MagicMock(side_effect=RuntimeError("Frame bulunamadı"))
        self.core._rol_buton_tikla = MagicMock()

        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        self.core._filtreleri_uygula(log_fn)

        # Hata loglanmış olmalı
        self.assertTrue(any("HATA" in m or "bulunamadı" in m for m in log_messages))

    def test_filtre_paneli_acilamaz_hata(self):
        """Filtre paneli açılamazsa hata loglanmalı."""
        self.core._frame_bul = MagicMock(return_value=self.mock_frame)
        self.core._rol_buton_tikla = MagicMock(side_effect=PlaywrightTimeoutError("Timeout"))

        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        self.core._filtreleri_uygula(log_fn)

        self.assertTrue(any("HATA" in m for m in log_messages))

    def test_filtre_yil_secilemez_hata(self):
        """Yıl seçilemezse hata loglanmalı."""
        self.core._frame_bul = MagicMock(return_value=self.mock_frame)
        self.core._rol_buton_tikla = MagicMock()
        self.mock_frame.locator.return_value.select_option.side_effect = Exception("Select failed")

        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        self.core._filtreleri_uygula(log_fn)

        self.assertTrue(any("HATA" in m for m in log_messages))


# ============================================================
# toplu_mizan_raporu TESTLERI
# ============================================================

class TestTopluMizanRaporu(unittest.TestCase):

    def setUp(self):
        self.core = LucaOtomasyonCore(
            uye_no="12345",
            kullanici_adi="test@test.com",
            parola="sifre123",
            cikti_klasoru="test_raporlar",
            headless=True,
        )
        self.mock_page = MockPage()
        self.core.dashboard = self.mock_page
        self.core._context = MockContext()
        self.core._context.pages = [self.mock_page]
        self.core._musteri_listesi_sayfasi = self.mock_page
        self.core._son_yil = "2026"
        self.core._son_sinif = "1"
        self.core.liste_frame = MockFrame()
        self.core.cikti_klasoru = Path("test_raporlar")

    @patch('luca_otomasyon_core.sync_playwright')
    def test_tek_musteri_rapor(self, mock_pw):
        musteriler = [
            {"kisa_ad": "TEST FİRMA", "uzun_ad": "Test Firma A.Ş.", "vergi_dairesi": "İstanbul", "vergi_no": "1234567890"}
        ]

        self.core.musteri_sec = MagicMock()
        self.core.mizan_raporu_olustur = MagicMock(return_value=Path("test_raporlar/TEST FİRMA_Mizan_2026.xlsx"))
        self.core.musteri_kartina_don = MagicMock()
        self.core._filtreleri_uygula = MagicMock()

        sonuclar = self.core.toplu_mizan_raporu(musteriler, log=lambda m: None)

        self.assertEqual(len(sonuclar), 1)
        self.assertEqual(sonuclar[0]["durum"], "başarılı")
        self.core.musteri_sec.assert_called_once()
        self.core.mizan_raporu_olustur.assert_called_once()

    @patch('luca_otomasyon_core.sync_playwright')
    def test_iki_musteri_rapor(self, mock_pw):
        musteriler = [
            {"kisa_ad": "FİRMA A", "uzun_ad": "Firma A A.Ş.", "vergi_dairesi": "İstanbul", "vergi_no": "111"},
            {"kisa_ad": "FİRMA B", "uzun_ad": "Firma B A.Ş.", "vergi_dairesi": "Ankara", "vergi_no": "222"},
        ]

        self.core.musteri_sec = MagicMock()
        self.core.mizan_raporu_olustur = MagicMock(return_value=Path("test.xlsx"))
        self.core.musteri_kartina_don = MagicMock()
        self.core._filtreleri_uygula = MagicMock()

        sonuclar = self.core.toplu_mizan_raporu(musteriler, log=lambda m: None)

        self.assertEqual(len(sonuclar), 2)
        self.assertEqual(sonuclar[0]["durum"], "başarılı")
        self.assertEqual(sonuclar[1]["durum"], "başarılı")
        self.core.musteri_kartina_don.assert_called_once()

    @patch('luca_otomasyon_core.sync_playwright')
    def test_hatali_musteri_sonraki_devam(self, mock_pw):
        musteriler = [
            {"kisa_ad": "HATALI", "uzun_ad": "Hatalı Firma", "vergi_dairesi": "X", "vergi_no": "1"},
            {"kisa_ad": "İYİ", "uzun_ad": "İyi Firma", "vergi_dairesi": "Y", "vergi_no": "2"},
        ]

        call_count = [0]
        def mock_musteri_sec(kisa_ad, log=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Test hatası")
            return None

        self.core.musteri_sec = mock_musteri_sec
        self.core.mizan_raporu_olustur = MagicMock(return_value=Path("test.xlsx"))
        self.core.musteri_kartina_don = MagicMock()
        self.core._filtreleri_uygula = MagicMock()

        sonuclar = self.core.toplu_mizan_raporu(musteriler, log=lambda m: None)

        self.assertEqual(len(sonuclar), 2)
        self.assertEqual(sonuclar[0]["durum"], "hatalı")
        self.assertEqual(sonuclar[1]["durum"], "başarılı")

    @patch('luca_otomasyon_core.sync_playwright')
    def test_kurtarma_mekanizmasi(self, mock_pw):
        musteriler = [
            {"kisa_ad": "FİRMA A", "uzun_ad": "Test", "vergi_dairesi": "X", "vergi_no": "1"},
            {"kisa_ad": "FİRMA B", "uzun_ad": "Test", "vergi_dairesi": "Y", "vergi_no": "2"},
        ]

        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        self.core.musteri_sec = MagicMock()
        self.core.mizan_raporu_olustur = MagicMock(return_value=Path("test.xlsx"))

        don_sayac = [0]
        def mock_don(log=None):
            don_sayac[0] += 1
            if don_sayac[0] == 1:
                raise RuntimeError("Listeye dönülemedi")

        self.core.musteri_kartina_don = mock_don
        self.core._filtreleri_uygula = MagicMock()

        self.core.dashboard.goto = MagicMock()
        self.core._frame_bul = MagicMock(return_value=self.core.liste_frame)
        self.core.liste_frame.wait_for_selector = MagicMock()

        sonuclar = self.core.toplu_mizan_raporu(musteriler, log=log_fn)

        self.assertEqual(len(sonuclar), 2)
        self.assertTrue(any("Kurtarma başarılı" in m for m in log_messages))

    @patch('luca_otomasyon_core.sync_playwright')
    def test_uc_musteri_rapor(self, mock_pw):
        musteriler = [
            {"kisa_ad": "A", "uzun_ad": "A A.Ş.", "vergi_dairesi": "X", "vergi_no": "1"},
            {"kisa_ad": "B", "uzun_ad": "B A.Ş.", "vergi_dairesi": "Y", "vergi_no": "2"},
            {"kisa_ad": "C", "uzun_ad": "C A.Ş.", "vergi_dairesi": "Z", "vergi_no": "3"},
        ]

        self.core.musteri_sec = MagicMock()
        self.core.mizan_raporu_olustur = MagicMock(return_value=Path("test.xlsx"))
        self.core.musteri_kartina_don = MagicMock()
        self.core._filtreleri_uygula = MagicMock()

        sonuclar = self.core.toplu_mizan_raporu(musteriler, log=lambda m: None)

        self.assertEqual(len(sonuclar), 3)
        for s in sonuclar:
            self.assertEqual(s["durum"], "başarılı")
        self.assertEqual(self.core.musteri_kartina_don.call_count, 2)

    @patch('luca_otomasyon_core.sync_playwright')
    def test_ilerleme_cb_dogru_parametreler(self, mock_pw):
        """İlerleme callback'inin doğru parametrelerle çağrılmasını test et."""
        musteriler = [
            {"kisa_ad": "A", "uzun_ad": "A", "vergi_dairesi": "X", "vergi_no": "1"},
            {"kisa_ad": "B", "uzun_ad": "B", "vergi_dairesi": "Y", "vergi_no": "2"},
        ]

        self.core.musteri_sec = MagicMock()
        self.core.mizan_raporu_olustur = MagicMock(return_value=Path("test.xlsx"))
        self.core.musteri_kartina_don = MagicMock()
        self.core._filtreleri_uygula = MagicMock()

        cb_sayac = [0]
        cb_argumanlar = []
        def ilerleme_cb(mevcut, toplam, musteri):
            cb_sayac[0] += 1
            cb_argumanlar.append((mevcut, toplam, musteri["kisa_ad"]))

        self.core.toplu_mizan_raporu(musteriler, log=lambda m: None, ilerleme_cb=ilerleme_cb)

        self.assertEqual(cb_sayac[0], 2)
        self.assertEqual(cb_argumanlar[0], (0, 2, "A"))
        self.assertEqual(cb_argumanlar[1], (1, 2, "B"))

    @patch('luca_otomasyon_core.sync_playwright')
    def test_tum_musteriler_hatali(self, mock_pw):
        """Tüm müşteriler hatalıysa hepsi 'hatalı' dönmeli."""
        musteriler = [
            {"kisa_ad": "X", "uzun_ad": "X", "vergi_dairesi": "X", "vergi_no": "1"},
            {"kisa_ad": "Y", "uzun_ad": "Y", "vergi_dairesi": "Y", "vergi_no": "2"},
        ]

        self.core.musteri_sec = MagicMock(side_effect=RuntimeError("Hata"))
        self.core.mizan_raporu_olustur = MagicMock()
        self.core.musteri_kartina_don = MagicMock()
        self.core._filtreleri_uygula = MagicMock()
        self.core.dashboard.goto = MagicMock()
        self.core._frame_bul = MagicMock(return_value=self.core.liste_frame)
        self.core.liste_frame.wait_for_selector = MagicMock()

        sonuclar = self.core.toplu_mizan_raporu(musteriler, log=lambda m: None)

        self.assertEqual(len(sonuclar), 2)
        for s in sonuclar:
            self.assertEqual(s["durum"], "hatalı")

    @patch('luca_otomasyon_core.sync_playwright')
    def test_mizan_raporu_none_dondurur(self, mock_pw):
        """mizan_raporu_olustur None döndürürse durum 'kuyruğa alındı' olmalı."""
        musteriler = [
            {"kisa_ad": "A", "uzun_ad": "A", "vergi_dairesi": "X", "vergi_no": "1"},
        ]

        self.core.musteri_sec = MagicMock()
        self.core.mizan_raporu_olustur = MagicMock(return_value=None)
        self.core.musteri_kartina_don = MagicMock()
        self.core._filtreleri_uygula = MagicMock()

        sonuclar = self.core.toplu_mizan_raporu(musteriler, log=lambda m: None)

        self.assertEqual(len(sonuclar), 1)
        self.assertEqual(sonuclar[0]["durum"], "kuyruğa alındı")

    @patch('luca_otomasyon_core.sync_playwright')
    def test_siralama_korunur(self, mock_pw):
        """Müşteri sıralaması sonuçlarda korunmalı."""
        musteriler = [
            {"kisa_ad": "Z", "uzun_ad": "Z", "vergi_dairesi": "X", "vergi_no": "1"},
            {"kisa_ad": "A", "uzun_ad": "A", "vergi_dairesi": "Y", "vergi_no": "2"},
            {"kisa_ad": "M", "uzun_ad": "M", "vergi_dairesi": "Z", "vergi_no": "3"},
        ]

        self.core.musteri_sec = MagicMock()
        self.core.mizan_raporu_olustur = MagicMock(return_value=Path("test.xlsx"))
        self.core.musteri_kartina_don = MagicMock()
        self.core._filtreleri_uygula = MagicMock()

        sonuclar = self.core.toplu_mizan_raporu(musteriler, log=lambda m: None)

        self.assertEqual(sonuclar[0]["kisa_ad"], "Z")
        self.assertEqual(sonuclar[1]["kisa_ad"], "A")
        self.assertEqual(sonuclar[2]["kisa_ad"], "M")


# ============================================================
# Edge Cases TESTLERI
# ============================================================

class TestEdgeCases(unittest.TestCase):

    def test_bos_musteri_listesi(self):
        core = LucaOtomasyonCore("1", "a", "b")
        core.dashboard = MockPage()
        core._context = MockContext()
        core._context.pages = [core.dashboard]
        core.liste_frame = MockFrame()
        core._son_yil = "2026"
        core._son_sinif = "1"

        sonuclar = core.toplu_mizan_raporu([], log=lambda m: None)
        self.assertEqual(len(sonuclar), 0)

    def test_dashboard_yoksa_hata(self):
        core = LucaOtomasyonCore("1", "a", "b")
        with self.assertRaises(RuntimeError):
            core.musteri_kartina_don()

    def test_mizan_raporu_olustur_dashboard_yoksa(self):
        core = LucaOtomasyonCore("1", "a", "b")
        with self.assertRaises(RuntimeError):
            core.mizan_raporu_olustur("test")

    def test_tek_musteri_kurtarma_basarisiz(self):
        core = LucaOtomasyonCore("1", "a", "b")
        core.dashboard = MockPage()
        core._context = MockContext()
        core._context.pages = [core.dashboard]
        core.liste_frame = MockFrame()
        core._son_yil = "2026"
        core._son_sinif = "1"
        core.cikti_klasoru = Path("test_raporlar")

        musteriler = [
            {"kisa_ad": "A", "uzun_ad": "A", "vergi_dairesi": "X", "vergi_no": "1"},
        ]

        core.musteri_sec = MagicMock()
        core.mizan_raporu_olustur = MagicMock(return_value=Path("test.xlsx"))
        core.musteri_kartina_don = MagicMock(side_effect=RuntimeError("Dönülemedi"))
        core._filtreleri_uygula = MagicMock()
        core._frame_bul = MagicMock(return_value=core.liste_frame)
        core.liste_frame.wait_for_selector = MagicMock()
        core.dashboard.goto = MagicMock()

        sonuclar = core.toplu_mizan_raporu(musteriler, log=lambda m: None)

        self.assertEqual(len(sonuclar), 1)
        self.assertEqual(sonuclar[0]["durum"], "başarılı")

    def test_musteri_sec_liste_frame_yoksa_hata(self):
        """liste_frame None ise hata fırlatmalı."""
        core = LucaOtomasyonCore("1", "a", "b")
        core.dashboard = MockPage()
        core.liste_frame = None

        with self.assertRaises(RuntimeError) as ctx:
            core.musteri_sec("TEST", log=lambda m: None)
        self.assertIn("baslat_ve_filtrele", str(ctx.exception))

    def test_musteri_sec_birden_fazla_eslesme(self):
        """Birden fazla eşleşme olursa ilki seçilmeli."""
        core = LucaOtomasyonCore("1", "a", "b")
        core.dashboard = MockPage()
        core._context = MockContext()
        core._context.pages = [core.dashboard]
        core.liste_frame = MockFrame()
        core._son_yil = "2026"
        core._son_sinif = "1"
        core._frame_bul = MagicMock(return_value=core.liste_frame)

        satir_mock = MagicMock()
        satir_mock.get_attribute.return_value = "sec(this, '111', 'TEST', '222', '333', '');"
        eslesme_mock = MagicMock()
        eslesme_mock.count.return_value = 3  # 3 eşleşme
        eslesme_mock.first = satir_mock
        eslesme_mock.first.evaluate.return_value = 0
        core.liste_frame.locator.return_value = eslesme_mock

        def mock_evaluate(code, *args):
            if "sec(" in code:
                return {"ok": True, "onclick": "sec(this, '111', 'TEST', '222', '333', '');"}
            if "gonder" in code:
                return {"ok": True}
            return {"ok": True}
        core.liste_frame.evaluate = mock_evaluate

        log_messages = []
        core.musteri_sec("TEST", log=lambda m: log_messages.append(m))

        # sec() çağrıldı mı?
        self.assertTrue(any("sec()" in m for m in log_messages))


# ============================================================
# GUI IMPORT TESTLERI
# ============================================================

class TestGuiImports(unittest.TestCase):

    def test_gui_modulunu_import_et(self):
        import gui_app
        self.assertTrue(hasattr(gui_app, 'LucaGUI'))
        self.assertTrue(hasattr(gui_app, 'main'))

    def test_env_yukle(self):
        from gui_app import _env_yukle
        ayar = _env_yukle()
        self.assertIn("uye_no", ayar)
        self.assertIn("kullanici_adi", ayar)
        self.assertIn("parola", ayar)
        self.assertIn("yil", ayar)
        self.assertIn("sinif", ayar)

    def test_siniflar_tanimli(self):
        from gui_app import SINIFLAR
        self.assertIsInstance(SINIFLAR, list)
        self.assertTrue(len(SINIFLAR) > 0)
        for kod, etiket in SINIFLAR:
            self.assertIsInstance(kod, str)
            self.assertIsInstance(etiket, str)


# ============================================================
# DOSYA İŞLEMLERİ TESTLERİ
# ============================================================

class TestDosyaIslemleri(unittest.TestCase):

    def setUp(self):
        self.test_dizin = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.test_dizin, ignore_errors=True)

    def test_log_dosyasi_yazma(self):
        from gui_app import _dosyaya_log_yaz
        test_log = self.test_dizin / "test_log.txt"

        import gui_app
        eski_log = gui_app.LOG_DOSYASI
        gui_app.LOG_DOSYASI = test_log

        _dosyaya_log_yaz("Test mesaji")
        self.assertTrue(test_log.exists())

        icerik = test_log.read_text(encoding="utf-8")
        self.assertIn("Test mesaji", icerik)

        gui_app.LOG_DOSYASI = eski_log

    def test_env_kaydet(self):
        from gui_app import _env_kaydet
        env_dosya = self.test_dizin / ".env"

        import gui_app
        eski_env = gui_app.ENV_PATH
        gui_app.ENV_PATH = env_dosya

        _env_kaydet("12345", "test@test.com", "sifre123", "2026", "1")
        self.assertTrue(env_dosya.exists())

        icerik = env_dosya.read_text(encoding="utf-8")
        self.assertIn("12345", icerik)
        self.assertIn("test@test.com", icerik)

        gui_app.ENV_PATH = eski_env

    def test_log_dosyasi_zaman_damgasi(self):
        """Log dosyasına zaman damgası eklenmeli."""
        from gui_app import _dosyaya_log_yaz
        test_log = self.test_dizin / "test_log2.txt"

        import gui_app
        eski_log = gui_app.LOG_DOSYASI
        gui_app.LOG_DOSYASI = test_log

        _dosyaya_log_yaz("Zaman testi")
        icerik = test_log.read_text(encoding="utf-8")
        # Tarih formatı: YYYY-MM-DD HH:MM:SS
        self.assertRegex(icerik, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")

        gui_app.LOG_DOSYASI = eski_log

    def test_env_kaydet_tum_alanlar(self):
        """ENV kaydetme tüm alanları içermeli."""
        from gui_app import _env_kaydet
        env_dosya = self.test_dizin / ".env_tum"

        import gui_app
        eski_env = gui_app.ENV_PATH
        gui_app.ENV_PATH = env_dosya

        _env_kaydet("99999", "admin@firma.com", "gucluSifre42", "2025", "3")
        icerik = env_dosya.read_text(encoding="utf-8")

        self.assertIn("99999", icerik)
        self.assertIn("admin@firma.com", icerik)
        self.assertIn("gucluSifre42", icerik)
        self.assertIn("2025", icerik)
        self.assertIn("3", icerik)

        gui_app.ENV_PATH = eski_env


# ============================================================
# _frame_bul TESTLERİ
# ============================================================

class TestFrameBul(unittest.TestCase):

    def test_frame_buldu(self):
        core = LucaOtomasyonCore("1", "a", "b")
        mock_frame = MockFrame()
        mock_frame.locator = MagicMock()
        mock_frame.locator.return_value.count.return_value = 1

        mock_page = MockPage()
        mock_page.frames = [mock_frame]

        result = core._frame_bul(mock_page, "#YIL", deneme=3, bekleme_ms=10)
        self.assertEqual(result, mock_frame)

    def test_frame_bulamadi(self):
        core = LucaOtomasyonCore("1", "a", "b")
        mock_frame = MockFrame()
        mock_frame.locator = MagicMock()
        mock_frame.locator.return_value.count.return_value = 0

        mock_page = MockPage()
        mock_page.frames = [mock_frame]

        with self.assertRaises(RuntimeError):
            core._frame_bul(mock_page, "#YIL", deneme=2, bekleme_ms=10)

    def test_frame_coklu_frame_arasinda_bulur(self):
        """Birden fazla frame varsa doğru olanı bulmalı."""
        core = LucaOtomasyonCore("1", "a", "b")

        frame1 = MockFrame(url="https://test.luca.com.tr/first")
        frame1.locator.return_value.count.return_value = 0

        frame2 = MockFrame(url="https://test.luca.com.tr/second")
        frame2.locator.return_value.count.return_value = 1

        mock_page = MockPage()
        mock_page.frames = [frame1, frame2]

        result = core._frame_bul(mock_page, "#YIL", deneme=3, bekleme_ms=10)
        self.assertEqual(result, frame2)

    def test_frame_bul_seçenekli_hata_mesaji(self):
        """Frame bulunamadığında hata mesajında selector yer almalı."""
        core = LucaOtomasyonCore("1", "a", "b")
        mock_frame = MockFrame()
        mock_frame.locator.return_value.count.return_value = 0

        mock_page = MockPage()
        mock_page.frames = [mock_frame]

        with self.assertRaises(RuntimeError) as ctx:
            core._frame_bul(mock_page, "#FARKLI_SELECTOR", deneme=1, bekleme_ms=10)
        self.assertIn("#FARKLI_SELECTOR", str(ctx.exception))


# ============================================================
# _rol_buton_tikla TESTLERİ
# ============================================================

class TestRolButonTikla(unittest.TestCase):

    def test_birincil_yontem_basarili(self):
        core = LucaOtomasyonCore("1", "a", "b")
        mock_frame = MockFrame()

        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        core._rol_buton_tikla(mock_frame, "Ara", log_fn)

    def test_basarisiz_olunca_hata_firlatir(self):
        core = LucaOtomasyonCore("1", "a", "b")
        mock_frame = MagicMock()
        mock_frame.get_by_role.return_value.click.side_effect = PlaywrightTimeoutError("Timeout")
        mock_frame.get_by_text.return_value.count.return_value = 0
        mock_frame.get_by_text.return_value.first.click.side_effect = Exception("Timeout")

        # JS evaluate de hata versin
        mock_frame.evaluate.return_value = {"bulundu": False}

        # Butun secenekler de hata versin
        mock_locator = MagicMock()
        mock_locator.count.return_value = 0
        mock_frame.locator.return_value = mock_locator

        with self.assertRaises(RuntimeError):
            core._rol_buton_tikla(mock_frame, "OlmayanButon", lambda m: None, birincil_zaman_asimi=100)

    def test_js_yontemi_basarili(self):
        """get_by_role ve get_by_text başarısızsa JS ile denenmeli."""
        core = LucaOtomasyonCore("1", "a", "b")
        mock_frame = MagicMock()
        mock_frame.get_by_role.return_value.click.side_effect = PlaywrightTimeoutError("Timeout")
        mock_frame.get_by_text.return_value.count.return_value = 0

        # locator return_value.count = 0 (yedek secenekler bulamasın)
        mock_frame.locator.return_value.count.return_value = 0

        # JS ile bulundu
        mock_frame.evaluate.return_value = {"bulundu": True, "tag": "button"}

        log_messages = []
        core._rol_buton_tikla(mock_frame, "Rapor", lambda m: log_messages.append(m))

        # JS ile bulundu logu olmalı
        self.assertTrue(any("JS ile" in m or "JS" in m for m in log_messages),
                        f"JS log'u bulunamadı. Loglar: {log_messages}")


# ============================================================
# KAPSAMLI SENARYO TESTLERİ
# ============================================================

class TestKapsamliSenaryolar(unittest.TestCase):
    """Gerçek dünya senaryolarını taklit eden kapsamlı testler."""

    def test_3_musteri_seri_rapor(self):
        """3 müşteri art arda raporlanmalı, her biri bağımsız."""
        core = LucaOtomasyonCore("1", "a", "b", cikti_klasoru="test_raporlar")
        core.dashboard = MockPage()
        core._context = MockContext()
        core._context.pages = [core.dashboard]
        core.liste_frame = MockFrame()
        core._son_yil = "2026"
        core._son_sinif = "1"
        core.cikti_klasoru = Path("test_raporlar")

        musteriler = [
            {"kisa_ad": "ALFA", "uzun_ad": "Alfa A.Ş.", "vergi_dairesi": "İstanbul", "vergi_no": "111"},
            {"kisa_ad": "BETA", "uzun_ad": "Beta A.Ş.", "vergi_dairesi": "Ankara", "vergi_no": "222"},
            {"kisa_ad": "GAMA", "uzun_ad": "Gama A.Ş.", "vergi_dairesi": "İzmir", "vergi_no": "333"},
        ]

        sec_sayac = [0]
        rapor_sayac = [0]
        don_sayac = [0]

        def mock_sec(kisa_ad, log=None):
            sec_sayac[0] += 1
            return None

        def mock_rapor(kisa_ad, log=None):
            rapor_sayac[0] += 1
            return Path(f"test_raporlar/{kisa_ad}_Mizan_2026.xlsx")

        def mock_don(log=None):
            don_sayac[0] += 1
            return None

        core.musteri_sec = mock_sec
        core.mizan_raporu_olustur = mock_rapor
        core.musteri_kartina_don = mock_don
        core._filtreleri_uygula = MagicMock()

        sonuclar = core.toplu_mizan_raporu(musteriler, log=lambda m: None)

        self.assertEqual(sec_sayac[0], 3, "musteri_sec 3 kez çağrılmalı")
        self.assertEqual(rapor_sayac[0], 3, "mizan_raporu_olustur 3 kez çağrılmalı")
        self.assertEqual(don_sayac[0], 2, "musteri_kartina_don 2 kez çağrılmalı (son müşteri hariç)")
        self.assertEqual(len(sonuclar), 3)
        for s in sonuclar:
            self.assertEqual(s["durum"], "başarılı")

    def test_2_musteri_ilk_basarisiz(self):
        """İlk müşteri başarısız, ikincisi başarılı olmalı."""
        core = LucaOtomasyonCore("1", "a", "b")
        core.dashboard = MockPage()
        core._context = MockContext()
        core._context.pages = [core.dashboard]
        core.liste_frame = MockFrame()
        core._son_yil = "2026"
        core._son_sinif = "1"
        core.cikti_klasoru = Path("test_raporlar")

        musteriler = [
            {"kisa_ad": "HATALI", "uzun_ad": "Hatalı", "vergi_dairesi": "X", "vergi_no": "1"},
            {"kisa_ad": "BAŞARILI", "uzun_ad": "Başarılı", "vergi_dairesi": "Y", "vergi_no": "2"},
        ]

        sec_sayac = [0]
        def mock_sec(kisa_ad, log=None):
            sec_sayac[0] += 1
            if kisa_ad == "HATALI":
                raise RuntimeError("Frame detached")
            return None

        core.musteri_sec = mock_sec
        core.mizan_raporu_olustur = MagicMock(return_value=Path("test.xlsx"))
        core.musteri_kartina_don = MagicMock()
        core._filtreleri_uygula = MagicMock()
        core.dashboard.goto = MagicMock()
        core._frame_bul = MagicMock(return_value=core.liste_frame)
        core.liste_frame.wait_for_selector = MagicMock()

        log_messages = []
        sonuclar = core.toplu_mizan_raporu(musteriler, log=lambda m: log_messages.append(m))

        self.assertEqual(len(sonuclar), 2)
        self.assertEqual(sonuclar[0]["durum"], "hatalı")
        self.assertEqual(sonuclar[1]["durum"], "başarılı")
        self.assertEqual(sonuclar[0]["hata"], "Frame detached")
        self.assertEqual(sec_sayac[0], 2)

    def test_dosya_yolu_dogru(self):
        """Oluşturulan dosya yolları doğru formatta olmalı."""
        core = LucaOtomasyonCore("1", "a", "b")
        core.dashboard = MockPage()
        core._context = MockContext()
        core._context.pages = [core.dashboard]
        core.liste_frame = MockFrame()
        core._son_yil = "2026"
        core._son_sinif = "1"
        core.cikti_klasoru = Path("test_raporlar")

        musteriler = [
            {"kisa_ad": "TEST FİRMA", "uzun_ad": "Test Firma A.Ş.", "vergi_dairesi": "İstanbul", "vergi_no": "123"},
        ]

        beklenen_dosya = Path("test_raporlar/TEST FİRMA_Mizan_2026.xlsx")
        core.musteri_sec = MagicMock()
        core.mizan_raporu_olustur = MagicMock(return_value=beklenen_dosya)
        core.musteri_kartina_don = MagicMock()
        core._filtreleri_uygula = MagicMock()

        sonuclar = core.toplu_mizan_raporu(musteriler, log=lambda m: None)

        # dosya_yolu str(Path) olarak kaydedilir
        self.assertEqual(sonuclar[0]["dosya_yolu"], str(beklenen_dosya))

    def test_loglama_sirali_mi(self):
        """Log mesajları doğru sırada mı?"""
        core = LucaOtomasyonCore("1", "a", "b")
        core.dashboard = MockPage()
        core._context = MockContext()
        core._context.pages = [core.dashboard]
        core.liste_frame = MockFrame()
        core._son_yil = "2026"
        core._son_sinif = "1"
        core.cikti_klasoru = Path("test_raporlar")

        musteriler = [
            {"kisa_ad": "A", "uzun_ad": "A", "vergi_dairesi": "X", "vergi_no": "1"},
        ]

        core.musteri_sec = MagicMock()
        core.mizan_raporu_olustur = MagicMock(return_value=Path("test.xlsx"))
        core.musteri_kartina_don = MagicMock()
        core._filtreleri_uygula = MagicMock()

        log_messages = []
        core.toplu_mizan_raporu(musteriler, log=lambda m: log_messages.append(m))

        # İlk mesaj "Toplu rapor" içermeli
        self.assertTrue(any("Toplu rapor" in m for m in log_messages[:3]))


if __name__ == "__main__":
    test_klasor = Path("test_raporlar")
    if test_klasor.exists():
        shutil.rmtree(test_klasor)

    print("=" * 60)
    print("  LUCA MIZAN OTOMASYON - KAPSAMLI TESTLER")
    print("=" * 60)
    print()

    unittest.main(verbosity=2)
