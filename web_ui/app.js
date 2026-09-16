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
  _loglar.push({ seviye, mesaj });
  while (_loglar.length > 700) { _loglar.shift(); }
  const konsol = sec("logKonsol");
  if (!konsol) return;
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

let _dashAutoRefresh = null;

async function dashboardYukle() {
  const yukleniyor = document.getElementById("dashYukleniyor");
  const icerik = document.getElementById("dashIcerik");
  if (yukleniyor) yukleniyor.style.display = "block";
  if (icerik) icerik.style.display = "none";
  try {
    const r = await apiGetir("/api/kontrol/dashboard");
    if (!r.ok) { toastGoster("hata", "Dashboard yüklenemedi."); return; }
    const ist = r.istatistik || {};
    sec("dashToplam").textContent = ist.toplam || 0;
    sec("dashOk").textContent = ist.ok || 0;
    sec("dashHata").textContent = ist.hata || 0;
    sec("dashUyari").textContent = ist.uyari || 0;
    const setYuzde = (id, pay, toplam) => {
      const el = sec(id);
      if (el) el.textContent = toplam > 0 ? Math.round((pay / toplam) * 100) + "%" : "0%";
    };
    setYuzde("dashToplamYuzde", ist.toplam || 0, ist.toplam || 1);
    setYuzde("dashOkYuzde", ist.ok || 0, ist.toplam || 1);
    setYuzde("dashHataYuzde", ist.hata || 0, ist.toplam || 1);
    setYuzde("dashUyariYuzde", ist.uyari || 0, ist.toplam || 1);
    if (r.surum) {
      sec("versiyon").textContent = r.surum;
      const surumEl = document.getElementById("uygulamaSurum");
      if (surumEl) surumEl.textContent = "v" + r.surum;
      sec("versiyonBilgi").textContent = "v" + r.surum + (r.guncelleme && !r.guncelleme.guncellememevcut ? " — Güncelleme mevcut" : " — Güncel");
    }
    if (r.guncelleme && !r.guncelleme.guncellememevcut) {
      const bar = document.getElementById("guncelleBar");
      if (bar) bar.style.display = "block";
    }
    if (r.kural_ist && r.kural_ist.length > 0) {
      const kuralDiv = document.getElementById("dashKural");
      if (kuralDiv) kuralDiv.style.display = "block";
      const liste = document.getElementById("dashKuralListe");
      if (liste) {
        liste.innerHTML = r.kural_ist.map(([kid, veri]) =>
          '<div class="dash-kural-satir">' +
          '<span class="dash-kural-id">' + kid + '</span>' +
          '<span class="dash-kural-bar"><span class="dash-kural-dolu" style="width:' + Math.min(100, ((veri.hata || 0) / (veri.toplam || 1)) * 100) + '%; background:var(--kirmizi);"></span></span>' +
          '<span class="dash-kural-ist">' + (veri.hata || 0) + '/' + (veri.toplam || 0) + '</span>' +
          '</div>'
        ).join("");
      }
    }
    const sonKontrolEl = document.getElementById("dashSonKontrol");
    if (sonKontrolEl && r.son_kontrol) {
      sonKontrolEl.textContent = "Son kontrol: " + (r.son_kontrol.dosya_adi || "") + " — " + (r.son_kontrol.kontrol_tarihi || "").slice(0, 16);
    }
    let grafik = r.grafik || null;
    if (grafik && grafik.gunler && grafik.gunler.length > 0) {
      sec("grafikBaslik").textContent = "HATA/UYARI/OK Durumu — Son " + grafik.gunler.length + " Gün";
      sec("grafikPeriyot").textContent = grafik.gunler.length + " gün";
      cizChart(grafik);
    }
    const barlar = sec("grafikBarlar");
    if (barlar) {
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
    }
    const sarici = sec("dashTabloSarici");
    sarici.innerHTML = "";
    const sonuclar = r.sonuclar || [];
    if (sonuclar.length === 0) {
      sarici.innerHTML = '<div class="bos-liste">' + (DIL[aktifDil]?.bosListe || "Veri yok.") + '</div>';
      if (yukleniyor) yukleniyor.style.display = "none";
      if (icerik) icerik.style.display = "block";
      return;
    }
    const ust = document.createElement("div");
    ust.className = "dash-satir dash-ust";
    ust.innerHTML =
      '<span class="dash-son-durum">Durum</span>' +
      '<span class="dash-son-firma">Firma / Dosya</span>' +
      '<span class="dash-son-hata">HATA</span>' +
      '<span class="dash-son-uyari">UYARI</span>' +
      '<span class="dash-son-tarih">Tarih</span>';
    sarici.appendChild(ust);
    sonuclar.forEach(s => {
      const satir = document.createElement("div");
      satir.className = "dash-satir";
      const durumKucuk = (s.durum || "").toLowerCase();
      satir.innerHTML =
        '<span class="dash-son-durum ' + durumKucuk + '">' + (s.durum || "") + '</span>' +
        '<span class="dash-son-firma">' + (s.firma_adi || s.dosya_adi || "") + '</span>' +
        '<span class="dash-son-hata">' + (s.hata_sayisi || 0) + '</span>' +
        '<span class="dash-son-uyari">' + (s.uyari_sayisi || 0) + '</span>' +
        '<span class="dash-son-tarih">' + (s.kontrol_tarihi || "").slice(5, 16) + '</span>';
      sarici.appendChild(satir);
    });
    const sonRaporlar = r.son_raporlar || [];
    const raporBlok = document.getElementById("dashSonRaporlar");
    const raporSarici = document.getElementById("dashRaporSarici");
    if (raporBlok && raporSarici) {
      if (sonRaporlar.length === 0) {
        raporBlok.style.display = "none";
      } else {
        raporBlok.style.display = "block";
        raporSarici.innerHTML = "";
        let ru = "";
        sonRaporlar.forEach(s => {
          ru += '<div class="dash-satir">' +
            '<span class="dash-son-durum ' + (s.durum || "").toLowerCase() + '">' + (s.durum || "") + '</span>' +
            '<span class="dash-son-firma">' + muhafaza(s.urun_adi || s.kisa_ad || "") + '</span>' +
            '<span class="dash-son-hata">' + (s.sorgu_sayisi || 0) + '</span>' +
            '<span class="dash-son-uyari">' + muhafaza(s.rapor_dosyasi || "") + '</span>' +
            '<span class="dash-son-tarih">' + (s.tarih || "").slice(0, 16) + '</span>' +
          '</div>';
        });
        raporSarici.innerHTML = ru;
      }
    }
    if (yukleniyor) yukleniyor.style.display = "none";
    if (icerik) icerik.style.display = "block";
    baslatAutoRefresh();
  } catch (e) {
    toastGoster("hata", "Yüklenemedi.");
    if (yukleniyor) yukleniyor.style.display = "none";
    if (icerik) icerik.style.display = "block";
  }
}

