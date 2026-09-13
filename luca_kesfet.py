#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Luca Keşif Aracı — sayfa yapısını dökümleyip kesfet_raporu.txt dosyasına yazar.

Kullanım:
  1. Bu scripti çalıştırın.
  2. Açılan tarayıcıda KULLANICI ADI'nızı yazıp GİRİŞ'e basın (varsa doğrulamayı tamamlayın).
  3. Otomasyon giriş sonrası sayfa yapısını otomatik inceler ve raporu kaydeder.
  4. Çıkan "kesfet_raporu.txt" dosyasını paylaşın.

Güvenlik: Kimlik bilgileri rapora YAZILMAZ; yalnızca .env'den okunur.
"""

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

BASE = Path(__file__).parent
load_dotenv(BASE / ".env")

GIRIS_URL = "https://agiris.luca.com.tr/LUCASSO/giris.erp"
RAPOR = BASE / "kesfet_raporu.txt"

UYE_NO = os.getenv("LUCA_UYE_NO", "").strip()
PAROLA = os.getenv("LUCA_PAROLA", "").strip()

SATIRLAR: list[str] = []


def yaz(*a) -> None:
    m = " ".join(str(x) for x in a)
    print(m)
    SATIRLAR.append(m)


def raporu_kaydet() -> None:
    RAPOR.write_text("\n".join(SATIRLAR), encoding="utf-8")
    print(f"\nRAPOR KAYDEDİLDİ: {RAPOR}")


def main() -> None:
    yaz("=== Luca Keşif Aracı ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=30)
        ctx = browser.new_context(accept_downloads=True)
        sayfa = ctx.new_page()
        sayfa.goto(GIRIS_URL, wait_until="domcontentloaded")

        form_kontrol = """
            () => {
                const inputs = document.querySelectorAll('input');
                let textCount = 0, hasPassword = false;
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
            sayfa.wait_for_function(form_kontrol, timeout=5000)
        except PWTimeoutError:
            yaz("Captcha göründü — tarayıcıya geçip doğrulamayı tamamlayın...")
            try:
                sayfa.bring_to_front()
            except Exception:
                pass
            sayfa.wait_for_function(form_kontrol, timeout=300000)

        analiz = sayfa.evaluate(
            """
            () => {
                const r = [];
                for (const el of document.querySelectorAll('input')) {
                    if (el.offsetParent === null) continue;
                    r.push({type: el.type || '', name: el.name || '', id: el.id || '', ph: el.placeholder || ''});
                }
                return r;
            }
            """
        )

        def alan_bul(ipuclari: list[str]):
            for e in analiz:
                ad = (e.get("name", "") + " " + e.get("id", "") + " " + e.get("ph", "")).lower()
                for ip in ipuclari:
                    if ip in ad:
                        return e.get("name")
            return None

        uye = alan_bul(["musteri", "uye", "member"])
        par = alan_bul(["parola", "sifre", "password", "pass"])
        if uye:
            sayfa.locator(f'input[name="{uye}"]').fill(UYE_NO)
        else:
            sayfa.locator('input[type="text"]').first.fill(UYE_NO)
        if par:
            sayfa.locator(f'input[name="{par}"]').fill(PAROLA)
        else:
            sayfa.locator('input[type="password"]').first.fill(PAROLA)

        yaz("Üye No + Parola dolduruldu.")
        yaz("Lütfen tarayıcıda KULLANICI ADI'nı yazıp GİRİŞ'e basın (varsa doğrulamayı da tamamlayın)...")
        try:
            sayfa.bring_to_front()
        except Exception:
            pass
        try:
            sayfa.wait_for_url("**/main.erp*", timeout=300000)
            yaz("Giriş tamamlandı.")
        except PWTimeoutError:
            yaz("Giriş 5 dk içinde tamamlanmadı.")
            raporu_kaydet()
            sys.exit(1)

        sayfa.wait_for_load_state("domcontentloaded")
        sayfa.wait_for_timeout(1000)

        onceki = len(ctx.pages)
        onceki_url = sayfa.url
        try:
            sayfa.evaluate(
                """() => {
                    if (document.forms.length > 0) document.forms[0].target = '_self';
                    if (typeof gonder === 'function') { gonder('formTarget'); return true; }
                    return false;
                }"""
            )
        except Exception:
            pass

        hedef = None
        for _ in range(10):
            if len(ctx.pages) > onceki:
                hedef = ctx.pages[-1]
                break
            if sayfa.url != onceki_url:
                hedef = sayfa
                break
            sayfa.wait_for_timeout(500)

        if hedef is None:
            yaz("Ürün kartı otomatik tıklanamadı — lütfen tarayıcıda 'LUCA MALİ MÜŞAVİR PAKETİ' kartına kendiniz tıklayın.")
            try:
                sayfa.bring_to_front()
            except Exception:
                pass
            for _ in range(300):
                if len(ctx.pages) > onceki:
                    hedef = ctx.pages[-1]
                    break
                if sayfa.url != onceki_url:
                    hedef = sayfa
                    break
                sayfa.wait_for_timeout(500)

        if hedef is None:
            yaz("Ana panele ulaşılamadı.")
            raporu_kaydet()
            sys.exit(1)

        dashboard = hedef
        try:
            dashboard.bring_to_front()
        except Exception:
            pass
        for _ in range(20):
            if dashboard.url and "about:blank" not in dashboard.url:
                break
            dashboard.wait_for_timeout(500)
        dashboard.wait_for_timeout(2000)
        yaz(f"Ana panel: {dashboard.url}")

        # ================= KEŞİF =================
        yaz("\n===== 1. FRAME LİSTESİ =====")
        for i, cv in enumerate(dashboard.frames):
            try:
                yaz(f"  #{i} {cv.url}")
            except Exception:
                yaz(f"  #{i} (URL okunamadı)")

        yaz("\n===== 2. SirketCombo ARAMA =====")
        combo_frame = None
        for i, cv in enumerate(dashboard.frames):
            try:
                n = cv.locator("#SirketCombo").count()
                if n > 0:
                    combo_frame = cv
                    yaz(f"  SirketCombo #{i} içinde bulundu: {cv.url}")
                    secili = cv.evaluate(
                        """() => {
                            const s = document.getElementById('SirketCombo');
                            return s ? s.value + '=' + s.options[s.selectedIndex].text : null;
                        }"""
                    )
                    yaz(f"  Seçili: {secili}")
                    html = cv.evaluate(
                        """() => {
                            const s = document.getElementById('SirketCombo');
                            if (!s) return null;
                            let p = s.parentNode, out = '';
                            for (let k = 0; k < 3 && p; k++) {
                                out += '<' + p.tagName.toLowerCase();
                                if (p.id) out += ' id="' + p.id + '"';
                                out += '>';
                                p = p.parentNode;
                            }
                            return out + ' | ' + s.outerHTML.substring(0, 250);
                        }"""
                    )
                    yaz(f"  HTML: {html}")
                    break
            except Exception:
                continue
        if combo_frame is None:
            yaz("  SirketCombo hiçbir frame'de bulunamadı!")

        yaz("\n===== 3. loadDonem / showButton KAYNAK KODU =====")
        for i, cv in enumerate(dashboard.frames):
            try:
                src = cv.evaluate(
                    """() => {
                        const r = {};
                        for (const fn of ['loadDonem', 'showButton']) {
                            if (typeof window[fn] === 'function') r[fn] = window[fn].toString().substring(0, 800);
                            else r[fn] = null;
                        }
                        return r;
                    }"""
                )
                if src.get("loadDonem") or src.get("showButton"):
                    yaz(f"  Frame #{i}: {cv.url}")
                    for k, v in src.items():
                        yaz(f"    {k}: {v}")
            except Exception:
                continue

        yaz("\n===== 4. 'Tamam' DÜĞMESİ ARAMA =====")
        for i, cv in enumerate(dashboard.frames):
            try:
                sonuc = cv.evaluate(
                    """() => {
                        const r = [];
                        for (const el of document.querySelectorAll('button, input, a, td, div, span')) {
                            const t = (el.innerText || el.value || '').trim();
                            if (t === 'Tamam' && el.offsetParent !== null) {
                                r.push({
                                    tag: el.tagName.toLowerCase(),
                                    id: el.id || '',
                                    onclick: (el.getAttribute('onclick') || '').slice(0, 150),
                                    display: el.style.display || ''
                                });
                            }
                        }
                        return r.slice(0, 5);
                    }"""
                )
                if sonuc:
                    yaz(f"  Frame #{i}: {cv.url} -> {json.dumps(sonuc, ensure_ascii=False)}")
            except Exception:
                continue

        yaz("\n===== 5. MENÜ YAPISI (Muhasebe/Raporlar/Mizan) =====")
        for i, cv in enumerate(dashboard.frames):
            try:
                metin = cv.evaluate("() => document.body ? document.body.innerText : ''")
                if metin and any(k in metin for k in ("Muhasebe", "Raporlar", "Mizan")):
                    yaz(f"  Frame #{i}: {cv.url}")
                    for kelime in ("Muhasebe", "Raporlar", "Genel Raporlar", "Mizan"):
                        if kelime in metin:
                            yaz(f"    '{kelime}' VAR")
            except Exception:
                continue

        if combo_frame is not None:
            yaz("\n===== 6. SirketCombo İLE FIRMA DEĞİŞTİRME DENEMESİ =====")
            try:
                combo_frame.locator("#SirketCombo").select_option("112285648")  # ALİ BACAK
                yaz("  ALİ BACAK (112285648) seçildi — onchange tetiklendi.")
                combo_frame.wait_for_timeout(2000)
                secili2 = combo_frame.evaluate(
                    """() => {
                        const s = document.getElementById('SirketCombo');
                        return s ? s.value + '=' + s.options[s.selectedIndex].text : null;
                    }"""
                )
                yaz(f"  Seçili şimdi: {secili2}")
                tamam = combo_frame.evaluate(
                    """() => {
                        const r = [];
                        for (const el of document.querySelectorAll('button, input, a, td, div, span')) {
                            const t = (el.innerText || el.value || '').trim();
                            if (t === 'Tamam') {
                                r.push({
                                    tag: el.tagName.toLowerCase(),
                                    id: el.id || '',
                                    onclick: (el.getAttribute('onclick') || '').slice(0, 150),
                                    display: el.style.display || '',
                                    hidden: el.hidden || false
                                });
                            }
                        }
                        return r.slice(0, 8);
                    }"""
                )
                yaz(f"  Tamam düğmeleri: {json.dumps(tamam, ensure_ascii=False)}")
                yaz("  Değişen frame URL'leri (TopFrameAction / selectSirket):")
                for cv in dashboard.frames:
                    try:
                        if "TopFrameAction" in cv.url or "selectSirket" in cv.url:
                            yaz(f"    {cv.url}")
                    except Exception:
                        pass

                yaz("\n===== 7. DÖNEM COMBO + formSubmit + TAMAM TIKLAMA =====")
                donemler = combo_frame.evaluate(
                    """() => {
                        const r = {selectler: [], formSubmit: null, sirketDonem_secim: null};
                        for (const el of document.querySelectorAll('select')) {
                            const opts = [];
                            for (let k = 0; k < Math.min(el.options.length, 8); k++) {
                                opts.push(el.options[k].value + '=' + el.options[k].text);
                            }
                            r.selectler.push({
                                id: el.id || '', name: el.name || '',
                                secili: el.selectedIndex >= 0 ? el.options[el.selectedIndex].value + '=' + el.options[el.selectedIndex].text : null,
                                adet: el.options.length,
                                ilkSecenekler: opts
                            });
                        }
                        if (typeof formSubmit === 'function') r.formSubmit = formSubmit.toString().substring(0, 900);
                        return r;
                    }"""
                )
                for s in donemler.get("selectler", []):
                    yaz(f"  SELECT id={s.get('id')} name={s.get('name')} secili={s.get('secili')} adet={s.get('adet')} ilk={s.get('ilkSecenekler')}")
                if donemler.get("formSubmit"):
                    yaz(f"  formSubmit: {donemler['formSubmit']}")

                yaz("\n  Tamam düğmesine tıklanıyor (formSubmit(event,0))...")
                tiklama = combo_frame.evaluate(
                    """() => {
                        const buton = Array.from(document.querySelectorAll('button')).find(b => (b.innerText || '').trim() === 'Tamam');
                        if (!buton) return {ok: false, msg: 'Tamam butonu yok'};
                        const onclick = buton.getAttribute('onclick') || '';
                        if (onclick.includes('formSubmit')) {
                            if (typeof formSubmit === 'function') {
                                formSubmit(null, 0);
                                return {ok: true, method: 'formSubmit(null,0) direkt'};
                            }
                        }
                        buton.click();
                        return {ok: true, method: 'click()'};
                    }"""
                )
                yaz(f"  Tıklama sonucu: {tiklama}")
                combo_frame.wait_for_timeout(4000)
                yaz("  TAMAM sonrası tüm frame URL'leri:")
                for i, cv in enumerate(dashboard.frames):
                    try:
                        yaz(f"    #{i} {cv.url}")
                    except Exception:
                        pass
                yaz(f"  Dashboard URL: {dashboard.url}")
                yaz("  SirketCombo seçili: " + str(
                    combo_frame.evaluate(
                        """() => {
                            const s = document.getElementById('SirketCombo');
                            return s ? s.value + '=' + s.options[s.selectedIndex].text : null;
                        }"""
                    )
                ))
                yaz("  DONEM_ID (TopFrameAction):")
                for cv in dashboard.frames:
                    try:
                        if "TopFrameAction" in cv.url:
                            yaz(f"    {cv.url}")
                    except Exception:
                        pass
            except Exception as e:
                yaz(f"  SirketCombo değiştirme hatası: {str(e)[:200]}")

        # ===== 7. MİZAN SAYFASI: tüm form alanlarını dök (tarih alanlarını bul) =====
        yaz("\n===== 7. MİZAN SAYFASI FORM ALANLARI (tarih alanları aranıyor) =====")
        try:
            from time import time as _zaman
            mizan_url = (
                "https://auygs.luca.com.tr/Luca/raporMizanHazirla.do"
                f"?time={int(_zaman() * 1000)}"
            )
            mizan_cv = None
            for cv in dashboard.frames:
                try:
                    if ("musteriBilgileri" in cv.url or "rapor" in cv.url.lower()
                            or "selectSirket" in cv.url or "editSirket" in cv.url
                            or "listSirket" in cv.url):
                        cv.goto(mizan_url, wait_until="domcontentloaded", timeout=30000)
                        cv.wait_for_timeout(500)
                        yaz(f"  Mizan açıldı: {cv.url}")
                        mizan_cv = cv
                        break
                except Exception:
                    continue
            if mizan_cv is None:
                mizan_cv = dashboard
                dashboard.goto(mizan_url, wait_until="domcontentloaded", timeout=30000)
                dashboard.wait_for_timeout(500)
                yaz(f"  Mizan açıldı (main): {dashboard.url}")

            mizan_cv.wait_for_timeout(1500)
            alanlar = mizan_cv.evaluate(
                """() => {
                    const r = [];
                    for (const el of document.querySelectorAll('input, select, textarea')) {
                        r.push({
                            tag: el.tagName.toLowerCase(),
                            name: el.name || '',
                            id: el.id || '',
                            type: el.type || '',
                            value: (el.value || '') + '',
                        });
                    }
                    return r;
                }"""
            )
            yaz(f"  Toplam {len(alanlar)} alan:")
            yaz("  *** TARİH İLE İLGİLİ OLANLAR:")
            for a in alanlar:
                ad = (a.get('name') or '').lower()
                kimlik = (a.get('id') or '').lower()
                if any(k in ad + kimlik for k in ('tarih', 'tari', 'ilk', 'son', 'basla', 'biti')):
                    yaz(f"    {a}")
            yaz("  TÜM ALAN ADLARI:")
            for a in alanlar:
                if a.get('name'):
                    yaz(f"    name={a.get('name')} id={a.get('id')} type={a.get('type')}")
        except Exception as e:
            yaz(f"  Mizan formu dökümlenemedi: {str(e)[:200]}")

        raporu_kaydet()
        yaz("\nKeşif tamam. Tarayıcıyı kapatabilirsiniz (Enter'a basın).")
        try:
            input()
        except EOFError:
            time.sleep(3)
        browser.close()


if __name__ == "__main__":
    main()