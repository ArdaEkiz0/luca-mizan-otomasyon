#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Luca Mizan Otomasyonu - Çekirdek Mantık (arayüzden bağımsız)
==============================================================

Bu modül, LUCA Mali Müşavir Paketi'nde giriş yapıp Müşteri Listesi'ni
filtreleme, bir müşteri seçme ve o müşteri için Mizan raporu oluşturma
işlemlerini yürütür. Hiçbir ekran/konsol çıktısı üretmez; tüm ilerleme
bilgisi verdiğiniz `log(mesaj: str)` fonksiyonuna gönderilir — böylece
hem bir GUI'den hem de bir komut satırı betiğinden aynı motoru
kullanabilirsiniz.

Kullanım şekli iki aşamalıdır (bir GUI'de "önce listele, sonra seç ve
rapor oluştur" akışına uyacak şekilde):

    core = LucaOtomasyonCore(uye_no, kullanici_adi, parola, cikti_klasoru)
    musteriler = core.baslat_ve_filtrele(yil="2026", sinif="1", log=print)
    # ... kullanıcıya musteriler listesini göster, birini seçtir ...
    core.musteri_sec(musteriler[0]["kisa_ad"], log=print)
    dosya_yolu = core.mizan_raporu_olustur(musteriler[0]["kisa_ad"], log=print)
    core.kapat()

Toplu (tüm filtrelenen müşteriler için) rapor almak isterseniz:

    core.toplu_mizan_raporu(musteriler, log=print)

GÜVENLİK: Bu modül kimlik bilgilerini yalnızca kurucuya (constructor)
parametre olarak alır; hiçbir yere yazmaz/loglamaz.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

from playwright.sync_api import (
    Frame,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

GIRIS_URL = "https://agiris.luca.com.tr/LUCASSO/giris.erp"

SINIF_ETIKETLERI = {
    "": "Tümü",
    "1": "1.Sınıf",
    "2": "2.Sınıf",
    "3": "İşletme Defteri",
    "4": "Serbest Meslek Defteri",
    "5": "Basit Usül",
}

LogFn = Callable[[str], None]


def _sessiz_log(_: str) -> None:
    pass


def _sayfa_hayatta_mi(page: Page) -> bool:
    """Sayfa/tarayıcı hâlâ açık mı kontrol et."""
    try:
        _ = page.url
        return True
    except Exception:
        return False


class LucaOtomasyonCore:
    def __init__(
        self,
        uye_no: str,
        kullanici_adi: str,
        parola: str,
        cikti_klasoru: Path | str = "raporlar",
        headless: bool = False,
    ) -> None:
        self.uye_no = uye_no
        self.kullanici_adi = kullanici_adi
        self.parola = parola
        self.cikti_klasoru = Path(cikti_klasoru)
        self.headless = headless

        self._playwright = None
        self._browser = None
        self._context = None
        self.dashboard: Optional[Page] = None
        self.liste_frame: Optional[Frame] = None
        # Müşteri listesinin bulunduğu sayfa - "Detay" tıklaması müşteri
        # panelini YENİ bir sekmede açarsa self.dashboard o yeni sekmeye
        # geçer; bu durumda müşteri listesine geri dönebilmek (toplu rapor
        # akışı) için listenin olduğu ORİJİNAL sayfayı ayrıca saklıyoruz.
        self._musteri_listesi_sayfasi: Optional[Page] = None
        self._son_yil = "2026"
        self._son_sinif = "1"

    # ------------------------------------------------------------------
    # Yardımcılar
    # ------------------------------------------------------------------

    def _frame_bul(self, page: Page, selector: str, deneme: int = 40, bekleme_ms: int = 500) -> Frame:
        # Luca'nın frameset tabanlı arayüzü, özellikle SSO yönlendirmesinin
        # hemen ardından, bazen yüklenmesi 20-30 saniyeyi bulabilen yavaş bir
        # ilk yükleme yapabiliyor. Varsayılan deneme sayısı bunu tolere
        # edecek şekilde yükseltildi (40 x 500ms = ~20 saniye); özellikle
        # yavaş olduğu bilinen adımlarda daha da yüksek bir değer verilebilir.
        for _ in range(deneme):
            for f in page.frames:
                try:
                    if f.locator(selector).count() > 0:
                        return f
                except Exception:
                    continue
            page.wait_for_timeout(bekleme_ms)

        # Hata durumunda tanısal bilgi (hangi frame'ler vardı, hangi URL'lerdeydi)
        frame_sayisi = len(page.frames)
        frame_urls = [f.url[:80] for f in page.frames[:10]]
        raise RuntimeError(
            f"'{selector}' seçicisini içeren bir frame bulunamadı "
            f"(toplam {frame_sayisi} frame tarandı). Frame URL'leri: {frame_urls}"
        )

    def _menu_frame_bul(
        self, page: Page, deneme: int = 150, bekleme_ms: int = 1000, log: LogFn = _sessiz_log
    ) -> Frame:
        # Ana panel (menü çerçevesi), özellikle SSO girişinin hemen
        # ardından çok yavaş yüklenebiliyor (bazen bomboş bir "yükleniyor"
        # animasyonunda uzunca takılı kalabiliyor); bu yüzden burada ekstra
        # sabırlı davranıyoruz (varsayılan: ~150 saniyeye kadar) ve kullanıcı
        # "sanki takıldı" sanmasın diye arada bir durum mesajı basıyoruz.
        # Luca'nın menü çerçevesini tanımlayan metin/işaretler hesaba göre
        # değişebildiği için birden fazla aday sırayla deneniyor.
        secenekler = [
            "text=Yönetici",
            "text=Ana Menü",
            "text=Menü",
            "text=Hızlı Menü",
            "#menuFrame",
        ]
        # NOT: Burada bilerek sayfayı YENİLEMİYORUZ (page.reload()). Bu sayfa
        # bir SSO POST yönlendirmesinin sonucu olduğu için yenileme, Chrome'un
        # "formu yeniden gönder" uyarısına (native bir tarayıcı arayüzü,
        # Playwright'ın dialog API'siyle yakalanamaz) takılıp otomasyonu
        # tamamen kilitleme riski taşıyor. Bunun yerine sadece sabırla
        # bekliyor ve kullanıcıya arada durum mesajı basıyoruz; panel er ya
        # da geç kendiliğinden yükleniyor (gözlemlendi).
        for deneme_no in range(deneme):
            for secici in secenekler:
                for f in page.frames:
                    try:
                        if f.locator(secici).count() > 0:
                            return f
                    except Exception:
                        continue

            gecen_sn = deneme_no * bekleme_ms / 1000
            if deneme_no > 0 and deneme_no % 15 == 0:
                log(f"  ...hâlâ menü/panel yükleniyor, bekleniyor ({int(gecen_sn)} sn)...")

            page.wait_for_timeout(bekleme_ms)

        frame_sayisi = len(page.frames)
        frame_urls = [f.url[:80] for f in page.frames[:10]]
        raise RuntimeError(
            f"Menü çerçevesi bulunamadı (toplam {frame_sayisi} frame tarandı). "
            f"Frame URL'leri: {frame_urls}. Luca'nın ana paneli henüz tam "
            f"yüklenmemiş ya da arayüz yapısı değişmiş olabilir."
        )

    def _kart_tikla(self, frame_or_page, log: LogFn = _sessiz_log) -> bool:
        """Verilen frame/sayfada, "2.0" rozetli OLMAYAN 'LUCA MALİ MÜŞAVİR
        PAKETİ' kartını metne göre arayıp tıklar. Bu, deterministik
        gonder('formTarget') çağrısı bir sebeple işe yaramazsa kullanılan
        SON ÇARE bir yedektir — birincil yöntem değildir."""
        try:
            kartlar = frame_or_page.locator("a, div, td, span, button").filter(
                has_text="MALİ MÜŞAVİR PAKETİ"
            )
            sayi = kartlar.count()
            for i in range(sayi):
                kart = kartlar.nth(i)
                try:
                    metin = kart.inner_text(timeout=2000)
                    if "2.0" in metin or "2,0" in metin:
                        continue
                    if "MALİ MÜŞAVİR PAKETİ" in metin:
                        log(f"  Kart bulundu (yedek yöntem, #{i}), tıklanıyor...")
                        kart.click(timeout=5000)
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def _rol_buton_tikla(
        self, frame: Frame, isim: str, log: LogFn = _sessiz_log, birincil_zaman_asimi: int = 5000
    ) -> None:
        """Erişilebilirlik adına (accessible name) göre bir düğmeye tıklar.

        BİRİNCİL YÖNTEM: Playwright'ın get_by_role("button", name=...)
        eşleşmesi. YEDEK YÖNTEM: Sayfada ara sıra görülen bir JS hatası
        (ör. bir script'in iki kez yüklenip yarıda kesilmesi — teşhis
        günlüğünde "zaten tanımlı/already declared" olarak görülüyor)
        yüzünden düğmenin erişilebilir adı zamanında oluşmayabiliyor; bu
        durumda düğmeyi value/metin içeriğine göre CSS seçicilerle arayıp
        tıklıyoruz. Bu, "LUCA MALİ MÜŞAVİR PAKETİ" kartı için kullanılan
        aynı birincil+yedek desenin bir benzeridir."""
        try:
            frame.get_by_role("button", name=isim, exact=True).click(timeout=birincil_zaman_asimi)
            return
        except PlaywrightTimeoutError:
            log(f"  '{isim}' düğmesi (birincil yöntemle) bulunamadı, yedek yöntem deneniyor...")

        # YEDEK YÖNTEMLER: Luca'da bazı "düğmeler" gerçek <button>/<input>
        # değil, üzerinde onclick olan <div>/<td>/<span> gibi elemanlar
        # olabiliyor (eski usül JS menülerde de aynı desen görüldü). Bu
        # yüzden önce yaygın buton türlerini, olmazsa herhangi bir elemanın
        # TAM metnini deniyoruz. Her adımda ne olduğunu (kaç eşleşme
        # bulundu, tıklama neden başarısız oldu) günlüğe yazıyoruz — bir
        # sonraki takılmada tahmin yürütmek yerine gerçek sebebi görebilelim.
        yedek_secenekler = [
            f'input[type="button"][value="{isim}"]',
            f'input[type="submit"][value="{isim}"]',
            f'button:has-text("{isim}")',
            f'a:has-text("{isim}")',
        ]
        for secici in yedek_secenekler:
            try:
                adaylar = frame.locator(secici)
                sayi = adaylar.count()
            except Exception as e:
                log(f"    [{secici}] sayım hatası: {str(e)[:100]}")
                continue
            if sayi == 0:
                continue
            try:
                adaylar.first.click(timeout=3000)
                log(f"  '{isim}' düğmesi yedek yöntemle bulunup tıklandı ({secici}).")
                return
            except Exception as e:
                log(f"    [{secici}] {sayi} eşleşme bulundu ama tıklama başarısız: {str(e)[:120]}")
                continue

        # Son çare: buton/input/link olmayan ama TAM olarak bu metni içeren
        # herhangi bir eleman (div/td/span vb.) — Luca'nın eski usül
        # tıklanabilir hücrelerini yakalar.
        try:
            genel = frame.get_by_text(isim, exact=True)
            sayi = genel.count()
            if sayi > 0:
                genel.first.click(timeout=3000)
                log(f"  '{isim}' metni genel arama ile bulunup tıklandı ({sayi} eşleşme).")
                return
            log(f"    [genel metin araması] '{isim}' ile tam eşleşen hiçbir eleman bulunamadı.")
        except Exception as e:
            log(f"    [genel metin araması] hata: {str(e)[:120]}")

        # SON ÇARE: Playwright'ın "tıklanabilirlik" kontrolü (görünür olma,
        # başka bir elemanın altında kalmama vb.) bazı elemanları -insan
        # gözüyle tıklanabilir görünseler bile- reddedebiliyor (ör. hafif bir
        # üst üste binme/overlay). Bu yüzden elemanı doğrudan JS ile
        # (Playwright'ın kontrolünü atlayarak) tıklıyoruz — "LUCA MALİ
        # MÜŞAVİR PAKETİ" kartında işe yarayan yöntemin aynısı.
        try:
            sonuc = frame.evaluate(
                """
                (isim) => {
                    const secici = 'button, input[type="button"], input[type="submit"], a, [onclick]';
                    const adaylar = Array.from(document.querySelectorAll(secici));
                    const metniAl = (el) => (el.innerText || el.value || '').trim();
                    // Bir kapsayıcı eleman da (ör. bir <div>) içindeki asıl
                    // butonun metnini miras alıp yanlışlıkla eşleşebilir; en
                    // az alt-elemana sahip ("en yaprak") olanı tercih ederek
                    // gerçek tıklanabilir öğeyi buluyoruz.
                    let tamEslesenler = adaylar.filter(el => metniAl(el) === isim)
                        .sort((a, b) => a.children.length - b.children.length);
                    let hedef = tamEslesenler[0];
                    if (!hedef) {
                        let icerenler = adaylar.filter(el => metniAl(el).includes(isim))
                            .sort((a, b) => a.children.length - b.children.length);
                        hedef = icerenler[0];
                    }
                    if (!hedef) return {bulundu: false};
                    hedef.scrollIntoView({block: 'center'});
                    const r = hedef.getBoundingClientRect();
                    const s = window.getComputedStyle(hedef);
                    hedef.click();
                    return {
                        bulundu: true,
                        tag: hedef.tagName.toLowerCase(),
                        genislik: Math.round(r.width),
                        yukseklik: Math.round(r.height),
                        display: s.display,
                        visibility: s.visibility,
                        disabled: !!hedef.disabled,
                    };
                }
                """,
                isim,
            )
        except Exception as e:
            sonuc = {"bulundu": False, "hata": str(e)[:150]}

        if sonuc.get("bulundu"):
            log(
                f"  '{isim}' JS ile doğrudan tıklandı (tag={sonuc.get('tag')}, "
                f"boyut={sonuc.get('genislik')}x{sonuc.get('yukseklik')}, "
                f"display={sonuc.get('display')}, disabled={sonuc.get('disabled')})."
            )
            return
        log(f"    [JS doğrudan tıklama] eleman bulunamadı/hata: {sonuc}")

        # TEŞHİS: Hiçbir yöntem işe yaramadıysa, çerçevede bu isimle
        # (kısmen de olsa) eşleşen elemanları -tüm sayfayı değil, sadece
        # ilgili olanları- kısaca döküyoruz; böylece bir dahaki sefere
        # tahmin yürütmek yerine gerçek yapıyı görüp kalıcı bir seçici
        # ekleyebiliriz.
        try:
            ozet = frame.evaluate(
                """
                (isim) => {
                    const adaylar = Array.from(document.querySelectorAll('*'));
                    const kucukIsim = isim.toLowerCase();
                    return adaylar
                        .filter(el => el.children.length === 0)
                        .map(el => ({
                            tag: el.tagName.toLowerCase(),
                            metin: (el.innerText || el.value || '').trim().slice(0, 30),
                            onclick: !!el.onclick || el.hasAttribute('onclick'),
                            gorunur: el.offsetParent !== null,
                        }))
                        .filter(a => a.metin.toLowerCase().includes(kucukIsim))
                        .slice(0, 15);
                }
                """,
                isim,
            )
            log(f"    [teşhis] '{isim}' ile eşleşen elemanlar: {ozet}")
        except Exception as e:
            log(f"    [teşhis] Eleman dökümü alınamadı: {str(e)[:120]}")

        raise RuntimeError(
            f"'{isim}' düğmesi bulunamadı/tıklanamadı (tüm yöntemler "
            f"başarısız oldu). Luca sayfası beklenmedik bir durumda "
            f"olabilir — sayfayı yeniden yükleyip tekrar deneyin."
        )

    _METIN_JS_KODU = """
        ([metin, eylem]) => {
            // ÖNEMLİ: el.innerText'e göre TAM (===) eşleşme, menü öğesinin
            // yanında küçük bir ok/ikon elemanı (ör. bir alt-menüsü
            // olduğunu gösteren "▸" işareti, ayrı bir <span> olarak) varsa
            // KIRILIYOR — çünkü innerText o ikonun metnini de içeriyor
            // ("Müşteri İşlemleri▸" gibi) ve bu asla verdiğimiz "metin" ile
            // birebir eşleşmiyor. Bu yüzden ÖNCE elemanın YALNIZCA kendi
            // DOĞRUDAN metin düğümlerine (alt elemanların metnini SAYMADAN)
            // bakıyoruz - ikon/ok genelde ayrı bir alt eleman olduğu için bu
            // kontrol onu otomatik olarak dışarıda bırakıyor. Hiçbir aday
            // bulunamazsa (ör. metin doğrudan değil de tek bir alt <span>
            // içindeyse - ki o zaman zaten o <span>'in kendisi 1. katmanda
            // yakalanır) klasik tam innerText eşleşmesine düşüyoruz.
            const normallestir = (s) => (s || '').replace(/\\s+/g, ' ').trim();
            const hedefMetin = normallestir(metin);
            const dogrudanMetni = (el) => normallestir(
                Array.from(el.childNodes)
                    .filter(n => n.nodeType === Node.TEXT_NODE)
                    .map(n => n.textContent)
                    .join('')
            );
            const secici = 'a, div, td, span, li, button, [onclick], [onmouseover]';
            const tumElemanlar = Array.from(document.querySelectorAll(secici));

            let adaylar = tumElemanlar.filter(el => dogrudanMetni(el) === hedefMetin);
            if (adaylar.length === 0) {
                adaylar = tumElemanlar.filter(el => normallestir(el.innerText) === hedefMetin);
            }
            // Bir üst kapsayıcı (ör. bir <div>) da içindeki <a>'nın metnini
            // miras aldığı için AYNI metinle eşleşebilir; en az alt-elemana
            // sahip (en "yaprak") olanı seçerek gerçek tıklanabilir öğeyi
            // (ör. <a>) yanlışlıkla sarmalayıcısı yerine buluyoruz.
            adaylar.sort((a, b) => a.children.length - b.children.length);
            const hedef = adaylar[0];
            if (!hedef) return {bulundu: false};
            hedef.scrollIntoView({block: 'center'});
            // Eski usül JS menüleri sıklıkla ÖNCE bir mouseover ile açılıp
            // SONRA tıklanabiliyor (gerçek bir kullanıcı elini önce üstüne
            // getirir, sonra tıklar). Bu yüzden eylem "click" olsa bile
            // önce bir mouseover, ardından click dispatch ediyoruz — bu,
            // yalnızca onclick'e bağlı öğelerde zararsız, ama yalnızca
            // onmouseover'la açılan alt menülerde gerekli olabiliyor.
            hedef.dispatchEvent(new MouseEvent('mouseover', {bubbles: true, cancelable: true, view: window}));
            if (eylem !== 'hover') {
                hedef.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                if (typeof hedef.click === 'function') {
                    hedef.click();
                }
            }
            return {bulundu: true, tag: hedef.tagName.toLowerCase()};
        }
    """

    def _metin_etkilesim(
        self,
        sayfa_veya_frame,
        metin: str,
        eylem: str = "click",
        log: LogFn = _sessiz_log,
        deneme: int = 20,
        bekleme_ms: int = 500,
    ) -> None:
        """Tam olarak `metin`i içeren bir elemanla etkileşime girer
        (tıklama ya da üzerine gelme/hover) — menü gezinmesinde (Yönetici,
        Müşteri İşlemleri, Muhasebe, Raporlar, Mizan vb.) kullanılır.
        `sayfa_veya_frame` bir Page (o an ki TÜM çerçeveler taranır) ya da
        belirli bir Frame olabilir.

        BİRİNCİL YÖNTEM: Playwright'ın get_by_text(exact=True) +
        click()/hover(). YEDEK YÖNTEM: "Ara" düğmesinde işe yarayan JS ile
        doğrudan tetikleme deseninin aynısı — Luca'nın eski usül menüleri
        gerçek CSS ":hover" değil, elemanların onclick/onmouseover
        özniteliklerine bağlı JS olay dinleyicileriyle çalışıyor (bu proje
        boyunca birkaç kez doğrulandı). Bu yüzden bir mouseover/click DOM
        olayını doğrudan JS ile tetiklemek, gerçek bir fare hareketi/tıklama
        olmasa bile aynı sonucu (alt menünün açılması ya da bağlantının
        işlemesi) veriyor.

        NOT: Bir alt menü (ör. "Raporlar") bir üst öğeye tıklandıktan HEMEN
        sonra henüz DOM'a eklenmemiş olabilir (JS ile geç oluşturuluyor).
        Bu yüzden JS yöntemi TEK seferlik değil, birkaç saniye boyunca
        (ve `sayfa_veya_frame` bir Page ise TÜM çerçevelerde) tekrar tekrar
        deneniyor. ÖNEMLİ: Bu bekleme sırasında sayfa KESİNLİKLE
        yenilenmiyor (page.reload()) — Luca'nın bazı sayfaları yenilemeyi
        açıkça yasaklıyor ("LUCA HATA — Lütfen sayfayı yenilemeyin.") ve
        yenilenirse oturumu bozup tarayıcıyı erişilemez hale getirebiliyor;
        bu gerçek bir denemede doğrulandı. Sadece SABIRLA bekleniyor.
        """
        try:
            eleman = sayfa_veya_frame.get_by_text(metin, exact=True).first
            if eylem == "hover":
                eleman.hover(timeout=3000)
            else:
                eleman.click(timeout=3000)
            return
        except Exception:
            log(f"  '{metin}' ({eylem}) birincil yöntemle bulunamadı, sabırla JS ile deneniyor...")

        cerceveler = list(getattr(sayfa_veya_frame, "frames", [sayfa_veya_frame]))
        bekleyici = sayfa_veya_frame if hasattr(sayfa_veya_frame, "wait_for_timeout") else cerceveler[0]

        for deneme_no in range(deneme):
            for cv in cerceveler:
                try:
                    sonuc = cv.evaluate(self._METIN_JS_KODU, [metin, eylem])
                except Exception:
                    continue
                if sonuc.get("bulundu"):
                    log(f"  '{metin}' ({eylem}) JS ile tetiklendi (tag={sonuc.get('tag')}).")
                    return
            # ÖNEMLİ: Kullanıcıya "hiçbir şey olmuyor, uygulama takılı kaldı"
            # izlenimi vermemek için birkaç saniyede bir kısa bir nabız
            # (heartbeat) mesajı basıyoruz - gerçek bir kullanım örneğinde bu
            # sessizliğin kullanıcının uygulamayı ERKEN kapatmasına (ve
            # otomasyonun asıl işe yarayacak yedek adımlara hiç ulaşamamasına)
            # yol açtığı gözlemlendi.
            if deneme_no > 0 and deneme_no % 4 == 0:
                log(f"    ...hâlâ '{metin}' aranıyor ({deneme_no * bekleme_ms / 1000:.0f} sn)...")
            # Alt menü henüz render olmamış olabilir; sabırla tekrar dene
            # (sayfa yenilemeden — bkz. yukarıdaki NOT).
            try:
                bekleyici.wait_for_timeout(bekleme_ms)
            except Exception:
                pass
            # Çerçeve listesi bu arada değişmiş olabilir (yeni bir açılır
            # menü çerçevesi eklenmiş olabilir); Page ise yeniden oku.
            cerceveler = list(getattr(sayfa_veya_frame, "frames", cerceveler))

        # TEŞHİS: Hiçbir çerçevede/yöntemde bulunamadıysa, bu isimle KISMEN
        # eşleşen elemanları (tüm sayfayı değil, sadece ilgili olanları)
        # her çerçevede kısaca dökelim — böylece bir dahaki sefere gerçek
        # DOM yapısını görüp (ör. metnin farklı yazıldığını, hâlâ
        # display:none olduğunu, ya da hiç render olmadığını) tahmin
        # yürütmeden anlayabiliriz.
        kucuk_metin = metin.lower()
        hicbir_kismi_eslesme_yok = True
        for i, cv in enumerate(cerceveler):
            try:
                ozet = cv.evaluate(
                    """
                    (kucukMetin) => {
                        const normallestir = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                        // NOT: Burada 'çocuk sayısı az' filtresi UYGULANMIYOR —
                        // önceki bir sürümde bu filtre, gerçek bir üretim
                        // arızasında (2+ alt elemanı olan sarmalayıcılar
                        // yüzünden) HİÇBİR TEŞHİS ÇIKTISI vermeyip araştırmayı
                        // köreltmişti. Burada TÜM elemanlar (kısaltılmış metin
                        // ve doğrudan metin düğümüyle) dökülüyor.
                        return Array.from(document.querySelectorAll('*'))
                            .map(el => ({
                                tag: el.tagName.toLowerCase(),
                                metin: normallestir(el.innerText).slice(0, 40),
                                cocukSayisi: el.children.length,
                                gorunur: el.offsetParent !== null,
                            }))
                            .filter(a => a.metin.toLowerCase().includes(kucukMetin))
                            .slice(0, 15);
                    }
                    """,
                    kucuk_metin,
                )
                if ozet:
                    hicbir_kismi_eslesme_yok = False
                    log(f"    [teşhis] çerçeve #{i} ({cv.url[:80] if hasattr(cv, 'url') else '?'}) içinde '{metin}' ile kısmen eşleşen elemanlar: {ozet}")
            except Exception as e:
                log(f"    [teşhis] çerçeve #{i} taranamadı: {str(e)[:100]}")

        if hicbir_kismi_eslesme_yok:
            # '{metin}' kelimesinin bir KISMI bile hiçbir çerçevede
            # bulunamadı — bu, elemanın görünür olduğu ama TAM metninin
            # farklı olduğu bir durum değil, muhtemelen elemanın hiç DOM'a
            # gelmediği (ör. tıklanan üst öğe içeriği yeni bir SEKME/
            # PENCEREDE açtı ve biz hâlâ eski sayfaya bakıyoruz, ya da menü
            # hiç açılmadı) bir durum. Hangi sayfa/çerçevelere baktığımızı
            # da not düşüyoruz.
            try:
                sayfa_sayisi = len(self._context.pages) if self._context else "?"
            except Exception:
                sayfa_sayisi = "?"
            frame_urls = [getattr(cv, "url", "?")[:80] for cv in cerceveler[:10]]
            log(
                f"    [teşhis] '{metin}' kelimesinin BİR KISMI bile hiçbir "
                f"çerçevede bulunamadı ({len(cerceveler)} çerçeve tarandı, "
                f"toplam {sayfa_sayisi} sekme/pencere açık). Taranan çerçeve "
                f"URL'leri: {frame_urls}. Bu genellikle, tıklanan üst menü "
                f"öğesinin içeriği YENİ bir sekme/pencerede açtığı ya da "
                f"menünün hiç açılmadığı anlamına gelir."
            )

        raise RuntimeError(
            f"'{metin}' ile ilgili eleman {deneme * bekleme_ms / 1000:.0f} saniye "
            f"içinde bulunamadı/{eylem} tetiklenemedi (birincil ve JS "
            f"yöntemleri başarısız oldu)."
        )

    def _yeni_sekme_kontrol_et(
        self, onceki_sayfa_sayisi: int, log: LogFn, bekleme_sn: float = 4.0
    ) -> None:
        """Üst düzey bir menü öğesine (ör. 'Yönetici', 'Muhasebe')
        tıkladıktan HEMEN sonra çağrılır.

        GERÇEK OLAYLA DOĞRULANDI: "Detay" düğmesi ve 'LUCA MALİ MÜŞAVİR
        PAKETİ' kartı, içeriği bazen AYNI sekmede değil YENİ bir sekme/
        pencerede açıyor (bkz. musteri_sec ve _urun_paneli_ac). Bir müşteri
        panelinde iken "Muhasebe > Raporlar > ..." kaskadının BİR KISMI bile
        bulunamaması (teşhis dökümünde hiçbir kısmi eşleşme çıkmaması),
        aynı şeyin üst menü sekmelerinde ("Yönetici", "Muhasebe") de
        olabileceğini düşündürüyor — tıklama içeriği YENİ bir sekmede
        açıyor olabilir ve biz hâlâ ESKİ (artık arka plandaki) sayfaya
        bakmaya devam ediyoruz. Bu yüzden her üst düzey tıklamadan hemen
        sonra yeni bir sekme açılıp açılmadığını kontrol edip, açıldıysa
        self.dashboard'u ona geçiriyoruz — tıpkı musteri_sec'teki gibi."""
        adim_ms = 200
        adim_sayisi = max(1, int(bekleme_sn * 1000 / adim_ms))
        for _ in range(adim_sayisi):
            if len(self._context.pages) > onceki_sayfa_sayisi:
                log("  Yeni bir sekme/pencere açıldığı algılandı, otomasyon oraya geçiyor...")
                self.dashboard = self._context.pages[-1]
                try:
                    self.dashboard.bring_to_front()
                except Exception:
                    pass
                return
            try:
                self.dashboard.wait_for_timeout(adim_ms)
            except Exception:
                return

    def _urun_paneli_ac(self, secim_page: Page, log: LogFn) -> Page:
        """'LUCA MALİ MÜŞAVİR PAKETİ' kartına tıklar ve sonucu bekler.

        BİRİNCİL YÖNTEM: Kartın görünen metnine göre tıklamak güvenilmez —
        Luca bu metni CSS ile satırlara böldüğü için ("LUCA" ve "MALİ"
        arasında gerçek bir boşluk karakteri bile olmayabiliyor), metin
        eşleşmesi tarayıcının o anki satır kaydırmasına göre değişkenlik
        gösteriyor. Bunun yerine kartın kendi JavaScript tıklama
        mekanizmasını (gonder('formTarget')) doğrudan çağırıyoruz — bu,
        Luca'nın kendi arayüzünün kullandığı yöntemin ta kendisi ve
        güvenilir. Aynı zamanda formun target'ını '_self' yaparak yeni bir
        sekme/pencere yerine mevcut sekmede yönlendirme yapılmasını
        sağlıyoruz.

        YEDEK YÖNTEM: Deterministik çağrı bir sebeple sonuç vermezse (ör.
        Luca'nın gonder() fonksiyonunun adı/imzası değişmişse), metne göre
        kart arama (_kart_tikla) denenir; o da başarısız olursa kullanıcıdan
        kartı kendisinin tıklaması istenir — hangi kartın doğru olduğunu
        tahmin etmek yerine bu adımı kullanıcıya bırakırız."""
        onceki_sayfa_sayisi = len(self._context.pages)
        onceki_url = secim_page.url

        log("'LUCA MALİ MÜŞAVİR PAKETİ' kartına tıklanıyor...")
        try:
            secim_page.evaluate(
                """
                () => {
                    if (document.forms.length > 0) {
                        document.forms[0].target = '_self';
                    }
                    if (typeof gonder === 'function') {
                        gonder('formTarget');
                        return true;
                    }
                    return false;
                }
                """
            )
        except Exception:
            pass

        def _ilerleme_var_mi() -> Optional[Page]:
            if len(self._context.pages) > onceki_sayfa_sayisi:
                return self._context.pages[-1]
            if secim_page.url != onceki_url:
                return secim_page
            return None

        hedef: Optional[Page] = None
        for _ in range(10):  # ~5 saniye
            hedef = _ilerleme_var_mi()
            if hedef:
                return hedef
            secim_page.wait_for_timeout(500)

        # Deterministik çağrı sonuç vermedi — metne dayalı yedek yöntemi dene.
        log("  Doğrudan tıklama sonuç vermedi, yedek yöntem deneniyor...")
        tiklandi = self._kart_tikla(secim_page, log)
        if not tiklandi:
            for f in secim_page.frames:
                if f == secim_page.main_frame:
                    continue
                try:
                    if self._kart_tikla(f, log):
                        tiklandi = True
                        break
                except Exception:
                    continue

        if tiklandi:
            for _ in range(10):  # ~5 saniye
                hedef = _ilerleme_var_mi()
                if hedef:
                    return hedef
                secim_page.wait_for_timeout(500)

        log(
            "Kart otomatik tıklanamadı. Ekranda birden fazla 'LUCA MALİ "
            "MÜŞAVİR PAKETİ' kartı olabilir. Lütfen az önce açılan tarayıcı "
            "penceresinde normalde kullandığınız kartı (rozetsiz/düz kart) "
            "kendiniz tıklayın. Otomasyon ilerleme algıladığında "
            "kendiliğinden devam edecek (en fazla 5 dakika bekleniyor)..."
        )
        try:
            secim_page.bring_to_front()
        except Exception:
            pass
        for _ in range(600):  # ~300 saniye
            hedef = _ilerleme_var_mi()
            if hedef:
                log("İlerleme algılandı, devam ediliyor...")
                return hedef
            secim_page.wait_for_timeout(500)

        raise RuntimeError(
            "Ürün paneli açılamadı (5 dakika bekleme sonunda ilerleme algılanmadı)."
        )

    # ------------------------------------------------------------------
    # Aşama 1: Giriş + Müşteri Listesi filtreleme
    # ------------------------------------------------------------------

    def baslat_ve_filtrele(self, yil: str, sinif: str, log: LogFn = _sessiz_log) -> list[dict]:
        """Tarayıcıyı açar, giriş yapar, Müşteri Listesi'ni Yıl/Sınıf
        filtresiyle açar ve eşleşen müşterileri döndürür. Tarayıcı oturumu
        açık bırakılır (self.dashboard) — sonraki adım için gereklidir."""
        self._son_yil = yil
        self._son_sinif = sinif

        log("Tarayıcı başlatılıyor...")
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless, slow_mo=30)
        self._context = self._browser.new_context(accept_downloads=True)

        log("Giriş sayfası açılıyor...")
        secim_page = self._context.new_page()
        secim_page.goto(GIRIS_URL, wait_until="domcontentloaded")

        # Bazı durumlarda gerçek giriş formu (Üye No/Kullanıcı Adı/Parola)
        # açılmadan önce bir Captcha doğrulama ekranı çıkabilir. Captcha
        # çözmek güvenlik gereği yalnızca kullanıcıya bırakılmalıdır; bu
        # yüzden gerçek giriş alanları (bir parola alanı dahil) görünene
        # kadar bekleriz.
        giris_formu_kontrolu = """
            () => {
                const inputs = document.querySelectorAll('input');
                let textCount = 0;
                let hasPassword = false;
                for (const inp of inputs) {
                    if (inp.offsetParent === null) continue;
                    const t = (inp.type || '').toLowerCase();
                    if (t === 'text' || t === 'number' || t === 'email' || t === '') textCount++;
                    if (t === 'password') hasPassword = true;
                }
                return textCount >= 2 && hasPassword;
            }
        """
        try:
            secim_page.wait_for_function(giris_formu_kontrolu, timeout=5000)
        except PlaywrightTimeoutError:
            log(
                "Giriş formundan önce bir Captcha doğrulaması çıktı gibi "
                "görünüyor. Lütfen az önce açılan tarayıcı penceresine geçip "
                "resimdeki karakterleri girip \"Tamam\"a basın. Bunu "
                "tamamladıktan sonra normal giriş ekranı açılacak ve "
                "otomasyon kendiliğinden devam edecek (en fazla 5 dakika "
                "bekleniyor)..."
            )
            try:
                secim_page.bring_to_front()
            except Exception:
                pass
            secim_page.wait_for_function(giris_formu_kontrolu, timeout=300000)
            log("Doğrulama tamamlandı, giriş formu bulundu, devam ediliyor...")

        # Luca'nın giriş formundaki alan adları (name özniteliği) hesaba göre
        # küçük farklılıklar gösterebiliyor; bu yüzden önce alanları
        # isimlerine bakarak (üye no / kullanıcı adı / parola ipucu içeren
        # name'ler) bulmayı deniyoruz, bulamazsak sıradaki text input'a
        # yazmaya düşüyoruz.
        form_analiz = secim_page.evaluate(
            """
            () => {
                const elemanlar = document.querySelectorAll('input, select, textarea');
                const sonuc = [];
                for (const el of elemanlar) {
                    if (el.offsetParent === null) continue;
                    sonuc.push({
                        tag: el.tagName.toLowerCase(),
                        type: el.type || '',
                        name: el.name || '',
                        id: el.id || '',
                        placeholder: el.placeholder || '',
                    });
                }
                return sonuc;
            }
            """
        )
        try:
            analiz_dosyasi = self.cikti_klasoru / "_son_giris_formu.json"
            analiz_dosyasi.parent.mkdir(parents=True, exist_ok=True)
            analiz_dosyasi.write_text(json.dumps(form_analiz, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass  # Bu sadece isteğe bağlı bir teşhis kaydı; başarısız olması akışı bozmasın.

        def _alan_bul(ipuclari: list[str]) -> Optional[str]:
            """Form analizinde ipucu içeren ilk input'un name'ini döndürür."""
            for elem in form_analiz:
                if elem.get("tag") != "input":
                    continue
                tip = elem.get("type", "").lower()
                if tip not in ("text", "number", "email", "password", ""):
                    continue
                ad = (elem.get("name", "") + " " + elem.get("id", "") + " " + elem.get("placeholder", "")).lower()
                for ipucu in ipuclari:
                    if ipucu in ad:
                        return elem.get("name") or None
            return None

        uye_adi = _alan_bul(["musteri", "uye", "member"])
        kullanici_adi_alani = _alan_bul(["kullanici", "user", "login"])
        parola_adi = _alan_bul(["parola", "sifre", "password", "pass"])

        text_inputs = secim_page.locator('input[type="text"]')
        if uye_adi:
            secim_page.locator(f'input[name="{uye_adi}"]').fill(self.uye_no)
        elif text_inputs.count() >= 1:
            text_inputs.nth(0).fill(self.uye_no)

        # NOT: KULLANICI ADI alanı BİLEREK doldurulmuyor — kullanıcının kendi
        # isteğiyle bu alanı her seferinde kendisi elle giriyor. Üye No ve
        # Parola yine .env'den otomatik doluyor.
        if kullanici_adi_alani:
            log("  (KULLANICI ADI alanı bilerek boş bırakıldı — bunu siz gireceksiniz.)")

        if parola_adi:
            secim_page.locator(f'input[name="{parola_adi}"]').fill(self.parola)
        else:
            secim_page.locator('input[type="password"]').first.fill(self.parola)

        log(
            "Üye No ve Parola dolduruldu. Lütfen az önce açılan tarayıcı "
            "penceresinde KULLANICI ADI alanını kendiniz yazıp \"GİRİŞ\" "
            "düğmesine basın. Bunu yaptıktan sonra (varsa ardından gelen bir "
            "güvenlik doğrulamasını da tamamladıktan sonra) otomasyon "
            "kendiliğinden devam edecek (en fazla 5 dakika bekleniyor)..."
        )
        try:
            secim_page.bring_to_front()
        except Exception:
            pass

        log("Ürün paneli açılıyor...")
        # NOT: Bu adımı metin içeriğine göre değil, URL'ye göre bekliyoruz.
        # Ürün paneli her zaman ".../LUCASSO/main.erp" adresinde açılıyor,
        # bu yüzden URL daha güvenilir bir işaret. Kullanıcı adı girişi ve
        # GİRİŞ'e basma artık tamamen kullanıcı tarafından yapıldığından,
        # burada doğrudan uzun süreli (5 dakikaya kadar) bekliyoruz — bu süre
        # hem kullanıcı adının yazılmasını hem de olası bir güvenlik
        # doğrulamasını (Captcha/SMS-e-posta kodu) kapsar.
        try:
            secim_page.wait_for_url("**/main.erp*", timeout=300000)
            log("Giriş tamamlandı, devam ediliyor...")
        except PlaywrightTimeoutError:
            raise RuntimeError(
                "Giriş 5 dakika içinde tamamlanmadı (kullanıcı adı/GİRİŞ adımı "
                "bekleniyordu). Lütfen uygulamayı yeniden başlatıp tekrar deneyin."
            )

        secim_page.wait_for_load_state("domcontentloaded")
        secim_page.wait_for_timeout(500)

        self.dashboard = self._urun_paneli_ac(secim_page, log)

        # Bazı Chromium sürümleri, arka planda/odaksız kalan sekmelerdeki
        # JS zamanlayıcılarını (setTimeout/rAF) yavaşlatabiliyor. "ssoGiris.do"
        # sayfası kendiliğinden asıl panele yönlendiren bir ara sayfa
        # olduğundan, bu yönlendirmenin engellenmemesi için sekmeyi öne
        # alıyoruz (zararsız — sayfayı yenilemez/yeniden göndermez).
        try:
            self.dashboard.bring_to_front()
        except Exception:
            pass

        # TEŞHİS: "ssoGiris.do" ara sayfası bazen kendiliğinden asıl panele
        # geçmiyor (beyaz/iskelet ekranda takılı kalıyor). Bunun gerçek
        # nedenini görebilmek için sayfa/konsol hatalarını ve başarısız ağ
        # isteklerini günlüğe yazıyoruz — böylece bir sonraki takılmada
        # tarayıcıya bakmadan sebebi görebiliriz. Sadece bilgi amaçlıdır,
        # akışı değiştirmez; aşırı gürültüyü önlemek için sınırlı sayıda
        # mesaj basılır.
        _teshis_sayaci = {"n": 0}
        _TESHIS_LIMIT = 12

        def _teshis_log(mesaj: str) -> None:
            if _teshis_sayaci["n"] >= _TESHIS_LIMIT:
                return
            _teshis_sayaci["n"] += 1
            log(f"  [teşhis] {mesaj[:220]}")

        def _konsol_dinleyici(msg) -> None:
            try:
                if msg.type == "error":
                    _teshis_log(f"Konsol hatası: {msg.text}")
            except Exception:
                pass

        def _sayfa_hata_dinleyici(err) -> None:
            _teshis_log(f"Sayfa hatası: {err}")

        def _istek_hata_dinleyici(request) -> None:
            try:
                basarisizlik = request.failure
                if basarisizlik:
                    _teshis_log(f"Ağ isteği başarısız: {request.url} -> {basarisizlik}")
            except Exception:
                pass

        try:
            self.dashboard.on("console", _konsol_dinleyici)
            self.dashboard.on("pageerror", _sayfa_hata_dinleyici)
            self.dashboard.on("requestfailed", _istek_hata_dinleyici)
        except Exception:
            pass

        self.dashboard.wait_for_load_state("domcontentloaded")
        # Sayfa hâlâ about:blank veya geçiş aşamasındaysa yüklenmesini bekle
        for _ in range(20):
            if self.dashboard.url and "about:blank" not in self.dashboard.url:
                break
            self.dashboard.wait_for_timeout(500)
        self.dashboard.wait_for_timeout(1000)

        if not _sayfa_hayatta_mi(self.dashboard):
            raise RuntimeError(
                "Tarayıcı sayfası/konteksti kapatılmış. Lütfen uygulamayı yeniden başlatın."
            )
        log(f"Ana panele girildi: {self.dashboard.url}")

        log(
            "Müşteri Listesi açılıyor... (Ana panel ilk yüklenmede yavaş "
            "olabilir, menü bulununcaya kadar bekleniyor)"
        )

        # "Yönetici" menüsüne tıkla — normal olarak ayrı bir menü çerçevesinde
        # olur; bulunamazsa doğrudan ana sayfada aranır (yedek yol). Her
        # etkileşim artık _metin_etkilesim() üzerinden gidiyor: bu, Playwright
        # tıklama/hover'ı bir sebeple (görünürlük/aktifleştirme kontrolü)
        # başarısız olursa JS ile doğrudan tetiklemeye düşen dayanıklı bir
        # yöntem (aynı "Ara" düğmesinde işe yarayan desen).
        def _musteri_listesini_ac() -> None:
            """Müşteri Listesi'ni doğrudan URL ile aç — menü tıklaması
            apymenu.js yüzünden her zaman başarısız, zaman kaybı."""
            from time import time as _zaman
            log("  Doğrudan URL ile Müşteri Listesi açılıyor...")
            url = (
                "https://auygs.luca.com.tr/Luca/listSirketAction.do"
                f"?time={int(_zaman() * 1000)}"
            )
            for cv in self.dashboard.frames:
                if "musteriBilgileri" in cv.url:
                    cv.goto(url, wait_until="domcontentloaded", timeout=30000)
                    cv.wait_for_timeout(1000)
                    log(f"  Müşteri Listesi açıldı: {cv.url}")
                    return
            self.dashboard.goto(url, wait_until="domcontentloaded", timeout=30000)
            self.dashboard.wait_for_timeout(1000)
            log(f"  Müşteri Listesi açıldı: {self.dashboard.url}")

        _musteri_listesini_ac()

        # Müşteri listesi frame'ini bul — #YIL select'ını içeren frame.
        self.liste_frame = self._frame_bul(self.dashboard, "#YIL")
        self.liste_frame.wait_for_selector("table.data-table", timeout=15000)
        # Bu sayfayı ayrıca sakla — "Detay" müşteri panelini yeni bir
        # sekmede açarsa self.dashboard değişecek, ama listeye dönüş için
        # bu orijinal sayfa referansı gerekiyor (bkz. musteri_kartina_don).
        self._musteri_listesi_sayfasi = self.dashboard

        etiket = SINIF_ETIKETLERI.get(sinif, sinif)
        log(f"Filtre uygulanıyor: Yıl={yil}, Sınıf={etiket}")
        self._rol_buton_tikla(self.liste_frame, "Filtre", log)
        self.liste_frame.wait_for_selector("#YIL", state="visible")
        self.liste_frame.locator("#YIL").select_option(yil)
        # #YIL seçildiğinde onchange="gonder('yil')" formu gönderiyor ve
        # sayfa yeniden yükleniyor. Sayfa yüklenince Filtre paneli tekrar
        # kapanıyor, #SINIF görünmüyor. Sayfa tamamen yüklenip Filtre'yi
        # tekrar açıp #SINIF seçelim.
        self.liste_frame.wait_for_load_state("domcontentloaded")
        self.liste_frame.wait_for_timeout(500)
        self.liste_frame = self._frame_bul(self.dashboard, "#YIL")
        self._rol_buton_tikla(self.liste_frame, "Filtre", log)
        self.liste_frame.wait_for_selector("#SINIF", state="visible", timeout=10000)
        self.liste_frame.locator("#SINIF").select_option(sinif)
        self._rol_buton_tikla(self.liste_frame, "Ara", log)
        self.liste_frame.wait_for_timeout(1000)

        musteriler = self._musterileri_oku()
        log(f"{len(musteriler)} müşteri bulundu.")
        return musteriler

    def _musterileri_oku(self) -> list[dict]:
        assert self.liste_frame is not None
        satirlar = self.liste_frame.locator("table.data-table tr.satir")
        adet = satirlar.count()
        musteriler = []
        for i in range(adet):
            hucreler = satirlar.nth(i).locator("td")
            try:
                musteriler.append(
                    {
                        "index": i,
                        "kisa_ad": hucreler.nth(1).inner_text().strip(),
                        "uzun_ad": hucreler.nth(2).inner_text().strip(),
                        "vergi_dairesi": hucreler.nth(3).inner_text().strip(),
                        "vergi_no": hucreler.nth(4).inner_text().strip(),
                    }
                )
            except Exception:
                continue
        return musteriler

    # ------------------------------------------------------------------
    # Aşama 2: Müşteri seçimi + Mizan raporu
    # ------------------------------------------------------------------

    def _sirket_sec_kombodan(self, kisa_ad: str, log: LogFn = _sessiz_log) -> bool:
        """TopFrameAction frame'indeki SirketCombo + DonemCombo + Tamam
        akışıyla 'çalışılan firma'yı değiştir.

        KRİTİK: Luca'da raporun hangi firma için hazırlanacağını belirleyen
        şey müşteri listesindeki satıra tıklamak DEĞİL, sağ üstteki firma
        seçicisidir (SirketCombo). Seçim + Tamam sonrası TopFrameAction
        URL'i şuna döner:
            TopFrameAction.do?...&SIRKET_ID=<id>&DONEM_ID=<donem>&DONEM_TXT=...
        Bu yöntem başarılıysa True döner."""
        from time import time as _zaman

        # --- Önce frameset ana sayfasında olduğumuzdan emin ol ---
        # Müşteri listesi doğrudan dashboard.goto(listSirketAction) ile
        # açıldıysa frameset kaybolur ve TopFrameAction frame'i kalmaz.
        try:
            if "luca.do" not in self.dashboard.url:
                luca_url = (
                    "https://auygs.luca.com.tr/Luca/luca.do"
                    f"?time={int(_zaman() * 1000)}"
                )
                log("  Frameset'e geri dönülüyor (luca.do)...")
                self.dashboard.goto(luca_url, wait_until="domcontentloaded", timeout=30000)
                self.dashboard.wait_for_timeout(2500)
        except Exception as e:
            log(f"  UYARI: luca.do'ya dönülemedi: {str(e)[:100]}")

        # --- SirketCombo içeren frame'i SEÇİCİYE göre bul (URL'e güvenme) ---
        top_frame = None
        for _ in range(20):
            for cv in self.dashboard.frames:
                try:
                    if cv.locator("#SirketCombo").count() > 0:
                        top_frame = cv
                        break
                except Exception:
                    continue
            if top_frame is not None:
                break
            self.dashboard.wait_for_timeout(500)
        if top_frame is None:
            log("  UYARI: #SirketCombo hiçbir frame'de bulunamadı.")
            return False

        combo = top_frame.locator("#SirketCombo")
        secenekler = []
        adet = combo.locator("option").count()
        for i in range(adet):
            try:
                metin = combo.locator("option").nth(i).inner_text().strip()
                deger = combo.locator("option").nth(i).get_attribute("value")
            except Exception:
                continue
            secenekler.append((metin, deger, i))
        if not secenekler:
            log("  UYARI: SirketCombo seçenekleri okunamadı.")
            return False

        secili = None
        for metin, deger, i in secenekler:
            if metin == kisa_ad:
                secili = i
                break
        if secili is None:
            adaylar = []
            for metin, deger, i in secenekler:
                if not metin:
                    continue
                if metin == kisa_ad[: len(metin)]:
                    adaylar.append((metin, deger, i))
                elif kisa_ad == metin[: len(kisa_ad)]:
                    adaylar.append((metin, deger, i))
            if adaylar:
                adaylar.sort(key=lambda x: len(x[0]), reverse=True)
                secili = adaylar[0][2]
        if secili is None:
            log(f"  UYARI: '{kisa_ad}' SirketCombo'da bulunamadı.")
            return False

        secilen_metin = secenekler[secili][0]
        mevcut_index = combo.evaluate("el => el.selectedIndex")
        if mevcut_index != secili:
            combo.select_option(index=secili)
            top_frame.wait_for_timeout(1500)  # loadDonem() AJAX'ı dönemleri doldursun
            log(f"  SirketCombo'dan '{secilen_metin}' seçildi.")
        else:
            log(f"  '{secilen_metin}' zaten seçili.")

        # Dönem combo'su — _son_yil içeren (ör. 2026) dönemi seç
        try:
            donem = top_frame.locator("#DonemCombo")
            donem.wait_for_selector("option", timeout=10000)
            hedef = str(self._son_yil)
            secildi = False
            d_adet = donem.locator("option").count()
            for i in range(d_adet):
                try:
                    d_metin = donem.locator("option").nth(i).inner_text()
                except Exception:
                    continue
                if d_metin and hedef in d_metin:
                    donem.select_option(index=i)
                    log(f"  Dönem seçildi: {d_metin.strip()}")
                    secildi = True
                    break
            if not secildi and d_adet > 1:
                donem.select_option(index=1)
                log("  Dönem eşleşmedi, ilk dönem seçildi.")
        except Exception as e:
            log(f"  UYARI: Dönem seçilemedi: {str(e)[:100]}")

        # Tamam -> formSubmit(event, 0)
        try:
            sonuc = top_frame.evaluate(
                """() => {
                    if (typeof formSubmit === 'function') {
                        formSubmit(null, 0);
                        return {ok: true};
                    }
                    return {ok: false, msg: 'formSubmit yok'};
                }"""
            )
            log(f"  formSubmit çağrıldı: {sonuc}")
        except Exception as e:
            log(f"  formSubmit hatası: {str(e)[:120]}")
            return False

        top_frame.wait_for_timeout(3000)
        # Doğrula: TopFrameAction URL'i SIRKET_ID içeriyor mu?
        for cv in self.dashboard.frames:
            try:
                if "TopFrameAction" in cv.url and "SIRKET_ID" in cv.url:
                    log(f"  Firma değişti: {cv.url[:140]}")
                    return True
            except Exception:
                continue
        log("  Firma değişimi doğrulanamadı ama devam ediliyor.")
        return True

    def musteri_sec(self, kisa_ad: str, log: LogFn = _sessiz_log) -> None:
        if self.liste_frame is None:
            raise RuntimeError("Önce baslat_ve_filtrele() çağrılmalı.")
        log(f"'{kisa_ad}' seçilip müşteri kartı açılıyor...")

        # --- BİRİNCİL YÖNTEM: SirketCombo ile 'çalışılan firma'yı değiştir ---
        # Luca'da raporun hangi firmaya ait olacağını belirleyen şey sağ
        # üstteki firma seçicisidir (SirketCombo + Tamam). Bu akış başarılı
        # olursa eski dblclick akışına hiç gerek kalmaz.
        if self._sirket_sec_kombodan(kisa_ad, log):
            log(f"  '{kisa_ad}' SirketCombo ile çalışılan firma yapıldı.")
            return

        # --- YEDEK: dblclick akışı (eski yöntem) ---
        # Frame her çağrıyı yeniden bul — musteri_kartina_don() sonrası
        # eski frame referansı detached olabilir.
        try:
            self.liste_frame = self._frame_bul(self.dashboard, "#YIL")
            self.liste_frame.wait_for_selector("table.data-table tr.satir", timeout=10000)
        except Exception:
            pass

        satir_sayisi = self.liste_frame.locator("table.data-table tr.satir").count()
        log(f"  Tabloda {satir_sayisi} satır bulundu.")
        if satir_sayisi == 0:
            raise RuntimeError(
                f"Tabloda hiç satır yok! Filtre uygulanmamış olabilir. "
                f"Müşteri listesine geri dönüp filtreleri kontrol edin."
            )

        eslesme = self.liste_frame.locator("table.data-table tr.satir", has_text=kisa_ad)
        if eslesme.count() == 0:
            mevcut_isimler = []
            for i in range(min(satir_sayisi, 10)):
                try:
                    isim = self.liste_frame.locator(
                        "table.data-table tr.satir"
                    ).nth(i).locator("td").nth(1).inner_text().strip()
                    mevcut_isimler.append(isim)
                except Exception:
                    pass
            raise RuntimeError(
                f"'{kisa_ad}' tabloda bulunamadı! Tablodaki ilk isimler: {mevcut_isimler}"
            )

        satir = eslesme.first
        onceki_sayfa_sayisi = len(self._context.pages)
        onceki_url = self.dashboard.url

        tiklandi = False

        # --- ADIM 0: Debug — gonder() fonksiyonunu ve formları analiz et ---
        try:
            debug_info = self.liste_frame.evaluate(
                """() => {
                    const result = {
                        gonder_exists: typeof gonder === 'function',
                        sec_exists: typeof sec === 'function',
                        form_count: document.forms.length,
                        form_details: [],
                        gonder_source: null,
                    };
                    // Form detayları
                    for (let i = 0; i < document.forms.length; i++) {
                        const f = document.forms[i];
                        result.form_details.push({
                            name: f.name,
                            id: f.id,
                            action: f.action,
                            method: f.method,
                            field_count: f.elements.length,
                        });
                    }
                    // gonder kaynak kodu (ilk 500 karakter)
                    if (typeof gonder === 'function') {
                        result.gonder_source = gonder.toString().substring(0, 500);
                    }
                    return result;
                }"""
            )
            log(f"  DEBUG gonder: var={debug_info.get('gonder_exists')}, "
                f"forms={debug_info.get('form_count')}, "
                f"sec={debug_info.get('sec_exists')}")
            if debug_info.get('form_details'):
                for fd in debug_info['form_details'][:3]:
                    log(f"    form: name={fd.get('name','?')}, action={fd.get('action','?')[:60]}, "
                        f"fields={fd.get('field_count')}")
            if debug_info.get('gonder_source'):
                log(f"  gonder src: {debug_info['gonder_source'][:200]}")
        except Exception as e:
            log(f"  DEBUG analiz hatası: {str(e)[:120]}")

        # --- ADIM 1: dblclick ile müşteri satırına çift tıkla ---
        try:
            log(f"  '{kisa_ad}' dblclick deneniyor...")
            satir.dblclick(timeout=10000)
            tiklandi = True
            log(f"  '{kisa_ad}' dblclick başarılı.")
        except Exception as e:
            log(f"  dblclick başarısız: {str(e)[:120]}")

        # --- ADIM 2: dblclick sonrası debug — gonder çalıştı mı? ---
        if tiklandi:
            self.dashboard.wait_for_timeout(2000)
            try:
                after_debug = self.liste_frame.evaluate(
                    """() => {
                        const result = {
                            current_url: window.location.href,
                            form_count: document.forms.length,
                            form_details: [],
                        };
                        for (let i = 0; i < document.forms.length; i++) {
                            const f = document.forms[i];
                            const fields = {};
                            for (let j = 0; j < f.elements.length; j++) {
                                const el = f.elements[j];
                                if (el.name && el.value) {
                                    fields[el.name] = el.value.substring(0, 50);
                                }
                            }
                            result.form_details.push({
                                name: f.name,
                                id: f.id,
                                action: f.action,
                                method: f.method,
                                fields: fields,
                            });
                        }
                        return result;
                    }"""
                )
                log(f"  POST-dblclick frame URL: {after_debug.get('current_url', '?')[:80]}")
                if after_debug.get('form_details'):
                    for fd in after_debug['form_details'][:3]:
                        log(f"    form: name={fd.get('name','?')}, action={fd.get('action','?')[:60]}")
                        if fd.get('fields'):
                            for k, v in list(fd['fields'].items())[:5]:
                                log(f"      {k} = {v}")
            except Exception as e:
                log(f"  POST-dblclick debug hatası: {str(e)[:120]}")

            # Dashboard URL kontrolü
            log(f"  Dashboard URL after dblclick: {self.dashboard.url[:80]}")
            for cv in self.dashboard.frames:
                try:
                    log(f"  Frame URL: {cv.url[:80]}")
                except Exception:
                    pass

        # --- ADIM 3: dblclick başarısızsa programatik sec()+gonder() ---
        if not tiklandi:
            try:
                log("  dblclick başarısız, sec()+gonder() deneniyor...")
                onclick_str = satir.get_attribute("onclick") or ""
                if "sec(" in onclick_str:
                    import re
                    sec_match = re.search(
                        r"sec\(this,\s*'([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)'",
                        onclick_str
                    )
                    if sec_match:
                        sirket_id = sec_match.group(1)
                        kisa_ad_found = sec_match.group(2)
                        vergi_no = sec_match.group(3)
                        sec_gonder_sonuc = self.dashboard.evaluate(
                            """([sirketId, kisaAd, vergiNo]) => {
                                let secFunc = null;
                                let gonderFunc = null;
                                for (let i = 0; i < window.frames.length; i++) {
                                    try {
                                        let f = window.frames[i];
                                        if (typeof f.sec === 'function') {
                                            secFunc = f.sec;
                                            gonderFunc = f.gonder;
                                            break;
                                        }
                                    } catch(e) {}
                                }
                                if (!secFunc) return {ok: false, msg: 'sec not found'};
                                try { secFunc(null, sirketId, kisaAd, vergiNo, '', ''); }
                                catch(e) { return {ok: false, msg: 'sec() error: ' + e.toString()}; }
                                if (gonderFunc) {
                                    try { gonderFunc('guncelle'); return {ok: true, method: 'sec+gonder'}; }
                                    catch(e) { return {ok: false, msg: 'gonder() error: ' + e.toString()}; }
                                }
                                return {ok: false, msg: 'gonder not found'};
                            }""",
                            [sirket_id, kisa_ad_found, vergi_no]
                        )
                        log(f"  sec()+gonder() sonucu: {sec_gonder_sonuc}")
                        tiklandi = True
            except Exception as e:
                log(f"  sec()+gonder() hatası: {str(e)[:150]}")

        if not tiklandi:
            raise RuntimeError(f"'{kisa_ad}' için hiç bir tıklama yöntemi çalışmadı!")

        # --- Sayfa değişikliğini bekle ---
        frame_yonlendi = False
        for _ in range(40):  # ~20 saniye
            if len(self._context.pages) > onceki_sayfa_sayisi:
                log("  Yeni sekme açıldı, o sekmeye geçiliyor...")
                self.dashboard = self._context.pages[-1]
                try:
                    self.dashboard.bring_to_front()
                except Exception:
                    pass
                break
            if self.dashboard.url != onceki_url:
                log(f"  Sayfa yönlendirildi: {self.dashboard.url[:80]}")
                break
            # Frame URL'lerinde değişiklik var mı kontrol et (sadece 1 kez log)
            if not frame_yonlendi:
                try:
                    for cv in self.dashboard.frames:
                        if cv.url != onceki_url and "luca.do" not in cv.url:
                            log(f"  Frame yönlendirildi: {cv.url[:80]}")
                            frame_yonlendi = True
                            break
                except Exception:
                    pass
            self.dashboard.wait_for_timeout(500)

        self.dashboard.wait_for_timeout(2000)

        # --- Doğrulama: müşteri sayfası yüklendi mi? ---
        musteri_bulundu = False
        try:
            for cv in self.dashboard.frames:
                if ("musteriBilgileri" in cv.url or "sirketDetay" in cv.url
                        or "selectSirketAction" in cv.url or "editSirketAction" in cv.url):
                    musteri_bulundu = True
                    log(f"  Müşteri sayfası doğrulandı: {cv.url[:80]}")
                    break
        except Exception:
            pass

        if not musteri_bulundu:
            try:
                sayfa_icerigi = self.dashboard.content()
                if kisa_ad.upper() in sayfa_icerigi.upper():
                    musteri_bulundu = True
                    log(f"  Doğrulama: '{kisa_ad}' sayfa içeriğinde bulundu.")
            except Exception:
                pass

        if not musteri_bulundu:
            log(f"  UYARI: '{kisa_ad}' için müşteri sayfası doğrulanamadı! "
                f"URL: {self.dashboard.url[:80]}")
            # Son çare: dblclick event dispatch
            try:
                log("  Alternatif: satır dblclick event dispatch...")
                alt_result = self.liste_frame.evaluate(
                    """(satirIndex) => {
                        const satir = document.querySelectorAll('table.data-table tr.satir')[satirIndex];
                        if (!satir) return {ok: false, msg: 'satir not found'};
                        const evt = new MouseEvent('dblclick', {
                            bubbles: true, cancelable: true, view: window
                        });
                        satir.dispatchEvent(evt);
                        return {ok: true, method: 'dblclick event dispatched'};
                    }""",
                    eslesme.first.evaluate(
                        "el => Array.from(el.parentNode.children).indexOf(el)"
                    ),
                )
                log(f"  Alternatif dblclick event: {alt_result}")
                self.dashboard.wait_for_timeout(3000)
                for cv in self.dashboard.frames:
                    if ("musteriBilgileri" in cv.url or "sirketDetay" in cv.url
                            or "selectSirketAction" in cv.url or "editSirketAction" in cv.url):
                        musteri_bulundu = True
                        log(f"  Alternatif yöntemle müşteri bulundu: {cv.url[:80]}")
                        break
            except Exception as e:
                log(f"  Alternatif dblclick hatası: {str(e)[:120]}")

        if not musteri_bulundu:
            log(f"  HATA: '{kisa_ad}' müşteri sayfası açılamadı! "
                f"URL: {self.dashboard.url[:80]}")

    def _tarih_normalize(self, tarih: str) -> str:
        """Kullanıcı girişini GG/AA/YYYY formatına çevirir.

        Kabul edilen girişler: 01/01/2026, 01.01.2026, 01-01-2026,
        01012026, 1.1.2026. Boş/geçersiz ise boş döner.
        """
        if not tarih:
            return ""
        t = tarih.strip()
        # GGAAYYYY (8 basamak, ayraçsız)
        if t.isdigit() and len(t) == 8:
            return f"{t[0:2]}/{t[2:4]}/{t[4:8]}"
        # GG.AA.YYYY / GG-AA-YYYY / GG/AA/YYYY
        for ayrac in (".", "-", "/"):
            parcalar = [p for p in t.split(ayrac) if p]
            if len(parcalar) == 3 and len(parcalar[2]) == 4:
                gun = parcalar[0].zfill(2)
                ay = parcalar[1].zfill(2)
                yil = parcalar[2]
                return f"{gun}/{ay}/{yil}"
        return tarih

    def _filtreleri_uygula(self, log: LogFn = _sessiz_log) -> None:
        """Müşteri listesi sayfasında Yıl/Sınıf filtrelerini uygula.

        Her adımda başarısız olursa yeniden dener. Toplu rapor akışında
        filtrelerin doğru uygulanması kritiktir — filtre uygulanmazsa
        müşteri bulunamaz.
        """
        yil = self._son_yil
        sinif = self._son_sinif
        log(f"  Filtre uygulanıyor: Yıl={yil}, Sınıf={SINIF_ETIKETLERI.get(sinif, sinif)}")

        # ADIM 1: Frame'i bul
        for deneme in range(3):
            try:
                self.liste_frame = self._frame_bul(self.dashboard, "#YIL", deneme=20, bekleme_ms=500)
                break
            except Exception as e:
                log(f"  ...frame bulunamadı (deneme {deneme+1}/3): {e}")
                if deneme < 2:
                    self.dashboard.wait_for_timeout(2000)
                else:
                    log("  HATA: Frame hiç bulunamadı, filtre uygulanamıyor!")
                    return

        # ADIM 2: Filtre panelini aç
        try:
            self._rol_buton_tikla(self.liste_frame, "Filtre", log)
            self.liste_frame.wait_for_selector("#YIL", state="visible", timeout=10000)
            log("  Filtre paneli açıldı, #YIL görünür.")
        except Exception as e:
            log(f"  HATA: Filtre paneli açılamadı: {e}")
            return

        # ADIM 3: Yıl seç
        try:
            self.liste_frame.locator("#YIL").select_option(yil)
            log(f"  Yıl seçildi: {yil}")
        except Exception as e:
            log(f"  HATA: Yıl seçilemedi: {e}")
            return

        # ADIM 4: Yıl seçimi sayfayı yeniden yükler, frame'i yeniden bul
        try:
            self.liste_frame.wait_for_load_state("domcontentloaded")
            self.liste_frame.wait_for_timeout(500)
            self.liste_frame = self._frame_bul(self.dashboard, "#YIL", deneme=15, bekleme_ms=300)
            log("  Sayfa yeniden yüklendi, frame bulundu.")
        except Exception as e:
            log(f"  HATA: Sayfa yeniden yüklendikten sonra frame bulunamadı: {e}")
            return

        # ADIM 5: Filtre panelini tekrar aç
        try:
            self._rol_buton_tikla(self.liste_frame, "Filtre", log)
            self.liste_frame.wait_for_selector("#SINIF", state="visible", timeout=10000)
            log("  Filtre paneli tekrar açıldı, #SINIF görünür.")
        except Exception as e:
            log(f"  HATA: Filtre paneli tekrar açılamadı: {e}")
            return

        # ADIM 6: Sınıf seç
        try:
            self.liste_frame.locator("#SINIF").select_option(sinif)
            log(f"  Sınıf seçildi: {SINIF_ETIKETLERI.get(sinif, sinif)}")
        except Exception as e:
            log(f"  HATA: Sınıf seçilemedi: {e}")
            return

        # ADIM 7: Ara butonuna bas
        try:
            self._rol_buton_tikla(self.liste_frame, "Ara", log)
            log("  'Ara' tıklandı.")
        except Exception as e:
            log(f"  HATA: 'Ara' tıklanamadı: {e}")
            return

        # ADIM 8: Tablonun yüklenmesini bekle
        self.liste_frame.wait_for_timeout(500)
        try:
            self.liste_frame.wait_for_selector("table.data-table tr.satir", timeout=10000)
            satir_sayisi = self.liste_frame.locator("table.data-table tr.satir").count()
            log(f"  Filtre uygulandı, tablo yüklendi ({satir_sayisi} satır).")
        except Exception as e:
            log(f"  UYARI: Tablo satırları yüklenemedi: {e}")

    def musteri_kartina_don(self, log: LogFn = _sessiz_log) -> None:
        """Müşteri listesine geri dön — toplu rapor akışı için gereklidir.

        ÖNEMLİ: Döndükten sonra filtreleri (Yıl/Sınıf) yeniden uygular
        çünkü sayfa yeniden yüklendiğinde filtre kaybolur.
        """
        if self.dashboard is None:
            raise RuntimeError("Önce baslat_ve_filtrele() çağrılmalı.")
        log("Müşteri listesine geri dönülüyor...")

        # EN GÜVENİLİR YOL: Doğrudan URL ile müşteri listesine git,
        # sonra filtreleri yeniden uygula. go_back() ve sekme izleme
        # çok hata veriyor, doğrudan URL en stabil yöntem.
        from time import time as _zaman
        musteri_listesi_url = (
            "https://auygs.luca.com.tr/Luca/listSirketAction.do"
            f"?time={int(_zaman() * 1000)}"
        )

        # Önce mevcut sayfada frames.contains kontrolü yap
        navigasyon_basrildi = False
        try:
            for cv in self.dashboard.frames:
                try:
                    if ("musteriBilgileri" in cv.url or "rapor" in cv.url.lower()
                            or "selectSirket" in cv.url or "editSirket" in cv.url
                            or "listSirket" in cv.url):
                        cv.goto(musteri_listesi_url, wait_until="domcontentloaded", timeout=30000)
                        cv.wait_for_timeout(1000)
                        navigasyon_basrildi = True
                        log("  Doğrudan URL ile müşteri listesine dönüldü (frame).")
                        break
                except Exception:
                    continue
        except Exception:
            pass

        if not navigasyon_basrildi:
            try:
                self.dashboard.goto(musteri_listesi_url, wait_until="domcontentloaded", timeout=30000)
                self.dashboard.wait_for_timeout(1000)
                log("  Doğrudan URL ile müşteri listesine dönüldü (sayfa).")
            except Exception as e:
                raise RuntimeError(f"Müşteri listesine dönülemedi: {e}")

        # Frame'i bul ve tabloyu bekle
        self.liste_frame = self._frame_bul(self.dashboard, "#YIL")
        self.liste_frame.wait_for_selector("table.data-table", timeout=15000)

        # Filtreleri yeniden uygula (sayfa yeniden yüklendiğinde filtreler kaybolur)
        self._filtreleri_uygula(log)

    def mizan_raporu_olustur(
        self,
        kisa_ad: str,
        log: LogFn = _sessiz_log,
        baslangic: str = "",
        bitis: str = "",
    ) -> Optional[Path]:
        """Seçili müşteri için Mizan raporu oluşturur.

        Args:
            kisa_ad: Müşterinin kısa adı
            log: ilerleme mesajları için callback
            baslangic: (Opsiyonel) GG/AA/YYYY formatında başlangıç tarihi.
                Boş bırakılırsa dönem başından (ör. 01/01/2026) alınır.
            bitis: (Opsiyonel) GG/AA/YYYY formatında bitiş tarihi.
                Boş bırakılırsa dönem sonuna (ör. 31/12/2026) kadar alınır.
        """
        # Tarih formatını normalize et: kullanıcı 01.01.2026 / 01-01-2026 /
        # 01012026 / 1.1.2026 gibi girmiş olsa da GG/AA/YYYY haline getir.
        baslangic = self._tarih_normalize(baslangic)
        bitis = self._tarih_normalize(bitis)
        if self.dashboard is None:
            raise RuntimeError("Önce baslat_ve_filtrele() ve musteri_sec() çağrılmalı.")

        log("Mizan ekranı açılıyor...")
        # NOT: Her alt menü seviyesi ("Raporlar", "Genel Raporlar", "Mizan")
        # üst menüyle ("Muhasebe") aynı çerçevede değil — Luca bunları
        # paylaşılan, ayrı bir açılır-menü içerik çerçevesine yerleştiriyor.
        # Bu yüzden her adımda ilgili metni içeren çerçeveyi yeniden arıyoruz.
        sirket_id = None  # outer scope — _mizan_ac() nonlocal ile yazar
        def _mizan_ac() -> None:
            """Mizan sayfasını doğrudan URL ile aç — seçili müşterinin
            context'ini (SIRKET_ID + DONEM_ID) TopFrameAction URL'inden al.

            NOT: SirketCombo + Tamam akışından sonra TopFrameAction URL'i
            şu biçime döner:
                TopFrameAction.do?...&SIRKET_ID=<sid>&DONEM_ID=<donem>&DONEM_TXT=...
            Mizan URL'inde bu iki değeri de kullanırız. Eski yöntemdeki
            DONEM_ID=36672795 değeri ŞULE ÇATAL'ın dönemiydi ve yanlış
            rapora yol açıyordu.
            """
            nonlocal sirket_id
            from time import time as _zaman
            from urllib.parse import parse_qs, urlparse

            # --- Seçili müşterinin ID'sini (SIRKET_ID) ve dönem ID'sini
            # (DONEM_ID) güncellenmiş TopFrameAction URL'inden bul ---
            sirket_id = None
            donem_id = None
            for cv in self.dashboard.frames:
                try:
                    if "TopFrameAction" in cv.url:
                        qs = parse_qs(urlparse(cv.url).query)
                        sid_list = qs.get("SIRKET_ID") or qs.get("sid")
                        donem_list = qs.get("DONEM_ID") or qs.get("donem")
                        if sid_list:
                            sirket_id = sid_list[0]
                            log(f"  Seçili müşteri ID (SIRKET_ID): {sirket_id}")
                        if donem_list:
                            donem_id = donem_list[0]
                            log(f"  Dönem ID (DONEM_ID): {donem_id}")
                except Exception:
                    continue

            log("  Doğrudan URL ile Mizan açılıyor...")
            url = (
                "https://auygs.luca.com.tr/Luca/raporMizanHazirla.do"
                f"?time={int(_zaman() * 1000)}"
            )
            if sirket_id:
                url += f"&sid={sirket_id}"
            if donem_id:
                url += f"&DONEM_ID={donem_id}"
            log(f"  Mizan URL: {url[:100]}")

            for cv in self.dashboard.frames:
                if ("musteriBilgileri" in cv.url or "rapor" in cv.url.lower()
                        or "selectSirket" in cv.url or "editSirket" in cv.url
                        or "listSirket" in cv.url):
                    cv.goto(url, wait_until="domcontentloaded", timeout=30000)
                    cv.wait_for_timeout(500)
                    log(f"  Mizan açıldı: {cv.url}")
                    return
            # Son çare: main page'de rapor frame'i ara
            for cv in self.dashboard.frames:
                try:
                    if cv.url and "luca.do" not in cv.url and "header" not in cv.url and "menu" not in cv.url:
                        cv.goto(url, wait_until="domcontentloaded", timeout=30000)
                        cv.wait_for_timeout(500)
                        log(f"  Mizan açıldı (fallback): {cv.url}")
                        return
                except Exception:
                    continue
            self.dashboard.goto(url, wait_until="domcontentloaded", timeout=30000)
            self.dashboard.wait_for_timeout(500)
            log(f"  Mizan açıldı (main page): {self.dashboard.url}")

        _mizan_ac()

        mizan_frame = self._frame_bul(self.dashboard, "#hesap_plani_dovizi_goster")

        # --- Debug: mizan form alanlarını dök (müşteri context'i nerede?) ---
        try:
            form_veri = mizan_frame.evaluate(
                """() => {
                    const sonuc = {formlar: []};
                    for (let i = 0; i < document.forms.length; i++) {
                        const f = document.forms[i];
                        const alanlar = {};
                        for (let j = 0; j < f.elements.length; j++) {
                            const el = f.elements[j];
                            if (el.name) alanlar[el.name] = (el.value || '') + '';
                        }
                        sonuc.formlar.push({name: f.name, action: f.action, alanlar: alanlar});
                    }
                    return sonuc;
                }"""
            )
            for fd in form_veri.get('formlar', [])[:2]:
                log(f"  Mizan form: name={fd.get('name','?')}, action={fd.get('action','?')[:60]}")
                if fd.get('alanlar'):
                    for k, v in list(fd['alanlar'].items())[:15]:
                        log(f"      {k} = {v[:40]}")
        except Exception as e:
            log(f"  Mizan form analizi hatası: {str(e)[:120]}")

        # --- Müşteri context alanlarını ayarla (sid URL'e gitmezse güvence) ---
        if sirket_id:
            for alan_ad in ("sirket_id", "sid", "firma_id", "sirketNo"):
                try:
                    ayar_ok = mizan_frame.evaluate(
                        """(name, val) => {
                            const el = document.querySelector('[name="' + name + '"]');
                            if (!el) return false;
                            const tag = el.tagName.toLowerCase();
                            if (tag === 'select') {
                                for (const opt of el.options) {
                                    if (opt.value === val || opt.value === '0' + val) {
                                        el.value = opt.value;
                                        el.dispatchEvent(new Event('change', {bubbles: true}));
                                        return true;
                                    }
                                }
                                return false;
                            }
                            el.value = val;
                            el.dispatchEvent(new Event('input', {bubbles: true}));
                            el.dispatchEvent(new Event('change', {bubbles: true}));
                            return true;
                        }""",
                        [alan_ad, sirket_id]
                    )
                    if ayar_ok:
                        log(f"  {alan_ad} alanı {sirket_id} olarak ayarlandı.")
                except Exception:
                    pass

        log("Mizan ayarları uygulanıyor (döviz kolonu gizle, sıfır bakiye gizle)...")
        mizan_frame.locator("#hesap_plani_dovizi_goster").select_option("0")
        mizan_frame.locator("#bakiye_tipi").select_option("2")

        # --- Tarih aralığı (opsiyonel) ---
        # Luca mizan formunda tarih aralığı birden çok alan adıyla geliyor
        # (TARIH_ILK/TARIH_SON büyük harf, tarih_ilk/tarih_son küçük harf).
        # Hangi isimle sunulduğu değişebildiği için hepsini birden doldururuz.
        # Boş bırakılırsa dönemin tamamı (ör. 01/01/2026 - 31/12/2026) alınır.
        if baslangic or bitis:
            log(f"Tarih aralığı uygulanıyor: {baslangic or 'başlangıç'} - {bitis or 'bitiş'}...")
            # NOT: Playwright'ın evaluate(expression, arg) metodu TEK argüman alır.
            # İki ayrı değeri liste olarak geçemeyiz (JS'te son=undefined olur);
            # bu yüzden tek bir sözlük olarak gönderiyoruz.
            tarih_ayar_js = """
                (veri) => {
                    const ilk = veri.ilk || '';
                    const son = veri.son || '';
                    const sonuc = {ilk: [], son: []};
                    const ayarla = (alanAd, deger, tip) => {
                        if (!deger) return;
                        const seciciler = [
                            '[name="' + alanAd + '"]',
                            '#' + alanAd,
                        ];
                        for (const secici of seciciler) {
                            let elemanlar = [];
                            try { elemanlar = Array.from(document.querySelectorAll(secici)); }
                            catch (e) { continue; }
                            for (const el of elemanlar) {
                                try {
                                    const setter = Object.getOwnPropertyDescriptor(
                                        HTMLInputElement.prototype, 'value'
                                    ).set;
                                    setter.call(el, deger);
                                    el.dispatchEvent(new Event('input', {bubbles: true}));
                                    el.dispatchEvent(new Event('change', {bubbles: true}));
                                    tip.push(alanAd + ':' + secici);
                                } catch (e) {}
                            }
                        }
                    };
                    ayarla('TARIH_ILK', ilk, sonuc.ilk);
                    ayarla('TARIH_SON', son, sonuc.son);
                    ayarla('tarih_ilk', ilk, sonuc.ilk);
                    ayarla('tarih_son', son, sonuc.son);
                    return {
                        ilk: sonuc.ilk,
                        son: sonuc.son,
                    };
                }
            """
            try:
                tarih_sonuc = mizan_frame.evaluate(tarih_ayar_js, {"ilk": baslangic, "son": bitis})
                log(f"  Tarih alanları: {tarih_sonuc}")
            except Exception as e:
                log(f"  UYARI: Tarih alanları doldurulamadı: {str(e)[:120]}")

        log("Rapor oluşturuluyor...")
        self.cikti_klasoru.mkdir(parents=True, exist_ok=True)
        if baslangic and bitis:
            aralik_etiket = f"{baslangic.replace('/', '-')}_{bitis.replace('/', '-')}"
            hedef_dosya = self.cikti_klasoru / f"{kisa_ad}_Mizan_{self._son_yil}_{aralik_etiket}.xlsx"
        else:
            hedef_dosya = self.cikti_klasoru / f"{kisa_ad}_Mizan_{self._son_yil}.xlsx"

        try:
            with self.dashboard.expect_download(timeout=15000) as indirme_bilgisi:
                self._rol_buton_tikla(mizan_frame, "Rapor", log, birincil_zaman_asimi=5000)
            indirme = indirme_bilgisi.value
            indirme.save_as(str(hedef_dosya))
            log(f"Rapor indirildi: {hedef_dosya}")
            return hedef_dosya
        except PlaywrightTimeoutError:
            log(
                "Rapor birkaç saniye içinde otomatik indirilmedi. Luca bu raporu "
                "arka planda hazırlıyor olabilir — Muhasebe > Raporlar > "
                "Diğer İşlemler > Rapor Takip menüsünden indirebilirsiniz."
            )
            return None

    # ------------------------------------------------------------------
    # Aşama 3: Toplu müşteri raporu (tüm filtrelenen müşteriler için)
    # ------------------------------------------------------------------

    def toplu_mizan_raporu(
        self,
        musteriler: list[dict],
        log: LogFn = _sessiz_log,
        ilerleme_cb: "Callable[[int, int, dict], None] | None" = None,
        baslangic: str = "",
        bitis: str = "",
    ) -> list[dict]:
        """Filtrelenen tüm müşteriler için sırasıyla Mizan raporu oluşturur.

        Her müşteri için: (1) müşteri kartını açar, (2) Mizan raporu
        oluşturur (aynı ayarlarla), (3) müşteri listesine geri döner.

        Args:
            musteriler: baslat_ve_filtrele() sonucu dönen müşteri listesi
            log: ilerleme mesajları için callback
            ilerleme_cb: (mevcut_index, toplam, musteri_dict) çağrısı —
                GUI ilerleme çubuğu için
            baslangic: (Opsiyonel) GG/AA/YYYY formatında başlangıç tarihi
            bitis: (Opsiyonel) GG/AA/YYYY formatında bitiş tarihi

        Returns:
            Her müşteri için {kisa_ad, uzun_ad, dosya_yolu, durum, hata}
            bilgilerini içeren bir liste.
        """
        if self.dashboard is None or self.liste_frame is None:
            raise RuntimeError("Önce baslat_ve_filtrele() çağrılmalı.")

        toplam = len(musteriler)
        sonuclar: list[dict] = []
        basarili = 0
        basarisiz = 0

        log(f"Toplu rapor başlatılıyor: {toplam} müşteri")

        for i, musteri in enumerate(musteriler):
            kisa_ad = musteri["kisa_ad"]
            uzun_ad = musteri.get("uzun_ad", "")

            if ilerleme_cb:
                ilerleme_cb(i, toplam, musteri)

            log(f"[{i + 1}/{toplam}] {kisa_ad} ({uzun_ad}) işleniyor...")

            sonuc = {
                "kisa_ad": kisa_ad,
                "uzun_ad": uzun_ad,
                "dosya_yolu": None,
                "durum": "",
                "hata": None,
            }

            try:
                self.musteri_sec(kisa_ad, log=log)
                dosya = self.mizan_raporu_olustur(kisa_ad, log=log, baslangic=baslangic, bitis=bitis)
                if dosya:
                    sonuc["dosya_yolu"] = str(dosya)
                    sonuc["durum"] = "başarılı"
                else:
                    sonuc["durum"] = "kuyruğa alındı"
                basarili += 1
            except Exception as e:
                sonuc["durum"] = "hatalı"
                sonuc["hata"] = str(e)
                basarisiz += 1
                log(f"  HATA: {kisa_ad} için rapor oluşturulamadı — {e}")

            sonuclar.append(sonuc)

            if i < toplam - 1:
                try:
                    self.musteri_kartina_don(log=log)
                except Exception as e:
                    log(f"  UYARI: Listeye geri dönülemedi — {e}. URL ile yeniden deneniyor...")
                    try:
                        # Zorla doğrudan URL ile dön
                        from time import time as _zaman
                        url = (
                            "https://auygs.luca.com.tr/Luca/listSirketAction.do"
                            f"?time={int(_zaman() * 1000)}"
                        )
                        self.dashboard.goto(url, wait_until="domcontentloaded", timeout=30000)
                        self.dashboard.wait_for_timeout(1000)
                        self.liste_frame = self._frame_bul(self.dashboard, "#YIL")
                        self.liste_frame.wait_for_selector("table.data-table", timeout=10000)
                        self._filtreleri_uygula(log)
                        log("  Kurtarma başarılı, listeye dönüldü.")
                    except Exception:
                        log(f"  HATA: {kisa_ad} sonrası listeye dönülemedi, kalanlar atlanıyor.")
                        break

        log(f"Toplu rapor tamamlandı: {basarili} başarılı, {basarisiz} hatalı (toplam {toplam})")
        return sonuclar

    # ------------------------------------------------------------------
    # Kapatma
    # ------------------------------------------------------------------

    def kapat(self) -> None:
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:
            pass
        self.dashboard = None
        self.liste_frame = None
