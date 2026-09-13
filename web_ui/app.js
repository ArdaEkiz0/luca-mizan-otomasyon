/* ============================================================
   Luca Mizan Otomasyonu — Frontend Mantığı
   ============================================================ */

"use strict";

/* ---------- Çeviri ---------- */
const DIL = {
  tr: {
    altBaslik: "Raporlarınız bir tık uzağınızda",
    kontrolBaslik: "Mizan Kontrolu",
    dashboardBaslik: "Dashboard",
    grafikBaslik: "HATA Durumu — Son 7 Gün",
    dashTabloBaslik: "Son Kontroller",
    bosListe: "Veri yok.",
    dashboardAc: "📊 Dashboard",
    dosyaKontrolEt: "Raporlari Kontrol Et",
    hataBildirim: " dosyada HATA var! Kontrol listesini inceleyin.",
    uyariBildirim: " dosyada UYARI var.",
    okBildirim: "Tum dosyalar OK!",
    kontrolBildirim: " dosyada HATA\n\nLütfen HATA içeren dosyaları kontrol edin.",
  },
  en: {
    altBaslik: "Your reports are just a click away",
    kontrolBaslik: "Balance Control",
    dashboardBaslik: "Dashboard",
    grafikBaslik: "ERROR Status — Last 7 Days",
    dashTabloBaslik: "Last Controls",
    bosListe: "No data.",
    dashboardAc: "📊 Dashboard",
    dosyaKontrolEt: "Check Reports",
    hataBildirim: " files have ERROR! Check the control list.",
    uyariBildirim: " files have WARNING.",
    okBildirim: "All files OK!",
    kontrolBildirim: " files have ERROR\n\nPlease check the files with errors.",
  },
};

let aktifDil = "tr";

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

function dilDegistir(dil) {
  aktifDil = dil;
  document.querySelectorAll(".dil-btn").forEach(b => b.classList.toggle("aktif", b.dataset.dil === dil));
  const dilVeri = DIL[dil] || DIL.tr;
  sec("altBaslik").textContent = dilVeri.altBaslik;
  sec("kontrolBaslik").textContent = dilVeri.kontrolBaslik;
  ayar_kaydet("dil", dil);
}

function dashboardAc() {
  sec("blokDashboard").style.display = "block";
  dashboardYukle();
}

function dashboardGizle() {
  sec("blokDashboard").style.display = "none";
}

async function dashboardYukle() {
  try {
    const r = await apiGetir("/api/kontrol/dashboard");
    if (!r.ok) return;
    const ist = r.istatistik || {};
    sec("dashToplam").textContent = ist.toplam || 0;
    sec("dashOk").textContent = ist.ok || 0;
    sec("dashHata").textContent = ist.hata || 0;
    sec("dashUyari").textContent = ist.uyari || 0;
    if (r.surum) {
      sec("versiyon").textContent = r.surum;
      sec("versiyonBilgi").textContent = "v" + r.surum + (r.guncelleme && !r.guncelleme.guncellememevcut ? " — Güncelleme mevcut" : " — Güncel");
    }
    if (r.guncelleme && !r.guncelleme.guncellememevcut) {
      const bar = document.getElementById("guncelleBar");
      if (bar) bar.style.display = "block";
    }
    const barlar = sec("grafikBarlar");
    barlar.innerHTML = "";
    if (ist.hata_firmalari && ist.hata_firmalari.length > 0) {
      const enCok = ist.hata_firmalari.slice(0, 7);
      const max = Math.max(...enCok.map(f => f.n || 0), 1);
      enCok.forEach(f => {
        const bar = document.createElement("div");
        bar.className = "grafik-bar";
        bar.style.height = Math.max(4, (f.n / max) * 72) + "px";
        bar.title = f.firma_adi + ": " + (f.n || 0);
        barlar.appendChild(bar);
      });
    } else {
      barlar.innerHTML = '<div class="bos-liste">Veri yok.</div>';
    }
    const sarici = sec("dashTabloSarici");
    sarici.innerHTML = "";
    const sonuclar = r.sonuclar || [];
    if (sonuclar.length === 0) {
      sarici.innerHTML = '<div class="bos-liste">' + (DIL[aktifDil]?.bosListe || "Veri yok.") + '</div>';
      return;
    }
    sonuclar.forEach(s => {
      const satir = document.createElement("div");
      satir.className = "dash-satir";
      const durumKucuk = s.durum.toLowerCase();
      satir.innerHTML =
        '<span class="dash-son-durum ' + durumKucuk + '">' + (s.durum || "") + '</span>' +
        '<span class="dash-son-firma">' + (s.firma_adi || s.dosya_adi || "") + '</span>' +
        '<span class="dash-son-tarih">' + (s.kontrol_tarihi || "").slice(5, 16) + '</span>';
      sarici.appendChild(satir);
    });
  } catch (e) {
    toastGoster("hata", "Yüklenemedi.");
  }
}

