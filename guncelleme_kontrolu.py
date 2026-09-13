import json
import os
import subprocess
import urllib.request
from pathlib import Path

REPO_OWNER = "ArdaEkiz0"
REPO_NAME = "luca-mizan-otomasyon"
VERSION_FILE = ".version"


def simdiki_surum() -> str:
    path = os.path.join(os.getcwd(), VERSION_FILE)
    if os.path.exists(path):
        return open(path, "r", encoding="utf-8").read().strip()
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
                "mesaj": f"Yeni sürüm var: {son['yeni']} (şimdi: {simdi}). Güncellemek için 'Güncelle' butonuna tıklayın."}
    return {"guncellememevcut": True, "simdi": simdi, "son": son["yeni"],
            "mesaj": "En güncel sürüme sahipsiniz."}


def guncelle() -> dict:
    try:
        son = guncellememi_kontrol_et()
        if son.get("guncellememevcut"):
            return {"ok": True, "guncellendi": False, "mesaj": "Zaten en güncel sürüm."}

        result = subprocess.run(
            ["git", "pull", "origin", "master"],
            capture_output=True, text=True, timeout=120,
            cwd=os.getcwd(),
        )
        cikti = result.stdout.strip()
        hata = result.stderr.strip()

        if result.returncode == 0:
            import importlib
            try:
                import guncelleme_kontrolu
                importlib.reload(guncelleme_kontrolu)
            except Exception:
                pass
            return {"ok": True, "guncellendi": True, "mesaj": f"Güncelleme başarılı!\n{cikti[:300]}", "yeni_surum": guncellememi_kontrol_et()["yeni"]}
        else:
            return {"ok": False, "guncellendi": False, "mesaj": f"Güncelleme başarısız:\n{hata[:300]}\n\n{cikti[:200]}", "yeni_surum": son.get("yeni", "")}
    except subprocess.TimeoutExpired:
        return {"ok": False, "guncellendi": False, "mesaj": "Güncelleme zaman aşımına uğradı. Manuel olarak 'git pull origin master' çalıştırın."}
    except Exception as e:
        return {"ok": False, "guncellendi": False, "mesaj": f"Güncelleme hatası: {str(e)}"}
