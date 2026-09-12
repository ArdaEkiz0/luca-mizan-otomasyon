# Luca Mizan Raporu Otomasyonu

LUCA Mali Müşavir Paketi'nde şu işlemleri sizin yerinize otomatikleştiren,
grafik arayüzlü bir masaüstü uygulaması:

1. Oturum açma
2. Yönetici → Müşteri İşlemleri → Müşteri Listesi'ni açma
3. Yıl ve Sınıf (ör. 1.Sınıf) filtresini uygulama
4. Filtrelenen listeyi bir tabloda gösterme, aralarından **tek** müşteri veya **tümünü** seçtirme
5. Muhasebe → Raporlar → Genel Raporlar → Mizan ekranını açma
6. Ayarları uygulama: tarih aralığı boş, döviz kolonları gizli, sıfır bakiyeli hesaplar gizli
7. Raporu oluşturup indirmeyi deneme (tekli veya toplu)

## Tek tıkla başlatma (Windows)

Bu klasördeki **`Mizan_Raporu_Baslat.bat`** dosyasına çift tıklamanız yeterli.

- İlk çalıştırmada gerekli kurulumu (sanal ortam, paketler, Chromium)
  otomatik yapar — biraz sürebilir.
- Ardından grafik arayüz penceresi açılır (aşağıya bakın).

Python bilgisayarınızda kurulu değilse `.bat` dosyası bunu size söyler ve
kurulum bağlantısını verir; Python'u kurduktan sonra `.bat`'a tekrar çift
tıklamanız yeterli. **Not:** Python'u python.org'dan kurarken varsayılan
seçenekleri değiştirmeyin — grafik arayüz için gereken "tcl/tk" bileşeni
varsayılan kurulumla birlikte gelir.

## Grafik arayüz nasıl kullanılır

Pencere açıldığında:

1. **Giriş Bilgileri** bölümüne Üye Numarası / Kullanıcı Adı / Parolanızı
   girin (bir sonraki sefer hatırlanması için "Bilgileri Kaydet (.env)"
   butonuna basabilirsiniz — bilgiler yalnızca bu bilgisayardaki `.env`
   dosyasında saklanır).
2. **Filtre ve Müşteri Seçimi** bölümünden Yıl ve Sınıf'ı seçip
   "Müşterileri Getir" butonuna basın. Arka planda bir tarayıcı açılıp
   giriş yapılır ve eşleşen müşteriler alttaki tabloda listelenir.
3. Tablodan rapor almak istediğiniz müşteriyi tıklayın, ardından
   "Mizan Raporu Oluştur" butonuna basın. Ya da "Tüm Müşteriler İçin Rapor"
   butonuna basarak filtrelenen tüm müşteriler için sıralı rapor alabilirsiniz.
4. Alt kısımdaki günlük (log) alanından ilerlemeyi takip edebilirsiniz.
   Rapor hemen indirilebilirse `raporlar/` klasörüne kaydedilir; Luca
   raporu arka planda hazırlıyorsa size "Rapor Takip" menüsüne
   yönlendiren bir not düşer.
5. İşiniz bittiğinde "Tarayıcıyı Kapat" ile oturumu kapatabilir, ya da
   "Müşterileri Getir"e tekrar basarak başka bir Yıl/Sınıf ile yeniden
   başlayabilirsiniz.

## Elle kurulum (macOS/Linux veya .bat kullanmadan)

```bash
cd luca_mizan_otomasyon
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium

cp .env.example .env            # ilk çalıştırmada boş bırakabilirsiniz,
                                 # bilgileri arayüzden de girebilirsiniz

python gui_app.py               # grafik arayüz
# veya
python luca_mizan_otomasyon.py  # komut satırı (CLI) sürümü
```

## Dosyalar

| Dosya | Ne işe yarar |
|---|---|
| `Mizan_Raporu_Baslat.bat` | Windows'ta çift tıkla başlatma (kurulum + `gui_app.py`) |
| `gui_app.py` | Grafik arayüz (önerilen kullanım şekli) |
| `luca_mizan_otomasyon.py` | Komut satırı (CLI) sürümü — aynı motoru kullanır |
| `luca_otomasyon_core.py` | Asıl otomasyon mantığı (Playwright); hem GUI hem CLI bunu kullanır |
| `.env` / `.env.example` | Giriş bilgileri ve varsayılan filtre ayarları |
| `requirements.txt` | Python bağımlılıkları |

## Ayarları değiştirme

`.env` dosyasındaki (veya arayüzdeki) şu değerlerle varsayılan filtreyi değiştirebilirsiniz:

```
MIZAN_YIL=2026
MIZAN_SINIF=1        # 1=1.Sınıf, 2=2.Sınıf, 3=İşletme Defteri, 4=Serbest Meslek Defteri, 5=Basit Usül
CIKTI_KLASORU=raporlar
```

## Neden şifrenizi ben (Claude) girmedim, uygulama giriyor?

Canlı bir tarayıcı oturumunda kimlik bilgilerinizi başkasının (benim) sizin
adınıza girmesi güvenlik açısından uygun değildi. Ama kendi bilgisayarınızda
çalışan, kimlik bilgilerini yalnızca sizin doldurduğunuz yerel bir dosyadan
okuyan bir uygulama yazmak farklı bir şey — bu, bir şifre yöneticisi
kullanmaya benzer bir örüntü. Uygulama, üye no/kullanıcı adı/parolanızı
`.env` dosyanızdan (veya arayüzdeki alanlardan) okuyup formu kendisi dolduruyor.

**`.env` dosyanızı kimseyle paylaşmayın, e-postayla göndermeyin, git'e eklemeyin.**

## Bilinen sınırlamalar

- Luca arayüzü klasik "frameset" tabanlı, eski nesil bir web uygulaması.
  Menü metinleri veya alan kimlikleri (id) Luca tarafında değişirse ilgili
  adımın güncellenmesi gerekir. Tüm mantık `luca_otomasyon_core.py` içinde
  ayrı, isimlendirilmiş fonksiyonlarda olduğu için düzeltmek kolaydır.
- Uygulama hem **tek** hem de **toplu** müşteri raporu için çalışacak şekilde
  tasarlandı. Toplu modda tüm filtrelenen müşteriler için sırasıyla rapor
  oluşturulur.
- İki adımlı doğrulama (varsa) veya beklenmeyen bir uyarı penceresi çıkarsa,
  tarayıcı görünür olduğu için elle müdahale edebilirsiniz.
