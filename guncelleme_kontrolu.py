import json
import urllib.request
from datetime import datetime

REPO_OWNER = "ArdaEkiz0"
REPO_NAME = "luca-mizan-otomasyon"
VERSION_FILE = ".version"


def simdiki_surum() -> str:
    import os
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
        return {"guncellememevcut": True, "simdi": simdi, "son": son.get("yeni", simdi)}
    if son["yeni"] != simdi:
        return {
            "guncellememevcut": False,
            "simdi": simdi,
            "yeni": son["yeni"],
            "yuklenmis": False,
        }
    return {"guncellememevcut": True, "simdi": simdi, "son": son["yeni"]}
