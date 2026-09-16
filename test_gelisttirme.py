import os
import sys
import tempfile
import shutil
import json
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

import pytest

BASE = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE))


class TestTopluKayit(unittest.TestCase):
    def setUp(self):
        import veri_tabani
        self.db = veri_tabani
        tmpdir = self.enterContext(tempfile.TemporaryDirectory(dir=Path.cwd()))
        self.enterContext(patch.object(self.db, "_db_yol", return_value=Path(tmpdir) / "toplu.db"))

    def test_bos_liste_baglanti_acmaz(self):
        with patch.object(self.db, "baglanti_olustur") as baglanti:
            self.assertEqual(self.db.kontrol_sonuclari_toplu_kaydet([]), [])
            baglanti.assert_not_called()

    def test_tekli_ile_ayni_veri_ve_sirali_idler(self):
        kayitlar = [
            {"dosya_adi": "a.xlsx", "firma_adi": "Firma", "donem": "Ocak",
             "satir_sayisi": 10, "durum": "HATA", "hata_sayisi": 1, "yil": "2025",
             "sinif": "2", "kontrol_dosyasi": "a_KONTROL.xlsx",
             "ihlaller": [{"kural": "K1", "hesap": "100", "ad": "Kasa",
                           "seviye": "HATA", "deger": "1", "mesaj": "Test"}]},
            {"dosya_adi": "b.xlsx", "ihlaller": None},
        ]
        orijinal = json.dumps(kayitlar)
        tekli = [self.db.kontrol_sonuc_kaydet(**k) for k in kayitlar]
        with patch.object(self.db, "baglanti_olustur", wraps=self.db.baglanti_olustur) as baglanti:
            toplu = self.db.kontrol_sonuclari_toplu_kaydet(kayitlar)
            baglanti.assert_called_once()
        self.assertEqual(toplu, sorted(set(toplu)))
        self.assertEqual(len(toplu), len(kayitlar))
        rows = {r["id"]: r for r in self.db.kontrol_sonuclari_getir()}
        for a, b in zip(tekli, toplu):
            for key in rows[a].keys() - {"id", "kontrol_tarihi"}:
                self.assertEqual(rows[a][key], rows[b][key])
            temizle = lambda r: {k: v for k, v in r.items() if k not in ("id", "kontrol_id")}
            self.assertEqual([temizle(r) for r in self.db.ihlaller_getir(a)],
                             [temizle(r) for r in self.db.ihlaller_getir(b)])
        self.assertEqual(json.dumps(kayitlar), orijinal)
        self.assertEqual(self.db.istatistik_getir()["kurallar"], {})

    def test_hata_tum_toplu_islemi_geri_alir(self):
        import sqlite3
        onceki = self.db.kontrol_sonuc_kaydet("onceki.xlsx")
        for bozuk in ({"dosya_adi": None}, {"dosya_adi": "b.xlsx", "ihlaller": [
                {"kural": "K1", "hesap": "100", "seviye": None}]}):
            with self.subTest(bozuk=bozuk):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.db.kontrol_sonuclari_toplu_kaydet([
                        {"dosya_adi": "a.xlsx", "ihlaller": [{"kural": "K1", "seviye": "HATA"}]},
                        bozuk,
                    ], istatistik_guncelle=True)
                self.assertEqual([r["id"] for r in self.db.kontrol_sonuclari_getir()], [onceki])
                conn = self.db.baglanti_olustur()
                try:
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM hata_ihlalleri").fetchone()[0], 0)
                finally:
                    conn.close()
                self.assertEqual(self.db.istatistik_getir()["kurallar"], {})

    def test_istatistikler_tek_baglantida_birer_kez_artar(self):
        ihlaller = [{"kural": "K1", "seviye": "HATA"},
                    {"kural_id": "K1", "seviye": "UYARI"}]
        self.db.kural_istatistik_guncelle("K1", "HATA")
        with patch.object(self.db, "baglanti_olustur", wraps=self.db.baglanti_olustur) as baglanti:
            self.db.kontrol_sonuclari_toplu_kaydet(
                [{"dosya_adi": "a.xlsx", "ihlaller": ihlaller}], istatistik_guncelle=True)
            baglanti.assert_called_once()
        self.assertEqual(self.db.istatistik_getir()["kurallar"]["K1"],
                         {"toplam": 3, "hata": 2, "uyari": 1})

    def test_commit_hatasinda_rollback_ve_kapatma(self):
        import sqlite3
        from unittest.mock import MagicMock
        conn = self.db.baglanti_olustur()
        proxy = MagicMock(wraps=conn)
        proxy.commit.side_effect = sqlite3.OperationalError("commit failed")
        with patch.object(self.db, "baglanti_olustur", return_value=proxy):
            with self.assertRaises(sqlite3.OperationalError):
                self.db.kontrol_sonuclari_toplu_kaydet([{"dosya_adi": "a.xlsx"}])
        proxy.rollback.assert_called_once()
        proxy.close.assert_called_once()
        self.assertEqual(self.db.kontrol_sonuclari_getir(), [])