function baslatAutoRefresh() {
  if (_dashAutoRefresh) clearInterval(_dashAutoRefresh);
  _dashAutoRefresh = setInterval(() => {
    const blok = document.getElementById("blokDashboard");
    if (blok && blok.style.display !== "none") dashboardYukle();
  }, 60000);
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

let sayfaIndex = 0;
let sayfaBoyut = 25;

function tabloDoldur() {
  const govde = sec("tabloGovde");
  govde.innerHTML = "";
  const filtre = sec("arama")?.value.trim().toLocaleLowerCase("tr") || "";
  const fKisa = (sec("filtreKisa")?.value || "").toLocaleLowerCase("tr");
  const fUzun = (sec("filtreUzun")?.value || "").toLocaleLowerCase("tr");
  const fVDairesi = (sec("filtreVDairesi")?.value || "").toLocaleLowerCase("tr");
  const fVNo = (sec("filtreVNo")?.value || "").toLocaleLowerCase("tr");

  let filtrelenen = [];
  musteriSayisi = musteriler.length;
  musteriler.forEach((m, i) => {
    const kisa = (m.kisa_ad || "").toLocaleLowerCase("tr");
    const uzun = (m.uzun_ad || "").toLocaleLowerCase("tr");
    if (filtre && !kisa.includes(filtre) && !uzun.includes(filtre)) return;
    if (fKisa && !kisa.includes(fKisa)) return;
    if (fUzun && !uzun.includes(fUzun)) return;
    if (fVDairesi && !(m.vergi_dairesi || "").toLowerCase().includes(fVDairesi)) return;
    if (fVNo && !(m.vergi_no || "").toLowerCase().includes(fVNo)) return;
    filtrelenen.push({ m, i });
  });

  const toplamSayfa = Math.max(1, Math.ceil(filtrelenen.length / sayfaBoyut));
  if (sayfaIndex >= toplamSayfa) sayfaIndex = toplamSayfa - 1;
  if (sayfaIndex < 0) sayfaIndex = 0;
  const baslangic = sayfaIndex * sayfaBoyut;
  const son = baslangic + sayfaBoyut;
  const gorunen = filtrelenen.slice(baslangic, son);

  gorunen.forEach(({ m, i }) => {
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
    tr.addEventListener("dblclick", () => { musteriDetay(m.kisa_ad); });
    govde.appendChild(tr);
  });

  sec("musteriSayisi").textContent = musteriSayisi + " musteri";
  sec("topluBtn").disabled = calisiyor || musteriSayisi === 0;

  if (filtrelenen.length === 0 && musteriSayisi > 0) {
    const bos = document.createElement("tr");
    bos.className = "bos-satir";
    bos.innerHTML = "<td colspan='4'>Filtrelere uyan musteri yok.</td>";
    govde.appendChild(bos);
  } else if (musteriler.length === 0) {
    const bos = document.createElement("tr");
    bos.className = "bos-satir";
    bos.innerHTML = "<td colspan='4'>Oncelikle \"Musterileri Getir\" butonuna basin.</td>";
    govde.appendChild(bos);
  }

  const sayfalama = sec("sayfalama");
  if (sayfalama) {
    sayfalama.style.display = filtrelenen.length > sayfaBoyut ? "block" : "none";
  }
  const sayfaBilgi = sec("sayfaBilgi");
  if (sayfaBilgi) sayfaBilgi.textContent = (sayfaIndex + 1) + " / " + toplamSayfa;
  const onceBtn = sec("sayfaOnceBtn");
  if (onceBtn) onceBtn.disabled = sayfaIndex === 0;
  const sonraBtn = sec("sayfaSonraBtn");
  if (sonraBtn) sonraBtn.disabled = sayfaIndex >= toplamSayfa - 1;
}

function sayfaOnce() {
  if (sayfaIndex > 0) { sayfaIndex--; tabloDoldur(); }
}

function sayfaSonra() {
  const max = Math.max(1, Math.ceil(musteriler.length / sayfaBoyut));
  if (sayfaIndex < max - 1) { sayfaIndex++; tabloDoldur(); }
}

function sayfaBoyutDegistir() {
  const el = sec("sayfaBoyut");
  sayfaBoyut = el ? parseInt(el.value) || 25 : 25;
  sayfaIndex = 0;
  tabloDoldur();
}

function filtreTemizle() {
  ["filtreKisa", "filtreUzun", "filtreVDairesi", "filtreVNo"].forEach(id => {
    const el = sec(id);
    if (el) el.value = "";
  });
  tabloDoldur();
}

function aramaAc() {
  const blok = sec("blokArama");
  if (blok) blok.style.display = blok.style.display === "none" ? "block" : "none";
}

function aramaGizle() {
  const blok = sec("blokArama");
  if (blok) blok.style.display = "none";
}

function tabloFiltrele() { sayfaIndex = 0; tabloDoldur(); }

/* ---------- Log Filtre ---------- */
let aktifLogFiltre = "tum";

function logFiltrele(seviye) {
  aktifLogFiltre = seviye;
  logGoster();
}

function logGoster() {
  const konsol = sec("logKonsol");
  if (!konsol) return;
  konsol.innerHTML = "";
  const filtre = aktifLogFiltre;
  const kayitlar = filtre === "tum" ? _loglar : _loglar.filter(l => l.seviye === filtre);
  if (kayitlar.length === 0) {
    const bos = document.createElement("div");
    bos.className = "log-satir bilgi";
    bos.textContent = "Bu filtreyle kayıt yok.";
    konsol.appendChild(bos);
    return;
  }
  kayitlar.forEach(l => {
    const satir = document.createElement("div");
    satir.className = "log-satir " + l.seviye;
    satir.textContent = l.mesaj;
    konsol.appendChild(satir);
  });
  konsol.scrollTop = konsol.scrollHeight;
}

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

/* ---------- Grafik ---------- */
let _grafikGun = 7;
let _chart = null;

function cizChart(data) {
  const canvas = sec("grafikCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (_chart) { _chart.destroy(); _chart = null; }
  _chart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: data.gunler,
      datasets: [
        { label: "OK", data: data.ok, backgroundColor: "rgba(34,197,94,0.7)", borderRadius: 3 },
        { label: "UYARI", data: data.uyari, backgroundColor: "rgba(250,204,21,0.7)", borderRadius: 3 },
        { label: "HATA", data: data.hata, backgroundColor: "rgba(239,68,68,0.7)", borderRadius: 3 },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { font: { size: 11 } } } },
      scales: {
        y: { beginAtZero: true, ticks: { stepSize: 1 } },
        x: { stacked: false },
      },
    },
  });
}

