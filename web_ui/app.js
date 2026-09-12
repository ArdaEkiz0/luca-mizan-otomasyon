/* ============================================================
   Luca Mizan Otomasyonu — Frontend Mantığı
   ============================================================ */

"use strict";

/* ---------- Yardımcılar ---------- */
function sec(id) { return document.getElementById(id); }

function muhafaza(deger) {
  return String(deger ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function toastBaslikSeviye(seviye) {
  switch (seviye) {
    case "hata": return "Hata";
    case "uyari": return "Uyari";
    case "basarili": return "Basari";
    default: return "Bilgi";
  }
}

function toastGoster(seviye, mesaj) {
  const sarici = sec("toastSarici");
  const toast = document.createElement("div");
  toast.className = "toast";
  const baslik = document.createElement("div");
  baslik.className = "toast-baslik " + seviye;
  baslik.textContent = toastBaslikSeviye(seviye);
  const gvde = document.createElement("div");
  gvde.className = "toast-mesaj";
  gvde.textContent = mesaj;
  toast.appendChild(baslik);
  toast.appendChild(gvde);
  sarici.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("sol");
    setTimeout(() => toast.remove(), 420);
  }, 5200);
}

function logEkle(seviye, mesaj) {
  const konsol = sec("logKonsol");
  const satir = document.createElement("div");
  satir.className = "log-satir " + seviye;
  satir.textContent = mesaj;
  konsol.appendChild(satir);

  // Konsol çok büyürse eski satırları kırp
  while (konsol.childElementCount > 700) {
    konsol.removeChild(konsol.firstChild);
  }
  konsol.scrollTop = konsol.scrollHeight;
}

function durumGuncelle(metin, seviye) {
  sec("durumYazi").textContent = metin;
  const rozet = sec("durumRozeti");
  rozet.classList.remove("durum-seviye-calisiyor", "durum-seviye-hata", "durum-seviye-basarili");
  rozet.classList.add("durum-seviye-" + seviye);
}

/* ---------- Tarih otomatik format ---------- */
function tarihFormatla(el) {
  const rakamlar = el.value.replace(/\D/g, "").slice(0, 8);
  const parcalar = [];
  if (rakamlar.length >= 1) parcalar.push(rakamlar.slice(0, 2));
  if (rakamlar.length >= 3) parcalar.push(rakamlar.slice(2, 4));
  if (rakamlar.length >= 5) parcalar.push(rakamlar.slice(4, 8));
  const yeni = parcalar.join(".");
  if (el.value !== yeni) el.value = yeni;
}

function tarihTemizle(deger) {
  return deger.replace(/\D/g, "").slice(0, 8);
}

/* ---------- Buton yükleniyor durumu ---------- */
let calisiyor = false;

function butonlariKilitle(kilitli) {
  calisiyor = kilitli;
  sec("getirBtn").disabled = kilitli;
  sec("raporBtn").disabled = kilitli || !seciliKisaAd;
  sec("topluBtn").disabled = kilitli || musteriSayisi === 0;
  sec("kapatBtn").disabled = kilitli;
}

/* ---------- Tablo ---------- */
let musteriler = [];
let seciliKisaAd = null;
let musteriSayisi = 0;
let raporListesi = [];
let sonLogId = 0;
let ilkYukleme = true;

