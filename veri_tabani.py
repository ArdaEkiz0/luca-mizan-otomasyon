import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

VERI_KOK = Path(os.getcwd()).resolve()


def _db_yol() -> Path:
    return Path(os.getcwd()).resolve() / "mizan_kontrol.db"


def baglanti_olustur() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_yol()))
    conn.row_factory = sqlite3.Row
    _tablolar_olustur(conn)
    return conn


def _tablolar_olustur(conn: sqlite3.Connection) -> None:
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS kontrol_sonuclari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dosya_adi TEXT NOT NULL,
            firma_adi TEXT DEFAULT '',
            donem TEXT DEFAULT '',
            satir_sayisi INTEGER DEFAULT 0,
            durum TEXT NOT NULL,
            hata_sayisi INTEGER DEFAULT 0,
            uyari_sayisi INTEGER DEFAULT 0,
            ihlaller_json TEXT DEFAULT '[]',
            kontrol_tarihi TEXT NOT NULL,
            yil TEXT DEFAULT '2026',
            sinif TEXT DEFAULT '1',
            kontrol_dosyasi TEXT DEFAULT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS hata_ihlalleri (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kontrol_id INTEGER NOT NULL,
            kural_id TEXT NOT NULL,
            hesap_kodu TEXT NOT NULL,
            hesap_adi TEXT DEFAULT '',
            seviye TEXT NOT NULL,
            deger TEXT DEFAULT '',
            mesaj TEXT DEFAULT '',
            FOREIGN KEY (kontrol_id) REFERENCES kontrol_sonuclari(id) ON DELETE CASCADE
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS kural_istatistik_db (
            kural_id TEXT PRIMARY KEY,
            toplam INTEGER DEFAULT 0,
            hata INTEGER DEFAULT 0,
            uyari INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS ayarlar (
            anahtar TEXT PRIMARY KEY,
            deger TEXT DEFAULT ''
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS rapor_gecmis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kisi_no TEXT DEFAULT '',
            kisa_ad TEXT DEFAULT '',
            urun_adi TEXT DEFAULT '',
            urun_kodu TEXT DEFAULT '',
            musteri_kodu TEXT DEFAULT '',
            urun_hafi TEXT DEFAULT '',
            rapor_tipi TEXT DEFAULT '',
            sorgu_sayisi INTEGER DEFAULT 0,
            sure_saniye REAL DEFAULT 0,
            rapor_dosyasi TEXT DEFAULT '',
            durum TEXT DEFAULT '',
            tarih TEXT DEFAULT ''
        )
    """)
    conn.commit()


def kontrol_sonuc_kaydet(
    dosya_adi: str,
    firma_adi: str = "",
    donem: str = "",
    satir_sayisi: int = 0,
    durum: str = "OK",
    hata_sayisi: int = 0,
    uyari_sayisi: int = 0,
    ihlaller: list = None,
    yil: str = "2026",
    sinif: str = "1",
    kontrol_dosyasi: str = None,
) -> int:
    kayit_ihlaller = []
    for i in (ihlaller or []):
        kanonik = dict(i)
        kanonik["kural_id"] = i.get("kural_id") or i.get("kural", "")
        kanonik["hesap_kodu"] = i.get("hesap_kodu") or i.get("hesap", "")
        kanonik["hesap_adi"] = i.get("hesap_adi") or i.get("ad", "")
        kayit_ihlaller.append(kanonik)
    conn = baglanti_olustur()
    c = conn.cursor()
    c.execute(
        """INSERT INTO kontrol_sonuclari
           (dosya_adi, firma_adi, donem, satir_sayisi, durum, hata_sayisi,
            uyari_sayisi, ihlaller_json, kontrol_tarihi, yil, sinif, kontrol_dosyasi)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (dosya_adi, firma_adi, donem, satir_sayisi, durum, hata_sayisi,
         uyari_sayisi, json.dumps(kayit_ihlaller), datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         yil, sinif, kontrol_dosyasi),
    )
    kontrol_id = c.lastrowid
    for i in kayit_ihlaller:
        c.execute(
            """INSERT INTO hata_ihlalleri
               (kontrol_id, kural_id, hesap_kodu, hesap_adi, seviye, deger, mesaj)
               VALUES (?,?,?,?,?,?,?)""",
            (kontrol_id, i["kural_id"], i["hesap_kodu"],
             i["hesap_adi"], i.get("seviye", ""), i.get("deger", ""),
             i.get("mesaj", "")),
        )
    conn.commit()
    conn.close()
    return kontrol_id


def kontrol_sonuclari_getir(
    firma: str = None,
    durum: str = None,
    gunun: str = None,
    gun: int = None,
    yil: str = None,
    baslangic: str = None,
    bitis: str = None,
    limit: Optional[int] = 100,
) -> list:
    conn = baglanti_olustur()
    c = conn.cursor()
    query = "SELECT * FROM kontrol_sonuclari WHERE 1=1"
    params = []
    if firma:
        query += " AND firma_adi LIKE ?"
        params.append(f"%{firma}%")
    if durum:
        query += " AND durum = ?"
        params.append(durum)
    if gunun:
        query += " AND kontrol_tarihi LIKE ?"
        params.append(f"%{gunun}%")
    if gun is not None:
        query += " AND CAST(strftime('%w', kontrol_tarihi) AS INTEGER) = ?"
        params.append(gun)
    if yil:
        query += " AND yil = ?"
        params.append(yil)
    if baslangic:
        query += " AND kontrol_tarihi >= ?"
        params.append(baslangic)
    if bitis:
        if len(bitis) == 10:
            query += " AND kontrol_tarihi < date(?, '+1 day')"
        else:
            query += " AND kontrol_tarihi <= ?"
        params.append(bitis)
    query += " ORDER BY kontrol_tarihi DESC"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    rows = c.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def ihlaller_getir(kontrol_id: int) -> list:
    conn = baglanti_olustur()
    c = conn.cursor()
    rows = c.execute(
        "SELECT * FROM hata_ihlalleri WHERE kontrol_id = ?", (kontrol_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def istatistik_getir() -> dict:
    conn = baglanti_olustur()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as toplam FROM kontrol_sonuclari")
    toplam = c.fetchone()["toplam"]
    c.execute("SELECT COUNT(*) as n FROM kontrol_sonuclari WHERE durum='OK'")
    ok = c.fetchone()["n"]
    c.execute("SELECT COUNT(*) as n FROM kontrol_sonuclari WHERE durum='HATA'")
    hata = c.fetchone()["n"]
    c.execute("SELECT COUNT(*) as n FROM kontrol_sonuclari WHERE durum='UYARI'")
    uyari = c.fetchone()["n"]
    c.execute("SELECT kural_id, toplam, hata, uyari FROM kural_istatistik_db")
    kurallar = {}
    for r in c.fetchall():
        kurallar[r["kural_id"]] = {"toplam": r["toplam"], "hata": r["hata"], "uyari": r["uyari"]}
    c.execute(
        "SELECT firma_adi, COUNT(*) as n FROM kontrol_sonuclari WHERE durum='HATA' GROUP BY firma_adi ORDER BY n DESC LIMIT 10"
    )
    hata_firmalari = [{**dict(r)} for r in c.fetchall()]
    conn.close()
    return {
        "toplam": toplam, "ok": ok, "hata": hata, "uyari": uyari,
        "kurallar": kurallar, "hata_firmalari": hata_firmalari,
    }


def grafik_verisi_getir(gun_sayisi: int = 7) -> dict:
    conn = baglanti_olustur()
    c = conn.cursor()
    gunler = []
    hata_sayilari = []
    uyari_sayilari = []
    ok_sayilari = []
    for i in range(gun_sayisi - 1, -1, -1):
        c.execute(
            "SELECT DATE('now', ? || ' days') as gun",
            (-i,)
        )
        gun = c.fetchone()["gun"]
        c.execute("SELECT COUNT(*) as n FROM kontrol_sonuclari WHERE DATE(kontrol_tarihi) = ? AND durum = 'OK'", (gun,))
        ok = c.fetchone()["n"]
        c.execute("SELECT COUNT(*) as n FROM kontrol_sonuclari WHERE DATE(kontrol_tarihi) = ? AND durum = 'HATA'", (gun,))
        hata = c.fetchone()["n"]
        c.execute("SELECT COUNT(*) as n FROM kontrol_sonuclari WHERE DATE(kontrol_tarihi) = ? AND durum = 'UYARI'", (gun,))
        uyari = c.fetchone()["n"]
        gunler.append(gun[5:])
        ok_sayilari.append(ok)
        hata_sayilari.append(hata)
        uyari_sayilari.append(uyari)
    conn.close()
    return {
        "gunler": gunler,
        "ok": ok_sayilari,
        "hata": hata_sayilari,
        "uyari": uyari_sayilari,
    }


def kural_istatistik_guncelle(kural_id: str, seviye: str) -> None:
    conn = baglanti_olustur()
    c = conn.cursor()
    c.execute(
        """INSERT INTO kural_istatistik_db (kural_id, toplam, hata, uyari)
           VALUES (?,1,?,?) ON CONFLICT(kural_id) DO UPDATE SET
           toplam = toplam + 1,
           hata = hata + (CASE WHEN excluded.hata > 0 THEN 1 ELSE 0 END),
           uyari = uyari + (CASE WHEN excluded.uyari > 0 THEN 1 ELSE 0 END)""",
        (kural_id, 1 if seviye == "HATA" else 0, 1 if seviye == "UYARI" else 0),
    )
    conn.commit()
    conn.close()


def ayar_getir(anahtar: str, varsayilan: str = "") -> str:
    conn = baglanti_olustur()
    c = conn.cursor()
    c.execute("SELECT deger FROM ayarlar WHERE anahtar = ?", (anahtar,))
    row = c.fetchone()
    conn.close()
    return row["deger"] if row else varsayilan


def ayar_kaydet(anahtar: str, deger: str) -> None:
    conn = baglanti_olustur()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO ayarlar (anahtar, deger) VALUES (?,?)",
        (anahtar, deger),
    )
    conn.commit()
    conn.close()


def veri_tabani_temizle() -> None:
    conn = baglanti_olustur()
    c = conn.cursor()
    c.execute("DELETE FROM kontrol_sonuclari")
    c.execute("DELETE FROM hata_ihlalleri")
    c.execute("DELETE FROM kural_istatistik_db")
    conn.commit()
    conn.close()


def rapor_gecmis_kaydet(
    kisi_no: str = "",
    kisa_ad: str = "",
    urun_adi: str = "",
    urun_kodu: str = "",
    musteri_kodu: str = "",
    urun_hafi: str = "",
    rapor_tipi: str = "",
    sorgu_sayisi: int = 0,
    sure_saniye: float = 0,
    rapor_dosyasi: str = "",
    durum: str = "",
    tarih: str = "",
) -> int:
    conn = baglanti_olustur()
    c = conn.cursor()
    c.execute(
        """INSERT INTO rapor_gecmis
           (kisi_no, kisa_ad, urun_adi, urun_kodu, musteri_kodu, urun_hafi,
            rapor_tipi, sorgu_sayisi, sure_saniye, rapor_dosyasi, durum, tarih)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (kisi_no, kisa_ad, urun_adi, urun_kodu, musteri_kodu, urun_hafi,
         rapor_tipi, sorgu_sayisi, sure_saniye, rapor_dosyasi, durum, tarih),
    )
    kayit_id = c.lastrowid
    conn.commit()
    conn.close()
    return kayit_id


def rapor_gecmis_getir(limit: int = 50, kisi_no: str = None,
                       tarih_baslangic: str = None, tarih_bitis: str = None,
                       durum: str = None) -> list:
    conn = baglanti_olustur()
    c = conn.cursor()
    query = "SELECT * FROM rapor_gecmis WHERE 1=1"
    params = []
    if kisi_no:
        query += " AND kisi_no LIKE ?"
        params.append(f"%{kisi_no}%")
    if tarih_baslangic:
        query += " AND tarih >= ?"
        params.append(tarih_baslangic)
    if tarih_bitis:
        query += " AND tarih <= ?"
        params.append(tarih_bitis)
    if durum:
        query += " AND durum = ?"
        params.append(durum)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = c.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    print("Veritabani test ediliyor...")
    sonuc = kontrol_sonuc_kaydet("test.xlsx", "Test Firma", "2026", 100, "OK", 0, 0)
    print(f"Kaydedildi: ID={sonuc}")
    sonuclar = kontrol_sonuclari_getir()
    print(f"Toplam kayit: {len(sonuclar)}")
    ist = istatistik_getir()
    print(f"Istatistik: {ist}")