function grafikGunDegistir(yon) {
  _grafikGun = Math.max(1, Math.min(30, _grafikGun + yon));
  apiGetir("/api/kontrol/dashboard").then(r => {
    if (r.ok && r.grafik) {
      cizChart(r.grafik);
    }
  });
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

    // Toplu rapor tamamlandıysa karşılaştırma göster
    if (_onceCalisiyor && !d.calisiyor) {
      karistirmaGoster();
    }
    _onceCalisiyor = d.calisiyor;
  } catch (e) {
    // Sunucu henüz hazır değilse sessizce bekle
  }
  setTimeout(durumPoll, 700);
}

let _onceCalisiyor = false;

async function kontrolGecmisGizle() {
  sec("kontrolGecmisBolum").style.display = "none";
  const filtre = sec("kontrolGecmisFiltre");
  if (filtre) filtre.style.display = "none";
  kontrolGecmisTumuVeriler = [];
  kontrolGecmisFiltreli = "tum";
}

function kontrolGecmisAc() {
  sec("kontrolGecmisBolum").style.display = "block";
  sec("kontrolGecmisArama").focus();
}

async function kontrolGecmisAra() {
  const firma = (sec("kontrolGecmisArama")?.value || "").trim();
  if (!firma) {
    toastGoster("hata", "Firma adı yazın.");
    return;
  }
  const liste = sec("kontrolGecmisListe");
  liste.innerHTML = '<div class="bos-liste">Aranıyor...</div>';
  liste.style.display = "block";
  try {
    const r = await apiGonder("/api/kontrol/arama", { firma });
    if (!r.ok) {
      liste.innerHTML = '<div class="bos-liste">Hata: ' + muhafaza(r.hata || "bilinmiyor") + '</div>';
      return;
    }
    const sonuclar = r.sonuclar || [];
    if (sonuclar.length === 0) {
      liste.innerHTML = '<div class="bos-liste">Bu firma için geçmiş kayıt bulunamadı.</div>';
      return;
    }
    let html = '<div style="padding:8px 12px;font-weight:600;">Geçmiş Kontrol Raporları (' + sonuclar.length + ')</div>';
    sonuclar.forEach(s => {
      html += '<div class="kontrol-kayit ok" style="cursor:default;">' +
        '<span class="kontrol-ad">' + muhafaza(s.firma || s.dosya) + '</span>' +
        '<span class="kontrol-ozet">' + muhafaza(s.ozet || '') + ' — ' + muhafaza(s.kontrol_tarihi || '') + '</span>' +
      '</div>';
    });
    liste.innerHTML = html;
  } catch (e) {
    liste.innerHTML = '<div class="bos-liste">Bağlantı hatası.</div>';
  }
}

let kontrolGecmisFiltreli = "tum";

