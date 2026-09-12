#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Luca Mizan Otomasyon - Unit Test (Mock ile)
============================================
Gerçek siteye bağlanmadan kod mantığını test eder.
Playwright nesneleri taklit edilir (mock).
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, PropertyMock, call
from pathlib import Path
from typing import Optional

# .env yükle (test ortamı için)
from dotenv import load_dotenv
load_dotenv()

# Test edilecek modülü import et
from luca_otomasyon_core import LucaOtomasyonCore, SINIF_ETIKETLERI


class MockFrame:
    """Playwright Frame nesnesini taklit eder."""
    def __init__(self, url="https://test.luca.com.tr/test"):
        self.url = url
        self._selectors = {}
        self._elements = {}

    def locator(self, selector):
        mock = MagicMock()
        mock.count.return_value = 1
        mock.first = MagicMock()
        mock.nth = MagicMock(return_value=MagicMock())
        return mock

    def get_by_text(self, text, exact=False):
        mock = MagicMock()
        mock.first = MagicMock()
        mock.count.return_value = 1
        return mock

    def get_by_role(self, role, name="", exact=False):
        mock = MagicMock()
        mock.click = MagicMock()
        return mock

    def wait_for_selector(self, selector, state="visible", timeout=10000):
        return True

    def wait_for_load_state(self, state):
        return True

    def wait_for_timeout(self, ms):
        return True

    def evaluate(self, code, *args):
        return {"bulundu": True, "tag": "button"}

    def goto(self, url, wait_until="domcontentloaded", timeout=30000):
        self.url = url
        return True

    def select_option(self, value):
        return True


class MockPage:
    """Playwright Page nesnesini taklit eder."""
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
    """Playwright Browser nesnesini taklit eder."""
    def __init__(self):
        self._closed = False

    def new_context(self, accept_downloads=True):
        return MockContext()

    def close(self):
        self._closed = True


class MockContext:
    """Playwright BrowserContext nesnesini taklit eder."""
    def __init__(self):
        self.pages = []
        self._page = MockPage()

    def new_page(self):
        page = MockPage()
        self.pages.append(page)
        return page


class MockPlaywright:
    """Playwright nesnesini taklit eder."""
    def __init__(self):
        self.chromium = MagicMock()
        self.chromium.launch.return_value = MockBrowser()

    def start(self):
        return self

    def stop(self):
        pass


class TestLucaOtomasyonCore(unittest.TestCase):
    """LucaOtomasyonCore sınıfının temel testleri."""

    def setUp(self):
        """Her test öncesi çalışır."""
        self.core = LucaOtomasyonCore(
            uye_no="12345",
            kullanici_adi="test@test.com",
            parola="sifre123",
            cikti_klasoru="test_raporlar",
            headless=True,
        )

    def tearDown(self):
        """Her test sonrası çalışır."""
        try:
            self.core.kapat()
        except Exception:
            pass

    def test_sınıf_etiketleri_doğru_mu(self):
        """Sınıf etiketleri doğru tanımlanmış mı?"""
        self.assertEqual(SINIF_ETIKETLERI[""], "Tümü")
        self.assertEqual(SINIF_ETIKETLERI["1"], "1.Sınıf")
        self.assertEqual(SINIF_ETIKETLERI["2"], "2.Sınıf")
        self.assertEqual(SINIF_ETIKETLERI["3"], "İşletme Defteri")
        self.assertEqual(SINIF_ETIKETLERI["4"], "Serbest Meslek Defteri")
        self.assertEqual(SINIF_ETIKETLERI["5"], "Basit Usül")

    def test_core_başlangıç_durumu(self):
        """Core nesnesi doğru başlangıç durumunda mı?"""
        self.assertEqual(self.core.uye_no, "12345")
        self.assertEqual(self.core.kullanici_adi, "test@test.com")
        self.assertEqual(self.core.parola, "sifre123")
        self.assertIsNone(self.core.dashboard)
        self.assertIsNone(self.core.liste_frame)

    def test_cikti_klasoru_olusturma(self):
        """Çıktı klasörü doğru oluşturuluyor mu?"""
        self.assertEqual(self.core.cikti_klasoru, Path("test_raporlar"))