class TestVeriTabaniRegresyon(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(sys.modules, {
            "dotenv": Mock(load_dotenv=Mock(return_value=False)),
        }))
        import veri_tabani
        self.db = veri_tabani
        tmpdir = self.enterContext(tempfile.TemporaryDirectory(dir=Path.cwd()))
        self.enterContext(patch.object(
            self.db, "_db_yol", return_value=Path(tmpdir) / "regresyon.db",
        ))

    def _tarihli_kayitlar(self, tarihler):
        conn = self.db.baglanti_olustur()
        try:
            conn.executemany(
                "INSERT INTO kontrol_sonuclari "
                "(dosya_adi, durum, kontrol_tarihi) VALUES (?, 'OK', ?)",
                [(f"{tarih}.xlsx", tarih) for tarih in tarihler],
            )
            conn.commit()
        finally:
            conn.close()

    def _ihlali_dogrula(self, ihlal, beklenen):
        orijinal = dict(ihlal)
        kid = self.db.kontrol_sonuc_kaydet("test.xlsx", ihlaller=[ihlal])
        satirlar = self.db.ihlaller_getir(kid)
        self.assertEqual(len(satirlar), 1)
        for anahtar, deger in beklenen.items():
            self.assertEqual(satirlar[0][anahtar], deger)
        kayit = next(
            s for s in self.db.kontrol_sonuclari_getir() if s["id"] == kid
        )
        self.assertEqual(json.loads(kayit["ihlaller_json"]), [{**orijinal, **beklenen}])
        self.assertEqual(ihlal, orijinal)

    def test_kanonik_ihlal_kaydedilir(self):
        ihlal = {
            "kural_id": "K1", "hesap_kodu": "100.01", "hesap_adi": "Kasa",
            "seviye": "HATA", "deger": "12.50", "mesaj": "Test hata",
        }
        self._ihlali_dogrula(ihlal, ihlal)

    def test_eski_web_anahtarlari_korunur(self):
        self._ihlali_dogrula(
            {"kural": "K11", "hesap": "760", "ad": "Gider",
             "seviye": "UYARI", "mesaj": "Test uyari", "oneri": "Korunacak"},
            {"kural_id": "K11", "hesap_kodu": "760", "hesap_adi": "Gider"},
        )

    def test_kanonik_anahtarlar_onceliklidir(self):
        self._ihlali_dogrula(
            {"kural_id": "K1", "hesap_kodu": "100", "hesap_adi": "Kasa",
             "kural": "K2", "hesap": "102", "ad": "Banka"},
            {"kural_id": "K1", "hesap_kodu": "100", "hesap_adi": "Kasa"},
        )

    def test_bos_kanonik_anahtarlar_eski_anahtarlardan_alinir(self):
        self._ihlali_dogrula(
            {"kural_id": None, "hesap_kodu": "", "hesap_adi": None,
             "kural": "K1", "hesap": "100", "ad": "Kasa"},
            {"kural_id": "K1", "hesap_kodu": "100", "hesap_adi": "Kasa"},
        )

    def test_ihlalsiz_kayit(self):
        for ihlaller in (None, []):
            with self.subTest(ihlaller=ihlaller):
                kid = self.db.kontrol_sonuc_kaydet("bos.xlsx", ihlaller=ihlaller)
                self.assertEqual(self.db.ihlaller_getir(kid), [])
        self.assertTrue(all(
            json.loads(s["ihlaller_json"]) == []
            for s in self.db.kontrol_sonuclari_getir()
        ))

    def test_tarih_araligi_tum_gunu_kapsar(self):
        tarihler = [
            "2026-09-12 23:59:59", "2026-09-13 00:00:00",
            "2026-09-13 12:00:00", "2026-09-13 23:59:59.999999",
            "2026-09-14 00:00:00",
        ]
        self._tarihli_kayitlar(tarihler)
        rows = self.db.kontrol_sonuclari_getir(
            baslangic="2026-09-13", bitis="2026-09-13",
        )
        self.assertEqual([r["kontrol_tarihi"] for r in rows], tarihler[1:4][::-1])

    def test_zaman_damgasi_sinirlari_dahildir(self):
        tarihler = [
            "2026-09-13 11:59:59", "2026-09-13 12:00:00",
            "2026-09-13 12:30:00", "2026-09-13 13:00:00",
            "2026-09-13 13:00:00.000001",
        ]
        self._tarihli_kayitlar(tarihler)
        rows = self.db.kontrol_sonuclari_getir(
            baslangic="2026-09-13 12:00:00", bitis="2026-09-13 13:00:00",
        )
        self.assertEqual([r["kontrol_tarihi"] for r in rows], tarihler[1:4][::-1])

    def test_tarih_bitisi_ay_yil_ve_artik_gun_sinirlari(self):
        for gun, ertesi in (
            ("2026-09-30", "2026-10-01"),
            ("2026-12-31", "2027-01-01"),
            ("2028-02-29", "2028-03-01"),
        ):
            with self.subTest(gun=gun):
                tarih = gun + " 23:59:59.999999"
                self._tarihli_kayitlar([tarih, ertesi + " 00:00:00"])
                rows = self.db.kontrol_sonuclari_getir(baslangic=gun, bitis=gun)
                self.assertEqual([r["kontrol_tarihi"] for r in rows], [tarih])

    def test_pazar_sifir_filtresi(self):
        tarihler = [
            "2026-09-12 12:00:00", "2026-09-13 12:00:00", "2026-09-14 12:00:00",
        ]
        self._tarihli_kayitlar(tarihler)
        for gun, beklenen in ((0, tarihler[1]), (1, tarihler[2])):
            with self.subTest(gun=gun):
                rows = self.db.kontrol_sonuclari_getir(gun=gun)
                self.assertEqual([r["kontrol_tarihi"] for r in rows], [beklenen])
        self.assertEqual(len(self.db.kontrol_sonuclari_getir()), 3)

    def test_limitsiz_sirali_sonuclar_ve_sayisal_limit(self):
        tarihler = [f"2026-09-13 12:{i // 60:02}:{i % 60:02}" for i in range(105)]
        self._tarihli_kayitlar(tarihler)
        rows = self.db.kontrol_sonuclari_getir(limit=None)
        self.assertEqual([r["kontrol_tarihi"] for r in rows], tarihler[::-1])
        self.assertEqual(len(self.db.kontrol_sonuclari_getir()), 100)
        self.assertEqual(self.db.kontrol_sonuclari_getir(limit=0), [])
        self.assertEqual(
            [r["kontrol_tarihi"] for r in self.db.kontrol_sonuclari_getir(limit=2)],
            tarihler[-2:][::-1],
        )


