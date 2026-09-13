# Luca Mizan Raporu Otomasyonu

LUCA Mali Müşavir Paketi'nde müşteri mizan raporlarını otomatik oluşturan,
**modern animasyonlu arayüzlü bir web uygulaması**.

## Özellikler

- 🚀 **Tek tıkla kurulum + başlatma** (Windows `.bat`)
- 🎨 **Modern animasyonlu arayüz** — hareketli gradyan arka plan, cam efekti
  (glassmorphism), parlayan butonlar, canlı log konsolu
- 📋 **Müşteri listesi** — Yıl/Sınıf filtresi, canlı arama, tek veya toplu seçim
- 📅 **Tarih aralığı** — sadece 8 rakam yazarsınız (örn. `01012026`), noktalar
  otomatik eklenir; boş bırakırsanız tüm yıl raporlanır
- 📊 **Mizan raporu** — tek müşteri veya filtrelenen tüm müşteriler için sıralı
  toplu rapor; çıktılar `raporlar/` klasörüne Excel (.xlsx) olarak kaydedilir
- 🔒 **Güvenlik** — kimlik bilgileri yalnızca kendi bilgisayarınızdaki `.env`
  dosyasında saklanır; hiçbir yere gönderilmez/git'e eklenmez
- 📤 **Çoklu export** — JSON, CSV, PDF, HTML, TXT formatında rapor indirabilirsiniz

## Ekran görüntüsü

> Arayüz tarayıcıda açılır (yerel sunucu + Chromium). Tarayıcıdan erişilir.

## Hızlı Başlangıç (Windows)

Python kurulu olmadan bile **`Mizan_Raporu_Baslat.bat`** dosyasına
çift tıklayın — uygulama Python'u, sanal ortamı, bağımlılıkları
ve Chromium'u otomatik kurar, ardından tarayıcıda arayüz açılır.

> Zaten Python kuruluysa otomatik kurulum atlanır.

İlk açılışta:

1. **Giriş Bilgileri**'ne Üye No / Kullanıcı Adı / Parola girin → **Kaydet**
   (bilgiler `.env` dosyasına yazılır, bir sonraki sefere hatırlanır)
2. **Müşterileri Getir**'e basın — arka planda tarayıcı açılır, giriş yapılır;
   **KULLANICI ADI alanını siz elle girip "Giriş"e basarsınız** (güvenlik
   gereği otomasyon bu alanı doldurmaz)
3. Tablodan müşteri seçin → **Mizan Raporu Oluştur**, ya da
   **Tüm Müşteriler İçin Rapor** ile toplu rapor alın
4. İsterseniz **Tarih Aralığı**'na başlangıç/bitiş yazın (8 rakam, örn.
   `01012026` – `31032026`); boş = tüm yıl

## Elle Kurulum (Windows / macOS / Linux)

```bash
git clone https://github.com/ArdaEkiz0/luca-mizan-otomasyon.git
cd luca-mizan-otomasyon

python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
playwright install chromium

cp .env.example .env   # kendi bilgilerinizi girin (veya arayüzden girin)

python web_ui.py       # yerel sunucu + tarayıcıda arayüz
```

## Dosya Yapısı

| Dosya | Açıklama |
|---|---|
| `arayuz.py` | Web arayüzü sunucusu (Flask — sadece yerel) |
| `web_ui.py` | Yerel HTTP sunucusu + arka plan otomasyon işçisi + API |
| `luca_otomasyon_core.py` | Asıl otomasyon motoru (Playwright) — firma seçimi, mizan oluşturma |
| `Mizan_Raporu_Baslat.bat` | Web arayüzünü başlatır (kullanılacak) |
| `Luca_Mizan_Baslat.bat` | Desktop uygulamasını başlatır (özel) |
| `web_ui/` | Modern arayüz (HTML/CSS/JS) ve ikon |
| `.env` / `.env.example` | Giriş bilgileri ve varsayılan filtreler |
| `logo_uret.py` | Terazi logoyu `.ico`/`.png` olarak üretir |
| `kisayol_olustur.py` | İlk açılışta masaüstüne ikonlu kısayol oluşturur |
| `test_unit.py` | 92 birim testi |
| `test_gelisttirme.py` | 36 geliştirme testi |
| `hata_onerileri.py` | Kural bazlı hata önerileri (K1-K12) |