function kontrolFiltreleAra() {
  const arama = (sec("kontrolArama")?.value || "").toLocaleLowerCase("tr");
  if (!arama) {
    kontrolFiltrele(kontrolFiltreli || "tum");
    return;
  }
  const liste = sec("kontrolListe");
  liste.innerHTML = "";
  filtrelenen = (kontrolFiltreli === "tum" ? kontrolSonuclari : kontrolSonuclari.filter(s => s.durum === kontrolFiltreli))
    .filter(s => (s.firma || "").toLocaleLowerCase("tr").includes(arama) || (s.dosya || "").toLocaleLowerCase("tr").includes(arama));
  if (filtrelenen.length === 0) {
    liste.innerHTML = '<div class="bos-liste">Eslesen kayit yok.</div>';
    return;
  }
  filtrelenen.forEach(s => kayitOlustur(s));
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

dilYukle();
guncellemeKontrolEt();

async function guncellemeKontrolEt() {
  try {
    const r = await apiGonder("/api/guncelleme");
    if (r && r.ok && !r.guncelleme.guncellememevcut) {
      toastGoster("uyari", r.guncelleme.mesaj || ("Yeni sürüm var: " + (r.guncelleme.yeni || "")));
      setTimeout(() => {
        const bar = document.getElementById("guncelleBar");
        if (bar) bar.style.display = "block";
      }, 2000);
    }
  } catch (e) {
    // Guncelleme kontol opsiyonel
  }
}

async function updateApp() {
  toastGoster("uyari", "Güncelleniyor...");
  try {
    const r = await apiGonder("/api/guncelleme/guncelle");
    if (r && r.ok) {
      if (r.guncellendi) {
        toastGoster("basarili", r.mesaj || "Güncelleme başarılı!");
        setTimeout(() => location.reload(), 2000);
      } else {
        toastGoster("basarili", r.mesaj || "Zaten en güncel sürüm.");
      }
    } else {
      toastGoster("hata", (r && r.mesaj) || "Güncelleme başarısız.");
    }
  } catch (e) {
    toastGoster("hata", "Güncelleme hatası: " + (e.message || ""));
  }
}

async function dilYukle() {
  try {
    const r = await apiGonder("/api/ayar_dil");
    if (r && r.ok) {
      aktifDil = r.dil || "tr";
    }
  } catch (e) {
    // Dil yukleme opsiyonel
  }
  document.querySelectorAll(".dil-btn").forEach(b => b.classList.toggle("aktif", b.dataset.dil === aktifDil));
  const dilVeri = DIL[aktifDil] || DIL.tr;
  sec("altBaslik").textContent = dilVeri.altBaslik;
  sec("kontrolBaslik").textContent = dilVeri.kontrolBaslik;
}

let kontrolSonuclari = [];
let kontrolFiltreli = "tum";

/* ---------- Mizan kontrol ---------- */
function mizanKontrol() {
  const liste = sec("kontrolListe");
  liste.innerHTML = '<div class="bos-liste">Kontrol ediliyor...</div>';
  kontrolSonuclari = [];
  kontrolFiltreli = "tum";
  sec("kontrolIstatistik").style.display = "none";
  sec("kontrolFiltre").style.display = "none";
  apiGonder("/api/kontrol", {}).then(r => {
    if (!r.ok) {
      liste.innerHTML = '<div class="bos-liste">Kontrol hatasi: ' + muhafaza(r.hata || "bilinmiyor") + '</div>';
      return;
    }
    const sonuclar = r.sonuclar || [];
    kontrolSonuclari = sonuclar;
    if (sonuclar.length === 0) {
      liste.innerHTML = '<div class="bos-liste">Kontrol edilecek rapor yok.</div>';
      return;
    }

    // Istatistikleri goster
    const ist = r.istatistik || {};
    sec("istToplam").textContent = ist.toplam || 0;
    sec("istOk").textContent = ist.ok || 0;
    sec("istHata").textContent = ist.hata || 0;
    sec("istUyari").textContent = ist.uyari || 0;
    sec("kontrolIstatistik").style.display = "flex";
    sec("kontrolFiltre").style.display = "flex";

    // Filtre butonlarini guncelle
    document.querySelectorAll(".btn-filtre").forEach(btn => {
      btn.classList.toggle("aktif", btn.dataset.filtre === "tum");
    });

    kontrolFiltrele("tum");

    // HATA dosyalari bildirimi
    const hataSayisi = ist.hata || 0;
    const uyariSayisi = ist.uyari || 0;
    if (hataSayisi > 0) {
      const hataListe = sonuclar.filter(s => s.durum === "HATA").map(s => s.firma || s.dosya);
      toastGoster("hata", hataSayisi + " dosyada HATA var! Kontrol listesini inceleyin.");
      setTimeout(() => {
        alert("⚠️ MİZAN KONTROL — " + hataSayisi + " HATA\n\n" + hataListe.join("\n") + "\n\nLütfen HATA içeren dosyaları kontrol edin.");
      }, 800);
    } else if (uyariSayisi > 0) {
      toastGoster("uyari", uyariSayisi + " dosyada UYARI var.");
    } else {
      toastGoster("basarili", "Tum dosyalar OK!");
    }

    dashboardYukle();
    sec("blokDashboard").style.display = "block";

    // Loglara ekle
    sonuclar.forEach(s => {
      if (s.kontrol_dosyasi) {
        logEkle("bilgi", "Kontrol raporu: " + s.kontrol_dosyasi);
      }
    });
  }).catch(e => {
    liste.innerHTML = '<div class="bos-liste">Kontrol yapilamadi: ' + muhafaza(String(e)) + '</div>';
  });
}

function kayitOlustur(s) {
  const liste = sec("kontrolListe");
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
  } else if (s.durum === "UYARI") {
    kayit.classList.add("uyari");
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
      sat.textContent = "[" + (i.kural || i.kural_id) + "] Hesap " + (i.hesap || i.hesap_kodu) + " " + (i.ad || i.hesap_adi) + " -> " + (i.mesaj || "");
      detay.appendChild(sat);
    });
    kayit.appendChild(detay);
  });

  liste.appendChild(kayit);
}