# --- SQLite Tests ---
class TestVeriTabani:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)

    def teardown_method(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.tmpdir)

    def test_tablolar_olusturulur(self):
        from veri_tabani import baglanti_olustur
        conn = baglanti_olustur()
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tablolar = [r[0] for r in c.fetchall()]
        conn.close()
        assert "kontrol_sonuclari" in tablolar
        assert "hata_ihlalleri" in tablolar
        assert "kural_istatistik_db" in tablolar
        assert "ayarlar" in tablolar

    def test_kontrol_sonucu_kaydet(self):
        from veri_tabani import kontrol_sonuc_kaydet, kontrol_sonuclari_getir
        kid = kontrol_sonuc_kaydet(
            dosya_adi="test.xlsx", firma_adi="Test A.S.",
            durum="HATA", hata_sayisi=2, uyari_sayisi=1,
            ihlaller=[{"kural_id": "K1", "hesap_kodu": "100", "seviye": "HATA", "mesaj": "test"}],
        )
        assert kid > 0
        sonuclar = kontrol_sonuclari_getir()
        assert len(sonuclar) == 1
        assert sonuclar[0]["dosya_adi"] == "test.xlsx"
        assert sonuclar[0]["firma_adi"] == "Test A.S."
        assert sonuclar[0]["durum"] == "HATA"

    def test_kontrol_sonucu_getir_filtreleme(self):
        from veri_tabani import kontrol_sonuc_kaydet, kontrol_sonuclari_getir
        kontrol_sonuc_kaydet(dosya_adi="a.xlsx", firma_adi="Firma A", durum="OK")
        kontrol_sonuc_kaydet(dosya_adi="b.xlsx", firma_adi="Firma B", durum="HATA")
        kontrol_sonuc_kaydet(dosya_adi="c.xlsx", firma_adi="Firma A", durum="HATA")

        tum = kontrol_sonuclari_getir()
        assert len(tum) == 3

        firma_a = kontrol_sonuclari_getir(firma="Firma A")
        assert len(firma_a) == 2
        assert all(s["firma_adi"] == "Firma A" for s in firma_a)

        hatalar = kontrol_sonuclari_getir(durum="HATA")
        assert len(hatalar) == 2
        assert all(s["durum"] == "HATA" for s in hatalar)

    def test_istatistik_getir(self):
        from veri_tabani import kontrol_sonuc_kaydet, istatistik_getir
        kontrol_sonuc_kaydet(dosya_adi="a.xlsx", durum="OK")
        kontrol_sonuc_kaydet(dosya_adi="b.xlsx", durum="HATA", hata_sayisi=3)
        kontrol_sonuc_kaydet(dosya_adi="c.xlsx", durum="UYARI", uyari_sayisi=2)

        ist = istatistik_getir()
        assert ist["toplam"] == 3
        assert ist["ok"] == 1
        assert ist["hata"] == 1
        assert ist["uyari"] == 1

    def test_hata_firmalari(self):
        from veri_tabani import kontrol_sonuc_kaydet, istatistik_getir
        kontrol_sonuc_kaydet(dosya_adi="a.xlsx", firma_adi="Firma X", durum="HATA")
        kontrol_sonuc_kaydet(dosya_adi="b.xlsx", firma_adi="Firma X", durum="HATA")
        kontrol_sonuc_kaydet(dosya_adi="c.xlsx", firma_adi="Firma Y", durum="HATA")

        ist = istatistik_getir()
        hata_firmalar = ist["hata_firmalari"]
        assert len(hata_firmalar) >= 2
        firma_x = [f for f in hata_firmalar if f["firma_adi"] == "Firma X"]
        assert len(firma_x) == 1
        assert firma_x[0]["n"] == 2

    def test_ayar_kaydet_getir(self):
        from veri_tabani import ayar_kaydet, ayar_getir
        ayar_kaydet("dil", "en")
        assert ayar_getir("dil") == "en"
        assert ayar_getir("yok", "varsayilan") == "varsayilan"

    def test_veri_tabani_temizle(self):
        from veri_tabani import kontrol_sonuc_kaydet, veri_tabani_temizle, istatistik_getir
        kontrol_sonuc_kaydet(dosya_adi="a.xlsx", durum="HATA")
        ist = istatistik_getir()
        assert ist["toplam"] == 1
        veri_tabani_temizle()
        ist = istatistik_getir()
        assert ist["toplam"] == 0

    def test_kural_istatistik_guncelle(self):
        from veri_tabani import kural_istatistik_guncelle, istatistik_getir
        kural_istatistik_guncelle("K1", "HATA")
        kural_istatistik_guncelle("K1", "HATA")
        kural_istatistik_guncelle("K2", "UYARI")
        ist = istatistik_getir()
        assert ist["kurallar"]["K1"]["hata"] == 2
        assert ist["kurallar"]["K1"]["toplam"] == 2
        assert ist["kurallar"]["K2"]["uyari"] == 1
        assert ist["kurallar"]["K2"]["toplam"] == 1

    def test_rapor_gecmis_kaydet(self):
        from veri_tabani import rapor_gecmis_kaydet, rapor_gecmis_getir
        kid = rapor_gecmis_kaydet(
            kisi_no="12345", kisa_ad="Test A.S.", urun_adi="Ürün",
            urun_kodu="100", musteri_kodu="M1", urun_hafi="H1",
            rapor_tipi="Tek", sorgu_sayisi=5, sure_saniye=2.5,
            rapor_dosyasi="test.xlsx", durum="OK", tarih="2026-09-13",
        )
        assert kid > 0

    def test_rapor_gecmis_getir(self):
        from veri_tabani import rapor_gecmis_kaydet, rapor_gecmis_getir
        rapor_gecmis_kaydet(kisi_no="111", kisa_ad="A", durum="OK", tarih="2026-09-13")
        rapor_gecmis_kaydet(kisi_no="222", kisa_ad="B", durum="HATA", tarih="2026-09-13")
        rapor_gecmis_kaydet(kisi_no="333", kisa_ad="C", durum="OK", tarih="2026-09-13")

        tum = rapor_gecmis_getir()
        assert len(tum) == 3

        ok = rapor_gecmis_getir(durum="OK")
        assert len(ok) == 2
        assert all(s["durum"] == "OK" for s in ok)

        kisi = rapor_gecmis_getir(kisi_no="111")
        assert len(kisi) == 1
        assert kisi[0]["kisi_no"] == "111"

        limit = rapor_gecmis_getir(limit=1)
        assert len(limit) == 1

    def test_rapor_gecmis_arama(self):
        from veri_tabani import rapor_gecmis_kaydet, rapor_gecmis_getir
        rapor_gecmis_kaydet(kisi_no="123", kisa_ad="Aranacak", durum="OK", tarih="2026-09-13")
        sonuc = rapor_gecmis_getir(kisi_no="12")
        assert len(sonuc) == 1
        assert sonuc[0]["kisi_no"] == "123"

    def test_kontrol_arama_endpoint_bos(self):
        """/api/kontrol/arama — bos firma ve durum → bos sonuc"""
        class MockHandler:
            def __init__(self):
                self.sonuc = None
            def _json(self, veri, durum=200):
                self.sonuc = (veri, durum)

        handler = MockHandler()
        from web_ui import ApiHandler
        ApiHandler._kontrol_arama(handler, {"firma": "", "durum": ""})
        assert handler.sonuc is not None
        assert handler.sonuc[0]["ok"] is True
        assert handler.sonuc[0]["sonuclar"] == []

    def test_grafik_verisi_getir(self):
        from veri_tabani import grafik_verisi_getir
        grafik = grafik_verisi_getir(7)
        assert "gunler" in grafik
        assert "ok" in grafik
        assert "hata" in grafik
        assert "uyari" in grafik
        assert len(grafik["gunler"]) == 7
        assert len(grafik["ok"]) == 7
        assert len(grafik["hata"]) == 7
        assert len(grafik["uyari"]) == 7