function tabloDoldur() {
  const govde = sec("tabloGovde");
  govde.innerHTML = "";
  const filtre = sec("arama").value.trim().toLocaleLowerCase("tr");

  let gorunen = 0;
  musteriler.forEach((m, i) => {
    const kisa = (m.kisa_ad || "").toLocaleLowerCase("tr");
    const uzun = (m.uzun_ad || "").toLocaleLowerCase("tr");
    if (filtre && !kisa.includes(filtre) && !uzun.includes(filtre)) return;
    gorunen++;

    const tr = document.createElement("tr");
    tr.className = "satir-giris";
    tr.style.animationDelay = Math.min(i * 0.015, 0.4) + "s";
    tr.innerHTML =
      "<td>" + muhafaza(m.kisa_ad) + "</td>" +
      "<td>" + muhafaza(m.uzun_ad) + "</td>" +
      "<td>" + muhafaza(m.vergi_dairesi) + "</td>" +
      "<td>" + muhafaza(m.vergi_no) + "</td>";
    tr.addEventListener("click", () => {
      seciliKisaAd = m.kisa_ad;
      Array.from(govde.querySelectorAll("tr")).forEach(r => r.classList.remove("secili"));
      tr.classList.add("secili");
      sec("raporBtn").disabled = calisiyor || !seciliKisaAd;
    });
    govde.appendChild(tr);
  });

  musteriSayisi = musteriler.length;
  sec("musteriSayisi").textContent = musteriSayisi + " musteri";
  sec("topluBtn").disabled = calisiyor || musteriSayisi === 0;

  if (gorunen === 0 && musteriler.length > 0) {
    const bos = document.createElement("tr");
    bos.className = "bos-satir";
    bos.innerHTML = "<td colspan='4'>Arama filtresine uyan musteri yok.</td>";
    govde.appendChild(bos);
  } else if (musteriler.length === 0) {
    const bos = document.createElement("tr");
    bos.className = "bos-satir";
    bos.innerHTML = "<td colspan='4'>Oncelikle \"Musterileri Getir\" butonuna basin.</td>";
    govde.appendChild(bos);
  }
}

function tabloFiltrele() { tabloDoldur(); }

/* ---------- Raporlar ---------- */
function raporListeGuncelle() {
  const liste = sec("raporListe");
  liste.innerHTML = "";
  if (raporListesi.length === 0) {
    const bos = document.createElement("div");
    bos.className = "bos-liste";
    bos.textContent = "Henuz rapor indirilmedi.";
    liste.appendChild(bos);
  } else {
    raporListesi.forEach(r => {
      const kayit = document.createElement("div");
      kayit.className = "rapor-kayit";
      kayit.innerHTML =
        "<span class='dosya-ikon'>&#128196;</span>" +
        "<span class='dosya-ad'>" + muhafaza(r.dosya) + "</span>" +
        "<span class='dosya-meta'>" + muhafaza(r.boyut) + " &middot; " + muhafaza(r.tarih) + "</span>";
      kayit.addEventListener("click", () => dosyaAc(false, r.yol));
      liste.appendChild(kayit);
    });
  }
  sec("raporSayisi").textContent = raporListesi.length + " dosya";
}

function logTemizle() {
  const konsol = sec("logKonsol");
  konsol.innerHTML = "";
  const satir = document.createElement("div");
  satir.className = "log-satir bilgi";
  satir.textContent = "Log temizlendi.";
  konsol.appendChild(satir);
}

/* ---------- API istekleri ---------- */
async function apiGetir(url) {
  const cevap = await fetch(url, { cache: "no-store" });
  return cevap.json();
}

async function apiGonder(url, veri = {}) {
  const cevap = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(veri),
  });
  return cevap.json();
}

/* ---------- Aksiyonlar ---------- */
function ayarlariKaydet() {
  const veri = {
    uye_no: sec("uyeNo").value.trim(),
    kullanici_adi: sec("kullaniciAdi").value.trim(),
    parola: sec("parola").value,
    yil: sec("yil").value,
    sinif: sec("sinif").value,
  };
  apiGonder("/api/ayar_kaydet", veri).then(r => {
    if (r.ok) toastGoster("basarili", "Bilgiler .env dosyasina kaydedildi.");
  });
}

function musterileriGetir() {
  if (calisiyor) return;
  const uye_no = sec("uyeNo").value.trim();
  const kullanici_adi = sec("kullaniciAdi").value.trim();
  const parola = sec("parola").value;
  if (!uye_no || !kullanici_adi || !parola) {
    toastGoster("uyari", "Uye No, Kullanici Adi ve Parola alanlarini doldurun.");
    return;
  }

  musteriler = [];
  seciliKisaAd = null;
  tabloDoldur();

  butonlariKilitle(true);
  sec("getirBtn").innerHTML = '<span class="btn-ikon">&#9696;</span> Giris yapiliyor...';
  durumGuncelle("Giris yapiliyor...", "calisiyor");

  apiGonder("/api/musterileri_getir", {
    uye_no, kullanici_adi, parola,
    yil: sec("yil").value,
    sinif: sec("sinif").value,
  }).then(r => {
    if (!r.ok) {
      butonlariKilitle(false);
      sec("getirBtn").innerHTML = '<span class="btn-ikon">&#8635;</span> Musterileri Getir';
      toastGoster("hata", r.hata || "Bilinmeyen hata.");
    }
  });
}