## Sürüm Geçmişi

- **0.1.6** — Kontrol geçmişinde filtreleme (OK/HATA/UYARI), API'de durum filtresi
- **0.1.5** — Kontrol geçmişinde "Tümünü Göster" özelliği, API'de tüm sonuçlar desteği
- **0.1.4** — Kontrol detaylarında hata önerileri (K1-K12) gösteriliyor
- **0.1.3** — Python otomatik kurulum: `Mizan_Raporu_Baslat.bat` ve `Luca_Mizan_Baslat.bat` Python yoksa `python-3.12.7` otomatik olarak indir ve kur
- **0.1.2** — Kontrol bölümünde "📜 Geçmiş Ara" özelliği (geçmiş kontrol raporu arama), `/api/kontrol/arama` endpointi UI'ye bağlandı
- **0.1.1** — Dashboard iyileştirmeleri (yüzde çubukları, auto-refresh, en çok hata yapan kurallar), HTML/TXT export, güncellenmiş README, batch dosyası ayrımı
- **0.1.0** — Web arayüzü (Flask), HTML/TXT/JSON/CSV/PDF export, dashboard, güncelleme kontrolü
- **0.0.2** — Tek tıkla kurulum, otomatik kısayol, hata yönetimi
- **0.0.1** — İlk sürüm (masaüstü, pywebview, Chromium yükleme)

**Sürüm notu:** Luca'nin gerçek sürüm numarası masaüstü uygulamasına ait olduğundan, proje sürümü **0.x** olarak tutulmaktadır. (Mevcut masaüstü sürüm: **v3.1**)

## Ayarlar (`.env`)

```
LUCA_UYE_NO=          # Luca üye numaranız
LUCA_KULLANICI_ADI=   # Luca kullanıcı adınız
LUCA_PAROLA=          # Luca parolanız
MIZAN_YIL=2026        # varsayılan yıl
MIZAN_SINIF=1         # 1=1.Sınıf, 2=2.Sınıf, 3=İşletme Defteri, 4=Serbest Meslek, 5=Basit Usül
CIKTI_KLASORU=raporlar
```

> ⚠️ **`.env` dosyanızı kimseyle paylaşmayın.** Bu dosya `.gitignore`'da
> olduğu için git'e/gitHub'a asla yüklenmez.

## Teknik Notlar

- **Nasıl çalışır?** Luca, raporun hangi firma için hazırlanacağını sağ
  üstteki firma seçicisinden (`SirketCombo`) alır. Otomasyon bu seçiciyi
  Playwright ile otomatik yönetir: firmayı seçer, dönemi ayarlar, "Tamam"a
  basar; ardından mizan sayfasını doğru firmayla açar.
- **Kimlik doğrulama:** Giriş sırasında KULLANICI ADI alanı bilinçli olarak
  sizin için boş bırakılır (iki adımlı doğrulama olabilir). Tarayıcı görünür
  çalıştığı için müdahale edebilirsiniz.
- **Toplu rapor:** Filtrelenen tüm müşteriler sırayla işlenir; her müşteri
  için firma seçimi yeniden yapılır, böylece raporlar doğru firmaya aittir.
- **Export formatları:** Kontrol raporları JSON, CSV, PDF, HTML ve TXT
  formatında indirilebilir. HTML ve TXT formatları doğrudan dosya olarak
  kaydedilir; JSON/CSV/PDF tarayıcıdan indirilir.
- **İki batch dosyası:** `Mizan_Raporu_Baslat.bat` → Web arayüzü (kullanılacak),
  `Luca_Mizan_Baslat.bat` → Masaüstü uygulaması (özel).

## Lisans

Bu proje kişisel kullanım ve öğrenme amacıyla yayınlanmıştır. LUCA ile
etkileşimi otomasyona bırakmadan önce ilgili hizmet şartlarını kontrol edin.

---

**Developer: Arda M. Ekiz** — Luca Mizan Raporu Otomasyonu