# --- Error Suggestions Tests ---
class TestHataOnerileri:
    def test_k1_onerisi(self):
        from hata_onerileri import hata_onusu_ara
        oner = hata_onusu_ara("K1")
        assert len(oner) > 0
        assert "100" in oner

    def test_k10_onerisi(self):
        from hata_onerileri import hata_onusu_ara
        oner = hata_onusu_ara("K10")
        assert len(oner) > 0
        assert "600" in oner

    def test_k12_onerisi(self):
        from hata_onerileri import hata_onusu_ara
        oner = hata_onusu_ara("K12")
        assert len(oner) > 0

    def test_bos_oneri(self):
        from hata_onerileri import hata_onusu_ara
        assert hata_onusu_ara("YL0") == ""

    def test_ihlaller_ozeti(self):
        from hata_onerileri import ihlaller_ozeti_ihlaller
        ihlaller = [
            {"kural_id": "K1", "hesap_kodu": "100", "hesap_adi": "Test", "seviye": "HATA", "mesaj": "test"},
            {"kural_id": "K11", "hesap_kodu": "760", "hesap_adi": "Test2", "seviye": "UYARI", "mesaj": "test2"},
        ]
        sonuc = ihlaller_ozeti_ihlaller(ihlaller)
        assert len(sonuc) == 2
        assert sonuc[0]["oneri"] != ""
        assert sonuc[0]["kural_id"] == "K1"
        assert sonuc[1]["kural_id"] == "K11"