function kontrolFiltreleAra() {
  const arama = (sec("kontrolArama")?.value || "").toLocaleLowerCase("tr");
  const liste = sec("kontrolListe");
  liste.innerHTML = "";
  let kaynak = kontrolFiltreli === "tum" ? kontrolSonuclari : kontrolSonuclari.filter(s => s.durum === kontrolFiltreli);
  if (arama) {
    kaynak = kaynak.filter(s => (s.firma || "").toLocaleLowerCase("tr").includes(arama) || (s.dosya || "").toLocaleLowerCase("tr").includes(arama));
  }
  if (kaynak.length === 0) {
    liste.innerHTML = '<div class="bos-liste">Eslesen kayit yok.</div>';
    return;
  }
  kaynak.forEach(s => kayitOlustur(s));
}

function kontrolFiltrele(filtre) {
  kontrolFiltreli = filtre;
  const liste = sec("kontrolListe");
  liste.innerHTML = "";

  document.querySelectorAll(".btn-filtre").forEach(btn => {
    btn.classList.toggle("aktif", btn.dataset.filtre === filtre);
  });

  const arama = (sec("kontrolArama")?.value || "").toLocaleLowerCase("tr");
  let filtrelenen = filtre === "tum" ? kontrolSonuclari : kontrolSonuclari.filter(s => s.durum === filtre);
  if (arama) {
    filtrelenen = filtrelenen.filter(s => (s.firma || "").toLocaleLowerCase("tr").includes(arama) || (s.dosya || "").toLocaleLowerCase("tr").includes(arama));
  }

  if (filtrelenen.length === 0) {
    liste.innerHTML = '<div class="bos-liste">Bu filtreyle eslesen kayit yok.</div>';
    return;
  }

  filtrelenen.forEach(s => kayitOlustur(s));
}

/* ---------- Kontrol Export ---------- */
function kontrolExportJson() {
  kontrolExportYap("json");
}

function kontrolExportCsv() {
  kontrolExportYap("csv");
}

function kontrolExportPdf() {
  kontrolExportYap("pdf");
}

function kontrolExportYap(format) {
  const filtrelenen = kontrolFiltreli === "tum"
    ? kontrolSonuclari
    : kontrolSonuclari.filter(s => s.durum === kontrolFiltreli);
  if (filtrelenen.length === 0) {
    toastGoster("uyari", "Indirilecek kayit yok.");
    return;
  }
  filtrelenen.forEach(s => {
    const dosya = s.dosya;
    fetch("/api/kontrol/export/" + format, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dosya: dosya }),
    }).then(r => {
      if (!r.ok) return r.json().then(j => { throw new Error(j.hata || "Bilinmeyen hata"); });
      return r.blob();
    }).then(blob => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      let uzanti = format;
      if (format === "pdf") uzanti = dosya.replace(/\.xlsx$/, "_KONTROL.pdf");
      else if (format === "csv") uzanti = dosya.replace(/\.xlsx$/, ".csv");
      else uzanti = dosya.replace(/\.xlsx$/, ".json");
      a.download = uzanti;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toastGoster("basarili", uzanti + " indirildi.");
    }).catch(e => {
      toastGoster("hata", "Indirilemedi: " + (e.message || "Bilinmeyen hata"));
    });
  });
}