function raporOlustur() {
  if (calisiyor || !seciliKisaAd) return;
  butonlariKilitle(true);
  durumGuncelle("Rapor olusturuluyor...", "calisiyor");
  apiGonder("/api/rapor_olustur", {
    kisa_ad: seciliKisaAd,
    baslangic: tarihTemizle(sec("tarihIlk").value),
    bitis: tarihTemizle(sec("tarihSon").value),
  });
}

function topluRapor() {
  if (calisiyor || musteriSayisi === 0) return;
  if (!confirm(musteriSayisi + " musteri icin Mizan raporu olusturulacak.\n\nBu islem biraz surebilir. Devam etmek istiyor musunuz?")) return;

  butonlariKilitle(true);
  durumGuncelle("Toplu rapor olusturuluyor...", "calisiyor");
  apiGonder("/api/toplu_rapor", {
    baslangic: tarihTemizle(sec("tarihIlk").value),
    bitis: tarihTemizle(sec("tarihSon").value),
  });
}

function tarayiciyiKapat() {
  if (calisiyor) return;
  butonlariKilitle(true);
  apiGonder("/api/tarayici_kapat").then(() => {
    musteriler = [];
    seciliKisaAd = null;
    raporListesi = [];
    tabloDoldur();
    raporListeGuncelle();
    butonlariKilitle(false);
    durumGuncelle("Hazir", "bekleme");
  });
}

function dosyaAc(klasorMu, yol) {
  if (klasorMu) {
    apiGonder("/api/klasor_ac");
  } else if (yol) {
    apiGonder("/api/dosya_ac", { yol });
  }
}

function raporListesiTemizle() {
  apiGonder("/api/liste_temizle").then(() => {
    raporListesi = [];
    raporListeGuncelle();
  });
}

/* ---------- Ayar yükle + durum polling ---------- */
function secenekDoldur() {
  apiGetir("/api/ayarlar").then(a => {
    const yilSec = sec("yil");
    yilSec.innerHTML = "";
    for (let y = 2026; y >= 2010; y--) {
      const o = document.createElement("option");
      o.value = String(y);
      o.textContent = String(y);
      yilSec.appendChild(o);
    }
    yilSec.value = a.yil || "2026";

    const sinifSec = sec("sinif");
    sinifSec.innerHTML = "";
    const siniflar = [
      ["", "Tumu"], ["1", "1.Sinif"], ["2", "2.Sinif"], ["3", "Isletme Defteri"],
      ["4", "Serbest Meslek Defteri"], ["5", "Basit Usul"],
    ];
    siniflar.forEach(([k, e]) => {
      const o = document.createElement("option");
      o.value = k;          // Luca KOD bekler: '1','2',...
      o.textContent = e;    // ekranda etiket görünür
      sinifSec.appendChild(o);
    });
    // kayıtlı sınıfı kod üzerinden eşle
    const seciliKod = (a.sinif || "1");
    sinifSec.value = siniflar.some(([k]) => k === seciliKod) ? seciliKod : "1";

    sec("uyeNo").value = a.uye_no || "";
    sec("kullaniciAdi").value = a.kullanici_adi || "";
    sec("parola").value = a.parola || "";

    sec("tarihIlk").addEventListener("input", () => tarihFormatla(sec("tarihIlk")));
    sec("tarihSon").addEventListener("input", () => tarihFormatla(sec("tarihSon")));
  });
}