# --- Update Checker Tests ---
class TestGuncellemeKontrolu:
    def test_simdiki_surum(self):
        from guncelleme_kontrolu import simdiki_surum
        surum = simdiki_surum()
        assert isinstance(surum, str)
        assert len(surum) > 0

    def test_guncelleme_kontrol_et(self):
        from guncelleme_kontrolu import guncellememi_kontrol_et
        sonuc = guncellememi_kontrol_et()
        assert "guncellememevcut" in sonuc
        assert "simdi" in sonuc


# --- Integration Tests ---
class TestEntegrasyon:
    def test_mizan_kontrol_sonucu_veritabanina_kaydedilir(self):
        tmpdir = tempfile.mkdtemp()
        orig = os.getcwd()
        os.chdir(tmpdir)
        try:
            from mizan_kontrol import mizan_kontrol, KontrolSonucu, KuralIhlali
            from veri_tabani import kontrol_sonuc_kaydet, kontrol_sonuclari_getir

            sonuc = KontrolSonucu(
                dosya_adi="test_mizan.xlsx", firma_adi="Entegre A.S.",
                hata_sayisi=1, uyari_sayisi=0,
                ihlaller=[KuralIhlali("K1", "100", "Hesap100", "Test hata", "HATA")],
            )
            kontrol_sonuc_kaydet(
                dosya_adi=sonuc.dosya_adi,
                firma_adi=sonuc.firma_adi,
                durum=sonuc.durum,
                hata_sayisi=sonuc.hata_sayisi,
                uyari_sayisi=sonuc.uyari_sayisi,
                ihlaller=[{"kural_id": i.kural_id, "hesap_kodu": i.hesap_kodu,
                           "hesap_adi": i.hesap_adi, "seviye": i.seviye, "mesaj": i.mesaj} for i in sonuc.ihlaller],
            )
            sonuclar = kontrol_sonuclari_getir()
            assert len(sonuclar) == 1
            assert sonuclar[0]["firma_adi"] == "Entegre A.S."
            assert sonuclar[0]["durum"] == "HATA"
        finally:
            os.chdir(orig)
            shutil.rmtree(tmpdir)


