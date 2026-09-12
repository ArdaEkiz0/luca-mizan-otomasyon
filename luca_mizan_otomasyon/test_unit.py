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
from unittest.mock import MagicMock, patch, PropertyMock, call
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from luca_otomasyon_core import LucaOtomasyonCore, SINIF_ETIKETLERI
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


class MockFrame:
    def __init__(self, url="https://test.luca.com.tr/test"):
        self.url = url

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


class TestFrameBul(unittest.TestCase):
    """_frame_bul fonksiyonunun testleri."""

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


class TestRolButonTikla(unittest.TestCase):
    """_rol_buton_tikla fonksiyonunun testleri."""

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


if __name__ == "__main__":
    test_klasor = Path("test_raporlar")
    if test_klasor.exists():
        shutil.rmtree(test_klasor)

    print("=" * 60)
    print("  LUCA MIZAN OTOMASYON - KAPSAMLI TESTLER")
    print("=" * 60)
    print()

    unittest.main(verbosity=2)
