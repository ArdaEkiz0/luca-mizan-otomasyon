import json
import os
import subprocess
import urllib.request
import zipfile
import shutil
import io
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

    son = guncellememi_kontrol_et()
    if son.get("guncellememevcut"):
        return {"ok": True, "guncellendi": False, "mesaj": "Zaten en guncel surum."}

    yeni_surum = son.get("yeni", "")

    if git_klasor.exists():
        return _git_pull(proj, son)
    else:
        return _zip_guncelle(proj, yeni_surum)


def _git_pull(proj: Path, son: dict) -> dict:
    try:
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        result = subprocess.run(
            ["git", "pull", "origin", "master"],
            capture_output=True, text=True, timeout=120,
            cwd=str(proj), env=env,
        )
        cikti = result.stdout.strip()
        hata = result.stderr.strip()
        if result.returncode == 0:
            return {"ok": True, "guncellendi": True,
                    "mesaj": f"Guncelleme basarili!\n\n{cikti[:500]}",
                    "yeni_surum": son.get("yeni", "")}
        else:
            return {"ok": False, "guncellendi": False,
                    "mesaj": f"Guncelleme basarisiz:\n{hata[:500]}\n\n{cikti[:300]}",
                    "yeni_surum": son.get("yeni", "")}
    except subprocess.TimeoutExpired:
        return {"ok": False, "guncellendi": False, "mesaj": "Zaman asimi. Manuel olarak 'git pull origin master' calistirin."}
    except FileNotFoundError:
        return {"ok": False, "guncellendi": False, "mesaj": "Git bulunamadi. Manuel olarak guncelleyin."}
    except Exception as e:
        return {"ok": False, "guncellendi": False, "mesaj": f"Guncelleme hatasi: {str(e)}"}


def _zip_guncelle(proj: Path, yeni_surum: str) -> dict:
    try:
        zip_url = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/archive/refs/heads/master.zip"
        req = urllib.request.Request(zip_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            zip_data = resp.read()

        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            dosya_listesi = zf.namelist()
            if not dosya_listesi:
                return {"ok": False, "guncellendi": False, "mesaj": "ZIP dosyasi bos."}
            root_klasor = dosya_listesi[0].split("/")[0]

            korunacak = {".env", "mizan_kontrol.db", "raporlar", "yedekler",
                          "__pycache__", "venv", ".git"}
            mevcut_dosyalar = {}
            for item in proj.iterdir():
                if item.name not in korunacak:
                    mevcut_dosyalar[item.name] = item

            for dosya in dosya_listesi:
                rel = dosya.split("/", 1)[1] if "/" in dosya else ""
                if not rel:
                    continue
                hedef = proj / rel
                if hedef.is_dir():
                    continue
                icerik = zf.read(dosya)
                hedef.parent.mkdir(parents=True, exist_ok=True)
                hedef.write_bytes(icerik)

        return {"ok": True, "guncellendi": True,
                "mesaj": f"Guncelleme basarili! Surum: v{yeni_surum}\nUygulamayi yeniden baslatin.",
                "yeni_surum": yeni_surum}
    except Exception as e:
        return {"ok": False, "guncellendi": False,
                "mesaj": f"Guncelleme hatasi: {str(e)}\n\nManuel olarak GitHub'dan ZIP indirip dosyalari degistirin."}