async function durumPoll() {
  try {
    const d = await apiGetir("/api/durum");

    // Loglar
    d.loglar.forEach(l => logEkle(l.seviye, l.mesaj));

    // Müşteriler
    if (JSON.stringify(d.musteriler) !== JSON.stringify(musteriler)) {
      musteriler = d.musteriler;
      seciliKisaAd = d.secili_kisa_ad;
      tabloDoldur();
    }

    // Raporlar
    if (JSON.stringify(d.raporlar) !== JSON.stringify(raporListesi)) {
      raporListesi = d.raporlar;
      raporListeGuncelle();
    }

    // Durum
    durumGuncelle(d.durum_metni, d.durum_seviye);
    sec("ilerleme").classList.toggle("ilerleme-gorunur", d.calisiyor);

    // Butonlar
    if (d.calisiyor !== calisiyor) {
      butonlariKilitle(d.calisiyor);
      if (!d.calisiyor) {
        sec("getirBtn").innerHTML = '<span class="btn-ikon">&#8635;</span> Musterileri Getir';
      }
    }

    // İlk yüklemede yeni müşteri geldiyse toast
    if (ilkYukleme && d.musteriler.length > 0) {
      ilkYukleme = false;
      toastGoster("basarili", d.musteriler.length + " musteri listelendi.");
    }
  } catch (e) {
    // Sunucu henüz hazır değilse sessizce bekle
  }
  setTimeout(durumPoll, 700);
}

/* ---------- Giriş ---------- */
secenekDoldur();
durumPoll();

/* ---------- Mizan kontrol ---------- */
function mizanKontrol() {
  const liste = sec("kontrolListe");
  liste.innerHTML = '<div class="bos-liste">Kontrol ediliyor...</div>';
  apiGonder("/api/kontrol", {}).then(r => {
    if (!r.ok) {
      liste.innerHTML = '<div class="bos-liste">Kontrol hatasi: ' + muhafaza(r.hata || "bilinmiyor") + '</div>';
      return;
    }
    const sonuclar = r.sonuclar || [];
    if (sonuclar.length === 0) {
      liste.innerHTML = '<div class="bos-liste">Kontrol edilecek rapor yok.</div>';
      return;
    }
    liste.innerHTML = "";
    sonuclar.forEach(s => {
      const kayit = document.createElement("div");
      kayit.className = "kontrol-kayit";
      const rozet = s.durum === "OK"
        ? '<span class="durum-rozet ok">OK</span>'
        : s.durum === "UYARI"
          ? '<span class="durum-rozet uyari">UYARI</span>'
          : '<span class="durum-rozet hata">HATA</span>';
      kayit.innerHTML =
        rozet +
        '<span class="kontrol-ad">' + muhafaza(s.firma || s.dosya) + '</span>' +
        '<span class="kontrol-ozet">' + muhafaza(s.ozet) + '</span>';

      const ayrinti = s.ihlaller || [];
      if (s.durum === "OK") {
        kayit.classList.add("ok");
      } else {
        kayit.classList.add("hata");
      }

      kayit.addEventListener("click", () => {
        if (ayrinti.length === 0) return;
        const mevcut = kayit.querySelector(".kontrol-detay");
        if (mevcut) { mevcut.remove(); return; }
        const detay = document.createElement("div");
        detay.className = "kontrol-detay";
        ayrinti.forEach(i => {
          const sat = document.createElement("div");
          sat.className = "kontrol-detay-" + (i.seviye === "HATA" ? "hata" : "uyari");
          sat.textContent = "[" + i.kural + "] Hesap " + i.hesap + " " + i.ad + " -> " + i.mesaj;
          detay.appendChild(sat);
        });
        kayit.appendChild(detay);
      });

      liste.appendChild(kayit);
    });

    // Kontrol raporu dosyalarini gorunur rapor listesine ekle
    sonuclar.forEach(s => {
      if (s.kontrol_dosyasi) {
        // Goster butonu: en azindan log
        logEkle("bilgi", "Kontrol raporu: " + s.kontrol_dosyasi);
      }
    });
  }).catch(e => {
    liste.innerHTML = '<div class="bos-liste">Kontrol yapilamadi: ' + muhafaza(String(e)) + '</div>';
  });
}