# --- Update Function Tests ---
class TestGuncellemeIslem:
    def test_guncelle_mesaj(self):
        from guncelleme_kontrolu import guncellememi_kontrol_et
        sonuc = guncellememi_kontrol_et()
        assert "mesaj" in sonuc
        assert isinstance(sonuc["mesaj"], str)
        assert len(sonuc["mesaj"]) > 0

    def test_guncelle_fonksiyon_yok(self):
        from guncelleme_kontrolu import guncelle
        sonuc = guncelle()
        assert "ok" in sonuc
        assert "guncellendi" in sonuc
        assert "mesaj" in sonuc

    def test_simdiki_surum_donuyor(self):
        from guncelleme_kontrolu import simdiki_surum
        surum = simdiki_surum()
        assert surum != ""


class TestHataOnerileriAPI:
    def test_web_ui_hata_onerileri_import(self):
        from web_ui import ApiHandler
        assert hasattr(ApiHandler, "_kontrol_raporlari")

    def test_hata_onusu_ara_kurallar(self):
        from hata_onerileri import hata_onusu_ara
        for kural in ["K1", "K2", "K5", "K10", "K12", "DOSYA", "OKU", "VERI"]:
            oner = hata_onusu_ara(kural)
            assert isinstance(oner, str)
            assert len(oner) > 0, f"{kural} icin oner bos olmali"

    def test_hata_onusu_ara_bos_kural(self):
        from hata_onerileri import hata_onusu_ara
        assert hata_onusu_ara("YL0") == ""

    def test_ihlaller_ozeti_oneriler_eklenir(self):
        from hata_onerileri import ihlaller_ozeti_ihlaller
        ihlaller = [
            {"kural_id": "K1", "hesap_kodu": "100", "hesap_adi": "Test", "seviye": "HATA", "mesaj": "test"},
            {"kural_id": "K11", "hesap_kodu": "760", "hesap_adi": "Test2", "seviye": "UYARI", "mesaj": "test2"},
            {"kural_id": "YL0", "hesap_kodu": "999", "hesap_adi": "Test3", "seviye": "HATA", "mesaj": "test3"},
        ]
        sonuc = ihlaller_ozeti_ihlaller(ihlaller)
        assert sonuc[0]["oneri"] != ""
        assert sonuc[1]["oneri"] != ""
        assert sonuc[2]["oneri"] == ""