class TestMusteriKartinaDon(unittest.TestCase):
    """musteri_kartina_don fonksiyonunun testleri."""

    def setUp(self):
        self.core = LucaOtomasyonCore(
            uye_no="12345",
            kullanici_adi="test@test.com",
            parola="sifre123",
            cikti_klasoru="test_raporlar",
            headless=True,
        )
        # Mock dashboard ve context
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
        # _frame_bul ve _rol_buton_tikla'yı mockla
        self.core._frame_bul = MagicMock(return_value=mock_frame)
        self.core._rol_buton_tikla = MagicMock()

    @patch('luca_otomasyon_core.sync_playwright')
    def test_musteri_kartina_don_url_ile_dönme(self, mock_pw):
        """musteri_kartina_don URL ile müşteri listesine dönmeli."""
        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        self.core._filtreleri_uygula = MagicMock()
        self.core.musteri_kartina_don(log=log_fn)

        self.assertTrue(any("Doğrudan URL ile müşteri listesine dönüldü" in m for m in log_messages))
        self.core._filtreleri_uygula.assert_called_once()

    @patch('luca_otomasyon_core.sync_playwright')
    def test_musteri_kartina_don_filtre_uygulama(self, mock_pw):
        """musteri_kartina_don sonrası filtreler yeniden uygulanmalı."""
        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        self.core._filtreleri_uygula = MagicMock()
        self.core.musteri_kartina_don(log=log_fn)

        self.core._filtreleri_uygula.assert_called_once_with(log_fn)


class TestFiltreleriUygula(unittest.TestCase):
    """_filtreleri_uygula fonksiyonunun testleri."""

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
        """Filtre Yıl ve Sınıf değerlerini uygulamalı."""
        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        # _rol_buton_tikla'yı mockla
        self.core._rol_buton_tikla = MagicMock()
        self.core._frame_bul = MagicMock(return_value=self.mock_frame)

        self.core._filtreleri_uygula(log_fn)

        # Yıl ve Sınıf seçilmiş olmalı
        self.assertIn("Filtre uygulanıyor", log_messages[0])
        self.assertIn("2026", log_messages[0])