async function kontrolGecmisTumu() {
  kontrolGecmisFiltreli = "tum";
  const liste = sec("kontrolGecmisListe");
  liste.innerHTML = '<div class="bos-liste">Yükleniyor...</div>';
  liste.style.display = "block";
  const filtre = sec("kontrolGecmisFiltre");
  if (filtre) filtre.style.display = "flex";
  document.querySelectorAll("#kontrolGecmisFiltre .btn-filtre").forEach(btn => {
    btn.classList.toggle("aktif", btn.dataset.filtre === "tum");
  });
  try {
    const r = await apiGonder("/api/kontrol/arama", { tumu: true });
    if (!r.ok) {
      liste.innerHTML = '<div class="bos-liste">Hata: ' + muhafaza(r.hata || "bilinmiyor") + '</div>';
      return;
    }
    const sonuclar = r.sonuclar || [];
    if (sonuclar.length === 0) {
      liste.innerHTML = '<div class="bos-liste">Geçmiş kontrol kaydı yok.</div>';
      return;
    }
    kontrolGecmisListeYap(sonuclar, sonuclar.length);
  } catch (e) {
    liste.innerHTML = '<div class="bos-liste">Bağlantı hatası.</div>';
  }
}

function kontrolGecmisFiltrele(filtre) {
  kontrolGecmisFiltreli = filtre;
  const liste = sec("kontrolGecmisListe");
  document.querySelectorAll("#kontrolGecmisFiltre .btn-filtre").forEach(btn => {
    btn.classList.toggle("aktif", btn.dataset.filtre === filtre);
  });
  const arama = (sec("kontrolGecmisArama")?.value || "").toLocaleLowerCase("tr");
  let kaynak = filtre === "tum" ? kontrolGecmisTumuVeriler : kontrolGecmisTumuVeriler.filter(s => s.durum === filtre);
  if (arama) {
    kaynak = kaynak.filter(s => (s.firma || "").toLocaleLowerCase("tr").includes(arama) || (s.dosya || "").toLocaleLowerCase("tr").includes(arama));
  }
  if (kaynak.length === 0) {
    liste.innerHTML = '<div class="bos-liste">Bu filtreyle eslesen kayit yok.</div>';
    return;
  }
  kontrolGecmisListeYap(kaynak, kaynak.length);
}

let kontrolGecmisTumuVeriler = [];

function kontrolGecmisListeYap(sonuclar, toplam) {
  const liste = sec("kontrolGecmisListe");
  kontrolGecmisTumuVeriler = sonuclar;
  let html = '<div style="padding:8px 12px;font-weight:600;">Geçmiş Kontrol Raporları — ' + (kontrolGecmisFiltreli === "tum" ? "Tümü" : kontrolGecmisFiltreli) + ' (' + toplam + ')</div>';
  sonuclar.forEach(s => {
    const durumRenk = s.durum === "OK" ? "var(--yesil)" : s.durum === "UYARI" ? "#facc15" : "var(--kirmizi)";
    html += '<div class="kontrol-kayit ok" style="cursor:pointer;border-left:4px solid ' + durumRenk + ';" onclick="kontrolDetay(' + (s.id || 0) + ')">' +
      '<span class="kontrol-ad">' + muhafaza(s.firma || s.dosya) + '</span>' +
      '<span class="kontrol-ozet">' + (s.hata_sayisi || 0) + 'HATA ' + (s.uyari_sayisi || 0) + 'UYARI — ' + muhafaza(s.kontrol_tarihi || '') + '</span>' +
    '</div>';
  });
  liste.innerHTML = html;
  if (sonuclar.length > 0) { const btn = sec("kontrolCSVBtn"); if (btn) btn.style.display = "inline-block"; }
}