class TestKontrolAPI:
    def test_kontrol_arama_tumu(self):
        class MockHandler:
            def __init__(self):
                self.sonuc = None
            def _json(self, veri, durum=200):
                self.sonuc = (veri, durum)

        handler = MockHandler()
        from web_ui import ApiHandler
        ApiHandler._kontrol_arama(handler, {"tumu": "true"})
        assert handler.sonuc[0]["ok"] is True
        sonuclar = handler.sonuc[0]["sonuclar"]
        assert isinstance(sonuclar, list)

    def test_kontrol_arama_bos(self):
        class MockHandler:
            def __init__(self):
                self.sonuc = None
            def _json(self, veri, durum=200):
                self.sonuc = (veri, durum)

        handler = MockHandler()
        from web_ui import ApiHandler
        ApiHandler._kontrol_arama(handler, {"firma": "", "durum": ""})
        assert handler.sonuc[0]["ok"] is True
        assert handler.sonuc[0]["sonuclar"] == []

    def test_kontrol_arama_tumu_durum(self):
        class MockHandler:
            def __init__(self):
                self.sonuc = None
            def _json(self, veri, durum=200):
                self.sonuc = (veri, durum)

        handler = MockHandler()
        from web_ui import ApiHandler
        ApiHandler._kontrol_arama(handler, {"tumu": "true", "durum": "HATA"})
        assert handler.sonuc[0]["ok"] is True
        sonuclar = handler.sonuc[0]["sonuclar"]
        assert isinstance(sonuclar, list)

    def test_kontrol_gecmis_detay_id_sifir(self):
        class MockHandler:
            def __init__(self):
                self.sonuc = None
            def _json(self, veri, durum=200):
                self.sonuc = (veri, durum)

        handler = MockHandler()
        from web_ui import ApiHandler
        ApiHandler._kontrol_gecmis_detay(handler, {"id": 0})
        assert handler.sonuc[0]["ok"] is False

    def test_kontrol_gecmis_detay_bulunamadi(self):
        class MockHandler:
            def __init__(self):
                self.sonuc = None
            def _json(self, veri, durum=200):
                self.sonuc = (veri, durum)

        handler = MockHandler()
        from web_ui import ApiHandler
        ApiHandler._kontrol_gecmis_detay(handler, {"id": 999999})
        assert handler.sonuc[0]["ok"] is False

    def test_dashboard_son_raporlar(self):
        class MockHandler:
            def __init__(self):
                self.sonuc = None
            def _json(self, veri, durum=200):
                self.sonuc = (veri, durum)

        handler = MockHandler()
        from web_ui import ApiHandler
        ApiHandler._kontrol_dashboard(handler)
        assert handler.sonuc[0]["ok"] is True
        assert "son_raporlar" in handler.sonuc[0]
        assert isinstance(handler.sonuc[0]["son_raporlar"], list)

    def test_rapor_gecmis_detay_id_sifir(self):
        class MockHandler:
            def __init__(self):
                self.sonuc = None
            def _json(self, veri, durum=200):
                self.sonuc = (veri, durum)

        handler = MockHandler()
        from web_ui import ApiHandler
        ApiHandler._rapor_gemis_detay(handler, {"id": 0})
        assert handler.sonuc[0]["ok"] is False

    def test_rapor_gecmis_detay_bulunamadi(self):
        class MockHandler:
            def __init__(self):
                self.sonuc = None
            def _json(self, veri, durum=200):
                self.sonuc = (veri, durum)

        handler = MockHandler()
        from web_ui import ApiHandler
        ApiHandler._rapor_gemis_detay(handler, {"id": 999999})
        assert handler.sonuc[0]["ok"] is False

    def test_musteri_detay_bos(self):
        class MockHandler:
            def __init__(self):
                self.sonuc = None
            def _json(self, veri, durum=200):
                self.sonuc = (veri, durum)

        handler = MockHandler()
        from web_ui import ApiHandler
        ApiHandler._musteri_detay(handler, {"kisa_ad": ""})
        assert handler.sonuc[0]["ok"] is False