class TestTopluMizanRaporu(unittest.TestCase):
    """toplu_mizan_raporu fonksiyonunun testleri."""

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
        """Tek müşteri için rapor oluşturulmalı."""
        musteriler = [
            {"kisa_ad": "TEST FİRMA", "uzun_ad": "Test Firma A.Ş.", "vergi_dairesi": "İstanbul", "vergi_no": "1234567890"}
        ]

        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        # Mock'ları ayarla
        self.core.musteri_sec = MagicMock()
        self.core.mizan_raporu_olustur = MagicMock(return_value=Path("test_raporlar/TEST FİRMA_Mizan_2026.xlsx"))
        self.core.musteri_kartina_don = MagicMock()
        self.core._filtreleri_uygula = MagicMock()

        sonuclar = self.core.toplu_mizan_raporu(musteriler, log=log_fn)

        self.assertEqual(len(sonuclar), 1)
        self.assertEqual(sonuclar[0]["durum"], "başarılı")
        self.core.musteri_sec.assert_called_once()
        self.core.mizan_raporu_olustur.assert_called_once()

    @patch('luca_otomasyon_core.sync_playwright')
    def test_iki_musteri_rapor(self, mock_pw):
        """İki müşteri için rapor oluşturulmalı, arada listeye dönülmeli."""
        musteriler = [
            {"kisa_ad": "FİRMA A", "uzun_ad": "Firma A A.Ş.", "vergi_dairesi": "İstanbul", "vergi_no": "111"},
            {"kisa_ad": "FİRMA B", "uzun_ad": "Firma B A.Ş.", "vergi_dairesi": "Ankara", "vergi_no": "222"},
        ]

        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        self.core.musteri_sec = MagicMock()
        self.core.mizan_raporu_olustur = MagicMock(return_value=Path("test.xlsx"))
        self.core.musteri_kartina_don = MagicMock()
        self.core._filtreleri_uygula = MagicMock()

        sonuclar = self.core.toplu_mizan_raporu(musteriler, log=log_fn)

        self.assertEqual(len(sonuclar), 2)
        self.assertEqual(sonuclar[0]["durum"], "başarılı")
        self.assertEqual(sonuclar[1]["durum"], "başarılı")
        # İki müşteri arasında bir kez listeye dönülmeli
        self.core.musteri_kartina_don.assert_called_once()

    @patch('luca_otomasyon_core.sync_playwright')
    def test_hatalı_musteri_sonraki_devam(self, mock_pw):
        """Bir müşteride hata olsa bile diğer müşterilere devam etmeli."""
        musteriler = [
            {"kisa_ad": "HATALI", "uzun_ad": "Hatalı Firma", "vergi_dairesi": "X", "vergi_no": "1"},
            {"kisa_ad": "İYİ", "uzun_ad": "İyi Firma", "vergi_dairesi": "Y", "vergi_no": "2"},
        ]

        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        # İlk müşteride hata fırlat
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

        sonuclar = self.core.toplu_mizan_raporu(musteriler, log=log_fn)

        self.assertEqual(len(sonuclar), 2)
        self.assertEqual(sonuclar[0]["durum"], "hatalı")
        self.assertEqual(sonuclar[1]["durum"], "başarılı")

    @patch('luca_otomasyon_core.sync_playwright')
    def test_kurtarma_mekanizması(self, mock_pw):
        """musteri_kartina_don hata verirse kurtarma denenmeli."""
        musteriler = [
            {"kisa_ad": "FİRMA A", "uzun_ad": "Test", "vergi_dairesi": "X", "vergi_no": "1"},
            {"kisa_ad": "FİRMA B", "uzun_ad": "Test", "vergi_dairesi": "Y", "vergi_no": "2"},
        ]

        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        self.core.musteri_sec = MagicMock()
        self.core.mizan_raporu_olustur = MagicMock(return_value=Path("test.xlsx"))

        # musteri_kartina_don ilk seferde hata versin, kurtarma ile düzelir
        don_sayac = [0]
        def mock_don(log=None):
            don_sayac[0] += 1
            if don_sayac[0] == 1:
                raise RuntimeError("Listeye dönülemedi")

        self.core.musteri_kartina_don = mock_don
        self.core._filtreleri_uygula = MagicMock()

        # dashboard.goto'yu mockla (kurtarma için)
        self.core.dashboard.goto = MagicMock()
        self.core._frame_bul = MagicMock(return_value=self.core.liste_frame)
        self.core.liste_frame.wait_for_selector = MagicMock()

        sonuclar = self.core.toplu_mizan_raporu(musteriler, log=log_fn)

        self.assertEqual(len(sonuclar), 2)
        # Kurtarma mesajı loglanmalı
        self.assertTrue(any("Kurtarma başarılı" in m for m in log_messages))


class TestEdgeCases(unittest.TestCase):
    """Sınır durumları testleri."""

    def test_bos_musteri_listesi(self):
        """Boş müşteri listesi ile toplu rapor çağrılmalı."""
        core = LucaOtomasyonCore("1", "a", "b")
        core.dashboard = MockPage()
        core._context = MockContext()
        core._context.pages = [core.dashboard]
        core.liste_frame = MockFrame()
        core._son_yil = "2026"
        core._son_sinif = "1"

        log_messages = []
        def log_fn(msg):
            log_messages.append(msg)

        sonuclar = core.toplu_mizan_raporu([], log=log_fn)
        self.assertEqual(len(sonuclar), 0)

    def test_dashboard_yoksa_hata(self):
        """Dashboard yoksa RuntimeError fırlatmalı."""
        core = LucaOtomasyonCore("1", "a", "b")

        with self.assertRaises(RuntimeError):
            core.musteri_kartina_don()


if __name__ == "__main__":
    # Test raporları klasörünü temizle
    import shutil
    test_klasor = Path("test_raporlar")
    if test_klasor.exists():
        shutil.rmtree(test_klasor)

    print("=" * 60)
    print("  LUCA MIZAN OTOMASYON - UNIT TESTLER")
    print("=" * 60)
    print()

    # Testleri çalıştır
    unittest.main(verbosity=2)
