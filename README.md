# Luca Mizan Raporu Otomasyonu

LUCA Mali Müşavir Paketi'nde müşteri mizan raporlarını otomatik oluşturan,
**modern animasyonlu arayüzlü bir masaüstü uygulaması**.

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

## Ekran görüntüsü

> Arayüz tarayıcıda değil, **kendi masaüstü penceresinde** açılır
> (pywebview / Windows WebView2 ile). Tarayıcı açılmaz.

## Hızlı Başlangıç (Windows)

Python'un kurulu olduğunu varsayar. **`Mizan_Raporu_Baslat.bat`** dosyasına
çift tıklayın — sanal ortam, bağımlılıklar ve Chromium otomatik kurulur,
ardından uygulama açılır. İlk açılışta **masaüstüne otomatik bir kısayol**
oluşturulur; bir daha klasörden açmanıza gerek kalmaz.

> Python kurulu değilse: [python.org](https://www.python.org/downloads/)'dan
> kurun, "Add Python to PATH" seçeneğini işaretleyin, sonra `.bat`'a tekrar
> çift tıklayın.

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

python arayuz.py       # masaüstü pencere (pywebview; yoksa tarayıcıda açılır)
# veya
python web_ui.py       # yalnızca yerel web sunucusu + tarayıcıda arayüz
```

## Dosya Yapısı

| Dosya | Açıklama |
|---|---|
| `arayuz.py` | Masaüstü pencere giriş noktası (pywebview) |
| `web_ui.py` | Yerel HTTP sunucusu + arka plan otomasyon işçisi + API |
| `web_ui/` | Modern arayüz (HTML/CSS/JS) ve ikon |
| `luca_otomasyon_core.py` | Asıl otomasyon motoru (Playwright) — firma seçimi, mizan oluşturma |
| `Mizan_Raporu_Baslat.bat` | Windows tek tıkla kurulum + başlatma |
| `.env` / `.env.example` | Giriş bilgileri ve varsayılan filtreler |
| `logo_uret.py` | Terazi logoyu `.ico`/`.png` olarak üretir |
| `kisayol_olustur.py` | İlk açılışta masaüstüne ikonlu kısayol oluşturur |
| `test_unit.py` | 70+ birim testi |

## Sürüm Geçmişi

- **v3.1** — Masaüstüne otomatik kısayol, güncellenmiş kısayol yönetimi
- **v3.0** — Modern animasyonlu web tabanlı masaüstü arayüz (terazi logo),
  PyInstaller hazırlıkları

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

## Lisans

Bu proje kişisel kullanım ve öğrenme amacıyla yayınlanmıştır. LUCA ile
etkileşimi otomasyona bırakmadan önce ilgili hizmet şartlarını kontrol edin.

---

**Developer: Arda M. Ekiz** — Luca Mizan Raporu Otomasyonu