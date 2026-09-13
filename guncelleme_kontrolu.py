import json
import os
import subprocess
import urllib.request
from pathlib import Path

REPO_OWNER = "ArdaEkiz0"
REPO_NAME = "luca-mizan-otomasyon"
VERSION_FILE = "VERSION"


def _proj_kok() -> Path:
    return Path(__file__).parent.resolve()


def simdiki_surum() -> str:
    path = _proj_kok() / VERSION_FILE
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return "0.0.0"


def son_surum_oku() -> dict:
    url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/master/VERSION"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"yeni": resp.read().decode().strip(), "yeni_mi": True}
    except Exception as e:
        return {"yeni": simdiki_surum(), "yeni_mi": False, "hata": str(e)}


def guncellememi_kontrol_et() -> dict:
    simdi = simdiki_surum()
    son = son_surum_oku()
    if not son.get("yeni_mi"):
        return {"guncellememevcut": True, "simdi": simdi, "son": son.get("yeni", simdi),
                "mesaj": "Güncelleme kontrolü yapılamadı. İnternet bağlantınızı kontrol edin."}
    if son["yeni"] != simdi:
        return {"guncellememevcut": False, "simdi": simdi, "yeni": son["yeni"],
                "mesaj": f"Yeni sürüm var: v{son['yeni']} (şimdi: v{simdi}). '🔄 Güncelle' butonuna tıklayın."}
    return {"guncellememevcut": True, "simdi": simdi, "son": son["yeni"],
            "mesaj": "En güncel sürüme sahipsiniz."}


def guncelle() -> dict:
    proj = _proj_kok()
    git_klasor = proj / ".git"

    if not git_klasor.exists():
        return {
            "ok": False,
            "guncellendi": False,
            "mesaj": (
                "Güncelleme yapılamadı: Bu proje bir git deposu değil (.git bulunamadı).\n\n"
                "Manuel güncelleme:\n"
                "1. Komut satırına gidin\n"
                "2. Cd \"luca-mizan-otomasyon\"\n"
                "3. git pull origin master"
            ),
        }

    try:
        son = guncellememi_kontrol_et()
        if son.get("guncellememevcut"):
            return {"ok": True, "guncellendi": False, "mesaj": "Zaten en güncel sürüm."}

        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"

        result = subprocess.run(
            ["git", "pull", "origin", "master"],
            capture_output=True, text=True, timeout=120,
            cwd=str(proj),
            env=env,
        )
        cikti = result.stdout.strip()
        hata = result.stderr.strip()

        if result.returncode == 0:
            return {
                "ok": True,
                "guncellendi": True,
                "mesaj": f"✅ Güncelleme başarılı!\n\n{cikti[:500]}",
                "yeni_surum": guncellememi_kontrol_et()["yeni"],
            }
        else:
            return {
                "ok": False,
                "guncellendi": False,
                "mesaj": f"❌ Güncelleme başarısız:\n{hata[:500]}\n\n{cikti[:300]}",
                "yeni_surum": son.get("yeni", ""),
            }
    except subprocess.TimeoutExpired:
        return {"ok": False, "guncellendi": False, "mesaj": "Güncelleme zaman aşımına uğradı (2 dk). Manuel olarak 'git pull origin master' çalıştırın."}
    except FileNotFoundError:
        return {
            "ok": False,
            "guncellendi": False,
            "mesaj": "Git komutu bulunamadı. Git kurulu olduğundan emin olun. Manuel olarak 'git pull origin master' çalıştırın.",
        }
    except Exception as e:
        return {"ok": False, "guncellendi": False, "mesaj": f"Güncelleme hatası: {str(e)}"}