function kontrolCSVIndir() {
  if (!kontrolGecmisTumuVeriler || kontrolGecmisTumuVeriler.length === 0) return;
  let csv = "Firma;Dosya;Durum;Hata Sayisi;Uyari Sayisi;Tarih\n";
  kontrolGecmisTumuVeriler.forEach(s => {
    csv += '"' + (s.firma || s.dosya || "").replace(/"/g, '""') + '";'
      + '"' + (s.dosya || "").replace(/"/g, '""') + '";'
      + (s.durum || "") + ";"
      + (s.hata_sayisi || 0) + ";"
      + (s.uyari_sayisi || 0) + ";"
      + (s.kontrol_tarihi || "") + "\n";
  });
  const blob = new Blob(["\uFEFF" + csv], {type: "text/csv;charset=utf-8;"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "kontrol_sonuclari_" + new Date().toISOString().slice(0, 10) + ".csv";
  a.click();
  URL.revokeObjectURL(url);
}

function kontrolDetayModalKapat(e) {
  if (e && e.target !== e.currentTarget) return;
  const modal = sec("kontrolDetayModal");
  if (modal) modal.style.display = "none";
}

function raporDetayModalKapat(e) {
  if (e && e.target !== e.currentTarget) return;
  const modal = sec("raporDetayModal");
  if (modal) modal.style.display = "none";
}

let kontrolDetayIhlaller = [];

async function kontrolDetay(id) {
  const modal = sec("kontrolDetayModal");
  if (!modal) return;
  modal.style.display = "flex";
  const grid = sec("kontrolDetayGrid");
  const ihlallerDiv = sec("kontrolDetayIhlaller");
  const baslik = sec("kontrolDetayBaslik");
  const filtreInput = sec("kontrolDetayHesapFiltre");
  if (filtreInput) filtreInput.value = "";
  if (grid) grid.innerHTML = '<div class="bos-liste">Yükleniyor...</div>';
  if (ihlallerDiv) ihlallerDiv.innerHTML = '<div class="bos">Yükleniyor...</div>';
  if (baslik) baslik.textContent = "Kontrol Detayı";
  kontrolDetayIhlaller = [];
  try {
    const r = await apiGonder("/api/kontrol/gecmis-detay", { id: id });
    if (!r.ok) {
      if (grid) grid.innerHTML = '<div class="bos-liste">Hata: ' + muhafaza(r.hata || "bilinmiyor") + '</div>';
      return;
    }
    const d = r.detay || {};
    if (baslik) baslik.textContent = muhafaza(d.firma_adi || d.dosya_adi || "Kontrol Detayı");
    if (grid) {
      let gh = "";
      gh += '<div class="mg-sol">Dosya</div><div class="mg-sag">' + muhafaza(d.dosya_adi || "") + '</div>';
      gh += '<div class="mg-sol">Firma</div><div class="mg-sag">' + muhafaza(d.firma_adi || "") + '</div>';
      gh += '<div class="mg-sol">Dönem</div><div class="mg-sag">' + muhafaza(d.donem || "") + '</div>';
      gh += '<div class="mg-sol">Tarih</div><div class="mg-sag">' + muhafaza(d.kontrol_tarihi || "") + '</div>';
      gh += '<div class="mg-sol">Satır</div><div class="mg-sag">' + (d.satir_sayisi || 0) + '</div>';
      gh += '<div class="mg-sol">Durum</div><div class="mg-sag">' + (d.durum || "") + '</div>';
      gh += '<div class="mg-sol">HATA</div><div class="mg-sag" style="color:var(--kirmizi);">' + (d.hata_sayisi || 0) + '</div>';
      gh += '<div class="mg-sol">UYARI</div><div class="mg-sag" style="color:#facc15;">' + (d.uyari_sayisi || 0) + '</div>';
      grid.innerHTML = gh;
    }
    if (ihlallerDiv) {
      const ihl = d.ihlaller || [];
      kontrolDetayIhlaller = ihl;
      if (ihl.length === 0) {
        ihlallerDiv.innerHTML = '<div class="bos">İhlal kaydı yok.</div>';
        return;
      }
      const ozet = {};
      ihl.forEach(i => {
        const hk = i.hesap_kodu || "bilinmiyor";
        if (!ozet[hk]) ozet[hk] = {hata: 0, uyari: 0};
        if ((i.seviye || "").toLowerCase() === "hata") ozet[hk].hata++;
        else ozet[hk].uyari++;
      });
      let ozetHtml = '<div class="ihl-ozet"><h4>Hesap Bazlı Özet</h4><div class="ihl-ozet-tablo">';
      const sirali = Object.entries(ozet).sort((a, b) => (b[1].hata + b[1].uyari) - (a[1].hata + a[1].uyari));
      sirali.forEach(([hesap, s]) => {
        const toplam = s.hata + s.uyari;
        ozetHtml += '<div class="ihl-ozet-satir">'
          + '<span class="ihl-ozet-hesap">' + muhafaza(hesap) + '</span>'
          + '<span class="ihl-ozet-hata">' + s.hata + ' HATA</span>'
          + '<span class="ihl-ozet-uyari">' + s.uyari + ' UYARI</span>'
          + '<span class="ihl-ozet-toplam">' + toplam + ' toplam</span>'
          + '</div>';
      });
      ozetHtml += '</div></div>';

      let ih = "";
      ihl.forEach(i => {
        const sev = (i.seviye || "").toLowerCase();
        const sevClass = sev === "hata" ? "hata" : sev === "uyari" ? "uyari" : "";
        ih += '<div class="ihl-satir">' +
          '<span class="ihl-kural">' + muhafaza(i.kural_id || "") + '</span>' +
          '<span class="ihl-hesap">' + muhafaza(i.hesap_kodu || "") + '</span>' +
          '<span class="ihl-mesaj">' + muhafaza(i.mesaj || i.deger || "") + '</span>' +
          (sevClass ? '<span class="ihl-seviye ' + sevClass + '">' + (i.seviye || "").toUpperCase() + '</span>' : '') +
        '</div>';
        if (i.oneri) {
          ih += '<div class="ihl-oneri">💡 ' + muhafaza(i.oneri) + '</div>';
        }
      });
      ihlallerDiv.innerHTML = ozetHtml + ih;
    }
  } catch (e) {
    if (grid) grid.innerHTML = '<div class="bos-liste">Bağlantı hatası.</div>';
  }
}

function kontrolDetayFiltrele() {
  const filtreInput = sec("kontrolDetayHesapFiltre");
  const ihlallerDiv = sec("kontrolDetayIhlaller");
  if (!filtreInput || !ihlallerDiv) return;
  const filtre = (filtreInput.value || "").trim().toLowerCase();
  const ihl = filtre ? kontrolDetayIhlaller.filter(i => (i.hesap_kodu || "").toLowerCase().includes(filtre)) : kontrolDetayIhlaller;
  if (ihl.length === 0) {
    ihlallerDiv.innerHTML = '<div class="bos">Sonuç bulunamadı.</div>';
    return;
  }
  const ozet = {};
  ihl.forEach(i => {
    const hk = i.hesap_kodu || "bilinmiyor";
    if (!ozet[hk]) ozet[hk] = {hata: 0, uyari: 0};
    if ((i.seviye || "").toLowerCase() === "hata") ozet[hk].hata++;
    else ozet[hk].uyari++;
  });
  let ozetHtml = '<div class="ihl-ozet"><h4>Hesap Bazlı Özet</h4><div class="ihl-ozet-tablo">';
  const sirali = Object.entries(ozet).sort((a, b) => (b[1].hata + b[1].uyari) - (a[1].hata + a[1].uyari));
  sirali.forEach(([hesap, s]) => {
    const toplam = s.hata + s.uyari;
    ozetHtml += '<div class="ihl-ozet-satir">'
      + '<span class="ihl-ozet-hesap">' + muhafaza(hesap) + '</span>'
      + '<span class="ihl-ozet-hata">' + s.hata + ' HATA</span>'
      + '<span class="ihl-ozet-uyari">' + s.uyari + ' UYARI</span>'
      + '<span class="ihl-ozet-toplam">' + toplam + ' toplam</span>'
      + '</div>';
  });
  ozetHtml += '</div></div>';
  let ih = "";
  ihl.forEach(i => {
    const sev = (i.seviye || "").toLowerCase();
    const sevClass = sev === "hata" ? "hata" : sev === "uyari" ? "uyari" : "";
    ih += '<div class="ihl-satir">' +
      '<span class="ihl-kural">' + muhafaza(i.kural_id || "") + '</span>' +
      '<span class="ihl-hesap">' + muhafaza(i.hesap_kodu || "") + '</span>' +
      '<span class="ihl-mesaj">' + muhafaza(i.mesaj || i.deger || "") + '</span>' +
      (sevClass ? '<span class="ihl-seviye ' + sevClass + '">' + (i.seviye || "").toUpperCase() + '</span>' : '') +
    '</div>';
    if (i.oneri) {
      ih += '<div class="ihl-oneri">💡 ' + muhafaza(i.oneri) + '</div>';
    }
  });
  ihlallerDiv.innerHTML = ozetHtml + ih;
}

async function raporDetay(id) {
  const modal = sec("raporDetayModal");
  if (!modal) return;
  modal.style.display = "flex";
  const grid = sec("raporDetayGrid");
  const baslik = sec("raporDetayBaslik");
  if (grid) grid.innerHTML = '<div class="bos-liste">Yükleniyor...</div>';
  if (baslik) baslik.textContent = "Rapor Detayı";
  try {
    const r = await apiGonder("/api/rapor_gecmis-detay", { id: id });
    if (!r.ok) {
      if (grid) grid.innerHTML = '<div class="bos-liste">Hata: ' + muhafaza(r.hata || "bilinmiyor") + '</div>';
      return;
    }
    const d = r.detay || {};
    if (baslik) baslik.textContent = muhafaza(d.urun_adi || d.kisa_ad || "Rapor Detayı");
    if (grid) {
      let gh = "";
      gh += '<div class="mg-sol">Tarih</div><div class="mg-sag">' + muhafaza(d.tarih || "").slice(0, 16) + '</div>';
      gh += '<div class="mg-sol">KŞ</div><div class="mg-sag">' + muhafaza(d.kisi_no || "") + '</div>';
      gh += '<div class="mg-sol">Ürün</div><div class="mg-sag">' + muhafaza(d.urun_adi || "") + '</div>';
      gh += '<div class="mg-sol">Kod</div><div class="mg-sag">' + muhafaza(d.urun_kodu || "") + '</div>';
      gh += '<div class="mg-sol">Müşteri</div><div class="mg-sag">' + muhafaza(d.musteri_kodu || "") + '</div>';
      gh += '<div class="mg-sol">Hafi</div><div class="mg-sag">' + muhafaza(d.urun_hafi || "") + '</div>';
      gh += '<div class="mg-sol">Tip</div><div class="mg-sag">' + muhafaza(d.rapor_tipi || "") + '</div>';
      gh += '<div class="mg-sol">Sorgu</div><div class="mg-sag" style="color:var(--turkuaz);">' + (d.sorgu_sayisi || 0) + '</div>';
      gh += '<div class="mg-sol">Süre</div><div class="mg-sag">' + (d.sure_saniye || 0) + 's</div>';
      gh += '<div class="mg-sol">Durum</div><div class="mg-sag ' + (d.durum || "").toLowerCase() + '">' + (d.durum || "") + '</div>';
      gh += '<div class="mg-sol">Dosya</div><div class="mg-sag" style="font-size:10px;">' + muhafaza(d.rapor_dosyasi || "") + '</div>';
      grid.innerHTML = gh;
    }
  } catch (e) {
    if (grid) grid.innerHTML = '<div class="bos-liste">Bağlantı hatası.</div>';
  }
}

function musteriDetayModalKapat(e) {
  if (e && e.target !== e.currentTarget) return;
  const modal = sec("musteriDetayModal");
  if (modal) modal.style.display = "none";
}

function kurallarAc() {
  const overlay = sec("kurallarOverlay");
  const icerik = sec("kurallarIcerik");
  if (!overlay || !icerik) return;
  overlay.style.display = "flex";
  icerik.innerHTML = '<div style="text-align:center;padding:20px;">Yükleniyor...</div>';
  fetch("/api/kurallar").then(c => c.json()).then(r => {
    if (!r.ok) { icerik.innerHTML = '<div class="bos-liste">Hata: ' + muhafaza(r.hata || "Bilinmeyen hata") + '</div>'; return; }
    let h = '<div class="kurallar-listesi">';
    (r.kurallar || []).forEach(k => {
      const sevClass = (k.seviye || "").toLowerCase() === "hata" ? "hata" : "uyari";
      h += '<div class="kural-satir">'
        + '<div class="kural-satir-baslik">'
        + '<span class="kural-id">' + muhafaza(k.id) + '</span>'
        + '<span class="kural-seviye ' + sevClass + '">' + muhafaza(k.seviye) + '</span>'
        + '<span class="kural-kodlar">' + muhafaza((k.kodlar || []).join(", ")) + '</span>'
        + '</div>'
        + '<div class="kural-kosul">' + muhafaza(k.kosul) + '</div>'
        + (k.oneri ? '<div class="kural-oneri">💡 ' + muhafaza(k.oneri) + '</div>' : '')
        + '</div>';
    });
    h += '</div>';
    icerik.innerHTML = h;
  }).catch(e => { icerik.innerHTML = '<div class="bos-liste">Bağlantı hatası.</div>'; });
}
function kurallarKapat() { const o = sec("kurallarOverlay"); if (o) o.style.display = "none"; }

async function musteriDetay(kisaAd) {
  const modal = sec("musteriDetayModal");
  if (!modal) return;
  modal.style.display = "flex";
  const grid = sec("musteriDetayGrid");
  const baslik = sec("musteriDetayBaslik");
  const raporDiv = sec("musteriDetayRaporlar");
  const kontrolDiv = sec("musteriDetayKontroller");
  if (grid) grid.innerHTML = '<div class="bos-liste">Yükleniyor...</div>';
  if (raporDiv) raporDiv.innerHTML = '<div class="bos">Yükleniyor...</div>';
  if (kontrolDiv) kontrolDiv.innerHTML = '<div class="bos">Yükleniyor...</div>';
  if (baslik) baslik.textContent = "Müşteri Detayı";
  try {
    const r = await apiGonder("/api/musteri-detay", { kisa_ad: kisaAd });
    if (!r.ok) {
      if (grid) grid.innerHTML = '<div class="bos-liste">Hata: ' + muhafaza(r.hata || "bilinmiyor") + '</div>';
      return;
    }
    const m = r.musteri || {};
    if (baslik) baslik.textContent = muhafaza(m.kisa_ad || kisaAd);
    if (grid) {
      let gh = "";
      gh += '<div class="mg-sol">Kısa Ad</div><div class="mg-sag">' + muhafaza(m.kisa_ad || "") + '</div>';
      gh += '<div class="mg-sol">Uzun Ad</div><div class="mg-sag">' + muhafaza(m.uzun_ad || "") + '</div>';
      gh += '<div class="mg-sol">Vergi Dairesi</div><div class="mg-sag">' + muhafaza(m.vergi_dairesi || "") + '</div>';
      gh += '<div class="mg-sol">Vergi No</div><div class="mg-sag">' + muhafaza(m.vergi_no || "") + '</div>';
      gh += '<div class="mg-sol">Toplam Rapor</div><div class="mg-sag" style="color:var(--turkuaz);">' + (r.raporlar || []).length + '</div>';
      gh += '<div class="mg-sol">Toplam Kontrol</div><div class="mg-sag" style="color:var(--mor-acik);">' + (r.kontroller || []).length + '</div>';
      grid.innerHTML = gh;
    }
    if (raporDiv) {
      const raporlar = r.raporlar || [];
      if (raporlar.length === 0) {
        raporDiv.innerHTML = '<div class="bos">Rapor kaydı yok.</div>';
      } else {
        let rh = '<table class="tablo" style="font-size:11px;"><thead><tr><th>Tarih</th><th>Ürün</th><th>Durum</th><th>Süre</th></tr></thead><tbody>';
        raporlar.forEach(r => {
          const rd = (r.durum || "").toLowerCase();
          rh += '<tr><td>' + muhafaza((r.tarih || "").slice(0, 16)) + '</td>'
            + '<td>' + muhafaza(r.urun_adi || "") + '</td>'
            + '<td><span class="durum-rozet ' + rd + '">' + (r.durum || "") + '</span></td>'
            + '<td>' + (r.sure_saniye || 0) + 's</td></tr>';
        });
        rh += '</tbody></table>';
        raporDiv.innerHTML = rh;
      }
    }
    if (kontrolDiv) {
      const kontroller = r.kontroller || [];
      if (kontroller.length === 0) {
        kontrolDiv.innerHTML = '<div class="bos">Kontrol kaydı yok.</div>';
      } else {
        let kh = '<table class="tablo" style="font-size:11px;"><thead><tr><th>Tarih</th><th>Dosya</th><th>Durum</th><th>HATA</th><th>UYARI</th></tr></thead><tbody>';
        kontroller.forEach(k => {
          const kd = (k.durum || "").toLowerCase();
          kh += '<tr><td>' + muhafaza((k.kontrol_tarihi || "").slice(0, 16)) + '</td>'
            + '<td>' + muhafaza(k.dosya_adi || "") + '</td>'
            + '<td><span class="durum-rozet ' + kd + '">' + (k.durum || "") + '</span></td>'
            + '<td>' + (k.hata_sayisi || 0) + '</td>'
            + '<td>' + (k.uyari_sayisi || 0) + '</td></tr>';
        });
        kh += '</tbody></table>';
        kontrolDiv.innerHTML = kh;
      }
    }
  } catch (e) {
    if (grid) grid.innerHTML = '<div class="bos-liste">Bağlantı hatası.</div>';
  }
}

/* ---------- Giriş ---------- */
secenekDoldur();
durumPoll();
dilYukle();
guncellemeKontrolEt();

async function guncellemeKontrolEt() {
  try {
    const r = await apiGonder("/api/guncelleme");
    if (r && r.ok) {
      const surumEl = document.getElementById("uygulamaSurum");
      if (surumEl && r.surum) surumEl.textContent = "v" + r.surum;
      if (!r.guncelleme.guncellememevcut) {
        toastGoster("uyari", r.guncelleme.mesaj || ("Yeni sürüm var: " + (r.guncelleme.yeni || "")));
        setTimeout(() => {
          const bar = document.getElementById("guncelleBar");
          if (bar) bar.style.display = "block";
        }, 2000);
      } else {
        toastGoster("basarili", r.guncelleme.mesaj || "En güncel sürüme sahipsiniz.");
      }
    }
  } catch (e) {
    toastGoster("hata", "Güncelleme kontrolü başarısız.");
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

let _loglar = [];

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
      if (i.oneri) {
        const onerSat = document.createElement("div");
        onerSat.className = "kontrol-detay-oneri";
        onerSat.style.cssText = "color: var(--mor); font-size: 11px; padding: 2px 8px; font-style: italic;";
        onerSat.textContent = "💡 Öneri: " + i.oneri;
        detay.appendChild(onerSat);
      }
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

function kontrolExportHtml() {
  kontrolExportYap("html");
}

function kontrolExportTxt() {
  kontrolExportYap("txt");
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
      else if (format === "html") uzanti = dosya.replace(/\.xlsx$/, ".html");
      else if (format === "txt") uzanti = dosya.replace(/\.xlsx$/, "_KONTROL.txt");
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

/* ---------- Rapor Karşılaştırma ---------- */
function karistirmaGoster() {
  apiGetir("/api/rapor_karistirma").then(r => {
    if (!r.ok) return;
    const k = r.karistirma;
    const blok = sec("blokKaristirma");
    if (!blok) return;
    blok.style.display = "block";
    const icerik = sec("karistirmaIcerik");
    if (!icerik) return;
    let html = '<div style="display:flex; gap:10px; margin-bottom:10px; flex-wrap:wrap;">'
      + '<div class="ist-toplam"><span>' + k.toplam + '</span> 📄 Toplam</div>'
      + '<div class="ist-ok"><span>' + k.basarili + '</span> ✅ Başarılı</div>'
      + '<div class="ist-hata"><span>' + k.hatali + '</span> ❌ Hatalı</div>'
      + '<div class="ist-uyari"><span>' + (k.ortalama_sure || 0) + 's</span> ⏱️ Ort. Süre</div>'
      + '</div>';
    if (k.kisiler && k.kisiler.length > 0) {
      html += '<table class="tablo"><thead><tr>'
        + '<th>Müşteri</th><th>Ürün</th><th>Durum</th><th>Süre</th><th>Sorgu</th><th>Hata</th>'
        + '</tr></thead><tbody>';
      k.kisiler.forEach(s => {
        const rozet = s.durum === "basarili"
          ? '<span class="durum-rozet ok">OK</span>'
          : s.durum === "kuyruga alindi"
            ? '<span class="durum-rozet uyari">KUYRUK</span>'
            : '<span class="durum-rozet hata">HATA</span>';
        html += '<tr class="satir-giris">'
          + '<td>' + muhafaza(s.kisa_ad) + '</td>'
          + '<td>' + muhafaza(s.urun_adi) + '</td>'
          + '<td>' + rozet + '</td>'
          + '<td>' + (s.sure_saniye || 0) + 's</td>'
          + '<td>' + (s.sorgu_sayisi || 0) + '</td>'
          + '<td>' + muhafaza(s.hata || "") + '</td>'
          + '</tr>';
      });
      html += '</tbody></table>';
    }
    icerik.innerHTML = html;
    toastGoster("basarili", "Toplu rapor karşılaştırma hazır.");
  });
}

function karistirmaGizle() {
  const blok = sec("blokKaristirma");
  if (blok) blok.style.display = "none";
}

/* ---------- Rapor Geçmişi ---------- */
function gecmisAc() {
  const blok = sec("blokGecmis");
  if (blok) blok.style.display = "block";
  gecmisYukle();
}

function gecmisGizle() {
  const blok = sec("blokGecmis");
  if (blok) blok.style.display = "none";
}

function gecmisYukle() {
  const arama = (sec("gecmisArama")?.value || "").trim();
  const durum = (sec("gecmisDurum")?.value || "");
  apiGetir("/api/rapor_gecmis?kisi_no=" + encodeURIComponent(arama) + "&durum=" + encodeURIComponent(durum)).then(r => {
    const liste = sec("gecmisListe");
    if (!liste) return;
    if (!r.ok) {
      liste.innerHTML = '<div class="bos-liste">Hata: ' + muhafaza(r.hata || "bilinmiyor") + '</div>';
      return;
    }
    const kayitlar = r.kayitlar || [];
    if (kayitlar.length === 0) {
      liste.innerHTML = '<div class="bos-liste">Kayıt yok.</div>';
      return;
    }
    let html = '<table class="tablo"><thead><tr>'
      + '<th>Tarih</th><th>KŞ</th><th>Ürün</th><th>Kod</th><th>Müşteri</th><th>Hafi</th><th>Durum</th><th>Süre</th>'
      + '</tr></thead><tbody>';
    kayitlar.forEach(k => {
      const rozet = k.durum === "OK"
        ? '<span class="durum-rozet ok">OK</span>'
        : '<span class="durum-rozet hata">' + muhafaza(k.durum) + '</span>';
      html += '<tr class="satir-giris" style="cursor:pointer;" onclick="raporDetay(' + k.id + ')" title="Detayını görüntüle">'
        + '<td>' + muhafaza((k.tarih || "").slice(0, 16)) + '</td>'
        + '<td>' + muhafaza(k.kisi_no || k.kisa_ad || "") + '</td>'
        + '<td>' + muhafaza(k.urun_adi || "") + '</td>'
        + '<td>' + muhafaza(k.urun_kodu || "") + '</td>'
        + '<td>' + muhafaza(k.musteri_kodu || "") + '</td>'
        + '<td>' + muhafaza(k.urun_hafi || "") + '</td>'
        + '<td>' + rozet + '</td>'
        + '<td>' + (k.sure_saniye || 0) + 's</td>'
        + '</tr>';
    });
    html += '</tbody></table>';
    liste.innerHTML = html;
  });
}