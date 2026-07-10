import tkinter as tk
from tkinter import messagebox, filedialog
import random
import json
import os
import time
import math
import urllib.request
import urllib.parse
import threading
import zipfile
import io
import sys
import subprocess
import platform
import socket

try:
    import pygame
    pygame.mixer.init()
    PYGAME_OK = True
except Exception:
    PYGAME_OK = False

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except Exception:
    PIL_OK = False

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
STATS_FILE = os.path.join(BASE_DIR, "VilmaLearn_statistik.json")
SHOP_FILE  = os.path.join(BASE_DIR, "VilmaLearn_shop.json")
BIG_STORY_FILE = os.path.join(BASE_DIR, "VilmaLearn_big_story.json")
STORY_SPRACH_DATEIEN = {
    "de": os.path.join(BASE_DIR, "Story_DE.json"),
    "en": os.path.join(BASE_DIR, "Story_EN.json"),
    "fi": os.path.join(BASE_DIR, "Story_FI.json"),
}
STORY_FORTSCHRITT_FILE = os.path.join(BASE_DIR, "Story_Fortschritt.json")
DRAGONBALL_PACK_BILD = os.path.join(BASE_DIR, "Dragonball Pack.jpg")
DRAGONBALL_STERN_BILDER = [os.path.join(BASE_DIR, f"Dragonball Stern {i}.png") for i in range(1, 8)]
JOKER_BILD = os.path.join(BASE_DIR, "Joker.jpg")
XP_TRANK_BILD = os.path.join(BASE_DIR, "Xp Trank.jpg")
DOUBLE_COIN_BILD = os.path.join(BASE_DIR, "Double Coin.jpg")

# ============================================================
#  Auto-Update (VilmaUpdater Repo auf GitHub)
# ============================================================
# Entwickler-Schalter: auf False setzen, waehrend lokal an VilmaLearn.py
# entwickelt/getestet wird, damit Aenderungen nicht durch ein Update von
# GitHub wieder ueberschrieben werden. Fuer den echten Release wieder auf
# True stellen (oder die Datei NO_UPDATE im selben Ordner loeschen).
AUTO_UPDATE_AKTIV = not os.path.exists(os.path.join(BASE_DIR, "NO_UPDATE"))

VERSION_DATEI = os.path.join(BASE_DIR, "version_lokal.json")
UPDATE_VERSION_URL = "https://raw.githubusercontent.com/ElektroMoonAutoTranslator/VilmaUpdater/main/version.json"

def lokale_version_laden():
    """Liest die lokal gespeicherte Version. Falls noch keine Datei existiert, wird "0" angenommen
    (garantiert ein Update-Angebot beim allerersten Start)."""
    try:
        with open(VERSION_DATEI, "r", encoding="utf-8") as f:
            return json.load(f).get("version", "0")
    except Exception:
        return "0"

def lokale_version_speichern(neue_version):
    try:
        with open(VERSION_DATEI, "w", encoding="utf-8") as f:
            json.dump({"version": neue_version}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

VERSION = lokale_version_laden()

def update_pruefen():
    """Ruft version.json von GitHub ab. Gibt (neue_version, download_url) zurück
    wenn die Remote-Version von der lokalen abweicht (egal in welche Richtung), sonst None."""
    try:
        req = urllib.request.Request(UPDATE_VERSION_URL, headers={
            "User-Agent": "Mozilla/5.0"
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            daten = json.loads(resp.read().decode("utf-8"))
        remote_version = daten.get("version", "")
        download_url   = daten.get("download_url", "")
        if not remote_version or not download_url:
            return None
        if remote_version.strip() != VERSION.strip():
            return (remote_version, download_url)
        return None
    except Exception:
        return None

def update_herunterladen_und_installieren(download_url, neue_version):
    """Lädt die ZIP von download_url herunter und entpackt sie direkt in BASE_DIR,
    wobei bestehende Dateien überschrieben werden. Speichert danach die neue Version lokal.
    Gibt (True, "") oder (False, fehlertext) zurück."""
    try:
        req = urllib.request.Request(download_url, headers={
            "User-Agent": "Mozilla/5.0"
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            daten = resp.read()
    except Exception as e:
        return (False, f"Download-Fehler: {e}")
    try:
        with zipfile.ZipFile(io.BytesIO(daten)) as zf:
            zf.extractall(BASE_DIR)
        lokale_version_speichern(neue_version)
        return (True, "")
    except Exception as e:
        return (False, f"Entpack-Fehler: {e}")

def update_neustart():
    """Startet das Skript neu (gleicher Python-Interpreter, gleiche Datei) und beendet den aktuellen Prozess."""
    python = sys.executable
    skript = os.path.abspath(__file__)
    subprocess.Popen([python, skript])
    os._exit(0)

# ============================================================
#  Google-Sheets-Tracking (VilmaLearn Statistik)
# ============================================================
TRACKING_URL = "https://script.google.com/macros/s/AKfycbxolKenEHJmShIrj5VoLQY0IRejjbpuz-ohR10wOXUAHlo8GIn0tT3sdjuHTLq6KVnD/exec"
TRACKING_NUTZER = "Vilma"

def _pc_name():
    try:
        return socket.gethostname()
    except Exception:
        return ""

def _windows_version():
    try:
        return platform.version()
    except Exception:
        return ""

def tracking_senden(typ, **kwargs):
    """Sendet ein Tracking-Event im Hintergrund (eigener Thread, kein Blockieren der UI)
    an das Google-Apps-Script. Fehler werden bewusst verschluckt, damit Tracking niemals
    das Programm zum Absturz bringt oder es verlangsamt."""
    def worker():
        try:
            payload = {
                "typ": typ,
                "nutzer": TRACKING_NUTZER,
                "pc_name": _pc_name(),
                "windows": _windows_version(),
            }
            payload.update(kwargs)
            daten = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(TRACKING_URL, data=daten, headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            })
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass
    threading.Thread(target=worker, daemon=True).start()

os.makedirs(AUDIO_DIR, exist_ok=True)

# ============================================================
#  Google-Translate TTS (automatische Audio-Erzeugung)
# ============================================================

GTTS_LANGCODE = {"de": "de", "en": "en", "fi": "fi"}

TTS_FEHLER_LOG = os.path.join(BASE_DIR, "tts_fehler_log.txt")

def tts_fehler_loggen(kontext, text, fehler):
    """Schreibt einen TTS-Download-Fehlschlag mit Zeitstempel, HTTP-Code
    (falls vorhanden) und Fehlertyp in tts_fehler_log.txt. Wird bewusst nie
    selbst eine Exception werfen, damit Logging niemals den Download-Ablauf
    stoert."""
    try:
        http_code = getattr(fehler, "code", None)
        fehler_typ = type(fehler).__name__
        zeile = (f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {kontext} | "
                 f"text='{text}' | typ={fehler_typ} | http={http_code} | {fehler}\n")
        with open(TTS_FEHLER_LOG, "a", encoding="utf-8") as f:
            f.write(zeile)
    except Exception:
        pass

def gtts_dateiname(wort, sprache):
    sicher = "".join(c for c in wort if c.isalnum() or c in (" ", "_", "-")).strip()
    sicher = sicher.replace(" ", "_")
    return f"{sprache}_{sicher}.mp3"

def gtts_herunterladen(text, sprache, ziel_dateiname):
    """Lädt Audio für `text` in `sprache` von Google Translate TTS herunter
    und speichert es unter AUDIO_DIR/ziel_dateiname. Gibt True/False zurück."""
    if not text.strip():
        return False
    lc = GTTS_LANGCODE.get(sprache, sprache)
    ziel_pfad = os.path.join(AUDIO_DIR, ziel_dateiname)
    params = urllib.parse.urlencode({
        "ie": "UTF-8",
        "q": text,
        "tl": lc,
        "client": "tw-ob",
    })
    url = f"https://translate.google.com/translate_tts?{params}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36"
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            daten = resp.read()
        if not daten or len(daten) < 100:
            tts_fehler_loggen("gtts_herunterladen", text, Exception("Antwort zu kurz/leer"))
            return False
        with open(ziel_pfad, "wb") as f:
            f.write(daten)
        return True
    except Exception as e:
        tts_fehler_loggen("gtts_herunterladen", text, e)
        return False

# ============================================================
#  Datei-Hilfsfunktionen
# ============================================================

def speicher_pfad(ls):
    return os.path.join(BASE_DIR, f"VilmaLearn_{ls}.json")

def saetze_pfad(ls):
    return os.path.join(BASE_DIR, f"saetze_{ls}.json")

def saetze_laden(ls):
    p = saetze_pfad(ls)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def saetze_speichern(ls, liste):
    with open(saetze_pfad(ls), "w", encoding="utf-8") as f:
        json.dump(liste, f, ensure_ascii=False, indent=2)

def vokabeln_laden(ls):
    p = speicher_pfad(ls)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def vokabeln_speichern(ls, liste):
    with open(speicher_pfad(ls), "w", encoding="utf-8") as f:
        json.dump(liste, f, ensure_ascii=False, indent=2)

def vokabeln_fuer_test(ls):
    """Vollständige Vokabelliste fuer Test/Blitz/MC. Die Herz-Filterung
    ('nur markierte Woerter ueben') erfolgt optional ueber die Auswahl
    auf dem Level-Screen (zeige_lvl_auswahl), nicht mehr automatisch hier."""
    return vokabeln_laden(ls)

ARTIKEL_WOERTER = {"der", "die", "das", "den", "dem", "des"}

def artikel_extrahieren(lern_text):
    """Zerlegt ein 'lern'-Feld wie 'Die Liebe' oder 'Das Den Zombie' in
    (artikel_liste, wort_ohne_artikel).
    - 'Die Liebe'          -> (['Die'], 'Liebe')
    - 'Das Den Zombie'     -> (['Das', 'Den'], 'Zombie')
    - 'Danke'              -> ([], 'Danke')   (kein Artikel -> nicht nutzbar)
    """
    text = (lern_text or "").strip()
    if not text:
        return [], ""
    teile = text.split(" ")
    artikel = []
    i = 0
    while i < len(teile) and i < 2 and teile[i].lower() in ARTIKEL_WOERTER:
        artikel.append(teile[i])
        i += 1
    rest = " ".join(teile[i:]).strip()
    if not artikel or not rest:
        return [], text
    return artikel, rest

def vokabeln_mit_artikel(ls):
    """Filtert vokabeln_fuer_test auf Eintraege mit erkennbarem Artikel im
    'lern'-Feld. Jeder Eintrag bekommt zusaetzlich '_artikel' (Liste, 1 oder
    2 Eintraege) und '_artikel_wort' (Wort ohne Artikel)."""
    ergebnis = []
    for v in vokabeln_fuer_test(ls):
        artikel, rest = artikel_extrahieren(v.get("lern", ""))
        if artikel:
            neu = dict(v)
            neu["_artikel"] = artikel
            neu["_artikel_wort"] = rest
            ergebnis.append(neu)
    return ergebnis

def stats_laden():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            try:
                d = json.load(f)
                if "freigeschaltet" not in d:
                    d["freigeschaltet"] = []
                if "aktiviert" not in d:
                    d["aktiviert"] = []
                return d
            except Exception:
                pass
    return {
        "richtig": 0,
        "falsch": 0,
        "lernzeit_sek": 0,
        "level_xp": 0,
        "wort_stats": {},
        "freigeschaltet": [],
        "aktiviert": [],
    }

def stats_speichern(s):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

# ============================================================
#  Shop / Coins / Inventar / Dragonballs
# ============================================================

def big_story_laden():
    if os.path.exists(BIG_STORY_FILE):
        with open(BIG_STORY_FILE, "r", encoding="utf-8") as f:
            try:
                d = json.load(f)
                d.setdefault("teile", [])
                return d
            except Exception:
                pass
    return {"teile": []}

def big_story_speichern(d):
    with open(BIG_STORY_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

# ============================================================
#  Big Story - Seiteninhalte (Text + Luecken-Multiple-Choice)
# ============================================================
# Jede Seite: "text" mit {0}, {1}, ... Platzhaltern, "luecken": Liste von
# (richtiges_wort, [3 falsche Woerter]). Inhalte liegen pro Sprache in
# eigenen JSON-Dateien (Story_DE.json / Story_EN.json / Story_FI.json),
# Schluessel im JSON sind die Teil-Indizes als String ("0", "1", ...).
_BIG_STORY_FI_STANDARD = {
    "0": [
        {
            "text": (
                "Vilma istui {0}, jonka seinät oli maalattu pehmeän {1} sävyyn. "
                "Hyllyllä sängyn edessä seisoi kokonainen kokoelma {2}, jotka vahtivat häntä "
                "kuin hiljaiset vanhat ystävät. Hän haukotteli ja vilkaisi avattua saksan "
                "sanasto-{3} sylissään. Hänen {4} alkoivat painua kiinni. Vielä yksi sivu, "
                "hän ajatteli — mutta hän nukahti ennen kuin ehti kääntää sivun."
            ),
            "luecken": [
                ["Das Zimmer", ["Der Laden", "Das Buch", "Der Baum"]],
                ["Violett", ["Rot", "Grün", "Blau"]],
                ["Die Puppe", ["Der Hund", "Die Katze", "Der Fisch"]],
                ["Das Buch", ["Die Kette", "Der Stift", "Die Kamera"]],
                ["Die Augen", ["Die Hand", "Die Nase", "Die Lippen"]],
            ],
        },
    ],
}

def _story_datei_laden(sprache):
    """Laedt die Story-JSON-Datei fuer die gegebene Sprache. Legt sie beim
    ersten Aufruf an, falls sie noch nicht existiert (fuer 'fi' mit dem
    bisherigen Standardinhalt vorbefuellt, sonst leer)."""
    pfad = STORY_SPRACH_DATEIEN.get(sprache)
    if not pfad:
        return {}
    if not os.path.exists(pfad):
        inhalt = dict(_BIG_STORY_FI_STANDARD) if sprache == "fi" else {}
        try:
            with open(pfad, "w", encoding="utf-8") as f:
                json.dump(inhalt, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return inhalt
    try:
        with open(pfad, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def big_story_seiten_holen(sprache, teil_index):
    """Gibt die Liste der Seiten (dicts mit text/luecken) fuer die gegebene
    Story-Sprache und den gegebenen Teil-Index zurueck. Leere Liste, falls
    noch nichts hinterlegt ist."""
    daten = _story_datei_laden(sprache)
    return daten.get(str(teil_index), [])

def story_fortschritt_laden():
    if os.path.exists(STORY_FORTSCHRITT_FILE):
        try:
            with open(STORY_FORTSCHRITT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def story_fortschritt_speichern(daten):
    try:
        with open(STORY_FORTSCHRITT_FILE, "w", encoding="utf-8") as f:
            json.dump(daten, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def story_fortschritt_setzen(sprache, teil_index, seite_index):
    """Speichert die zuletzt bearbeitete Seite fuer die gegebene Sprache,
    getrennt pro Sprache (de/en/fi jeweils eigener Stand)."""
    daten = story_fortschritt_laden()
    daten[sprache] = {"teil": teil_index, "seite": seite_index}
    story_fortschritt_speichern(daten)

def story_fortschritt_holen(sprache, teil_index):
    """Gibt den gespeicherten Seiten-Index fuer diese Sprache zurueck, falls
    er zum gleichen Teil gehoert, sonst None."""
    daten = story_fortschritt_laden()
    eintrag = daten.get(sprache)
    if not eintrag or eintrag.get("teil") != teil_index:
        return None
    return eintrag.get("seite")

def shop_laden():
    if os.path.exists(SHOP_FILE):
        with open(SHOP_FILE, "r", encoding="utf-8") as f:
            try:
                d = json.load(f)
                d.setdefault("coins", 0)
                d.setdefault("inventar", {"joker": 0, "traenke": 0, "double_coin": 0})
                d["inventar"].setdefault("double_coin", 0)
                d.setdefault("dragonballs", [False] * 7)
                d.setdefault("dragonballs_eingeloest", False)
                d.setdefault("packs_gekauft", 0)
                d.setdefault("double_coin_bis", 0)
                d.setdefault("trank_bis", 0)
                d.setdefault("trank_stufe", 0)
                d.setdefault("pack_pech_streak", 0)
                return d
            except Exception:
                pass
    return {
        "coins": 0,
        "inventar": {"joker": 0, "traenke": 0, "double_coin": 0},
        "dragonballs": [False] * 7,
        "dragonballs_eingeloest": False,
        "packs_gekauft": 0,
        "double_coin_bis": 0,
        "trank_bis": 0,
        "trank_stufe": 0,
        "pack_pech_streak": 0,
    }

def shop_speichern(s):
    with open(SHOP_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

DOUBLE_COIN_DAUER_SEK = 7 * 60
TRANK_DAUER_SEK = 7 * 60
TRANK_VERLAENGERUNG_SEK = 30

def _timer_aktiv(bis_timestamp):
    """Prueft ob ein per Unix-Timestamp gespeicherter Timer noch aktiv ist."""
    return time.time() < bis_timestamp

def shop_double_coin_aktivieren():
    """Aktiviert den Double-Coin-Timer, falls mind. 1 Double Coin im
    Inventar ist. Jeder Klick addiert 7 Min auf die aktuelle Restzeit
    (laeuft der Timer schon, kommen die 7 Min oben drauf; laeuft er nicht,
    startet er bei 7 Min ab jetzt). JEDER Klick verbraucht sofort 1 Double
    Coin aus dem Inventar, sofern noch mind. 1 vorhanden ist. Gibt
    (erfolg, verlaengert, s) zurueck."""
    s = shop_laden()
    if s.get("inventar", {}).get("double_coin", 0) <= 0:
        return False, False, s
    s["inventar"]["double_coin"] = max(0, s["inventar"].get("double_coin", 0) - 1)
    war_aktiv = _timer_aktiv(s.get("double_coin_bis", 0))
    basis = s["double_coin_bis"] if war_aktiv else time.time()
    s["double_coin_bis"] = basis + DOUBLE_COIN_DAUER_SEK
    shop_speichern(s)
    return True, war_aktiv, s

def shop_trank_aktivieren():
    """Aktiviert den XP-Trank-Timer (7 Min), falls mind. 1 Trank im Inventar
    ist. Ist der Timer schon aktiv, wird er stattdessen um 30 Sek verlaengert.
    JEDER Klick verbraucht sofort 1 Trank aus dem Inventar (egal ob Neustart
    oder Verlaengerung) UND erhoeht die Trank-Stufe um 1, wodurch der
    XP-Bonus pro richtiger Antwort um weitere 0,25 steigt (stapelbar: 2 Klicks
    = +0,50 XP, 3 Klicks = +0,75 XP usw). Laeuft der Timer ab, wird die Stufe
    komplett auf 0 zurueckgesetzt (shop_timer_pruefen_und_verbrauchen). Gibt
    (erfolg, verlaengert, s) zurueck."""
    s = shop_laden()
    if s.get("inventar", {}).get("traenke", 0) <= 0:
        return False, False, s
    s["inventar"]["traenke"] = max(0, s["inventar"].get("traenke", 0) - 1)
    s["trank_stufe"] = s.get("trank_stufe", 0) + 1
    if _timer_aktiv(s.get("trank_bis", 0)):
        s["trank_bis"] = s["trank_bis"] + TRANK_VERLAENGERUNG_SEK
        shop_speichern(s)
        return True, True, s
    s["trank_bis"] = time.time() + TRANK_DAUER_SEK
    shop_speichern(s)
    return True, False, s

def shop_timer_pruefen_und_verbrauchen():
    """Prueft beide Timer (Double Coin, Trank) und setzt abgelaufene
    Zeitstempel auf 0 zurueck. Der Inventar-Verbrauch passiert bereits bei
    Aktivierung (shop_double_coin_aktivieren/shop_trank_aktivieren), hier wird
    nur noch der Timer selbst zurueckgesetzt. Gibt das aktualisierte
    shop-dict zurueck. Sollte regelmaessig (z.B. per Sekunden-Timer in der UI)
    aufgerufen werden."""
    s = shop_laden()
    geaendert = False
    dc_bis = s.get("double_coin_bis", 0)
    if dc_bis > 0 and time.time() >= dc_bis:
        s["double_coin_bis"] = 0
        geaendert = True
    tr_bis = s.get("trank_bis", 0)
    if tr_bis > 0 and time.time() >= tr_bis:
        s["trank_bis"] = 0
        s["trank_stufe"] = 0
        geaendert = True
    if geaendert:
        shop_speichern(s)
    return s

def shop_double_coin_ist_aktiv():
    """True, wenn der Double-Coin-Bonus aktuell aktiv ist (Timer laeuft)."""
    s = shop_laden()
    return _timer_aktiv(s.get("double_coin_bis", 0))

def shop_trank_ist_aktiv():
    """True, wenn der XP-Trank-Bonus aktuell aktiv ist (Timer laeuft)."""
    s = shop_laden()
    return _timer_aktiv(s.get("trank_bis", 0))

def shop_trank_xp_bonus():
    """Gibt den aktuellen XP-Bonus pro richtiger Antwort zurueck: 0,25 je
    aktiver Trank-Stufe (stapelbar durch mehrfaches Klicken), 0 wenn kein
    Trank-Timer laeuft."""
    s = shop_laden()
    if not _timer_aktiv(s.get("trank_bis", 0)):
        return 0
    return 0.25 * s.get("trank_stufe", 0)

def shop_coins_effektiv(anzahl=1):
    """Gibt zurueck, wie viele Coins 'anzahl' tatsaechlich ergeben wuerde
    (verdoppelt, falls der Double-Coin-Bonus aktuell aktiv ist), ohne
    etwas zu veraendern. Fuer Anzeigezwecke."""
    s = shop_laden()
    if _timer_aktiv(s.get("double_coin_bis", 0)):
        return anzahl * 2
    return anzahl

def shop_coins_hinzufuegen(anzahl=1):
    """Fuegt Coins hinzu (verdoppelt, falls der Double-Coin-Bonus aktiv ist)
    und prueft ob dadurch Dragonballs komplettiert wurden.
    Gibt das aktualisierte shop-dict zurueck."""
    s = shop_laden()
    if _timer_aktiv(s.get("double_coin_bis", 0)):
        anzahl = anzahl * 2
    s["coins"] = s.get("coins", 0) + anzahl
    shop_speichern(s)
    return s

def shop_level_belohnung_geben():
    """Wird einmal pro neu freigeschaltetem Level-Feature aufgerufen.
    Vergibt 500 Coins, 2 Joker, 2 XP-Traenke, 2 Double-Coin-Boosts
    und 5 Packs."""
    s = shop_laden()
    s["coins"] = s.get("coins", 0) + 500
    s["inventar"]["joker"] = s["inventar"].get("joker", 0) + 2
    s["inventar"]["traenke"] = s["inventar"].get("traenke", 0) + 2
    s["inventar"]["double_coin"] = s["inventar"].get("double_coin", 0) + 2
    s["packs_gekauft"] = s.get("packs_gekauft", 0) + 5
    shop_speichern(s)
    return s

def shop_dragonball_freischalten(index):
    """index: 0-6 fuer Dragonball 1-7. Bei Vervollstaendigung aller 7:
    +10 Joker, +10 Traenke, +10 Double Coins, danach werden die Baelle zurueckgesetzt.
    Die 5000 Coins gibt es nur beim allerersten Mal ueberhaupt."""
    s = shop_laden()
    if 0 <= index < 7:
        s["dragonballs"][index] = True
    if all(s["dragonballs"]):
        if not s.get("dragonballs_eingeloest", False):
            s["coins"] = s.get("coins", 0) + 5000
            s["dragonballs_eingeloest"] = True
        s["inventar"]["joker"] = s["inventar"].get("joker", 0) + 10
        s["inventar"]["traenke"] = s["inventar"].get("traenke", 0) + 10
        s["inventar"]["double_coin"] = s["inventar"].get("double_coin", 0) + 10
        s["dragonballs"] = [False] * 7
    shop_speichern(s)
    return s

# Dragonball-Pack: 100 Coins. Man bekommt IMMER mindestens 1 Ball pro
# Pack-Oeffnung. Zusaetzlich gibt es (exklusiv, von selten nach haeufig
# geprueft) eine Chance auf mehr Baelle auf einmal:
#   1%  Chance -> alle 7 Baelle
#   15% Chance -> 3 Baelle insgesamt
#   35% Chance -> 2 Baelle insgesamt
#   sonst (49%) -> 1 Ball
# Jeder einzelne Ball wird unabhaengig (gewichtet) gezogen, Duplikate sind
# jetzt erlaubt.
# 5 der 7 Baelle sind "haeufig", 2 sind "selten" (deutlich seltener).
DRAGONBALL_PACK_PREIS = 100
DRAGONBALL_SELTEN_INDIZES = (5, 6)  # Dragonball 6 und 7 (0-basiert) sind die seltenen
DRAGONBALL_GEWICHTE = [16, 16, 16, 16, 16, 5, 5]  # 5x haeufig, 2x selten

def _dragonball_pack_anzahl_wuerfeln():
    """Bestimmt, wie viele Baelle bei einer Pack-Oeffnung gezogen werden
    (exklusive Pruefung von der seltensten Chance nach oben)."""
    r = random.random()
    if r < 0.01:
        return 7
    if r < 0.01 + 0.15:
        return 3
    if r < 0.01 + 0.15 + 0.35:
        return 2
    return 1

def _dragonball_ziehen_liste(anzahl):
    """Zieht 'anzahl' Baelle unabhaengig voneinander (gewichtet), Duplikate
    erlaubt. Gibt eine Liste von Indizes (0-6) zurueck."""
    return [random.choices(range(7), weights=DRAGONBALL_GEWICHTE, k=1)[0] for _ in range(anzahl)]

# Pity-System (wie in Gacha-Spielen): Bekommt man mehrmals hintereinander
# beim Pack-Oeffnen KEINEN einzigen neuen Ball (nur Duplikate), steigt die
# Chance auf einen garantierten neuen Ball beim naechsten Mal stufenweise an.
# Streak = Anzahl Pack-Oeffnungen in Folge ohne neuen Ball.
#   Streak 0-1 -> normale Ziehung (kein Bonus)
#   Streak 2   -> Soft Pity: +20% Chance auf garantiert neuen Ball
#   Streak 3   -> Soft Pity: +40% Chance auf garantiert neuen Ball
#   Streak 4+  -> Hard Pity: garantiert neuer Ball (100%)
# Der Streak wird zurueckgesetzt, sobald ein neuer Ball dabei ist.
DRAGONBALL_PITY_SOFT_STUFEN = {2: 0.20, 3: 0.40}
DRAGONBALL_PITY_HARD_STREAK = 4

def _dragonball_pack_ziehen_mit_pity(s):
    """Fuehrt eine komplette Pack-Ziehung durch (Anzahl wuerfeln, Baelle
    ziehen, Duplikate in Coins umwandeln) und wendet dabei das Pity-System
    an: nach mehreren Fehlversuchen in Folge wird ein neuer Ball erzwungen,
    sofern noch mindestens einer fehlt. Veraendert 's' direkt (dragonballs,
    coins, pack_pech_streak) und gibt die gezogene Liste zurueck (Eintraege
    wie {"index": i, "neu": bool})."""
    anzahl = _dragonball_pack_anzahl_wuerfeln()
    indizes = _dragonball_ziehen_liste(anzahl)

    fehlende = [i for i in range(7) if not s["dragonballs"][i]]
    streak = s.get("pack_pech_streak", 0)

    if fehlende:
        erzwingen = streak >= DRAGONBALL_PITY_HARD_STREAK
        if not erzwingen:
            bonus_chance = DRAGONBALL_PITY_SOFT_STUFEN.get(streak, 0.0)
            if bonus_chance > 0 and random.random() < bonus_chance:
                erzwingen = True
        if erzwingen:
            # Ersetzt die erste Ziehung durch einen garantiert neuen (noch
            # fehlenden) Ball, der Rest bleibt normal zufaellig.
            indizes[0] = random.choice(fehlende)

    gezogen = []
    hat_neuen = False
    for idx in indizes:
        war_schon_da = s["dragonballs"][idx]
        if not war_schon_da:
            s["dragonballs"][idx] = True
            hat_neuen = True
        else:
            s["coins"] = s.get("coins", 0) + 5
        gezogen.append({"index": idx, "neu": not war_schon_da})

    s["pack_pech_streak"] = 0 if hat_neuen else streak + 1
    return gezogen

def shop_pack_kaufen_nur():
    """Kauft 1 Pack (100 Coins) OHNE es zu oeffnen: zieht Coins ab und erhoeht
    packs_gekauft. Es werden dabei KEINE Dragonballs aktiviert - das passiert
    ausschliesslich per Klick auf die Pack-Box im Inventar. Gibt (erfolg, s)
    zurueck."""
    s = shop_laden()
    if s.get("coins", 0) < DRAGONBALL_PACK_PREIS:
        return False, s
    s["coins"] -= DRAGONBALL_PACK_PREIS
    s["packs_gekauft"] = s.get("packs_gekauft", 0) + 1
    shop_speichern(s)
    return True, s

def shop_dragonball_pack_oeffnen():
    """Kauft ein Pack (100 Coins) und zieht Dragonballs (gewichtet, 5
    haeufige + 2 seltene, mit Pity-System gegen Duplikat-Pech-Serien). Man
    bekommt immer mindestens 1 Ball; mit 35%/15%/1% Chance (exklusiv) werden
    es 2/3/7 Baelle auf einmal. Duplikate gehen NICHT ins Inventar und geben
    stattdessen 5 Coins. Gibt (erfolg, gezogene_liste, s) zurueck, wobei
    gezogene_liste Eintraege wie {"index": i, "neu": bool} enthaelt."""
    s = shop_laden()
    if s.get("coins", 0) < DRAGONBALL_PACK_PREIS:
        return False, [], s
    s["coins"] -= DRAGONBALL_PACK_PREIS
    s["packs_gekauft"] = s.get("packs_gekauft", 0) + 1

    gezogen = _dragonball_pack_ziehen_mit_pity(s)

    if all(s["dragonballs"]):
        if not s.get("dragonballs_eingeloest", False):
            s["coins"] = s.get("coins", 0) + 5000
            s["dragonballs_eingeloest"] = True
        s["inventar"]["joker"] = s["inventar"].get("joker", 0) + 10
        s["inventar"]["traenke"] = s["inventar"].get("traenke", 0) + 10
        s["inventar"]["double_coin"] = s["inventar"].get("double_coin", 0) + 10
        s["dragonballs"] = [False] * 7

    shop_speichern(s)
    return True, gezogen, s

SHOP_JOKER_PREIS = 50
SHOP_TRANK_PREIS = 25
SHOP_DOUBLE_COIN_PREIS = 75

def shop_joker_kaufen():
    """Kauft 1 Joker fuer SHOP_JOKER_PREIS Coins. Gibt (erfolg, s) zurueck."""
    s = shop_laden()
    if s.get("coins", 0) < SHOP_JOKER_PREIS:
        return False, s
    s["coins"] -= SHOP_JOKER_PREIS
    s.setdefault("inventar", {"joker": 0, "traenke": 0})
    s["inventar"]["joker"] = s["inventar"].get("joker", 0) + 1
    shop_speichern(s)
    return True, s

def shop_trank_kaufen():
    """Kauft 1 XP-Trank fuer SHOP_TRANK_PREIS Coins. Gibt (erfolg, s) zurueck."""
    s = shop_laden()
    if s.get("coins", 0) < SHOP_TRANK_PREIS:
        return False, s
    s["coins"] -= SHOP_TRANK_PREIS
    s.setdefault("inventar", {"joker": 0, "traenke": 0, "double_coin": 0})
    s["inventar"]["traenke"] = s["inventar"].get("traenke", 0) + 1
    shop_speichern(s)
    return True, s

def shop_double_coin_kaufen():
    """Kauft 1 Double Coin fuer SHOP_DOUBLE_COIN_PREIS Coins. Gibt (erfolg, s) zurueck."""
    s = shop_laden()
    if s.get("coins", 0) < SHOP_DOUBLE_COIN_PREIS:
        return False, s
    s["coins"] -= SHOP_DOUBLE_COIN_PREIS
    s.setdefault("inventar", {"joker": 0, "traenke": 0, "double_coin": 0})
    s["inventar"]["double_coin"] = s["inventar"].get("double_coin", 0) + 1
    shop_speichern(s)
    return True, s

def audio_pfad(dateiname):
    if not dateiname:
        return ""
    if os.path.isabs(dateiname):
        return dateiname
    return os.path.join(AUDIO_DIR, dateiname)

# ============================================================
#  Silbentrennung (Vokalgruppen-Heuristik) fuer ABC-Woerter
# ============================================================

GETEILT_ORDNER = os.path.join(AUDIO_DIR, "Silben")

ARTIKEL_SAMMEL_ORDNER = "DER DIE DAS DEN"
ARTIKEL_WOERTER = {"der", "die", "das", "den"}

# Ordner beim Modul-Import garantiert direkt unter AUDIO_DIR anlegen,
# unabhaengig davon ob/wann je eine Artikel-Audiodatei heruntergeladen wird.
os.makedirs(os.path.join(AUDIO_DIR, ARTIKEL_SAMMEL_ORDNER), exist_ok=True)

def _silben_wort_ordner(wort):
    if wort.strip().lower() in ARTIKEL_WOERTER:
        pfad = os.path.join(AUDIO_DIR, ARTIKEL_SAMMEL_ORDNER)
        os.makedirs(pfad, exist_ok=True)
        return pfad
    sicher = "".join(c for c in wort if c.isalnum() or c in " _-").strip()
    if not sicher:
        sicher = "wort"
    pfad = os.path.join(GETEILT_ORDNER, sicher)
    os.makedirs(pfad, exist_ok=True)
    return pfad

VOKALE_KLEIN = "aeiouäöüy"

def silben_automatisch_trennen(wort):
    """Einfache Faustregel-Silbentrennung fuer deutsche Woerter, basierend auf
    Vokalgruppen: jede neue Gruppe zusammenhaengender Vokale markiert im
    Prinzip eine neue Silbe. Bei Konsonantenhaeufungen zwischen zwei Vokal-
    gruppen wandert (grob) der letzte Konsonant noch zur vorherigen Silbe,
    der Rest zur naechsten - das entspricht dem ungefaehren Sprachgefuehl
    (z.B. 'Wellensittich' -> ['Well', 'en', 'sitt', 'ich']).
    Gibt eine Liste von Silben-Strings zurueck (mind. 1 Element)."""
    stueck = wort.strip()
    if not stueck:
        return [wort]
    if stueck.lower() in ARTIKEL_WOERTER:
        return [stueck]
    if " " in stueck:
        # mehrere Woerter: jedes einzeln trennen, dann wieder zusammenfuegen.
        # Mehrfache/fuehrende/nachgestellte Leerzeichen (z.B. " Das Denken")
        # wuerden sonst leere Teilwoerter erzeugen, aus denen eine leere
        # Silbe entsteht - die dann beim TTS-Download immer fehlschlaegt.
        teile = []
        for w in stueck.split(" "):
            if w.strip():
                teile.extend(silben_automatisch_trennen(w))
        return teile if teile else [stueck]

    n = len(stueck)
    ist_vokal = [c.lower() in VOKALE_KLEIN for c in stueck]

    # Positionen finden, an denen eine Vokalgruppe beginnt
    vokalgruppen_start = []
    i = 0
    while i < n:
        if ist_vokal[i]:
            vokalgruppen_start.append(i)
            while i < n and ist_vokal[i]:
                i += 1
        else:
            i += 1

    if len(vokalgruppen_start) <= 1:
        return [stueck]

    trennstellen = []
    for idx in range(1, len(vokalgruppen_start)):
        vg_start = vokalgruppen_start[idx]
        vorheriges_ende = vokalgruppen_start[idx - 1]
        while vorheriges_ende < n and ist_vokal[vorheriges_ende]:
            vorheriges_ende += 1
        konsonanten_laenge = vg_start - vorheriges_ende
        if konsonanten_laenge <= 0:
            trennstelle = vg_start
        elif konsonanten_laenge == 1:
            trennstelle = vorheriges_ende
        else:
            trennstelle = vg_start - 1
        trennstellen.append(trennstelle)

    silben = []
    letzte = 0
    for t in trennstellen:
        if t > letzte:
            silben.append(stueck[letzte:t])
            letzte = t
    silben.append(stueck[letzte:])
    silben = [s for s in silben if s]

    # Erzwungene Mindest-Trennung: auch einsilbige Woerter (z.B. "Film") sollen
    # in mindestens 2 Kaestchen zerlegt werden, indem nach dem ersten Vokal
    # (plus direkt folgendem Konsonant) geschnitten wird.
    if len(silben) <= 1 and len(stueck) > 2:
        schnitt = 1
        while schnitt < n and not ist_vokal[schnitt - 1]:
            schnitt += 1
        if schnitt < n:
            schnitt += 1
        if 0 < schnitt < n:
            silben = [stueck[:schnitt], stueck[schnitt:]]

    return silben

def silben_liste_holen(vok):
    """Gibt die (ggf. manuell korrigierte) Silbenliste einer Vokabel zurueck.
    Falls das Feld 'silben' gespeichert ist, wird dieses genutzt (Format:
    durch '-' getrennter String), sonst automatisch berechnet."""
    gespeichert = vok.get("silben", "")
    if gespeichert.strip():
        return [s for s in gespeichert.split("-") if s]
    return silben_automatisch_trennen(vok.get("lern", ""))

def gtts_dateiname_silbe(silbe, sprache):
    sicher = "".join(c for c in silbe if c.isalnum())
    return f"{sicher}_{sprache}.mp3"

def audio_silbe_pfad_sicherstellen(silbe, sprache, wort=""):
    """Gibt den Pfad zur Audio-Datei fuer eine einzelne Silbe zurueck
    (gespeichert unter audio/Silben/<Wortname>/, bzw. im gemeinsamen
    Artikel-Ordner DER DIE DAS DEN, falls die Silbe selbst ein Artikel ist).
    Erzeugt die Datei einmalig per Google TTS, falls sie noch nicht existiert."""
    if not silbe.strip():
        return ""
    ordner = _silben_wort_ordner(silbe if silbe.strip().lower() in ARTIKEL_WOERTER else (wort if wort else silbe))
    dateiname = gtts_dateiname_silbe(silbe, sprache)
    pfad = os.path.join(ordner, dateiname)
    if os.path.exists(pfad):
        return pfad
    lc = GTTS_LANGCODE.get(sprache, sprache)
    params = urllib.parse.urlencode({"ie": "UTF-8", "q": silbe, "tl": lc, "client": "tw-ob"})
    url = f"https://translate.google.com/translate_tts?{params}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36"
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            daten = resp.read()
        if not daten or len(daten) < 100:
            tts_fehler_loggen("audio_silbe_pfad_sicherstellen", silbe, Exception("Antwort zu kurz/leer"))
            return ""
        with open(pfad, "wb") as f:
            f.write(daten)
        return pfad
    except Exception as e:
        tts_fehler_loggen("audio_silbe_pfad_sicherstellen", silbe, e)
        return ""

def alle_silben_audios_vorhanden(vok, sprache):
    silben = silben_liste_holen(vok)
    if not silben:
        return True
    wort = vok.get("lern", "")
    for s in silben:
        ordner = _silben_wort_ordner(s if s.strip().lower() in ARTIKEL_WOERTER else wort)
        pfad = os.path.join(ordner, gtts_dateiname_silbe(s, sprache))
        if not os.path.exists(pfad):
            return False
    return True

# ============================================================
#  Level-System
# ============================================================

def xp_format(wert):
    """Formatiert einen XP-Wert fuer die Anzeige: immer mit exakt 2
    Nachkommastellen (z.B. '21.00', '20.75', '39.75'), konsistent egal ob
    ganze Zahl oder Kommazahl."""
    return f"{round(wert, 2):.2f}"

def xp_fuer_level(lvl):
    if lvl <= 1:
        return 0
    return (lvl - 1) * (lvl - 1) * 50

def berechne_level(xp):
    lvl = 1
    while xp >= xp_fuer_level(lvl + 1):
        lvl += 1
    return lvl

def xp_fortschritt(xp):
    lvl = berechne_level(xp)
    xp_aktuell = xp - xp_fuer_level(lvl)
    xp_naechst = xp_fuer_level(lvl + 1) - xp_fuer_level(lvl)
    return lvl, xp_aktuell, xp_naechst

# ============================================================
#  Freischalt-System
# ============================================================

FREISCHALTUNGEN = {
    "de": [
        (3,  "thema_nacht",     "🌙 Nacht-Thema (dunkler Hintergrund)",          "🌙"),
        (5,  "joker",           "🃏 Joker: 1x pro Runde kein XP-Verlust",        "🃏"),
        (7,  "emoji_mode",      "😄 Emoji-Modus: Emojis in der Oberfläche",      "😄"),

        (12, "blitz_modus",     "⚡ Blitz-Modus: 5 Sekunden pro Wort",           "⚡"),
        (15, "mehrfach_wahl",   "🎯 Multiple-Choice-Modus",                      "🎯"),
        (20, "streak_bonus",    "🔥 Streak-Bonus: Doppel-XP bei 5+ in Folge",    "🔥"),
        (25, "xp_multiplikator","💎 XP x1.5 dauerhaft",                          "💎"),
        (30, "marathon_modus",  "🏃 Marathon: unbegrenzte Wörter-Runde",         "🏃"),
        (50, "legende",         "👑 Legende-Abzeichen freigeschaltet",            "👑"),
    ],
    "en": [
        (3,  "thema_nacht",     "🌙 Night Theme (dark background)",               "🌙"),
        (5,  "joker",           "🃏 Joker: 1x per round no XP loss",             "🃏"),
        (7,  "emoji_mode",      "😄 Emoji Mode: emojis in the interface",         "😄"),

        (12, "blitz_modus",     "⚡ Blitz Mode: 5 seconds per word",              "⚡"),
        (15, "mehrfach_wahl",   "🎯 Multiple Choice Mode",                        "🎯"),
        (20, "streak_bonus",    "🔥 Streak Bonus: double XP at 5+ in a row",      "🔥"),
        (25, "xp_multiplikator","💎 XP x1.5 permanently",                         "💎"),
        (30, "marathon_modus",  "🏃 Marathon: unlimited words per round",          "🏃"),
        (50, "legende",         "👑 Legend badge unlocked",                        "👑"),
    ],
    "fi": [
        (3,  "thema_nacht",     "🌙 Yöteema (tumma tausta)",                      "🌙"),
        (5,  "joker",           "🃏 Jokeri: 1x per kierros ilman XP-menetystä",  "🃏"),
        (7,  "emoji_mode",      "😄 Emoji-tila: emojit käyttöliittymässä",        "😄"),

        (12, "blitz_modus",     "⚡ Blitz-tila: 5 sekuntia per sana",             "⚡"),
        (15, "mehrfach_wahl",   "🎯 Monivalintatila",                             "🎯"),
        (20, "streak_bonus",    "🔥 Putki-bonus: tuplat XP 5+ peräkkäisestä",    "🔥"),
        (25, "xp_multiplikator","💎 XP x1.5 pysyvästi",                          "💎"),
        (30, "marathon_modus",  "🏃 Maraton: rajaton sanamäärä kierroksella",     "🏃"),
        (50, "legende",         "👑 Legenda-merkki avattu",                       "👑"),
    ],
}

def get_freigeschaltet(s):
    return set(s.get("freigeschaltet", []))

def get_aktiviert(s):
    return set(s.get("aktiviert", []))

def check_neue_freischaltungen(s, ui="de", root=None):
    xp  = s.get("level_xp", 0)
    lvl = berechne_level(xp)
    bereits = get_freigeschaltet(s)
    neu = []
    for (req_lvl, key, beschr, icon) in FREISCHALTUNGEN[ui]:
        if lvl >= req_lvl and key not in bereits:
            neu.append((key, beschr, icon, req_lvl))
            s["freigeschaltet"].append(key)
    return neu

def hat_freischaltung(key):
    s = stats_laden()
    return key in get_freigeschaltet(s) and key in get_aktiviert(s)

def toggle_aktivierung(key):
    s = stats_laden()
    aktiviert = s.get("aktiviert", [])
    if key in aktiviert:
        aktiviert.remove(key)
        an = False
    else:
        aktiviert.append(key)
        an = True
    s["aktiviert"] = aktiviert
    stats_speichern(s)
    return an

# ============================================================
#  Sprache / Texte
# ============================================================

SPRACH_NATIV = {"de": "Deutsch", "en": "English", "fi": "Suomi"}

SPRACH_NAMEN = {
    "de": {"de": "Deutsch",   "en": "Englisch",  "fi": "Finnisch"},
    "en": {"de": "German",    "en": "English",   "fi": "Finnish"},
    "fi": {"de": "Saksa",     "en": "Englanti",  "fi": "Suomi"},
}
MUTTERSPRACHE_LABEL = {"de": "Deutsch", "en": "English", "fi": "Suomi"}

TEXTE = {
    "de": {
        "lern_frage": "Welche Sprache möchtest du lernen?",
        "saetze": "❤️ Ganze Sätze",
        "saetze_titel": "❤️  Ganze Sätze",
        "saetze_ein_titel": "➕  Satz eintragen",
        "saetze_lern_titel": "📚   Sätze Lernen",
        "saetze_ein_hinweis": "Satz auf Deutsch oben, Übersetzung unten. Enter oder Speichern.",
        "saetze_ein_ok": "✓ Satz gespeichert!",
        "saetze_ein_fehler": "⚠ Bitte beide Felder ausfüllen!",
        "saetze_test_titel": "❤️  Satz-Test",
        "saetze_kein": "Bitte zuerst Sätze unter 'Ganze Sätze' hinzufügen!",
        "saetze_kein_titel": "Keine Sätze",
        "saetze_ergebnis": "Satz-Test abgeschlossen! 🎉\n\nRichtige Wörter: {r} / {g} ({p}%)\nFalsche Wörter: {f}",
        "saetze_gespeichert": "{n} Sätze gespeichert",
        "mix_kurz": "Mix 🔀",
        "titel": "Mein Vokabelheft",
        "lernsprache": "Lernsprache: {lang}",
        "gespeichert": "{n} Vokabeln gespeichert",
        "eintragen": "❤️   Eintragen",
        "lernen": "📚   Lernen",
        "test": "🧪   Test",
        "bearbeiten": "❤️   Bearbeiten",
        "statistik": "📊   Statistik",
        "freischaltungen": "🏆   Freischaltungen",
        "zurueck": "← Zurück",
        "weiter": "Weiter →",
        "speichern": "💾  Speichern",
        "audio_titel": "🎵  AUDIO (optional)",
        "audio_keine": "(keine)",
        "audio_waehlen": "📂 Wählen",
        "sprache_aendern": "Sprache / Lernsprache ändern",
        "richtung_titel": "Richtung wählen",
        "richtung_normal_kurz": "Normal",
        "richtung_umgekehrt_kurz": "Umgekehrt 🔄",
        "richtung_gemischt_kurz": "Gemischt 🔀",
        "richtung_gemischt_titel": "Zufällig gemischt",
        "richtung_mix_titel": "Mix: Richtung wechselt",
        "blitz_kurz_titel": "Blitz: 5 Sekunden pro Wort",
        "ein_titel": "❤️  Vokabel eintragen",
        "ein_hinweis": "Felder ausfüllen und Enter drücken oder auf Speichern klicken.",
        "ein_label_b": "LERNSPRACHE ({lang})",
        "ein_fehler": "⚠  Bitte beide Felder ausfüllen!",
        "ein_ok": "✓  '{w}' gespeichert!",
        "lern_titel": "📚  Lernen",
        "lern_titel_r": "📚  Lernen 🔄",
        "lern_hinweis": "H drücken oder auf das Kästchen klicken → aufdecken/verstecken",
        "lern_karte": "Karte {i} von {n}",
        "lern_versteckt": "❓  H drücken zum Aufdecken",
        "lern_fertig": "Du hast alle {n} Vokabeln durchgelernt! 🎉",
        "lern_vorherige": "← Vorherige",
        "test_titel": "🧪  Test",
        "test_titel_r": "🧪  Test 🔄",
        "test_titel_g": "🔀  Gemischter Test",
        "test_frage": "Frage {i} von {n}",
        "test_versuche": "Versuche übrig: {v}",
        "test_richtig": "✓  Richtig!",
        "test_falsch_n": "✗  Falsch! Noch {v} Versuch{e}",
        "test_falsch_end": "✗  Leider falsch!",
        "test_loesung": "Die richtige Antwort ist:",
        "test_ergebnis": "Test abgeschlossen! 🎉\n\nRichtig: {r} / {g}  ({p}%)\nFalsch: {f}",
        "test_prufen": "Prüfen ✓",
        "big_story_fertig": "Fertig 🏁",
        "lern_play": "▶  Audio",
        "lern_play_buchst": "🔊",
        "test_play": "▶  Audio",
        "test_kein_audio": "Kein Audio für dieses Wort.\n\nAudio-Dateien bitte in den Ordner:\n{folder}",
        "joker_btn": "🃏 Joker nutzen",
        "joker_genutzt": "🃏 Joker bereits genutzt",
        "joker_angewendet": "🃏 Joker! Kein XP-Verlust.",
        "shop_titel": "🛒  Shop",
        "inv_titel": "🎒  Inventar",
        "shop_coins": "{n} Coins",
        "shop_nicht_genug": "⚠ Nicht genug Coins! Du brauchst {n} Coins.",
        "shop_joker_gekauft": "Joker gekauft! Du hast jetzt {n} Joker.",
        "shop_trank_gekauft": "XP-Trank gekauft! Du hast jetzt {n} Tränke.",
        "shop_double_coin_gekauft": "Double Coin gekauft! Du hast jetzt {n} Double Coins.",
        "shop_pack_gekauft": "Pack gekauft! Du hast jetzt {n} Packs. Klicke auf die Pack-Box im Inventar zum Öffnen.",
        "shop_pack_hinweis": "Dragonballs anklicken  →  Pack öffnen ({preis} Coins → 1 Ball, Chance auf mehr)",
        "shop_gezogen": "Gezogen: ",
        "shop_neue_erhalten": "✨ {n} neue{suf} Dragonball{suf2} erhalten!",
        "shop_nur_duplikate": "(nur Duplikate diesmal)",
        "shop_alle_7_yippie": "🎉 Yippie! Alle 7 Dragonballs!",
        "shop_alle_komplett": "🎉 ALLE 7 DRAGONBALLS KOMPLETT! Bonus erhalten!",
        "bear_titel": "❤️  Bearbeiten",
        "bear_suche": "🔍  Suchen...",
        "bear_leer": "Noch keine Vokabeln gespeichert.",
        "bear_keine_treffer": "Keine Treffer für '{q}'.",
        "bear_aktion": "Aktion",
        "bear_audio_spalte": "Audio",
        "bear_alle_audios_laden": "🎵 Alle fehlenden Audios laden",
        "bear_reset_audio": "🔄 Audio zurücksetzen",
        "bear_seite": "Seite {i} / {n}",
        "bst_auswahl_zaehler": "{n} von {g} ausgewählt",
        "bear_zurueck_kurz": "◀ Zurück",
        "bear_weiter_kurz": "Weiter ▶",
        "bear_lade_titel": "Audios werden geladen …",
        "bear_downloads_status": "{geschafft} / {gesamt} Downloads",
        "bear_woerter_hinweis": "({n} Wörter, jeweils Wort-Audio + Silben)",
        "bear_fehlschlaege_folge": "{wort}  \u26a0 {n} Fehlschlag(e) in Folge",
        "bear_pause_text": "Pause ({s}s) - Google TTS Limit vermeiden...",
        "bear_woerter_zusammenfassung": "({n} Wörter → {gesamt} Audio-Dateien gesamt)",
        "bear_betroffen": "Betroffen:",
        "bear_volle_liste": "Volle Liste in:\naudio_fehlgeschlagen.txt",
        "bear_reset_frage": "Wirklich ALLE Audio-Dateien und -Ordner komplett löschen?",
        "bear_reset_fertig": "Alle Audio-Dateien und -Ordner wurden komplett gelöscht 🗑️",
        "bear_audio_vorhanden": "Alle Vokabeln haben bereits ein Audio 🎵",
        "bear_fertig_ergebnis": "{erfolgreich} von {gesamt} Audios erfolgreich geladen ✅",
        "bear_fertig_mit_fehlern": "{erfolgreich} von {gesamt} Audios erfolgreich geladen ✅\n\n{fehlgeschlagen} fehlgeschlagen ❌ (z.B. Google-Sperre bei zu vielen Anfragen).\nEinfach nochmal auf \"Alle fehlenden Audios laden\" klicken, um es erneut zu versuchen.",
        "bear_fertig_abgebrochen": "⏸ Abgebrochen bei {geschafft} / {gesamt}\n\nEs sind noch nicht alle Audios geladen. Einfach nochmal auf \"Alle fehlenden Audios laden\" klicken, um den Rest zu laden.",
        "bear_aendern": "Ändern",
        "bear_loeschen": "Löschen",
        "bear_nur_falsche": "❌ Nur falsche Wörter",
        "bear_dlg_titel": "Vokabel ändern",
        "bear_dlg_b": "Lernsprache ({lang}):",
        "bear_dlg_audio": "Audio-Datei (mp3) aus audio/-Ordner:",
        "bear_dlg_audio_btn": "Datei wählen",
        "bear_dlg_save": "Speichern",
        "bear_dlg_abbruch": "Abbrechen",
        "bear_del_frage": "'{w}' wirklich löschen?",
        "bear_del_titel": "Löschen",
        "keine_vok": "Bitte zuerst Vokabeln unter 'Eintragen' hinzufügen!",
        "keine_titel": "Keine Vokabeln",
        "falsche_keine": "Du hast noch keine falschen Wörter — super gemacht! Mach erst ein paar Tests.",
        "alle_gewusst": "Es sind gerade keine Wörter mit ❤️ zum Üben markiert — markiere Wörter mit dem Herz, um sie hier zu testen!",
        "falsche_woerter_titel": "❌   Falsche Wörter trainieren",
        "markierte_woerter_titel": "❤️ Markierte Wörter trainieren",
        "markierte_woerter_titel_text": "Markierte Wörter trainieren",
        "bugs_titel": "🐞  Bug melden",
        "trenn_woerter_titel": "🔤  Trenn Wörter abspielen",
        "bugs_hinweis": "Beschreibe kurz, was nicht funktioniert hat. Wird gespeichert und an ELEKTROMOON gesendet.",
        "bugs_speichern": "Senden",
        "bugs_gespeichert": "✓ Danke! Bug wurde gemeldet.",
        "big_story_titel": "📖  Große Geschichte",
        "big_story_hinweis": "Hier entsteht bald eine große Geschichte zum Lesen. Kommt bald!",
        "big_story_teil": "Teil {n}",
        "big_story_neuer_teil": "+ Teil hinzufügen",
        "big_story_loeschen_frage": "Diesen Teil wirklich löschen?",
        "big_story_fortschritt_frage": "Du hast hier schon weitergelesen. Weitermachen, wo du aufgehört hast?",
        "big_story_speichern": "Speichern",
        "stat_titel": "📊  Statistik",
        "stat_richtig": "Richtig beantwortet",
        "stat_falsch": "Falsch beantwortet",
        "stat_genauigkeit": "Genauigkeit",
        "stat_lernzeit": "Lernzeit gesamt",
        "stat_level": "Level",
        "stat_xp": "XP",
        "stat_naechstes": "Nächstes Level",
        "stat_top_falsch": "Häufigste Fehler",
        "stat_keine": "Noch keine Daten.",
        "stat_min": "Min.",
        "stat_std": "Std.",
        "lvl_titel": "🎯  Level-Modus",
        "lvl_hint": "Wie viel Prozent der Vokabeln möchtest du üben?",
        "lvl_prozent": "Prozent (1–100):",
        "lvl_schwach": "⚡  Schwächste Wörter zuerst",
        "lvl_zufall": "🎲  Zufällige Auswahl",
        "lvl_start": "Start",
        "lvl_fehler": "Bitte eine Zahl zwischen 1 und 100 eingeben.",
        "blitz_titel": "⚡  Blitz-Modus",
        "blitz_zeit": "Zeit: {s}s",
        "blitz_abgelaufen": "⏰ Zeit abgelaufen!",
        "mc_titel": "🎯  Multiple Choice",
        "artikel_titel": "📚  Der/Die/Das",
        "freisch_titel": "🏆  Freischaltungen",
        "freisch_gesperrt": "🔒  Gesperrt (Level {lvl} nötig)",
        "freisch_frei": "✅  Freigeschaltet",
        "freisch_an": "🟢  AN",
        "freisch_aus": "⚫  AUS",
        "freisch_aktivieren": "Aktivieren",
        "freisch_deaktivieren": "Deaktivieren",
        "level_auf": "🎉 Level {lvl} erreicht!\n\nFreigeschaltet:",
        "streak": "🔥 {n}x in Folge!",
        "xp_verlust": "-{xp} XP",
        "xp_gewinn": "+{xp} XP",
        "saetze_bear_titel": "❤️  Sätze bearbeiten",
        "saetze_bear_btn": "❤️   Sätze bearbeiten",
        "saetze_bear_aendern": "Ändern",
        "saetze_bear_loeschen": "Löschen",
        "saetze_bear_aendern_titel": "Satz ändern",
        "saetze_bear_audio": "Audio-Datei (mp3) aus audio/-Ordner:",
        "saetze_bear_audio_btn": "Datei wählen",
        "saetze_bear_speichern": "💾  Speichern",
        "saetze_bear_abbruch": "Abbrechen",
        "saetze_bear_loeschen_frage": "'{w}' wirklich löschen?",
        "saetze_bear_loeschen_titel": "Löschen",
        "saetze_bear_leer": "Noch keine Sätze gespeichert.",
        "saetze_bear_aktion": "Aktion",
        "satz_test_prufen": "Prüfen ✓",
        "satz_fb_titel": "WORT-FÜR-WORT AUSWERTUNG",
        "satz_vers_uebrig": "Versuche: {v} übrig",
        "satz_vers_fehler": "⚠ {f} Fehler  –  noch {v} Versuch{e}",
        "satz_vers_perfekt": "✅ Perfekt nach {v} Versuch{e}!",
        "satz_vers_auf": "❌ Versuche aufgebraucht! Lösung:",
        "vok_menue_titel": "📖   Vokabeln",
    },
    "en": {
        "lern_frage": "Which language do you want to learn?",
        "saetze": "❤️   Full Sentences",
        "saetze_titel": "❤️  Full Sentences",
        "saetze_ein_titel": "➕  Add Sentence",
        "saetze_lern_titel": "📚   Learn Sentences",
        "saetze_ein_hinweis": "Sentence in your language above, translation below. Enter or Save.",
        "saetze_ein_ok": "✓ Sentence saved!",
        "saetze_ein_fehler": "⚠ Please fill in both fields!",
        "saetze_test_titel": "❤️  Sentence Test",
        "saetze_kein": "Please add sentences in 'Full Sentences' first!",
        "saetze_kein_titel": "No Sentences",
        "saetze_ergebnis": "Sentence test done! 🎉\n\nCorrect words: {r} / {g} ({p}%)\nWrong words: {f}",
        "saetze_gespeichert": "{n} sentences saved",
        "mix_kurz": "Mix 🔀",
        "titel": "My Vocabulary Book",
        "lernsprache": "Learning: {lang}",
        "gespeichert": "{n} words saved",
        "eintragen": "❤️   Add Words",
        "lernen": "📚   Study",
        "test": "🧪   Test",
        "bearbeiten": "❤️   Edit",
        "statistik": "📊   Statistics",
        "freischaltungen": "🏆   Unlocks",
        "zurueck": "← Back",
        "weiter": "Next →",
        "speichern": "💾  Save",
        "audio_titel": "🎵  AUDIO (optional)",
        "audio_keine": "(none)",
        "audio_waehlen": "📂 Choose",
        "sprache_aendern": "Change language / learning language",
        "richtung_titel": "Choose direction",
        "richtung_normal_kurz": "Normal",
        "richtung_umgekehrt_kurz": "Reversed 🔄",
        "richtung_gemischt_kurz": "Mixed 🔀",
        "richtung_gemischt_titel": "Randomly mixed",
        "richtung_mix_titel": "Mix: direction changes",
        "blitz_kurz_titel": "Blitz: 5 seconds per word",
        "ein_titel": "❤️  Add a Word",
        "ein_hinweis": "Fill in both fields and press Enter or click Save.",
        "ein_label_b": "LEARNING LANGUAGE ({lang})",
        "ein_fehler": "⚠  Please fill in both fields!",
        "ein_ok": "✓  '{w}' saved!",
        "lern_titel": "📚  Study",
        "lern_titel_r": "📚  Study 🔄",
        "lern_hinweis": "Press H or click the box → reveal / hide word",
        "lern_karte": "Card {i} of {n}",
        "lern_versteckt": "❓  Press H to reveal",
        "lern_fertig": "You studied all {n} words! 🎉",
        "lern_vorherige": "← Previous",
        "test_titel": "🧪  Test",
        "test_titel_r": "🧪  Test 🔄",
        "test_titel_g": "🔀  Mixed Test",
        "test_frage": "Question {i} of {n}",
        "test_versuche": "Attempts left: {v}",
        "test_richtig": "✓  Correct!",
        "test_falsch_n": "✗  Wrong! {v} attempt{e} left",
        "test_falsch_end": "✗  Incorrect!",
        "test_loesung": "The correct answer is:",
        "test_ergebnis": "Test finished! 🎉\n\nCorrect: {r} / {g}  ({p}%)\nWrong: {f}",
        "test_prufen": "Check ✓",
        "big_story_fertig": "Done 🏁",
        "lern_play": "▶  Audio",
        "lern_play_buchst": "🔊",
        "test_play": "▶  Audio",
        "test_kein_audio": "No audio for this word.\n\nPlace audio files in:\n{folder}",
        "joker_btn": "🃏 Use Joker",
        "joker_genutzt": "🃏 Joker already used",
        "joker_angewendet": "🃏 Joker! No XP loss.",
        "shop_titel": "🛒  Shop",
        "inv_titel": "🎒  Inventory",
        "shop_coins": "{n} Coins",
        "shop_nicht_genug": "⚠ Not enough coins! You need {n} coins.",
        "shop_joker_gekauft": "Joker bought! You now have {n} jokers.",
        "shop_trank_gekauft": "XP potion bought! You now have {n} potions.",
        "shop_double_coin_gekauft": "Double Coin bought! You now have {n} Double Coins.",
        "shop_pack_gekauft": "Pack bought! You now have {n} packs. Click the pack box in your inventory to open it.",
        "shop_pack_hinweis": "Click dragonballs  →  open pack ({preis} coins → 1 ball, chance of more)",
        "shop_gezogen": "Drawn: ",
        "shop_neue_erhalten": "✨ {n} new dragonball{suf2} received!",
        "shop_nur_duplikate": "(duplicates only this time)",
        "shop_alle_7_yippie": "🎉 Yippee! All 7 Dragonballs!",
        "shop_alle_komplett": "🎉 ALL 7 DRAGONBALLS COMPLETE! Bonus received!",
        "bear_titel": "❤️  Edit",
        "bear_suche": "🔍  Search...",
        "bear_leer": "No words saved yet.",
        "bear_keine_treffer": "No results for '{q}'.",
        "bear_aktion": "Action",
        "bear_audio_spalte": "Audio",
        "bear_alle_audios_laden": "🎵 Load all missing audio",
        "bear_reset_audio": "🔄 Reset audio",
        "bear_seite": "Page {i} / {n}",
        "bst_auswahl_zaehler": "{n} of {g} selected",
        "bear_zurueck_kurz": "◀ Back",
        "bear_weiter_kurz": "Next ▶",
        "bear_lade_titel": "Loading audio …",
        "bear_downloads_status": "{geschafft} / {gesamt} downloads",
        "bear_woerter_hinweis": "({n} words, each with word audio + syllables)",
        "bear_fehlschlaege_folge": "{wort}  \u26a0 {n} failure(s) in a row",
        "bear_pause_text": "Pausing ({s}s) - avoiding Google TTS limit...",
        "bear_woerter_zusammenfassung": "({n} words → {gesamt} audio files total)",
        "bear_betroffen": "Affected:",
        "bear_volle_liste": "Full list in:\naudio_fehlgeschlagen.txt",
        "bear_reset_frage": "Really delete ALL audio files and folders completely?",
        "bear_reset_fertig": "All audio files and folders have been completely deleted 🗑️",
        "bear_audio_vorhanden": "All vocabulary already has audio 🎵",
        "bear_fertig_ergebnis": "{erfolgreich} of {gesamt} audio files successfully loaded ✅",
        "bear_fertig_mit_fehlern": "{erfolgreich} of {gesamt} audio files successfully loaded ✅\n\n{fehlgeschlagen} failed ❌ (e.g. Google rate limit).\nJust click \"Load all missing audio\" again to retry.",
        "bear_fertig_abgebrochen": "⏸ Cancelled at {geschafft} / {gesamt}\n\nNot all audio files were loaded yet. Just click \"Load all missing audio\" again to load the rest.",
        "bear_aendern": "Edit",
        "bear_loeschen": "Delete",
        "bear_nur_falsche": "❌ Wrong words only",
        "bear_dlg_titel": "Edit Word",
        "bear_dlg_b": "Learning language ({lang}):",
        "bear_dlg_audio": "Audio file (mp3) from audio/ folder:",
        "bear_dlg_audio_btn": "Choose file",
        "bear_dlg_save": "Save",
        "bear_dlg_abbruch": "Cancel",
        "bear_del_frage": "Really delete '{w}'?",
        "bear_del_titel": "Delete",
        "keine_vok": "Please add words in 'Add Words' first!",
        "keine_titel": "No Words",
        "falsche_keine": "You have no wrong words yet — great job! Do a few tests first.",
        "alle_gewusst": "No words are currently marked ❤️ to practice — mark words with the heart to test them here!",
        "falsche_woerter_titel": "❌   Practice Wrong Words",
        "markierte_woerter_titel": "❤️   Practice Marked Words",
        "markierte_woerter_titel_text": "Practice Marked Words",
        "bugs_titel": "🐞  Report a Bug",
        "trenn_woerter_titel": "🔤  Play Split Words",
        "bugs_hinweis": "Briefly describe what went wrong. This will be saved and sent to ELEKTROMOON.",
        "bugs_speichern": "Send",
        "bugs_gespeichert": "✓ Thanks! Bug reported.",
        "big_story_titel": "📖  Big Story",
        "big_story_hinweis": "A big story to read is coming here soon. Stay tuned!",
        "big_story_teil": "Part {n}",
        "big_story_neuer_teil": "+ Add part",
        "big_story_loeschen_frage": "Really delete this part?",
        "big_story_fortschritt_frage": "You already read further here. Continue where you left off?",
        "big_story_speichern": "Save",
        "stat_titel": "📊  Statistics",
        "stat_richtig": "Correct answers",
        "stat_falsch": "Wrong answers",
        "stat_genauigkeit": "Accuracy",
        "stat_lernzeit": "Total study time",
        "stat_level": "Level",
        "stat_xp": "XP",
        "stat_naechstes": "Next level",
        "stat_top_falsch": "Most frequent mistakes",
        "stat_keine": "No data yet.",
        "stat_min": "min",
        "stat_std": "h",
        "lvl_titel": "🎯  Level Mode",
        "lvl_hint": "What percentage of words do you want to practice?",
        "lvl_prozent": "Percent (1–100):",
        "lvl_schwach": "⚡  Weakest words first",
        "lvl_zufall": "🎲  Random selection",
        "lvl_start": "Start",
        "lvl_fehler": "Please enter a number between 1 and 100.",
        "blitz_titel": "⚡  Blitz Mode",
        "blitz_zeit": "Time: {s}s",
        "blitz_abgelaufen": "⏰ Time's up!",
        "mc_titel": "🎯  Multiple Choice",
        "artikel_titel": "📚  Der/Die/Das",
        "freisch_titel": "🏆  Unlocks",
        "freisch_gesperrt": "🔒  Locked (need Level {lvl})",
        "freisch_frei": "✅  Unlocked",
        "freisch_an": "🟢  ON",
        "freisch_aus": "⚫  OFF",
        "freisch_aktivieren": "Activate",
        "freisch_deaktivieren": "Deactivate",
        "level_auf": "🎉 Reached Level {lvl}!\n\nUnlocked:",
        "streak": "🔥 {n}x in a row!",
        "xp_verlust": "-{xp} XP",
        "xp_gewinn": "+{xp} XP",
        "saetze_bear_titel": "❤️  Edit Sentences",
        "saetze_bear_btn": "❤️   Edit Sentences",
        "saetze_bear_aendern": "Edit",
        "saetze_bear_loeschen": "Delete",
        "saetze_bear_aendern_titel": "Edit Sentence",
        "saetze_bear_audio": "Audio file (mp3) from audio/ folder:",
        "saetze_bear_audio_btn": "Choose file",
        "saetze_bear_speichern": "💾  Save",
        "saetze_bear_abbruch": "Cancel",
        "saetze_bear_loeschen_frage": "Really delete '{w}'?",
        "saetze_bear_loeschen_titel": "Delete",
        "saetze_bear_leer": "No sentences saved yet.",
        "saetze_bear_aktion": "Action",
        "satz_test_prufen": "Check ✓",
        "satz_fb_titel": "WORD-BY-WORD EVALUATION",
        "satz_vers_uebrig": "Attempts: {v} left",
        "satz_vers_fehler": "⚠ {f} error(s)  –  {v} attempt{e} left",
        "satz_vers_perfekt": "✅ Perfect after {v} attempt{e}!",
        "satz_vers_auf": "❌ Attempts used up! Solution:",
        "vok_menue_titel": "📖   Vocabulary",
    },
    "fi": {
        "lern_frage": "Minkä kielen haluat oppia?",
        "saetze": "❤️   Kokonaiset lauseet",
        "saetze_titel": "❤️  Kokonaiset lauseet",
        "saetze_ein_titel": "➕  Lisää lause",
        "saetze_lern_titel": "📚   Opettele lauseita",
        "saetze_ein_hinweis": "Lause ylhäällä, käännös alhaalla. Enter tai Tallenna.",
        "saetze_ein_ok": "✓ Lause tallennettu!",
        "saetze_ein_fehler": "⚠ Täytä molemmat kentät!",
        "saetze_test_titel": "❤️  Lausetesti",
        "saetze_kein": "Lisää ensin lauseita 'Kokonaiset lauseet' -osiossa!",
        "saetze_kein_titel": "Ei lauseita",
        "saetze_ergebnis": "Lausetesti valmis! 🎉\n\nOikeat sanat: {r} / {g} ({p}%)\nVäärät sanat: {f}",
        "saetze_gespeichert": "{n} lausetta tallennettu",
        "mix_kurz": "Mix 🔀",
        "titel": "Sanastovihkoni",
        "lernsprache": "Opiskelukieli: {lang}",
        "gespeichert": "{n} sanaa tallennettu",
        "eintragen": "❤️   Lisää sanoja",
        "lernen": "📚   Opiskele",
        "test": "🧪   Testi",
        "bearbeiten": "❤️   Muokkaa",
        "statistik": "📊   Tilastot",
        "freischaltungen": "🏆   Saavutukset",
        "zurueck": "← Takaisin",
        "weiter": "Seuraava →",
        "speichern": "💾  Tallenna",
        "audio_titel": "🎵  AUDIO (valinnainen)",
        "audio_keine": "(ei mitään)",
        "audio_waehlen": "📂 Valitse",
        "sprache_aendern": "Vaihda kieltä / opiskelukieltä",
        "richtung_titel": "Valitse suunta",
        "richtung_normal_kurz": "Normaali",
        "richtung_umgekehrt_kurz": "Käänteinen 🔄",
        "richtung_gemischt_kurz": "Sekalainen 🔀",
        "richtung_gemischt_titel": "Satunnaisesti sekaisin",
        "richtung_mix_titel": "Mix: suunta vaihtuu",
        "blitz_kurz_titel": "Pika: 5 sekuntia per sana",
        "ein_titel": "❤️  Lisää sana",
        "ein_hinweis": "Täytä molemmat kentät ja paina Enter tai Tallenna.",
        "ein_label_b": "OPISKELUKIELI ({lang})",
        "ein_fehler": "⚠  Täytä molemmat kentät!",
        "ein_ok": "✓  '{w}' tallennettu!",
        "lern_titel": "📚  Opiskele",
        "lern_titel_r": "📚  Opiskele 🔄",
        "lern_hinweis": "Paina H tai klikkaa ruutua → näytä / piilota sana",
        "lern_karte": "Kortti {i} / {n}",
        "lern_versteckt": "❓  Paina H näyttääksesi",
        "lern_fertig": "Olet opiskellut kaikki {n} sanaa! 🎉",
        "lern_vorherige": "← Edellinen",
        "test_titel": "🧪  Testi",
        "test_titel_r": "🧪  Testi 🔄",
        "test_titel_g": "🔀  Sekalainen testi",
        "test_frage": "Kysymys {i} / {n}",
        "test_versuche": "Yrityksiä jäljellä: {v}",
        "test_richtig": "✓  Oikein!",
        "test_falsch_n": "✗  Väärin! {v} yritys{e} jäljellä",
        "test_falsch_end": "✗  Yritystä!",
        "test_loesung": "Oikea vastaus on:",
        "test_ergebnis": "Testi valmis! 🎉\n\nOikein: {r} / {g}  ({p}%)\nVäärin: {f}",
        "test_prufen": "Tarkista ✓",
        "big_story_fertig": "Valmis 🏁",
        "lern_play": "▶  Audio",
        "lern_play_buchst": "🔊",
        "test_play": "▶  Audio",
        "test_kein_audio": "Ei ääntä tälle sanalle.\n\nLisää äänitiedostot kansioon:\n{folder}",
        "joker_btn": "🃏 Käytä jokeri",
        "joker_genutzt": "🃏 Jokeri käytetty",
        "joker_angewendet": "🃏 Jokeri! Ei XP-menetystä.",
        "shop_titel": "🛒  Kauppa",
        "inv_titel": "🎒  Inventaario",
        "shop_coins": "{n} kolikkoa",
        "shop_nicht_genug": "⚠ Ei tarpeeksi kolikoita! Tarvitset {n} kolikkoa.",
        "shop_joker_gekauft": "Jokeri ostettu! Sinulla on nyt {n} jokeria.",
        "shop_trank_gekauft": "XP-juoma ostettu! Sinulla on nyt {n} juomaa.",
        "shop_double_coin_gekauft": "Double Coin ostettu! Sinulla on nyt {n} Double Coinia.",
        "shop_pack_gekauft": "Pakkaus ostettu! Sinulla on nyt {n} pakkausta. Napsauta pakkauslaatikkoa inventaariossa avataksesi sen.",
        "shop_pack_hinweis": "Klikkaa lohikäärmepalloja  →  avaa pakkaus ({preis} kolikkoa → 1 pallo, mahdollisuus useampaan)",
        "shop_gezogen": "Nostettu: ",
        "shop_neue_erhalten": "✨ {n} uutta lohikäärmepalloa saatu!",
        "shop_nur_duplikate": "(vain kaksoiskappaleita tällä kertaa)",
        "shop_alle_7_yippie": "🎉 Jipii! Kaikki 7 lohikäärmepalloa!",
        "shop_alle_komplett": "🎉 KAIKKI 7 LOHIKÄÄRMEPALLOA VALMIINA! Bonus saatu!",
        "bear_titel": "❤️  Muokkaa",
        "bear_suche": "🔍  Etsi...",
        "bear_leer": "Ei tallennettuja sanoja.",
        "bear_keine_treffer": "Ei tuloksia haulle '{q}'.",
        "bear_aktion": "Toiminto",
        "bear_audio_spalte": "Audio",
        "bear_alle_audios_laden": "🎵 Lataa kaikki puuttuvat äänet",
        "bear_reset_audio": "🔄 Nollaa audio",
        "bear_seite": "Sivu {i} / {n}",
        "bst_auswahl_zaehler": "{n} / {g} valittu",
        "bear_zurueck_kurz": "◀ Takaisin",
        "bear_weiter_kurz": "Seuraava ▶",
        "bear_lade_titel": "Ladataan ääniä …",
        "bear_downloads_status": "{geschafft} / {gesamt} latausta",
        "bear_woerter_hinweis": "({n} sanaa, kukin sisältää sanaäänen + tavut)",
        "bear_fehlschlaege_folge": "{wort}  \u26a0 {n} epäonnistumista peräkkäin",
        "bear_pause_text": "Tauko ({s}s) - vältetään Google TTS -rajoitusta...",
        "bear_woerter_zusammenfassung": "({n} sanaa → {gesamt} äänitiedostoa yhteensä)",
        "bear_betroffen": "Koskee:",
        "bear_volle_liste": "Täydellinen lista:\naudio_fehlgeschlagen.txt",
        "bear_reset_frage": "Poistetaanko todella KAIKKI äänitiedostot ja -kansiot kokonaan?",
        "bear_reset_fertig": "Kaikki äänitiedostot ja -kansiot on poistettu kokonaan 🗑️",
        "bear_audio_vorhanden": "Kaikilla sanoilla on jo ääni 🎵",
        "bear_fertig_ergebnis": "{erfolgreich} / {gesamt} ääntä ladattu onnistuneesti ✅",
        "bear_fertig_mit_fehlern": "{erfolgreich} / {gesamt} ääntä ladattu onnistuneesti ✅\n\n{fehlgeschlagen} epäonnistui ❌ (esim. Googlen rajoitus liian monelle pyynnölle).\nPaina vain uudelleen \"Lataa kaikki puuttuvat äänet\" yrittääksesi uudelleen.",
        "bear_fertig_abgebrochen": "⏸ Peruutettu kohdassa {geschafft} / {gesamt}\n\nKaikkia ääniä ei vielä ladattu. Paina vain uudelleen \"Lataa kaikki puuttuvat äänet\" ladataksesi loput.",
        "bear_aendern": "Muokkaa",
        "bear_loeschen": "Poista",
        "bear_nur_falsche": "❌ Vain väärät sanat",
        "bear_dlg_titel": "Muokkaa sanaa",
        "bear_dlg_b": "Opiskelukieli ({lang}):",
        "bear_dlg_audio": "Äänitiedosto (mp3) audio/-kansiosta:",
        "bear_dlg_audio_btn": "Valitse tiedosto",
        "bear_dlg_save": "Tallenna",
        "bear_dlg_abbruch": "Peruuta",
        "bear_del_frage": "Poistetaanko '{w}'?",
        "bear_del_titel": "Poista",
        "keine_vok": "Lisää ensin sanoja 'Lisää sanoja' -osiossa!",
        "keine_titel": "Ei sanoja",
        "falsche_keine": "Sinulla ei ole vielä väärin menneitä sanoja — hienoa! Tee ensin muutama testi.",
        "alle_gewusst": "Yhtään sanaa ei ole merkitty ❤️ harjoiteltavaksi — merkitse sanoja sydämellä testataksesi niitä!",
        "falsche_woerter_titel": "❌   Harjoittele vääriä sanoja",
        "markierte_woerter_titel": "❤️   Harjoittele merkittyjä sanoja",
        "markierte_woerter_titel_text": "Harjoittele merkittyjä sanoja",
        "bugs_titel": "🐞  Ilmoita virheestä",
        "trenn_woerter_titel": "🔤  Toista tavutetut sanat",
        "bugs_hinweis": "Kuvaa lyhyesti, mikä ei toiminut. Tämä tallennetaan ja lähetetään ELEKTROMOONille.",
        "bugs_speichern": "Lähetä",
        "bugs_gespeichert": "✓ Kiitos! Virhe ilmoitettu.",
        "big_story_titel": "📖  Iso tarina",
        "big_story_hinweis": "Tähän tulee pian iso tarina luettavaksi. Pysy kuulolla!",
        "big_story_teil": "Osa {n}",
        "big_story_neuer_teil": "+ Lisää osa",
        "big_story_loeschen_frage": "Poistetaanko tämä osa varmasti?",
        "big_story_fortschritt_frage": "Olet jo lukenut tätä pidemmälle. Jatketaanko siitä, mihin jäit?",
        "big_story_speichern": "Tallenna",
        "stat_titel": "📊  Tilastot",
        "stat_richtig": "Oikein vastattu",
        "stat_falsch": "Väärin vastattu",
        "stat_genauigkeit": "Tarkkuus",
        "stat_lernzeit": "Opiskeluaika yhteensä",
        "stat_level": "Taso",
        "stat_xp": "XP",
        "stat_naechstes": "Seuraava taso",
        "stat_top_falsch": "Yleisimmät virheet",
        "stat_keine": "Ei vielä tietoja.",
        "stat_min": "min",
        "stat_std": "h",
        "lvl_titel": "🎯  Taso-tila",
        "lvl_hint": "Kuinka suuren osan sanoista haluat harjoitella?",
        "lvl_prozent": "Prosentti (1–100):",
        "lvl_schwach": "⚡  Heikoimmista sanoista",
        "lvl_zufall": "🎲  Satunnainen valinta",
        "lvl_start": "Aloita",
        "lvl_fehler": "Anna luku välillä 1–100.",
        "blitz_titel": "⚡  Blitz-tila",
        "blitz_zeit": "Aika: {s}s",
        "blitz_abgelaufen": "⏰ Aika loppui!",
        "mc_titel": "🎯  Monivalinta",
        "artikel_titel": "📚  Der/Die/Das",
        "freisch_titel": "🏆  Saavutukset",
        "freisch_gesperrt": "🔒  Lukittu (tarvitset tason {lvl})",
        "freisch_frei": "✅  Avattu",
        "freisch_an": "🟢  PÄÄLLÄ",
        "freisch_aus": "⚫  POIS",
        "freisch_aktivieren": "Aktivoi",
        "freisch_deaktivieren": "Poista käytöstä",
        "level_auf": "🎉 Taso {lvl} saavutettu!\n\nAvattu:",
        "streak": "🔥 {n}x peräkkäin!",
        "xp_verlust": "-{xp} XP",
        "xp_gewinn": "+{xp} XP",
        "saetze_bear_titel": "❤️  Muokkaa lauseita",
        "saetze_bear_btn": "❤️   Muokkaa lauseita",
        "saetze_bear_aendern": "Muokkaa",
        "saetze_bear_loeschen": "Poista",
        "saetze_bear_aendern_titel": "Muokkaa lausetta",
        "saetze_bear_audio": "Äänitiedosto (mp3) audio/-kansiosta:",
        "saetze_bear_audio_btn": "Valitse tiedosto",
        "saetze_bear_speichern": "💾  Tallenna",
        "saetze_bear_abbruch": "Peruuta",
        "saetze_bear_loeschen_frage": "Poistetaanko '{w}'?",
        "saetze_bear_loeschen_titel": "Poista",
        "saetze_bear_leer": "Ei tallennettuja lauseita.",
        "saetze_bear_aktion": "Toiminto",
        "satz_test_prufen": "Tarkista ✓",
        "satz_fb_titel": "SANA-SANA ARVIOINTI",
        "satz_vers_uebrig": "Yrityksiä: {v} jäljellä",
        "satz_vers_fehler": "⚠ {f} virhe(ttä)  –  {v} yritys{e} jäljellä",
        "satz_vers_perfekt": "✅ Täydellinen {v} yrityksen{e} jälkeen!",
        "satz_vers_auf": "❌ Yritykset loppu! Vastaus:",
        "vok_menue_titel": "📖   Sanasto",
    },
}

def t(ui, key, **kw):
    txt = TEXTE[ui].get(key, key)
    return txt.format(**kw) if kw else txt

def langname(ui, code):
    return SPRACH_NAMEN[ui][code]

def nativname(code):
    return SPRACH_NATIV[code]

def muttersprache_label(ui):
    return MUTTERSPRACHE_LABEL[ui]

# ============================================================
#  Farben
# ============================================================

CLR_LIGHT = {
    "bg":         "#f0f2f5",
    "white":      "white",
    "border":     "#dde3ea",
    "blue":       "#3498db",
    "green":      "#2ecc71",
    "orange":     "#e67e22",
    "purple":     "#9b59b6",
    "red":        "#e74c3c",
    "gray":       "#ecf0f1",
    "text":       "#2c3e50",
    "sub":        "#888",
    "light":      "#eef0f3",
    "xp":         "#f39c12",
    "row_a":      "white",
    "row_b":      "#f7f9fc",
    "entry_bg":   "white",
    "entry_fg":   "#2c3e50",
    "entry_ins":  "#2c3e50",
    "card_border":"black",
    "back_bg":    "white",
    "back_fg":    "#222222",
    "hdr_bg":     "black",
    "hdr_fg":     "white",
    "popup_bg":   "white",
}

CLR_DARK = {
    "bg":         "#1a1a2e",
    "white":      "#16213e",
    "border":     "#4a5568",
    "blue":       "#4a9fd4",
    "green":      "#27ae60",
    "orange":     "#e67e22",
    "purple":     "#9b59b6",
    "red":        "#e74c3c",
    "gray":       "#2d2d44",
    "text":       "#ffffff",
    "sub":        "#cccccc",
    "light":      "#1e1e35",
    "xp":         "#f39c12",
    "row_a":      "#16213e",
    "row_b":      "#1e1e35",
    "entry_bg":   "#0f3460",
    "entry_fg":   "#ffffff",
    "entry_ins":  "#ffffff",
    "card_border":"#ffffff",
    "back_bg":    "#2d2d44",
    "back_fg":    "#ffffff",
    "hdr_bg":     "#0f3460",
    "hdr_fg":     "#ffffff",
    "popup_bg":   "#16213e",
}

CLR = CLR_LIGHT.copy()

def make_frame(parent, **kw):
    return tk.Frame(parent, bg=CLR["bg"], **kw)

# ============================================================
#  Skalierung (Fenster frei groessenveraenderbar)
# ============================================================

class _Skalierung:
    def __init__(self):
        self.basis_w = 460
        self.basis_h = 560
        self.faktor  = 1.0

    def setze_basis(self, w, h):
        self.basis_w = max(1, w)
        self.basis_h = max(1, h)
        self.faktor  = 1.0

    def aktualisiere(self, w, h):
        if self.basis_w <= 0 or self.basis_h <= 0:
            return
        f = min(w / self.basis_w, h / self.basis_h)
        # Obergrenze bewusst niedriger als 2.2, damit bei sehr breiten/kurzen
        # maximierten Fenstern nicht mehr Inhalt (z.B. "Sprache aendern" im
        # Hauptmenue) durch zu grosse Skalierung aus dem sichtbaren Bereich
        # nach unten herausrutscht.
        self.faktor = max(0.6, min(1.6, f))

    def s(self, wert):
        if wert == 0:
            return 0
        ergebnis = int(round(wert * self.faktor))
        return ergebnis if ergebnis != 0 else (1 if wert > 0 else -1)

SKAL = _Skalierung()

def fnt(size, *stil):
    return ("Arial", SKAL.s(size)) + stil

# ============================================================
#  App
# ============================================================

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("VilmaLearn 1.4")
        try:
            self.root.iconbitmap(os.path.join(BASE_DIR, "heart.ico"))
        except Exception:
            pass
        try:
            self.root.tk.call("wm", "iconbitmap", "toplevel", os.path.join(BASE_DIR, "heart.ico"))
        except Exception:
            pass
        self.root.resizable(True, True)
        self.root.minsize(320, 280)
        self.root.configure(bg=CLR["bg"])
        self.ui  = None
        self.ls  = None
        self._session_start = None
        self._aktuelle_ansicht = None
        self._resize_after = None
        s = stats_laden()
        if hat_freischaltung("thema_nacht"):
            CLR.update(CLR_DARK)
            self.root.configure(bg=CLR["bg"])
        self._export_txt()
        self.root.protocol("WM_DELETE_WINDOW", self._beim_schliessen)
        self.root.bind("<Configure>", self._on_resize)
        self.zeige_ui_auswahl()

    def _on_resize(self, event):
        if event.widget is not self.root:
            return
        if self._resize_after:
            self.root.after_cancel(self._resize_after)
        self._resize_after = self.root.after(120, self._resize_anwenden)

    def _resize_anwenden(self):
        self._resize_after = None
        try:
            if not self.root.winfo_exists():
                return
            w = self.root.winfo_width()
            h = self.root.winfo_height()
        except tk.TclError:
            return
        alt = SKAL.faktor
        SKAL.aktualisiere(w, h)
        if abs(SKAL.faktor - alt) >= 0.03 and self._aktuelle_ansicht:
            ansicht = self._aktuelle_ansicht
            self._aktuelle_ansicht = None
            try:
                ansicht()
            except tk.TclError:
                pass
            self._aktuelle_ansicht = ansicht

    def _beim_schliessen(self):
        self._session_beenden()
        self._export_txt()
        self.root.destroy()

    def clear(self):
        # Navigations-Tracking: welche Seite wird verlassen, um zu welcher
        # gewechselt wird (Klickpfad). Die neue Seite setzt _aktuelle_ansicht
        # unmittelbar nach diesem clear()-Aufruf selbst.
        try:
            alte_seite = getattr(self._aktuelle_ansicht, "__name__", "") if self._aktuelle_ansicht else ""
            if alte_seite:
                tracking_senden("navigation", sprache=getattr(self, "ls", ""), von_seite=alte_seite, zu_seite="")
        except Exception:
            pass
        # Alle noch ausstehenden after()-Callbacks abbrechen, bevor die Widgets
        # zerstört werden. Verhindert Race Conditions wie: schnell "zurück" und
        # wieder "rein" klicken, während ein verzögerter Callback (z.B.
        # after(10, ...) aus einem Such-/Pagination-Handler) noch aussteht und
        # danach versucht, ein längst zerstörtes Widget zu konfigurieren.
        try:
            for job_id in self.root.tk.eval('after info').split():
                try:
                    self.root.after_cancel(job_id)
                except Exception:
                    pass
        except Exception:
            pass

        for w in self.root.winfo_children():
            try:
                w.destroy()
            except tk.TclError:
                pass
        self.root.unbind("<Return>")
        self.root.unbind("<h>")
        self.root.unbind("<H>")
        try:
            self.root.unbind_all("<MouseWheel>")
        except Exception:
            pass
        if hasattr(self, '_blitz_after') and self._blitz_after:
            self.root.after_cancel(self._blitz_after)
            self._blitz_after = None

    def _session_starten(self):
        self._session_start = time.time()

    def _session_beenden(self):
        if self._session_start:
            start_ts = self._session_start
            ende_ts  = time.time()
            sek = int(ende_ts - start_ts)
            s = stats_laden()
            s["lernzeit_sek"] = s.get("lernzeit_sek", 0) + sek
            stats_speichern(s)
            xp = s.get("level_xp", 0)
            lvl = berechne_level(xp)
            von_str = time.strftime("%H:%M:%S", time.localtime(start_ts))
            bis_str = time.strftime("%H:%M:%S", time.localtime(ende_ts))
            tracking_senden("update", sprache=self.ls, laufzeit=s.get("lernzeit_sek", 0),
                            level=lvl, xp=xp, von=von_str, bis=bis_str, dauer_sek=sek,
                            modus=getattr(self, "aktueller_modus", ""))
            self._session_start = None
        self._export_txt()

    def _export_txt(self):
        pfad = os.path.join(BASE_DIR, "vokabeln_export.txt")
        sprachen = ["de", "en", "fi"]
        sprach_namen = {"de": "Deutsch", "en": "Englisch", "fi": "Finnisch"}
        try:
            with open(pfad, "w", encoding="utf-8") as f:
                f.write("=" * 60 + "\n")
                f.write("  VOKABELHEFT  —  EXPORT\n")
                f.write(f"  Stand: {__import__('datetime').datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n")
                f.write("=" * 60 + "\n\n")
                reihenfolge = ["de", "fi"] + [s for s in sprachen if s not in ("de", "fi")]
                f.write("═" * 60 + "\n")
                f.write("  WÖRTER\n")
                f.write("═" * 60 + "\n\n")
                for ls in reihenfolge:
                    vok = vokabeln_laden(ls)
                    if not vok:
                        continue
                    f.write(f"─" * 60 + "\n")
                    f.write(f"  Lernsprache: {sprach_namen.get(ls, ls)}\n")
                    f.write(f"─" * 60 + "\n")
                    for i, v in enumerate(sorted(vok, key=lambda x: x.get('nativ','').lower()), 1):
                        audio_info = f"  [🎵 {v['audio']}]" if v.get('audio') else ""
                        f.write(f"  {i:>3}. Deutsch:  {v.get('nativ', '')}\n")
                        f.write(f"       {sprach_namen.get(ls,ls)+':':10} {v.get('lern', '')}{audio_info}\n")
                    f.write(f"\n  Gesamt: {len(vok)} Wörter\n\n")
                f.write("═" * 60 + "\n")
                f.write("  SÄTZE\n")
                f.write("═" * 60 + "\n\n")
                for ls in reihenfolge:
                    saetze = saetze_laden(ls)
                    if not saetze:
                        continue
                    f.write(f"─" * 60 + "\n")
                    f.write(f"  Lernsprache: {sprach_namen.get(ls, ls)}\n")
                    f.write(f"─" * 60 + "\n")
                    for i, s in enumerate(saetze, 1):
                        audio_info = f"  [🎵 {s['audio']}]" if s.get('audio') else ""
                        f.write(f"  {i:>3}. Deutsch:  {s.get('nativ', '')}\n")
                        f.write(f"       {sprach_namen.get(ls,ls)+':':10} {s.get('lern', '')}{audio_info}\n")
                    f.write(f"\n  Gesamt: {len(saetze)} Sätze\n\n")
                f.write("=" * 60 + "\n")
                f.write("  ENDE DES EXPORTS\n")
                f.write("=" * 60 + "\n")
        except Exception as e:
            print(f"Export-Fehler: {e}")

    def zeige_ui_auswahl(self):
        self._session_beenden()
        self._aktuelle_ansicht = self.zeige_ui_auswahl
        self.clear()
        if self.root.winfo_width() <= 1:
            self.root.geometry("440x360")
            SKAL.setze_basis(440, 360)
        tk.Label(self.root, text="🌍  Willkommen · Welcome · Tervetuloa",
                 font=fnt(13, "bold"), bg=CLR["bg"], fg=CLR["text"]).pack(pady=(SKAL.s(36), SKAL.s(6)))
        tk.Label(self.root, text="Version 1.4",
                 font=fnt(13, "bold"), bg=CLR["bg"], fg=CLR["text"]).pack(pady=(0, SKAL.s(6)))
        tk.Label(self.root,
                 text="Bitte wähle deine Sprache · Please choose your language\nValitse kielesi",
                 font=fnt(10), bg=CLR["bg"], fg=CLR["sub"], justify="center").pack(pady=(SKAL.s(0), SKAL.s(24)))
        for lbl, code, col in [("🇩🇪   Deutsch", "de", CLR["blue"]),
                                ("🇬🇧   English", "en", CLR["green"]),
                                ("🇫🇮   Suomi",   "fi", CLR["red"])]:
            tk.Button(self.root, text=lbl, font=fnt(13, "bold"),
                      bg=col, fg="white", relief="flat", padx=SKAL.s(0), pady=SKAL.s(12),
                      cursor="hand2", width=20,
                      command=lambda c=code: self._ui_gewaehlt(c)).pack(pady=SKAL.s(4))

    def _ui_gewaehlt(self, code):
        self.ui = code
        self.zeige_lern_auswahl()

    def zeige_lern_auswahl(self):
        self._aktuelle_ansicht = self.zeige_lern_auswahl
        self.clear()
        if self.root.winfo_width() <= 1:
            self.root.geometry("440x380")
            SKAL.setze_basis(440, 380)
        ui = self.ui
        tk.Label(self.root, text=t(ui, "lern_frage"),
                 font=fnt(14, "bold"), bg=CLR["bg"], fg=CLR["text"]).pack(pady=(SKAL.s(40), SKAL.s(28)))
        for code, col in [("de", CLR["blue"]), ("en", CLR["green"]), ("fi", CLR["red"])]:
            flag = {"de": "🇩🇪", "en": "🇬🇧", "fi": "🇫🇮"}[code]
            tk.Button(self.root, text=f"{flag}   {langname(ui, code)}",
                      font=fnt(13, "bold"), bg=col, fg="white", relief="flat",
                      padx=SKAL.s(0), pady=SKAL.s(12), cursor="hand2", width=20,
                      command=lambda c=code: self._lern_gewaehlt(c)).pack(pady=SKAL.s(4))

    def _lern_gewaehlt(self, code):
        self.ls = code
        self.zeige_hauptmenue()

    def zeige_hauptmenue(self):
        self._session_beenden()
        self._aktuelle_ansicht = self.zeige_hauptmenue
        self.clear()
        if self.root.winfo_width() <= 1:
            self.root.geometry("460x680")
            SKAL.setze_basis(460, 680)
        ui, ls = self.ui, self.ls

        _hm_canvas = tk.Canvas(self.root, bg=CLR["bg"], highlightthickness=0)
        _hm_scrollbar = tk.Scrollbar(self.root, orient="vertical", command=_hm_canvas.yview)
        _hm_inner = tk.Frame(_hm_canvas, bg=CLR["bg"])

        _hm_inner.bind("<Configure>", lambda e: _hm_canvas.configure(scrollregion=_hm_canvas.bbox("all")))
        _hm_window = _hm_canvas.create_window((0, 0), window=_hm_inner, anchor="n")
        _hm_canvas.configure(yscrollcommand=_hm_scrollbar.set)

        def _hm_center(event):
            _hm_canvas.itemconfig(_hm_window, width=event.width)
        _hm_canvas.bind("<Configure>", _hm_center)

        def _hm_mousewheel(event):
            _hm_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        _hm_canvas.bind_all("<MouseWheel>", _hm_mousewheel)

        _hm_canvas.pack(side="left", fill="both", expand=True)
        _hm_scrollbar.pack(side="right", fill="y")

        root = self.root
        self.root = _hm_inner

        tk.Label(self.root, text=t(ui, "titel"), font=fnt(20, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(SKAL.s(28), SKAL.s(2)))

        flag = {"de": "🇩🇪", "en": "🇬🇧", "fi": "🇫🇮"}[ls]
        tk.Label(self.root, text=f"{flag}  {t(ui, 'lernsprache', lang=langname(ui, ls))}",
                 font=fnt(11, "bold"), bg=CLR["bg"], fg=CLR["sub"]).pack()

        vok = vokabeln_laden(ls)
        tk.Label(self.root, text=t(ui, "gespeichert", n=len(vok)),
                 font=fnt(11), bg=CLR["bg"], fg=CLR["sub"]).pack(pady=(SKAL.s(2), SKAL.s(4)))

        s   = stats_laden()
        xp  = s.get("level_xp", 0)
        lvl, xp_ak, xp_nx = xp_fortschritt(xp)
        tk.Label(self.root,
                 text=f"⭐  {t(ui,'stat_level')} {lvl}   |   {xp_ak} / {xp_nx} XP",
                 font=fnt(10, "bold"), bg=CLR["bg"], fg=CLR["xp"]).pack(pady=(SKAL.s(0), SKAL.s(4)))
        bar_frame = tk.Frame(self.root, bg=CLR["border"], height=SKAL.s(8), width=SKAL.s(300))
        bar_frame.pack(pady=(SKAL.s(0), SKAL.s(14)))
        bar_frame.pack_propagate(False)
        perc  = xp_ak / xp_nx if xp_nx else 1
        bar_w = int(300 * perc)
        if bar_w > 0:
            tk.Frame(bar_frame, bg=CLR["xp"], height=SKAL.s(8), width=bar_w).place(x=0, y=0)

        btn_cfg = {"font": ("Arial", 13, "bold"), "relief": "flat",
                   "padx": 0, "pady": 13, "cursor": "hand2", "width": 28}
        tk.Button(self.root, text=t(ui, "vok_menue_titel"), bg=CLR["blue"], fg="white",
                  command=self.zeige_vokabeln_menue, **btn_cfg).pack(pady=SKAL.s(3))
        tk.Button(self.root, text=t(ui, "statistik"),  bg="#16a085", fg="white",
                  command=self.zeige_statistik, **btn_cfg).pack(pady=SKAL.s(3))
        tk.Button(self.root, text=t(ui, "saetze"),      bg="#d35400", fg="white",
                  command=self.zeige_saetze_menue, **btn_cfg).pack(pady=SKAL.s(3))
        tk.Button(self.root, text=t(ui, "freischaltungen"), bg="#8e44ad", fg="white",
                  command=self.zeige_freischaltungen, **btn_cfg).pack(pady=SKAL.s(3))
        shop_s = shop_laden()
        tk.Button(self.root, text=f"🛒  Shop  ·  {shop_s.get('coins', 0)} Coins", bg="#f1c40f", fg="#3a2f00",
                  command=self.zeige_shop, **btn_cfg).pack(pady=SKAL.s(3))
        tk.Button(self.root, text=t(ui, "falsche_woerter_titel"), bg=CLR["red"], fg="white",
                  command=self.zeige_falsche_woerter_test, **btn_cfg).pack(pady=SKAL.s(3))
        tk.Button(self.root, text=t(ui, "markierte_woerter_titel"), bg="#c0392b", fg="white",
                  command=self.zeige_markierte_woerter_test, **btn_cfg).pack(pady=SKAL.s(3))
        tk.Button(self.root, text=t(ui, "trenn_woerter_titel"), bg="#2980b9", fg="white",
                  command=self.zeige_trenn_woerter_liste, **btn_cfg).pack(pady=SKAL.s(3))
        tk.Button(self.root, text=t(ui, "big_story_titel"), bg="#1abc9c", fg="white",
                  command=self.zeige_big_story_sprachwahl, **btn_cfg).pack(pady=SKAL.s(3))
        tk.Button(self.root, text=t(ui, "bugs_titel"), bg="#7f8c8d", fg="white",
                  command=self.zeige_bugs, **btn_cfg).pack(pady=SKAL.s(3))
        tk.Button(self.root, text=t(ui, "sprache_aendern"),
                  font=fnt(11, "bold"), bg=CLR["bg"], fg=CLR["text"], relief="flat",
                  cursor="hand2", command=self.zeige_ui_auswahl).pack(pady=(SKAL.s(10), SKAL.s(0)))

        self.root = root

    def zeige_trenn_woerter_liste(self):
        ui, ls = self.ui, self.ls
        self._aktuelle_ansicht = self.zeige_trenn_woerter_liste
        self.clear()
        if self.root.winfo_width() <= 1:
            self.root.geometry("460x600")
            SKAL.setze_basis(460, 600)

        tk.Label(self.root, text=t(ui, "trenn_woerter_titel"), font=fnt(16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(SKAL.s(20), SKAL.s(4)))

        alle_sprachen = ["de", "en", "fi"]
        markiert_vok = []
        markiert_satz = []
        for sp in alle_sprachen:
            for v in vokabeln_laden(sp):
                if v.get("abc", False):
                    markiert_vok.append((sp, v))
            for sset in saetze_laden(sp):
                if sset.get("abc", False):
                    markiert_satz.append((sp, sset))

        aussen = tk.Frame(self.root, bg=CLR["bg"])
        aussen.pack(fill="both", expand=True, padx=SKAL.s(10))
        canvas = tk.Canvas(aussen, bg=CLR["bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(aussen, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=CLR["bg"])
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        if not markiert_vok and not markiert_satz:
            tk.Label(scroll_frame, text="Noch keine Wörter/Sätze markiert.",
                     font=fnt(12), bg=CLR["bg"], fg=CLR["sub"]).pack(pady=20)

        flag = {"de": "🇩🇪", "en": "🇬🇧", "fi": "🇫🇮"}
        for sp, vok_item in markiert_vok:
            zeile = tk.Frame(scroll_frame, bg=CLR["row_a"],
                             highlightbackground=CLR["card_border"], highlightthickness=2)
            zeile.pack(fill="x", pady=SKAL.s(1))
            tk.Label(zeile, text=flag.get(sp, sp), font=fnt(11),
                     bg=CLR["row_a"], fg=CLR["text"], width=2, anchor="w").pack(side="left", padx=SKAL.s(4), pady=SKAL.s(5))
            tk.Label(zeile, text=vok_item.get("lern", ""), font=fnt(11, "bold"),
                     bg=CLR["row_a"], fg=CLR["text"], width=18, anchor="w").pack(side="left", padx=SKAL.s(6), pady=SKAL.s(5))
            abc_btn = tk.Label(zeile, text="🔤", font=fnt(13),
                               bg=CLR["row_a"], fg=CLR["blue"], width=2, cursor="hand2")
            abc_btn.pack(side="left", padx=SKAL.s(1))
            abc_btn.bind("<Button-1>", lambda e, v=vok_item, s=sp: self._abc_kaestchen_oeffnen(
                v.get("lern", ""), s, vok=v, bearbeitbar=True,
                beim_schliessen=self.zeige_trenn_woerter_liste))

        for sp, satz_item in markiert_satz:
            zeile = tk.Frame(scroll_frame, bg=CLR["row_b"],
                             highlightbackground=CLR["card_border"], highlightthickness=2)
            zeile.pack(fill="x", pady=SKAL.s(1))
            tk.Label(zeile, text=flag.get(sp, sp), font=fnt(11),
                     bg=CLR["row_b"], fg=CLR["text"], width=2, anchor="w").pack(side="left", padx=SKAL.s(4), pady=SKAL.s(5))
            tk.Label(zeile, text=satz_item.get("lern", ""), font=fnt(11, "bold"),
                     bg=CLR["row_b"], fg=CLR["text"], width=18, anchor="w",
                     wraplength=180).pack(side="left", padx=SKAL.s(6), pady=SKAL.s(5))
            abc_btn = tk.Label(zeile, text="🔤", font=fnt(13),
                               bg=CLR["row_b"], fg=CLR["blue"], width=2, cursor="hand2")
            abc_btn.pack(side="left", padx=SKAL.s(1))
            abc_btn.bind("<Button-1>", lambda e, s_item=satz_item, s=sp: self._satz_abc_fenster_oeffnen_von_liste(s_item, s))

        tk.Button(self.root, text=t(ui, "zurueck"), font=fnt(12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=SKAL.s(20), pady=SKAL.s(10),
                  cursor="hand2", command=self.zeige_hauptmenue).pack(pady=(SKAL.s(10), SKAL.s(10)))

    def _satz_abc_fenster_oeffnen_von_liste(self, satz_item, sprache=None):
        ls = sprache if sprache is not None else self.ls
        self._satz_abc_kaestchen_oeffnen(satz_item, ls, bearbeitbar=True,
                                         beim_schliessen=self.zeige_trenn_woerter_liste)

    def zeige_falsche_woerter_test(self):
        ui, ls = self.ui, self.ls
        vok = vokabeln_laden(ls)
        s   = stats_laden()
        ws  = s.get("wort_stats", {})
        falsche_keys = {k for k, st in ws.items() if st.get("falsch", 0) > 0}
        auswahl = [v for v in vok if v.get("nativ", "") in falsche_keys]
        if not auswahl:
            messagebox.showinfo(t(ui, "keine_titel"), t(ui, "falsche_keine"))
            return
        random.shuffle(auswahl)
        self.zeige_test(False, auswahl=auswahl)

    def zeige_markierte_woerter_test(self):
        ui, ls = self.ui, self.ls
        vok = vokabeln_laden(ls)
        auswahl = [v for v in vok if v.get("gewusst", False)]
        if not auswahl:
            messagebox.showinfo(t(ui, "keine_titel"), t(ui, "alle_gewusst"))
            return
        random.shuffle(auswahl)
        self.zeige_test(False, auswahl=auswahl)

    def zeige_bugs(self):
        ui = self.ui
        self._aktuelle_ansicht = self.zeige_bugs
        self.clear()
        if self.root.winfo_width() <= 1:
            self.root.geometry("460x420")
            SKAL.setze_basis(460, 420)

        tk.Label(self.root, text=t(ui, "bugs_titel"), font=fnt(16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(SKAL.s(28), SKAL.s(4)))
        tk.Label(self.root, text=t(ui, "bugs_hinweis"), font=fnt(10),
                 bg=CLR["bg"], fg=CLR["sub"], wraplength=380, justify="center").pack(pady=(SKAL.s(0), SKAL.s(16)))

        f_bug = tk.Frame(self.root, bg=CLR["white"],
                         highlightbackground=CLR["card_border"], highlightthickness=2)
        f_bug.pack(padx=30, fill="x", pady=(0, 10))
        bug_text = tk.Text(f_bug, font=("Arial", 12), height=8, wrap="word",
                           fg=CLR["entry_fg"], bd=0, highlightthickness=0,
                           bg=CLR["entry_bg"], padx=10, pady=8,
                           insertbackground=CLR["entry_ins"])
        bug_text.pack(fill="x", padx=6, pady=6)
        bug_text.insert("1.0", "")

        lbl_status = tk.Label(self.root, text="", font=fnt(11),
                              bg=CLR["bg"], fg="#27ae60")
        lbl_status.pack(pady=(0, 6))

        def bug_senden():
            text = bug_text.get("1.0", tk.END).strip()
            if not text:
                return
            tracking_senden("bug_meldung", sprache=self.ls, text=text)
            bug_text.delete("1.0", tk.END)
            lbl_status.config(text=t(ui, "bugs_gespeichert"))

        row = make_frame(self.root)
        row.pack()
        tk.Button(row, text=t(ui, "bugs_speichern"), font=fnt(12, "bold"),
                  bg=CLR["blue"], fg="white", relief="flat", padx=SKAL.s(18), pady=SKAL.s(8),
                  cursor="hand2", command=bug_senden).pack(side="left", padx=6)
        tk.Button(row, text=t(ui, "zurueck"), font=fnt(12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=SKAL.s(14), pady=SKAL.s(8),
                  cursor="hand2", command=self.zeige_hauptmenue).pack(side="left", padx=6)

        bug_text.focus()

    def zeige_big_story_sprachwahl(self):
        """Fragt bei jedem Aufruf von Big Story erneut, in welcher Sprache
        gelesen/geuebt werden soll (unabhaengig von der App-weiten
        Lernsprache self.ls). Die Wahl gilt nur fuer diese Sitzung und wird
        NICHT dauerhaft gespeichert."""
        ui = self.ui
        self._aktuelle_ansicht = self.zeige_big_story_sprachwahl
        self.clear()
        if self.root.winfo_width() <= 1:
            self.root.geometry("440x380")
            SKAL.setze_basis(440, 380)

        tk.Label(self.root, text=t(ui, "big_story_titel"), font=fnt(16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(SKAL.s(28), SKAL.s(8)))
        tk.Label(self.root, text=t(ui, "lern_frage"),
                 font=fnt(13, "bold"), bg=CLR["bg"], fg=CLR["text"]).pack(pady=(SKAL.s(10), SKAL.s(24)))

        for code, col in [("de", CLR["blue"]), ("en", CLR["green"]), ("fi", CLR["red"])]:
            flag = {"de": "🇩🇪", "en": "🇬🇧", "fi": "🇫🇮"}[code]
            tk.Button(self.root, text=f"{flag}   {langname(ui, code)}",
                      font=fnt(13, "bold"), bg=col, fg="white", relief="flat",
                      padx=SKAL.s(0), pady=SKAL.s(12), cursor="hand2", width=20,
                      command=lambda c=code: self._big_story_sprache_gewaehlt(c)).pack(pady=SKAL.s(4))

        tk.Button(self.root, text=t(ui, "zurueck"), font=fnt(12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=SKAL.s(14), pady=SKAL.s(8),
                  cursor="hand2", command=self.zeige_hauptmenue).pack(pady=(SKAL.s(24), SKAL.s(10)))

    def _big_story_sprache_gewaehlt(self, code):
        self._bst_sprache = code
        self.zeige_big_story()

    def zeige_big_story(self):
        ui = self.ui
        if not getattr(self, "_bst_sprache", None):
            self.zeige_big_story_sprachwahl()
            return
        self._aktuelle_ansicht = self.zeige_big_story
        self.clear()
        if self.root.winfo_width() <= 1:
            self.root.geometry("460x600")
            SKAL.setze_basis(460, 600)

        tk.Label(self.root, text=t(ui, "big_story_titel"), font=fnt(16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(SKAL.s(28), SKAL.s(4)))

        flag = {"de": "🇩🇪", "en": "🇬🇧", "fi": "🇫🇮"}.get(self._bst_sprache, "")
        tk.Button(self.root, text=f"{flag}  {langname(ui, self._bst_sprache)}  ✎",
                  font=fnt(10, "bold"), bg=CLR["light"], fg=CLR["text"], relief="flat",
                  padx=SKAL.s(10), pady=SKAL.s(4), cursor="hand2",
                  command=self.zeige_big_story_sprachwahl).pack(pady=(SKAL.s(0), SKAL.s(4)))

        daten = big_story_laden()
        teile = daten.get("teile", [])

        if not teile:
            tk.Label(self.root, text=t(ui, "big_story_hinweis"), font=fnt(10),
                     bg=CLR["bg"], fg=CLR["sub"], wraplength=380, justify="center").pack(pady=(SKAL.s(0), SKAL.s(16)))
        else:
            tk.Frame(self.root, bg=CLR["bg"], height=SKAL.s(10)).pack()

        liste_frame = tk.Frame(self.root, bg=CLR["bg"])
        liste_frame.pack(pady=(0, SKAL.s(6)))

        for idx in range(len(teile)):
            row = tk.Frame(liste_frame, bg=CLR["bg"])
            row.pack(pady=SKAL.s(3))

            tk.Button(row, text=f"📖  {t(ui, 'big_story_teil', n=idx + 1)}",
                      font=("Arial", 12, "bold"), bg="#1abc9c", fg="white",
                      relief="flat", padx=SKAL.s(14), pady=SKAL.s(10), width=20,
                      cursor="hand2",
                      command=lambda i=idx: self.zeige_big_story_teil(i)
                      ).pack(side="left", padx=(0, 6))

            tk.Button(row, text="🗑️", font=("Arial", 12, "bold"),
                      bg=CLR["red"], fg="white", relief="flat",
                      padx=SKAL.s(10), pady=SKAL.s(10), cursor="hand2",
                      command=lambda i=idx: self._big_story_teil_loeschen(i)
                      ).pack(side="left")

        tk.Button(self.root, text=t(ui, "big_story_neuer_teil"), font=fnt(13, "bold"),
                  bg=CLR["blue"], fg="white", relief="flat", padx=SKAL.s(18), pady=SKAL.s(10),
                  cursor="hand2", command=self._big_story_teil_hinzufuegen).pack(pady=SKAL.s(14))

        tk.Button(self.root, text=t(ui, "zurueck"), font=fnt(12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=SKAL.s(14), pady=SKAL.s(8),
                  cursor="hand2", command=self.zeige_hauptmenue).pack(pady=SKAL.s(10))

    def _big_story_teil_hinzufuegen(self):
        daten = big_story_laden()
        daten["teile"].append({})
        big_story_speichern(daten)
        self.zeige_big_story()

    def _big_story_teil_loeschen(self, index):
        ui = self.ui
        if not messagebox.askyesno(t(ui, "big_story_titel"), t(ui, "big_story_loeschen_frage")):
            return
        daten = big_story_laden()
        if 0 <= index < len(daten["teile"]):
            daten["teile"].pop(index)
            big_story_speichern(daten)
        self.zeige_big_story()

    def zeige_big_story_teil(self, index, echter_einstieg=True):
        ui = self.ui
        self._aktuelle_ansicht = lambda: self.zeige_big_story_teil(index, echter_einstieg=False)
        self.clear()
        if self.root.winfo_width() <= 1:
            self.root.geometry("460x600")
            SKAL.setze_basis(460, 600)

        daten = big_story_laden()
        teile = daten.get("teile", [])
        if not (0 <= index < len(teile)):
            self.zeige_big_story()
            return

        tk.Label(self.root, text=t(ui, "big_story_teil", n=index + 1), font=fnt(16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(SKAL.s(20), SKAL.s(8)))

        container = make_frame(self.root)
        container.pack(padx=SKAL.s(16), fill="both", expand=True)
        canvas    = tk.Canvas(container, bg=CLR["bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self._bst_scroll_frame = make_frame(canvas)
        self._bst_scroll_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        _bst_fenster_id = canvas.create_window((0, 0), window=self._bst_scroll_frame, anchor="nw")
        # Breite des inneren Frames an die Canvas-Breite binden, damit der
        # Fliesstext (wrap="word") innerhalb der sichtbaren Breite umbricht
        # und Dropdowns nicht ueber den rechten Rand hinausragen.
        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(_bst_fenster_id, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            try:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self._bst_index = index
        if echter_einstieg:
            gespeicherte_seite = story_fortschritt_holen(self._bst_sprache, index)
            if gespeicherte_seite is not None and gespeicherte_seite > 0:
                weiter = messagebox.askyesno(
                    t(ui, "big_story_teil", n=index + 1),
                    t(ui, "big_story_fortschritt_frage"),
                )
                self._bst_seite = gespeicherte_seite if weiter else 0
            else:
                self._bst_seite = 0
        # bei einem Redraw durch Fenster-Resize/Minimieren bleibt self._bst_seite
        # unveraendert (kein erneuter Ja/Nein-Dialog, kein Reset auf Seite 0)

        _bst_btn_aussen = make_frame(self.root)
        _bst_btn_aussen.pack(fill="x", pady=SKAL.s(8), padx=SKAL.s(6))
        _bst_btn_canvas = tk.Canvas(_bst_btn_aussen, bg=CLR["bg"], highlightthickness=0,
                                     height=SKAL.s(44))
        _bst_btn_scrollbar = tk.Scrollbar(_bst_btn_aussen, orient="horizontal",
                                           command=_bst_btn_canvas.xview)
        _bst_btn_canvas.configure(xscrollcommand=_bst_btn_scrollbar.set)
        _bst_btn_canvas.pack(side="top", fill="x")
        _bst_btn_scrollbar.pack(side="top", fill="x")
        btn_row = make_frame(_bst_btn_canvas)
        _bst_btn_fenster_id = _bst_btn_canvas.create_window((0, 0), window=btn_row, anchor="nw")
        def _bst_btn_scrollregion_aktualisieren(event=None):
            _bst_btn_canvas.configure(scrollregion=_bst_btn_canvas.bbox("all"))
        btn_row.bind("<Configure>", _bst_btn_scrollregion_aktualisieren)
        _bst_btn_canvas.bind("<Configure>", _bst_btn_scrollregion_aktualisieren)

        s_bst = stats_laden()
        xp_bst = s_bst.get("level_xp", 0)
        lvl_bst, xp_ak_bst, xp_nx_bst = xp_fortschritt(xp_bst)
        shop_bst = shop_laden()
        xp_kasten = tk.Frame(btn_row, bg=CLR["white"],
                              highlightbackground=CLR["card_border"], highlightthickness=2)
        xp_kasten.pack(side="left", padx=SKAL.s(6))
        self._bst_lbl_xp = tk.Label(xp_kasten,
                 text=f"\u2b50 {lvl_bst} | {xp_ak_bst}/{xp_nx_bst} XP | \U0001FA99{shop_bst.get('coins', 0)}",
                 font=fnt(9, "bold"), bg=CLR["white"], fg=CLR["xp"])
        self._bst_lbl_xp.pack(padx=SKAL.s(8), pady=SKAL.s(4))

        def _bst_zurueck_zur_uebersicht():
            story_fortschritt_setzen(self._bst_sprache, self._bst_index, self._bst_seite)
            self.zeige_big_story()

        tk.Button(btn_row, text=t(ui, "zurueck"), font=fnt(12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=SKAL.s(14), pady=SKAL.s(8),
                  cursor="hand2", command=_bst_zurueck_zur_uebersicht).pack(side="left", padx=SKAL.s(6))

        tk.Frame(btn_row, bg=CLR["border"], width=2).pack(side="left", fill="y", padx=SKAL.s(12))

        def _bst_seite_wechseln(delta):
            self._bst_seite += delta
            story_fortschritt_setzen(self._bst_sprache, self._bst_index, self._bst_seite)
            self._bst_aufbauen()

        self._bst_btn_zurueck = tk.Button(btn_row, text=t(ui, "bear_zurueck_kurz"), font=fnt(11, "bold"),
                  bg=CLR["blue"], fg="white", relief="flat", padx=SKAL.s(14), pady=SKAL.s(6),
                  cursor="hand2", command=lambda: _bst_seite_wechseln(-1))
        self._bst_btn_zurueck.pack(side="left", padx=SKAL.s(6))

        self._bst_lbl_seite = tk.Label(btn_row, text=t(ui, "bear_seite", i=1, n=1),
                 font=fnt(11, "bold"), bg=CLR["bg"], fg=CLR["sub"])
        self._bst_lbl_seite.pack(side="left", padx=SKAL.s(10))

        self._bst_btn_weiter = tk.Button(btn_row, text=t(ui, "bear_weiter_kurz"), font=fnt(11, "bold"),
                  bg=CLR["blue"], fg="white", relief="flat", padx=SKAL.s(14), pady=SKAL.s(6),
                  cursor="hand2", command=lambda: _bst_seite_wechseln(1))
        self._bst_btn_weiter.pack(side="left", padx=SKAL.s(6))

        tk.Frame(btn_row, bg=CLR["border"], width=2).pack(side="left", fill="y", padx=SKAL.s(12))

        tk.Button(btn_row, text=t(ui, 'inv_titel'), font=fnt(11, "bold"),
                  bg=CLR["light"], fg=CLR["text"], relief="flat", padx=SKAL.s(10), pady=SKAL.s(6),
                  cursor="hand2", command=self.zeige_inventar).pack(side="left", padx=SKAL.s(6))

        self._bst_joker_verfuegbar = shop_laden().get("inventar", {}).get("joker", 0) > 0
        self._bst_joker_aktiv = False
        self._bst_btn_joker = tk.Button(btn_row, text=t(ui, "joker_btn"), font=fnt(11, "bold"),
                  bg="#8e44ad", fg="white", relief="flat", padx=SKAL.s(10), pady=SKAL.s(6),
                  cursor="hand2", command=self._bst_joker_nutzen)
        self._bst_btn_joker.pack(side="left", padx=SKAL.s(6))
        if not self._bst_joker_verfuegbar:
            self._bst_btn_joker.config(state="disabled", bg="#7f8c8d")

        self._bst_btn_fertig = tk.Button(btn_row, text=t(ui, "big_story_fertig"), font=fnt(11, "bold"),
                  bg="#2c3e50", fg="white", relief="flat", padx=SKAL.s(10), pady=SKAL.s(6),
                  cursor="hand2", command=self._bst_fertig)
        self._bst_btn_fertig.pack(side="left", padx=SKAL.s(6))

        self._bst_aufbauen()

    def _bst_xp_anzeige_aktualisieren(self):
        """Aktualisiert den Level/XP/Coins-Kasten oben in der Big-Story-Ansicht
        live, nachdem XP oder Coins vergeben/abgezogen wurden."""
        if not hasattr(self, "_bst_lbl_xp") or not self._bst_lbl_xp.winfo_exists():
            return
        s = stats_laden()
        lvl, xp_ak, xp_nx = xp_fortschritt(s.get("level_xp", 0))
        coins = shop_laden().get("coins", 0)
        self._bst_lbl_xp.config(text=f"\u2b50 {lvl} | {xp_ak}/{xp_nx} XP | \U0001FA99{coins}")

    def _bst_aufbauen(self):
        if not hasattr(self, "_bst_scroll_frame") or not self._bst_scroll_frame.winfo_exists():
            return
        ui = self.ui
        for w in self._bst_scroll_frame.winfo_children():
            w.destroy()

        # Joker-Status pro Seite neu ermitteln (1x nutzbar pro Seite, nur
        # solange noch mindestens 1 Joker im Inventar vorhanden ist).
        self._bst_joker_verfuegbar = shop_laden().get("inventar", {}).get("joker", 0) > 0
        self._bst_joker_aktiv = False
        if hasattr(self, "_bst_btn_joker") and self._bst_btn_joker.winfo_exists():
            if self._bst_joker_verfuegbar:
                self._bst_btn_joker.config(text=t(ui, "joker_btn"), state="normal", bg="#8e44ad")
            else:
                self._bst_btn_joker.config(text=t(ui, "joker_btn"), state="disabled", bg="#7f8c8d")

        if hasattr(self, "_bst_btn_fertig") and self._bst_btn_fertig.winfo_exists():
            self._bst_btn_fertig.config(state="normal", bg="#2c3e50")

        seiten = big_story_seiten_holen(self._bst_sprache, self._bst_index)
        gesamt_seiten = max(1, len(seiten))
        self._bst_seite = max(0, min(self._bst_seite, gesamt_seiten - 1))

        if not seiten:
            tk.Label(self._bst_scroll_frame, text="", font=fnt(12),
                     bg=CLR["bg"], fg=CLR["sub"]).pack(pady=SKAL.s(20))
        else:
            seite = seiten[self._bst_seite]
            self._bst_auswahl = {}
            self._bst_fluss_aufbauen(seite)

        self._bst_lbl_seite.config(text=t(ui, "bear_seite", i=self._bst_seite + 1, n=gesamt_seiten))
        self._bst_btn_zurueck.config(state="normal" if self._bst_seite > 0 else "disabled")
        self._bst_btn_weiter.config(state="normal" if self._bst_seite < gesamt_seiten - 1 else "disabled")

    def _bst_fluss_aufbauen(self, seite):
        """Baut den Fliesstext der Seite auf: normaler Text + an jeder Luecke
        ein Dropdown (OptionMenu) mit 4 zufaellig gemischten Woertern (1
        richtig, 3 falsch), initial ohne Auswahl angezeigt."""
        ui = self.ui
        text = seite["text"]
        luecken = seite["luecken"]

        fluss = tk.Frame(self._bst_scroll_frame, bg=CLR["bg"])
        fluss.pack(fill="x", padx=SKAL.s(4), pady=SKAL.s(10))

        # Text an den {n}-Platzhaltern in Stuecke zerlegen, dabei die Reihenfolge
        # der Luecken-Indizes im Text erhalten.
        teile = []
        rest = text
        i = 0
        while True:
            marker = "{" + str(i) + "}"
            pos = rest.find(marker)
            if pos == -1:
                teile.append(("text", rest))
                break
            teile.append(("text", rest[:pos]))
            teile.append(("luecke", i))
            rest = rest[pos + len(marker):]
            i += 1

        # Ein Text-Widget uebernimmt Wort-Wrap fuer den Fliesstext, mit
        # eingebetteten OptionMenu-Dropdowns direkt an den Luecken-Stellen.
        txt_widget = tk.Text(fluss, wrap="word", font=fnt(13), bg=CLR["bg"],
                              fg=CLR["text"], bd=0, highlightthickness=0,
                              padx=SKAL.s(4), pady=SKAL.s(4), cursor="arrow",
                              height=1)
        txt_widget.pack(fill="both", expand=True)

        for art, inhalt in teile:
            if art == "text":
                txt_widget.insert("end", inhalt)
            else:
                idx = inhalt
                richtig, falsche = luecken[idx]
                optionen = falsche + [richtig]
                random.shuffle(optionen)
                var = tk.StringVar(value="────────")
                self._bst_auswahl[idx] = {"var": var, "richtig": richtig}
                menu = tk.OptionMenu(txt_widget, var, *optionen)
                menu.config(font=fnt(11, "bold"), bg=CLR["blue"], fg="white",
                            relief="flat", cursor="hand2", highlightthickness=0)
                menu["menu"].config(font=fnt(11))
                menu.bind("<Button-1>", lambda e, i=idx: self._bst_luecke_geklickt(i), add="+")
                var.trace_add("write", lambda *a: self._bst_auswahl_zaehler_aktualisieren())
                self._bst_auswahl[idx]["menu"] = menu
                txt_widget.window_create("end", window=menu)

        # Hoehe des Text-Widgets an den Inhalt anpassen (kein Scrollbalken,
        # Seite soll komplett ohne Scrollen sichtbar sein).
        txt_widget.update_idletasks()
        zeilen = int(txt_widget.index("end-1c").split(".")[0])
        txt_widget.config(height=max(4, min(zeilen + 1, 14)), state="disabled")

        self._bst_zaehler_lbl = tk.Label(fluss, text="", font=fnt(10),
                                          bg=CLR["bg"], fg=CLR["sub"])
        self._bst_zaehler_lbl.pack(pady=(SKAL.s(2), SKAL.s(0)))
        self._bst_auswahl_zaehler_aktualisieren()

        self._bst_fehler_lbl = tk.Label(fluss, text="", font=fnt(11, "bold"),
                                         bg=CLR["bg"], fg=CLR["red"])
        self._bst_fehler_lbl.pack(pady=(SKAL.s(10), SKAL.s(4)))

    def _bst_auswahl_zaehler_aktualisieren(self):
        """Aktualisiert die Anzeige 'X von Y ausgewaehlt' unter dem Fliesstext,
        basierend darauf wie viele Luecken-Dropdowns bereits eine Auswahl
        (ungleich dem Platzhalter-Strich) haben."""
        if not hasattr(self, "_bst_auswahl") or not hasattr(self, "_bst_zaehler_lbl"):
            return
        try:
            if not self._bst_zaehler_lbl.winfo_exists():
                return
        except tk.TclError:
            return
        gesamt = len(self._bst_auswahl)
        ausgewaehlt = sum(
            1 for info in self._bst_auswahl.values()
            if info["var"].get() != "────────"
        )
        ui = self.ui
        self._bst_zaehler_lbl.config(text=t(ui, "bst_auswahl_zaehler", n=ausgewaehlt, g=gesamt))

    def _bst_joker_nutzen(self):
        """Aktiviert den Joker-Klick-Modus: der naechste Klick auf eine Luecke
        fuellt dort automatisch die richtige Antwort ein und verbraucht 1
        Joker aus dem Inventar. Nur 1x pro Seite nutzbar, nur solange noch
        mindestens 1 Joker im Inventar vorhanden ist."""
        if not self._bst_joker_verfuegbar or self._bst_joker_aktiv:
            return
        self._bst_joker_aktiv = True
        ui = self.ui
        self._bst_btn_joker.config(text=t(ui, "joker_angewendet"), state="disabled", bg="#7f8c8d")

    def _bst_luecke_geklickt(self, idx):
        """Wird bei jedem Klick auf eine Luecke aufgerufen. Falls der Joker
        aktiv ist, wird hier die richtige Antwort eingefuellt und der Joker
        aus dem Inventar verbraucht."""
        if not getattr(self, "_bst_joker_aktiv", False):
            return
        info = self._bst_auswahl.get(idx)
        if not info:
            return
        s = shop_laden()
        if s.get("inventar", {}).get("joker", 0) <= 0:
            self._bst_joker_verfuegbar = False
            return
        s["inventar"]["joker"] = s["inventar"].get("joker", 0) - 1
        shop_speichern(s)
        tracking_senden("joker_benutzt", sprache=self.ls, bereich="big_story")
        info["var"].set(info["richtig"])
        self._bst_joker_aktiv = False
        self._bst_joker_verfuegbar = False

    def _bst_pruefen(self):
        """Prueft alle Luecken der aktuellen Seite. Fuer jede richtig
        beantwortete Luecke gibt es XP + Coins (wie im normalen Test), fuer
        falsche nichts. Zeigt an, wie viele falsch waren, oder bei allem
        richtig eine Erfolgsmeldung."""
        ui = self.ui
        if not hasattr(self, "_bst_auswahl"):
            return
        falsch = 0
        richtig_neu = 0
        for idx, info in self._bst_auswahl.items():
            gewaehlt = info["var"].get()
            if gewaehlt != info["richtig"]:
                falsch += 1
            elif not info.get("belohnt", False):
                info["belohnt"] = True
                richtig_neu += 1
        if richtig_neu > 0:
            s = stats_laden()
            xp_gewinn = 10 * richtig_neu
            s["level_xp"] = s.get("level_xp", 0) + xp_gewinn
            stats_speichern(s)
            shop_coins_hinzufuegen(richtig_neu)
        if falsch == 0:
            self._bst_fehler_lbl.config(fg=CLR["green"], text="✓")
        else:
            self._bst_fehler_lbl.config(fg=CLR["red"], text=f"✗ {falsch}")
        self._bst_xp_anzeige_aktualisieren()

    def _bst_fertig(self):
        """Schliesst die Seite final ab: jede noch nicht belohnte richtige
        Luecke gibt XP+Coins (wie in _bst_pruefen), jede falsche ODER leere
        Luecke zieht XP ab (gleiche Formel wie im normalen Test-Modus:
        max(1, xp_basis // 2)). Danach werden alle Dropdowns gesperrt, es
        kann nichts mehr veraendert werden."""
        ui = self.ui
        if not hasattr(self, "_bst_auswahl"):
            return
        richtig_neu = 0
        falsch_neu = 0
        for idx, info in self._bst_auswahl.items():
            if info.get("fertig_ausgewertet", False):
                continue
            info["fertig_ausgewertet"] = True
            gewaehlt = info["var"].get()
            if gewaehlt == info["richtig"]:
                if not info.get("belohnt", False):
                    info["belohnt"] = True
                    richtig_neu += 1
            else:
                falsch_neu += 1
                tracking_senden("story_wort_falsch", sprache=getattr(self, "_bst_sprache", self.ls),
                                wort=info["richtig"])

        s = stats_laden()
        if richtig_neu > 0:
            xp_gewinn = 10 * richtig_neu
            s["level_xp"] = s.get("level_xp", 0) + xp_gewinn
            shop_coins_hinzufuegen(richtig_neu)
        if falsch_neu > 0:
            xp_verlust_je = max(1, 10 // 2)
            xp_verlust = xp_verlust_je * falsch_neu
            s["level_xp"] = max(0, s.get("level_xp", 0) - xp_verlust)
        stats_speichern(s)

        for idx, info in self._bst_auswahl.items():
            menu = info.get("menu")
            if menu is not None:
                try:
                    menu.config(state="disabled")
                except tk.TclError:
                    pass

        if hasattr(self, "_bst_btn_fertig") and self._bst_btn_fertig.winfo_exists():
            self._bst_btn_fertig.config(state="disabled", bg="#7f8c8d")

        if falsch_neu == 0:
            self._bst_fehler_lbl.config(fg=CLR["green"], text="✓")
        else:
            self._bst_fehler_lbl.config(fg=CLR["red"], text=f"✗ {falsch_neu}")
        self._bst_xp_anzeige_aktualisieren()

    def zeige_richtung(self, modus):
        ui, ls = self.ui, self.ls
        if not vokabeln_laden(ls):
            messagebox.showinfo(t(ui, "keine_titel"), t(ui, "keine_vok"))
            return
        self._aktuelle_ansicht = lambda: self.zeige_richtung(modus)
        self.clear()

        s   = stats_laden()
        xp  = s.get("level_xp", 0)
        lvl = berechne_level(xp)
        hat_gemischt = hat_freischaltung("gemischt")
        hat_blitz    = True if modus == "lernen" else hat_freischaltung("blitz_modus")
        hat_mc       = True if modus == "lernen" else hat_freischaltung("mehrfach_wahl")
        hat_artikel  = (ls == "de")
        hoehe = 460
        if hat_gemischt: hoehe += 60
        if hat_blitz:    hoehe += 60
        if hat_mc:       hoehe += 60
        if hat_artikel:  hoehe += 60
        hoehe = min(hoehe, 620)
        if self.root.winfo_width() <= 1:
            self.root.geometry(f"460x{hoehe}")
            SKAL.setze_basis(460, hoehe)

        _rc_canvas = tk.Canvas(self.root, bg=CLR["bg"], highlightthickness=0)
        _rc_scrollbar = tk.Scrollbar(self.root, orient="vertical", command=_rc_canvas.yview)
        _rc_inner = tk.Frame(_rc_canvas, bg=CLR["bg"])

        _rc_inner.bind("<Configure>", lambda e: _rc_canvas.configure(scrollregion=_rc_canvas.bbox("all")))
        _rc_window = _rc_canvas.create_window((0, 0), window=_rc_inner, anchor="n")
        _rc_canvas.configure(yscrollcommand=_rc_scrollbar.set)

        def _rc_center(event):
            _rc_canvas.itemconfig(_rc_window, width=event.width)
        _rc_canvas.bind("<Configure>", _rc_center)

        def _rc_mousewheel(event):
            _rc_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        _rc_canvas.bind_all("<MouseWheel>", _rc_mousewheel)

        _rc_canvas.pack(side="left", fill="both", expand=True)
        _rc_scrollbar.pack(side="right", fill="y")

        root = self.root
        self.root = _rc_inner

        mutter  = muttersprache_label(ui)
        lsname  = langname(ui, ls)
        flag_ls = {"de": "🇩🇪", "en": "🇬🇧", "fi": "🇫🇮"}[ls]
        flag_ui = {"de": "🇩🇪", "en": "🇬🇧", "fi": "🇫🇮"}[ui]

        header = t(ui, "lernen") if modus == "lernen" else t(ui, "test")
        tk.Label(self.root, text=header, font=fnt(16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(SKAL.s(28), SKAL.s(4)))
        tk.Label(self.root, text=t(ui, "richtung_titel"),
                 font=fnt(11), bg=CLR["bg"], fg=CLR["sub"]).pack(pady=(SKAL.s(0), SKAL.s(14)))

        def karte(zeile1, zeile2, col, cb, deaktiviert=False):
            rahmen_col = CLR["gray"] if deaktiviert else col
            bg_col     = CLR["gray"] if deaktiviert else CLR["white"]
            f = tk.Frame(self.root, bg=bg_col,
                         highlightbackground=rahmen_col, highlightthickness=2,
                         cursor="arrow" if deaktiviert else "hand2")
            f.pack(padx=SKAL.s(40), fill="x", pady=SKAL.s(6))
            inner = tk.Frame(f, bg=bg_col)
            inner.pack(padx=SKAL.s(16), pady=SKAL.s(13), fill="x")
            if deaktiviert:
                row = tk.Frame(inner, bg=bg_col)
                row.pack()
                tk.Label(row, text="\u2715", font=fnt(20, "bold"),
                         bg=bg_col, fg=CLR["sub"]).pack(side="left", padx=(0, SKAL.s(10)))
                textcol = tk.Frame(row, bg=bg_col)
                textcol.pack(side="left")
                tk.Label(textcol, text=zeile1, font=fnt(13, "bold"),
                         bg=bg_col, fg=CLR["sub"]).pack()
                tk.Label(textcol, text=zeile2, font=fnt(10),
                         bg=bg_col, fg=CLR["sub"]).pack()
                return
            l1 = tk.Label(inner, text=zeile1, font=fnt(13, "bold"),
                          bg=bg_col, fg=CLR["text"])
            l1.pack()
            l2 = tk.Label(inner, text=zeile2, font=fnt(10),
                          bg=bg_col, fg=CLR["sub"])
            l2.pack()
            for w in [f, inner, l1, l2]:
                w.bind("<Button-1>", lambda e: cb())

        karte(f"{flag_ui} {mutter}   →   {flag_ls} {lsname}",
              t(ui, "richtung_normal_kurz"), CLR["green"],
              lambda: self._start(modus, False))
        karte(f"{flag_ls} {lsname}   →   {flag_ui} {mutter}",
              t(ui, "richtung_umgekehrt_kurz"), CLR["orange"],
              lambda: self._start(modus, True))

        if hat_gemischt:
            karte(f"{flag_ui} ↔ {flag_ls}  {t(ui, 'richtung_gemischt_titel')}",
                  t(ui, "richtung_gemischt_kurz"), CLR["blue"],
                  lambda: self._start(modus, "gemischt"))

        karte(f"{flag_ui} ⇄ {flag_ls}  {t(ui, 'richtung_mix_titel')}",
              t(ui, "mix_kurz"), "#1abc9c",
              lambda: self._start(modus, "mix"))

        karte(f"⚡ {t(ui, 'blitz_kurz_titel')}",
              t(ui, "blitz_titel"), "#c0392b",
              lambda: self._start("blitz", False),
              deaktiviert=not hat_blitz)

        karte("🎯 Multiple Choice",
              t(ui, "mc_titel"), "#2980b9",
              lambda: self._start("mc", False),
              deaktiviert=not hat_mc)

        if hat_artikel:
            karte("📚 Der/Die/Das",
                  t(ui, "artikel_titel"), "#8e44ad",
                  lambda: self._start("artikel", False))

        tk.Button(self.root, text=t(ui, "zurueck"), font=fnt(12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=SKAL.s(20), pady=SKAL.s(10),
                  cursor="hand2", command=self.zeige_hauptmenue).pack(pady=(SKAL.s(10), SKAL.s(6)))

        self.root = root

    def _start(self, modus, umgekehrt):
        if modus == "lernen":
            self.zeige_lernen(umgekehrt)
        elif modus == "blitz":
            self.zeige_lvl_auswahl(False, modus="blitz")
        elif modus == "mc":
            self.zeige_lvl_auswahl(False, modus="mc")
        elif modus == "artikel":
            self.zeige_lvl_auswahl(False, modus="artikel")
        elif umgekehrt == "mix":
            self.zeige_lvl_auswahl("mix")
        else:
            self.zeige_lvl_auswahl(umgekehrt)

    def zeige_lvl_auswahl(self, umgekehrt, modus="test"):
        ui, ls = self.ui, self.ls
        vok    = vokabeln_mit_artikel(ls) if modus == "artikel" else vokabeln_fuer_test(ls)
        if not vok:
            messagebox.showinfo(t(ui, "keine_titel"), t(ui, "keine_vok"))
            self.zeige_hauptmenue()
            return
        self._aktuelle_ansicht = lambda: self.zeige_lvl_auswahl(umgekehrt, modus=modus)
        self.clear()
        if self.root.winfo_width() <= 1:
            self.root.geometry("460x360")
            SKAL.setze_basis(460, 360)

        tk.Label(self.root, text=t(ui, "lvl_titel"), font=fnt(16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(SKAL.s(28), SKAL.s(4)))
        tk.Label(self.root, text=t(ui, "lvl_hint"),
                 font=fnt(10), bg=CLR["bg"], fg=CLR["sub"]).pack(pady=(SKAL.s(0), SKAL.s(16)))

        rf = make_frame(self.root)
        rf.pack()
        tk.Label(rf, text=t(ui, "lvl_prozent"), font=fnt(11, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(side="left", padx=(SKAL.s(0), SKAL.s(8)))
        proz_var   = tk.StringVar(value="100")
        proz_entry = tk.Entry(rf, textvariable=proz_var, font=fnt(14, "bold"),
                              width=5, justify="center",
                              fg=CLR["entry_fg"], bg=CLR["entry_bg"],
                              insertbackground=CLR["entry_ins"],
                              bd=1, relief="solid")
        proz_entry.pack(side="left")

        tk.Label(self.root, text=f"(max. {len(vok)} Wörter)",
                 font=fnt(10), bg=CLR["bg"], fg=CLR["sub"]).pack(pady=(SKAL.s(4), SKAL.s(16)))

        modus_var = tk.StringVar(value="schwach")
        for txt, val, col in [(t(ui, "lvl_schwach"), "schwach", CLR["orange"]),
                               (t(ui, "lvl_zufall"),  "zufall",  CLR["blue"])]:
            tk.Radiobutton(self.root, text=txt, variable=modus_var, value=val,
                           font=fnt(11), bg=CLR["bg"], fg=col,
                           activebackground=CLR["bg"], selectcolor=CLR["bg"],
                           cursor="hand2").pack(anchor="w", padx=SKAL.s(60))

        err_lbl = tk.Label(self.root, text="", font=fnt(10),
                           bg=CLR["bg"], fg=CLR["red"])
        err_lbl.pack(pady=(SKAL.s(8), SKAL.s(0)))

        def starten():
            try:
                p = int(proz_var.get().strip())
                assert 1 <= p <= 100
            except Exception:
                err_lbl.config(text=t(ui, "lvl_fehler"))
                return
            n      = max(1, math.ceil(len(vok) * p / 100))
            auswahl = self._wort_auswahl(vok, n, modus_var.get())
            if modus == "blitz":
                self.zeige_blitz(False, auswahl=auswahl)
            elif modus == "mc":
                self.zeige_mc(auswahl=auswahl)
            elif modus == "artikel":
                self.zeige_artikel(auswahl=auswahl)
            else:
                self.zeige_test(umgekehrt, auswahl=auswahl)

        row = make_frame(self.root)
        row.pack(pady=SKAL.s(14))
        tk.Button(row, text=t(ui, "lvl_start"), font=fnt(12, "bold"),
                  bg=CLR["orange"], fg="white", relief="flat", padx=SKAL.s(20), pady=SKAL.s(8),
                  cursor="hand2", command=starten).pack(side="left", padx=SKAL.s(6))
        tk.Button(row, text=t(ui, "zurueck"), font=fnt(12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=SKAL.s(14), pady=SKAL.s(8),
                  cursor="hand2", command=self.zeige_hauptmenue).pack(side="left", padx=SKAL.s(6))

        self.root.bind("<Return>", lambda e: starten())
        proz_entry.focus()

    def _wort_auswahl(self, vok, n, modus):
        s  = stats_laden()
        ws = s.get("wort_stats", {})

        def fehler_score(v):
            key   = v.get("nativ", "")
            st    = ws.get(key, {})
            r, f  = st.get("richtig", 0), st.get("falsch", 0)
            total = r + f
            return 0.5 if total == 0 else f / total

        if modus == "schwach":
            return sorted(vok, key=fehler_score, reverse=True)[:n]
        else:
            sample = vok[:]
            random.shuffle(sample)
            return sample[:n]

    def zeige_vokabeln_menue(self):
        self._aktuelle_ansicht = self.zeige_vokabeln_menue
        self.clear()
        if self.root.winfo_width() <= 1:
            self.root.geometry("460x420")
            SKAL.setze_basis(460, 420)
        ui, ls = self.ui, self.ls

        tk.Label(self.root, text=t(ui, "vok_menue_titel"), font=fnt(16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(SKAL.s(28), SKAL.s(4)))

        vok = vokabeln_laden(ls)
        tk.Label(self.root, text=t(ui, "gespeichert", n=len(vok)),
                 font=fnt(11), bg=CLR["bg"], fg=CLR["sub"]).pack(pady=(SKAL.s(0), SKAL.s(20)))

        btn_cfg = {"font": ("Arial", 13, "bold"), "relief": "flat",
                   "padx": 0, "pady": 13, "cursor": "hand2", "width": 22}
        tk.Button(self.root, text=t(ui, "eintragen"), bg=CLR["blue"], fg="white",
                  command=self.zeige_eintragen, **btn_cfg).pack(pady=SKAL.s(4))
        tk.Button(self.root, text=t(ui, "lernen"), bg=CLR["green"], fg="white",
                  command=lambda: self.zeige_richtung("lernen"), **btn_cfg).pack(pady=SKAL.s(4))
        tk.Button(self.root, text=t(ui, "test"), bg=CLR["orange"], fg="white",
                  command=lambda: self.zeige_richtung("test"), **btn_cfg).pack(pady=SKAL.s(4))
        tk.Button(self.root, text=t(ui, "bearbeiten"), bg=CLR["purple"], fg="white",
                  command=self.zeige_bearbeiten, **btn_cfg).pack(pady=SKAL.s(4))
        tk.Button(self.root, text=t(ui, "zurueck"), font=fnt(12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=SKAL.s(14), pady=SKAL.s(8),
                  cursor="hand2", command=self.zeige_hauptmenue).pack(pady=(SKAL.s(16), SKAL.s(0)))

    def zeige_eintragen(self):
        self._aktuelle_ansicht = self.zeige_eintragen
        self.clear()
        if self.root.winfo_width() <= 1:
            self.root.geometry("460x560")
            SKAL.setze_basis(460, 560)
        ui, ls = self.ui, self.ls
        lsname = langname(ui, ls)
        mutter = muttersprache_label(ui)

        tk.Label(self.root, text=t(ui, "ein_titel"), font=fnt(16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(SKAL.s(22), SKAL.s(2)))
        tk.Label(self.root, text=t(ui, "ein_hinweis"),
                 font=fnt(10), bg=CLR["bg"], fg=CLR["sub"]).pack(pady=(SKAL.s(0), SKAL.s(14)))

        f_a = tk.Frame(self.root, bg=CLR["white"],
                       highlightbackground=CLR["card_border"], highlightthickness=2)
        f_a.pack(padx=SKAL.s(40), fill="x", pady=(SKAL.s(0), SKAL.s(10)))
        tk.Label(f_a, text=mutter.upper(), font=fnt(11, "bold"),
                 bg=CLR["white"], fg=CLR["text"]).pack(pady=(SKAL.s(8), SKAL.s(2)))
        self.ein_a = tk.Entry(f_a, font=fnt(20, "bold"), justify="center",
                              fg=CLR["entry_fg"], bd=0, highlightthickness=0,
                              bg=CLR["entry_bg"], insertbackground=CLR["entry_ins"])
        self.ein_a.pack(fill="x", padx=SKAL.s(12), pady=(SKAL.s(0), SKAL.s(10)))

        f_b = tk.Frame(self.root, bg=CLR["white"],
                       highlightbackground=CLR["card_border"], highlightthickness=2)
        f_b.pack(padx=SKAL.s(40), fill="x", pady=(SKAL.s(0), SKAL.s(10)))
        tk.Label(f_b, text=lsname.upper(), font=fnt(11, "bold"),
                 bg=CLR["white"], fg=CLR["text"]).pack(pady=(SKAL.s(8), SKAL.s(2)))
        self.ein_b = tk.Entry(f_b, font=fnt(20, "bold"), justify="center",
                              fg=CLR["entry_fg"], bd=0, highlightthickness=0,
                              bg=CLR["entry_bg"], insertbackground=CLR["entry_ins"])
        self.ein_b.pack(fill="x", padx=SKAL.s(12), pady=(SKAL.s(0), SKAL.s(10)))

        f_audio = tk.Frame(self.root, bg=CLR["white"],
                           highlightbackground=CLR["card_border"], highlightthickness=2)
        f_audio.pack(padx=SKAL.s(40), fill="x", pady=(SKAL.s(0), SKAL.s(10)))
        tk.Label(f_audio, text=t(ui, "audio_titel"), font=fnt(11, "bold"),
                 bg=CLR["white"], fg=CLR["text"]).pack(pady=(SKAL.s(8), SKAL.s(2)))
        self.ein_audio_var = tk.StringVar(value="")
        af_row = tk.Frame(f_audio, bg=CLR["white"])
        af_row.pack(fill="x", padx=SKAL.s(12), pady=(SKAL.s(0), SKAL.s(10)))
        self.ein_audio_lbl = tk.Label(af_row, text=t(ui, "audio_keine"),
                                      font=fnt(10), bg=CLR["white"],
                                      fg=CLR["sub"], anchor="w")
        self.ein_audio_lbl.pack(side="left", fill="x", expand=True)

        def waehle_ein_audio():
            pfad = filedialog.askopenfilename(
                title="MP3-Datei wählen",
                initialdir=AUDIO_DIR,
                filetypes=[("MP3-Dateien", "*.mp3"), ("Alle Dateien", "*.*")])
            if pfad:
                name = os.path.basename(pfad)
                self.ein_audio_var.set(name)
                self.ein_audio_lbl.config(text=name, fg=CLR["green"])

        def audio_loeschen():
            self.ein_audio_var.set("")
            self.ein_audio_lbl.config(text=t(ui, "audio_keine"), fg=CLR["sub"])

        tk.Button(af_row, text=t(ui, "audio_waehlen"), font=fnt(10),
                  bg=CLR["blue"], fg="white", relief="flat", padx=SKAL.s(8), pady=SKAL.s(3),
                  cursor="hand2", command=waehle_ein_audio).pack(side="left", padx=(SKAL.s(6), SKAL.s(2)))
        tk.Button(af_row, text="✕", font=fnt(10),
                  bg=CLR["red"], fg="white", relief="flat", padx=SKAL.s(6), pady=SKAL.s(3),
                  cursor="hand2", command=audio_loeschen).pack(side="left", padx=(SKAL.s(2), SKAL.s(0)))

        self.lbl_ein_status = tk.Label(self.root, text="", font=fnt(11),
                                       bg=CLR["bg"], fg="#27ae60")
        self.lbl_ein_status.pack(pady=(SKAL.s(0), SKAL.s(10)))

        row = make_frame(self.root)
        row.pack()
        tk.Button(row, text=t(ui, "speichern"), font=fnt(12, "bold"),
                  bg=CLR["blue"], fg="white", relief="flat", padx=SKAL.s(18), pady=SKAL.s(8),
                  cursor="hand2", command=self.eintragen_speichern).pack(side="left", padx=SKAL.s(6))
        tk.Button(row, text=t(ui, "zurueck"), font=fnt(12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=SKAL.s(14), pady=SKAL.s(8),
                  cursor="hand2", command=self.zeige_hauptmenue).pack(side="left", padx=SKAL.s(6))

        self.root.bind("<Return>", lambda e: self.eintragen_speichern())
        self.ein_a.focus()

    def eintragen_speichern(self):
        ui, ls = self.ui, self.ls
        a = self.ein_a.get().strip()
        b = self.ein_b.get().strip()
        if not a or not b:
            self.lbl_ein_status.config(text=t(ui, "ein_fehler"), fg=CLR["red"])
            return
        audio = self.ein_audio_var.get().strip() if hasattr(self, 'ein_audio_var') else ""
        if not audio:
            auto_name = gtts_dateiname(b, ls)
            self.lbl_ein_status.config(text="🎵 Audio wird geladen …", fg=CLR["sub"])
            self.root.update_idletasks()
            if gtts_herunterladen(b, ls, auto_name):
                audio = auto_name
        liste = vokabeln_laden(ls)
        liste.append({"nativ": a, "lern": b, "audio": audio})
        vokabeln_speichern(ls, liste)
        tracking_senden("vokabel_neu", sprache=ls, nativ=a, lern=b)
        self.lbl_ein_status.config(text=t(ui, "ein_ok", w=a), fg="#27ae60")
        self.ein_a.delete(0, tk.END)
        self.ein_b.delete(0, tk.END)
        self.ein_audio_var.set("")
        self.ein_audio_lbl.config(text=t(ui, "audio_keine"), fg=CLR["sub"])
        self.ein_a.focus()

    def zeige_lernen(self, umgekehrt=False):
        self._session_starten()
        self.aktueller_modus = "lernen"
        tracking_senden("lernen_start", sprache=self.ls)
        ui, ls = self.ui, self.ls
        mutter = muttersprache_label(ui)
        lsname = langname(ui, ls)
        self._aktuelle_ansicht = lambda: self.zeige_lernen(umgekehrt)
        self.clear()
        if self.root.winfo_width() <= 1:
            self.root.geometry("460x450")
            SKAL.setze_basis(460, 450)

        self.lern_liste      = vokabeln_laden(ls)[:]
        random.shuffle(self.lern_liste)
        self.lern_index      = 0
        self.lern_aufgedeckt = False
        self.lern_umgekehrt  = umgekehrt

        if umgekehrt == "gemischt":
            self.lern_key_oben  = None
            self.lern_key_unten = None
        elif umgekehrt:
            self.lern_key_oben, self.lern_key_unten = "lern", "nativ"
        else:
            self.lern_key_oben, self.lern_key_unten = "nativ", "lern"

        titel_key = "lern_titel_r" if umgekehrt is True else "lern_titel"
        tk.Label(self.root, text=t(ui, titel_key), font=fnt(16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(SKAL.s(20), SKAL.s(2)))
        tk.Label(self.root, text=t(ui, "lern_hinweis"),
                 font=fnt(10), bg=CLR["bg"], fg=CLR["sub"]).pack(pady=(SKAL.s(0), SKAL.s(10)))

        self.lbl_lern_nr = tk.Label(self.root, text="", font=fnt(11),
                                    bg=CLR["bg"], fg=CLR["sub"])
        self.lbl_lern_nr.pack()

        f_a = tk.Frame(self.root, bg=CLR["white"],
                       highlightbackground=CLR["card_border"], highlightthickness=2)
        f_a.pack(padx=SKAL.s(40), fill="x", pady=(SKAL.s(2), SKAL.s(8)))
        self.lbl_lern_a = tk.Label(f_a, text="", font=fnt(24, "bold"),
                                   bg=CLR["white"], fg=CLR["text"])
        self.lbl_lern_a.pack(pady=(SKAL.s(6), SKAL.s(12)))

        self.f_b_lern = tk.Frame(self.root, bg=CLR["light"],
                                 highlightbackground=CLR["card_border"], highlightthickness=2,
                                 cursor="hand2")
        self.f_b_lern.pack(padx=SKAL.s(40), fill="x", pady=(SKAL.s(0), SKAL.s(14)))
        self.lbl_lern_b = tk.Label(self.f_b_lern, text=t(ui, "lern_versteckt"),
                                   font=fnt(15), bg=CLR["light"], fg=CLR["sub"])
        self.lbl_lern_b.pack(pady=(SKAL.s(8), SKAL.s(12)))
        for w in [self.f_b_lern, self.lbl_lern_b]:
            w.bind("<Button-1>", lambda e: self.lern_toggle())

        row = make_frame(self.root)
        row.pack()
        self.btn_lern_vorherige = tk.Button(row, text=t(ui, "lern_vorherige"), font=fnt(11),
                  bg=CLR["orange"], fg="white", relief="flat", padx=SKAL.s(12), pady=SKAL.s(8),
                  cursor="hand2", command=self.lern_zurueck_wort)
        self.btn_lern_vorherige.pack(side="left", padx=SKAL.s(6))
        tk.Button(row, text=t(ui, "lern_play"), font=fnt(11, "bold"),
                  bg="#16a085", fg="white", relief="flat", padx=SKAL.s(12), pady=SKAL.s(8),
                  cursor="hand2", command=self._lern_play_audio).pack(side="left", padx=SKAL.s(6))
        tk.Button(row, text=t(ui, "lern_play_buchst"), font=fnt(11, "bold"),
                  bg="#2980b9", fg="white", relief="flat", padx=SKAL.s(12), pady=SKAL.s(8),
                  cursor="hand2", command=self._lern_play_audio_buchstabiert).pack(side="left", padx=SKAL.s(6))
        tk.Button(row, text=t(ui, "weiter"), font=fnt(12, "bold"),
                  bg=CLR["green"], fg="white", relief="flat", padx=SKAL.s(20), pady=SKAL.s(8),
                  cursor="hand2", command=self.lern_weiter).pack(side="left", padx=SKAL.s(6))
        tk.Button(self.root, text=t(ui, "zurueck"), font=fnt(12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=SKAL.s(20), pady=SKAL.s(10),
                  cursor="hand2", command=self._lern_zurueck).pack(pady=(SKAL.s(8), SKAL.s(4)))

        tk.Button(self.root, text="\U0001F392", font=("Segoe UI Emoji", SKAL.s(12), "bold"),
                  bg=CLR["light"], fg=CLR["text"], relief="flat", padx=SKAL.s(14), pady=SKAL.s(6),
                  cursor="hand2", command=self.zeige_inventar).pack(pady=(SKAL.s(0), SKAL.s(4)))

        self.root.bind("<h>", lambda e: self.lern_toggle())
        self.root.bind("<H>", lambda e: self.lern_toggle())
        self.lern_zeige()

    def _lern_zurueck(self):
        self._session_beenden()
        self.zeige_hauptmenue()

    def _lern_play_audio(self):
        ui = self.ui
        if not PYGAME_OK:
            messagebox.showinfo("Audio", "pygame nicht installiert.\npip install pygame")
            return
        if self.lern_index >= len(self.lern_liste):
            return
        vok       = self.lern_liste[self.lern_index]
        dateiname = vok.get("audio", "")
        pfad      = audio_pfad(dateiname)
        if pfad and os.path.exists(pfad):
            try:
                pygame.mixer.music.load(pfad)
                pygame.mixer.music.play()
            except Exception as e:
                messagebox.showerror("Audio", str(e))
        else:
            messagebox.showinfo("Audio", t(ui, "test_kein_audio", folder=AUDIO_DIR))

    def _lern_play_audio_buchstabiert(self):
        if self.lern_index >= len(self.lern_liste):
            return
        vok  = self.lern_liste[self.lern_index]
        wort = vok.get("lern", "")
        self._abc_kaestchen_oeffnen(wort, self.ls, vok=vok, bearbeitbar=True,
                                    beim_schliessen=self.lern_zeige)

    def lern_zeige(self):
        ui = self.ui
        if self.lern_index >= len(self.lern_liste):
            self._session_beenden()
            messagebox.showinfo("🎉", t(ui, "lern_fertig", n=len(self.lern_liste)))
            self.zeige_hauptmenue()
            return
        vok = self.lern_liste[self.lern_index]
        self.lbl_lern_nr.config(
            text=t(ui, "lern_karte", i=self.lern_index+1, n=len(self.lern_liste)))

        if self.lern_umgekehrt == "gemischt":
            self.lern_key_oben  = random.choice(["nativ", "lern"])
            self.lern_key_unten = "lern" if self.lern_key_oben == "nativ" else "nativ"

        self.lbl_lern_a.config(text=vok[self.lern_key_oben])
        self.lern_aufgedeckt = False
        self.lern_ist_abc = bool(vok.get("abc", False))
        if self.lern_ist_abc:
            self.lbl_lern_b.config(text="🎵", fg=CLR["sub"], font=fnt(20))
        else:
            self.lbl_lern_b.config(text=t(ui, "lern_versteckt"), fg=CLR["sub"], font=fnt(15))
        self.f_b_lern.config(bg=CLR["light"])
        self.lbl_lern_b.config(bg=CLR["light"])
        if hasattr(self, "btn_lern_vorherige"):
            state = "disabled" if self.lern_index == 0 else "normal"
            self.btn_lern_vorherige.config(state=state)

    def lern_toggle(self):
        if self.lern_index >= len(self.lern_liste):
            return
        vok = self.lern_liste[self.lern_index]
        if getattr(self, "lern_ist_abc", False):
            self._abc_kaestchen_oeffnen(vok.get(self.lern_key_unten, ""), self.ls, vok=vok, bearbeitbar=True,
                                        beim_schliessen=self.lern_zeige)
            return
        if not self.lern_aufgedeckt:
            self.lbl_lern_b.config(text=vok[self.lern_key_unten],
                                   fg=CLR["text"], font=fnt(24, "bold"))
            self.f_b_lern.config(bg=CLR["white"])
            self.lbl_lern_b.config(bg=CLR["white"])
            self.lern_aufgedeckt = True
        else:
            ui = self.ui
            self.lbl_lern_b.config(text=t(ui, "lern_versteckt"), fg=CLR["sub"], font=fnt(15))
            self.f_b_lern.config(bg=CLR["light"])
            self.lbl_lern_b.config(bg=CLR["light"])
            self.lern_aufgedeckt = False

    def lern_weiter(self):
        self.lern_index += 1
        self.lern_zeige()

    def lern_zurueck_wort(self):
        if self.lern_index > 0:
            self.lern_index -= 1
            self.lern_zeige()

    def zeige_test(self, umgekehrt=False, auswahl=None):
        self._session_starten()
        self.aktueller_modus = "umgekehrt" if umgekehrt else "test"
        tracking_senden("test_start", modus=self.aktueller_modus, sprache=self.ls)
        ui, ls = self.ui, self.ls
        mutter = muttersprache_label(ui)
        lsname = langname(ui, ls)

        self._aktuelle_ansicht = lambda: self.zeige_test(umgekehrt, auswahl=auswahl)
        self.clear()
        if self.root.winfo_width() <= 1:
            self.root.geometry("460x530")
            SKAL.setze_basis(460, 530)

        vok_liste            = auswahl if auswahl is not None else vokabeln_fuer_test(ls)
        self.test_liste      = vok_liste[:]
        random.shuffle(self.test_liste)
        self.test_index      = 0
        self.test_versuche_z = 0
        self.test_richtig_n  = 0
        self.test_falsch_n   = 0
        self.test_umgekehrt  = umgekehrt
        self.test_mix_zaehler  = 0
        self.test_streak     = 0
        self.joker_verfuegbar = hat_freischaltung("joker")
        self.joker_genutzt_runde = False
        self.streak_bonus_aktiv  = hat_freischaltung("streak_bonus")
        self.xp_multiplikator    = 1.5 if hat_freischaltung("xp_multiplikator") else 1.0

        if umgekehrt == "gemischt":
            self.test_key_oben    = None
            self.test_key_loesung = None
        elif umgekehrt:
            self.test_key_oben    = "lern"
            self.test_key_loesung = "nativ"
        else:
            self.test_key_oben    = "nativ"
            self.test_key_loesung = "lern"

        if umgekehrt == "gemischt":
            titel_key = "test_titel_g"
        elif umgekehrt:
            titel_key = "test_titel_r"
        else:
            titel_key = "test_titel"

        tk.Label(self.root, text=t(ui, titel_key), font=fnt(16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(SKAL.s(16), SKAL.s(2)))

        self.lbl_test_nr   = tk.Label(self.root, text="", font=fnt(11),
                                      bg=CLR["bg"], fg=CLR["sub"])
        self.lbl_test_nr.pack()
        self.lbl_test_vers = tk.Label(self.root, text="", font=fnt(11),
                                      bg=CLR["bg"], fg=CLR["orange"])
        self.lbl_test_vers.pack(pady=(SKAL.s(2), SKAL.s(0)))

        self.lbl_streak = tk.Label(self.root, text="", font=fnt(11, "bold"),
                                   bg=CLR["bg"], fg="#e74c3c")
        self.lbl_streak.pack()

        f_a = tk.Frame(self.root, bg=CLR["white"],
                       highlightbackground=CLR["card_border"], highlightthickness=2)
        f_a.pack(padx=SKAL.s(40), fill="x", pady=(SKAL.s(8), SKAL.s(6)))
        self.lbl_test_label_oben = tk.Label(f_a, text="", font=fnt(11, "bold"),
                 bg=CLR["white"], fg=CLR["text"])
        self.lbl_test_label_oben.pack(pady=(SKAL.s(8), SKAL.s(2)))
        self.lbl_test_a = tk.Label(f_a, text="", font=fnt(22, "bold"),
                                   bg=CLR["white"], fg=CLR["text"])
        self.lbl_test_a.pack(pady=(SKAL.s(0), SKAL.s(10)))

        f_b = tk.Frame(self.root, bg=CLR["white"],
                       highlightbackground=CLR["card_border"], highlightthickness=2)
        f_b.pack(padx=SKAL.s(40), fill="x", pady=(SKAL.s(0), SKAL.s(6)))
        self.lbl_test_label_eingabe = tk.Label(f_b, text="", font=fnt(11, "bold"),
                 bg=CLR["white"], fg=CLR["text"])
        self.lbl_test_label_eingabe.pack(pady=(SKAL.s(8), SKAL.s(2)))
        self.test_eingabe = tk.Entry(f_b, font=fnt(20, "bold"), justify="center",
                                     fg=CLR["entry_fg"], bd=0, highlightthickness=0,
                                     bg=CLR["entry_bg"], insertbackground=CLR["entry_ins"])
        self.test_eingabe.pack(fill="x", padx=SKAL.s(12), pady=(SKAL.s(0), SKAL.s(8)))

        self.f_abc_test = tk.Frame(self.root, bg=CLR["light"],
                                   highlightbackground=CLR["card_border"], highlightthickness=2,
                                   cursor="hand2")
        self.f_abc_test.pack(pady=(SKAL.s(0), SKAL.s(6)))
        self.lbl_abc_test = tk.Label(self.f_abc_test, text="🎵", font=fnt(18),
                                    bg=CLR["light"], fg=CLR["sub"])
        self.lbl_abc_test.pack(pady=(SKAL.s(4), SKAL.s(6)))
        for w in [self.f_abc_test, self.lbl_abc_test]:
            w.bind("<Button-1>", lambda e: self._test_abc_kaestchen_oeffnen())

        if umgekehrt == "gemischt":
            self.lbl_test_label_oben.config(text="?")
            self.lbl_test_label_eingabe.config(text="?")
        elif umgekehrt:
            self.lbl_test_label_oben.config(text=lsname.upper())
            self.lbl_test_label_eingabe.config(text=mutter.upper())
        else:
            self.lbl_test_label_oben.config(text=mutter.upper())
            self.lbl_test_label_eingabe.config(text=lsname.upper())

        # Sonderzeichen-Zeile – wird pro Wort ein/ausgeblendet
        self.sz_row = make_frame(self.root)
        self.sz_row.pack(pady=(SKAL.s(0), SKAL.s(4)))
        self.sz_buttons = []
        for zeichen in ["ß", "Ü", "Ä", "Ö"]:
            b = tk.Button(self.sz_row, text=zeichen, font=fnt(15, "bold"),
                          bg=CLR["blue"], fg="white", relief="flat",
                          padx=SKAL.s(18), pady=SKAL.s(6), cursor="hand2",
                          command=lambda z=zeichen: self._sonderzeichen(z))
            b.pack(side="left", padx=SKAL.s(6))
            self.sz_buttons.append(b)

        self.lbl_test_feedback = tk.Label(self.root, text="", font=fnt(12),
                                          bg=CLR["bg"])
        self.lbl_test_feedback.pack(pady=(SKAL.s(0), SKAL.s(4)))

        self.lbl_test_status = tk.Label(self.root, text=self._status_zeile_text(), font=fnt(9, "bold"),
                                        bg=CLR["bg"], fg=CLR["sub"])
        self.lbl_test_status.pack(pady=(SKAL.s(0), SKAL.s(4)))

        row = make_frame(self.root)
        row.pack()
        self.btn_play = tk.Button(row, text=t(ui, "test_play"),
                                  font=fnt(11, "bold"),
                                  bg="#16a085", fg="white", relief="flat",
                                  padx=SKAL.s(12), pady=SKAL.s(8), cursor="hand2",
                                  command=self._test_play_audio)
        self.btn_play.pack(side="left", padx=SKAL.s(4))
        self.btn_pruefen = tk.Button(row, text=t(ui, "test_prufen"),
                                     font=fnt(12, "bold"),
                                     bg=CLR["orange"], fg="white", relief="flat",
                                     padx=SKAL.s(20), pady=SKAL.s(8), cursor="hand2",
                                     command=self.test_pruefen)
        self.btn_pruefen.pack(side="left", padx=SKAL.s(4))
        unten_row = make_frame(self.root)
        unten_row.pack(pady=(SKAL.s(6), SKAL.s(4)))
        tk.Button(unten_row, text=t(ui, "zurueck"), font=fnt(12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=SKAL.s(20), pady=SKAL.s(10),
                  cursor="hand2", command=self._test_zurueck).pack(side="left", padx=SKAL.s(4))

        tk.Button(unten_row, text="\U0001F392", font=("Segoe UI Emoji", SKAL.s(12), "bold"),
                  bg=CLR["light"], fg=CLR["text"], relief="flat", padx=SKAL.s(20), pady=SKAL.s(10),
                  cursor="hand2", command=self.zeige_inventar).pack(side="left", padx=SKAL.s(4))

        if self.joker_verfuegbar:
            self.btn_joker = tk.Button(unten_row, text=t(ui, "joker_btn"),
                                       font=fnt(12, "bold"),
                                       bg="#8e44ad", fg="white", relief="flat",
                                       padx=SKAL.s(20), pady=SKAL.s(10), cursor="hand2",
                                       command=self._joker_nutzen)
            self.btn_joker.pack(side="left", padx=SKAL.s(4))

        self.root.bind("<Return>", lambda e: self.test_pruefen())
        self.test_naechste()

    def _joker_nutzen(self):
        if self.joker_genutzt_runde:
            return
        if self.test_eingabe.cget("state") == "disabled":
            return

        s = shop_laden()
        s.setdefault("inventar", {"joker": 0, "traenke": 0, "double_coin": 0})
        anzahl_joker = s["inventar"].get("joker", 0)
        if anzahl_joker <= 0:
            return

        s["inventar"]["joker"] = anzahl_joker - 1
        shop_speichern(s)

        self.joker_genutzt_runde = True
        tracking_senden("joker_benutzt", sprache=self.ls, bereich="vokabeln")
        ui = self.ui
        self.btn_joker.config(text=t(ui, "joker_genutzt"), bg="#7f8c8d", state="disabled")

        vok = self.test_liste[self.test_index]
        loesung = vok[self.test_key_loesung]

        self.test_eingabe.config(state="normal")
        self.test_eingabe.delete(0, tk.END)
        self.test_eingabe.insert(0, loesung)
        self.test_eingabe.config(state="disabled")
        self.btn_pruefen.config(state="disabled")

        self.lbl_test_feedback.config(
            text=t(ui, "joker_angewendet"), fg=CLR["orange"])

        self.root.after(900, self._test_weiter)

    def _sonderzeichen(self, z):
        try:
            pos = self.test_eingabe.index(tk.INSERT)
            self.test_eingabe.insert(pos, z)
        except Exception:
            self.test_eingabe.insert(tk.END, z)
        self.test_eingabe.focus()

    def _test_play_audio(self):
        ui = self.ui
        if not PYGAME_OK:
            messagebox.showinfo("Audio", "pygame nicht installiert.\npip install pygame")
            return
        if self.test_index >= len(self.test_liste):
            return
        vok       = self.test_liste[self.test_index]
        dateiname = vok.get("audio", "")
        pfad      = audio_pfad(dateiname)
        if pfad and os.path.exists(pfad):
            try:
                pygame.mixer.music.load(pfad)
                pygame.mixer.music.play()
            except Exception as e:
                messagebox.showerror("Audio", str(e))
        else:
            messagebox.showinfo("Audio", t(ui, "test_kein_audio", folder=AUDIO_DIR))

    def _wort_abspielen(self, wort, sprache, vorhandene_datei=""):
        """Zentrale Audio-Wiedergabe fuer ein vorhandenes Audio-File."""
        if not PYGAME_OK:
            messagebox.showinfo("Audio", "pygame nicht installiert.\npip install pygame")
            return
        pfad = audio_pfad(vorhandene_datei) if vorhandene_datei else ""
        if pfad and os.path.exists(pfad):
            try:
                pygame.mixer.music.load(pfad)
                pygame.mixer.music.play()
            except Exception as e:
                messagebox.showerror("Audio", str(e))
        else:
            messagebox.showinfo("Audio", t(self.ui, "test_kein_audio", folder=AUDIO_DIR))

    def _silbe_einzeln_abspielen(self, silbe, sprache, label_widget, wort=""):
        """Spielt eine einzelne Silbe per TTS ab und laesst das zugehoerige
        Label kurz gruen aufleuchten (in dem Moment wird der Ton abgespielt),
        danach wieder schwarz."""
        if not PYGAME_OK:
            messagebox.showinfo("Audio", "pygame nicht installiert.\npip install pygame")
            return
        try:
            label_widget.config(fg="#27ae60")
            self.root.after(350, lambda: label_widget.config(fg="black"))
        except Exception:
            pass
        tracking_senden("trennwort_abgespielt", sprache=sprache, wort=wort, silbe=silbe)

        def worker():
            pfad = audio_silbe_pfad_sicherstellen(silbe, sprache, wort=wort)

            def fertig():
                if pfad and os.path.exists(pfad):
                    try:
                        pygame.mixer.music.load(pfad)
                        pygame.mixer.music.play()
                    except Exception:
                        pass
            try:
                self.root.after(0, fertig)
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def _wort_kette_abspielen(self, silben_liste, sprache, wort="", label_widgets=None, tempo=1.0):
        """Spielt eine Liste von Silben nacheinander am Stueck ab (kompletes Wort),
        indem nach jeder Silbe kurz gewartet wird bevor die naechste startet.
        label_widgets (optional) ist eine Liste gleicher Laenge, deren Labels
        synchron gruen aufleuchten. tempo steuert die Geschwindigkeit der Kette
        (1.0 = normal, <1.0 = langsamer/mehr Pause, >1.0 = schneller/weniger Pause)."""
        if not PYGAME_OK:
            messagebox.showinfo("Audio", "pygame nicht installiert.\npip install pygame")
            return

        def spiele_index(i):
            if i >= len(silben_liste):
                return
            silbe = silben_liste[i]
            lbl = label_widgets[i] if label_widgets and i < len(label_widgets) else None
            if lbl is not None:
                try:
                    lbl.config(fg="#27ae60")
                    self.root.after(350, lambda l=lbl: l.config(fg="black"))
                except Exception:
                    pass

            def worker():
                pfad = audio_silbe_pfad_sicherstellen(silbe, sprache, wort=wort)

                def fertig():
                    dauer_ms = 500
                    if pfad and os.path.exists(pfad):
                        try:
                            pygame.mixer.music.load(pfad)
                            pygame.mixer.music.play()
                            dauer_ms = max(400, int(pygame.mixer.Sound(pfad).get_length() * 1000) + 80)
                        except Exception:
                            pass
                    dauer_ms = max(80, int(dauer_ms / max(0.1, tempo)))
                    self.root.after(dauer_ms, lambda: spiele_index(i + 1))
                try:
                    self.root.after(0, fertig)
                except Exception:
                    pass
            threading.Thread(target=worker, daemon=True).start()

        spiele_index(0)

    def _tempo_regler_bauen(self, parent):
        """Baut einen Geschwindigkeits-Regler im gleichen Look wie der Lautstaerke-
        Regler im Translator-Musikplayer (schwarzer Hintergrund, blauer Fuellbalken,
        weisser rechteckiger Schieber). Gibt ein tempo_zustand-Dict zurueck mit
        Key 'wert' (0.5 bis 2.0, Start 1.0). Der Regler steuert NICHT Lautstaerke,
        sondern wie schnell die Silben-Kette hintereinander abgespielt wird."""
        tempo_zustand = {"wert": 1.0}

        tempo_frame = tk.Frame(parent, bg="#0a0a0a")
        tempo_frame.pack(fill="x", padx=16, pady=(6, 0))
        lbl_tempo_icon = tk.Label(tempo_frame, text="❤️", bg="#0a0a0a", fg="#ff0000",
                                   font=("Segoe UI Emoji", 14))
        lbl_tempo_icon.pack(side="left", padx=(0, 4))
        tempo_canvas = tk.Canvas(tempo_frame, bg="#0a0a0a", height=20, highlightthickness=0, cursor="hand2")
        tempo_canvas.pack(side="left", fill="x", expand=True, padx=(0, 6))
        lbl_tempo_hase = tk.Label(tempo_frame, text="❤️", bg="#0a0a0a", fg="#ff0000",
                                   font=("Segoe UI Emoji", 14))
        lbl_tempo_hase.pack(side="left", padx=(0, 0))
        lbl_tempo_pct = tk.Label(parent, text="1.0x", bg="#0a0a0a", fg="#00aaff",
                                  font=("Arial", 9, "bold"), anchor="e")
        lbl_tempo_pct.pack(fill="x", padx=16, pady=(0, 6))

        MIN_TEMPO, MAX_TEMPO = 0.5, 2.0

        def zeichne_tempo():
            cv = tempo_canvas
            cv.delete("all")
            w = cv.winfo_width() or 200
            h = cv.winfo_height() or 20
            frac = (tempo_zustand["wert"] - MIN_TEMPO) / (MAX_TEMPO - MIN_TEMPO)
            frac = max(0.0, min(1.0, frac))
            pad = 2
            cv.create_rectangle(0, pad, w - 1, h - pad, fill="#1a1a1a", outline="#ffffff")
            fuell_w = int((w - 2) * frac)
            if fuell_w > 0:
                cv.create_rectangle(1, pad + 1, fuell_w, h - pad - 1, fill="#00aaff", outline="")
            sx = max(1, fuell_w)
            cv.create_rectangle(sx - 5, pad, sx + 5, h - pad, fill="#ffffff", outline="#00aaff")
            lbl_tempo_pct.config(text=f"{tempo_zustand['wert']:.1f}x")

        def tempo_aendern(frac):
            frac = max(0.0, min(1.0, frac))
            tempo_zustand["wert"] = round(MIN_TEMPO + frac * (MAX_TEMPO - MIN_TEMPO), 2)
            zeichne_tempo()

        def tempo_klick(event):
            w = tempo_canvas.winfo_width()
            if w > 0:
                tempo_aendern(event.x / w)

        tempo_canvas.bind("<Button-1>", tempo_klick)
        tempo_canvas.bind("<B1-Motion>", tempo_klick)
        tempo_canvas.bind("<Configure>", lambda e: zeichne_tempo())

        return tempo_zustand

    def _woerter_kette_abspielen(self, woerter_liste, sprache, wort_widgets=None, tempo=1.0):
        """Spielt eine Liste von KOMPLETTEN Woertern nacheinander ab (kein Silben-
        Haeppchen), indem pro Wort eine TTS-Audiodatei erzeugt/genutzt wird.
        wort_widgets (optional) ist eine Liste gleicher Laenge (z.B. Frames),
        die synchron aufleuchten waehrend das jeweilige Wort abgespielt wird.
        tempo steuert die Geschwindigkeit der Kette (1.0 = normal)."""
        if not PYGAME_OK:
            messagebox.showinfo("Audio", "pygame nicht installiert.\npip install pygame")
            return

        def spiele_index(i):
            if i >= len(woerter_liste):
                return
            wort = woerter_liste[i]
            widget = wort_widgets[i] if wort_widgets and i < len(wort_widgets) else None
            if widget is not None:
                try:
                    widget.config(bg="#27ae60")
                    self.root.after(400, lambda w=widget: w.config(bg=CLR["popup_bg"]))
                except Exception:
                    pass

            def worker():
                pfad = audio_silbe_pfad_sicherstellen(wort, sprache, wort=wort)

                def fertig():
                    dauer_ms = 500
                    if pfad and os.path.exists(pfad):
                        try:
                            pygame.mixer.music.load(pfad)
                            pygame.mixer.music.play()
                            dauer_ms = max(450, int(pygame.mixer.Sound(pfad).get_length() * 1000) + 120)
                        except Exception:
                            pass
                    dauer_ms = max(100, int(dauer_ms / max(0.1, tempo)))
                    self.root.after(dauer_ms, lambda: spiele_index(i + 1))
                try:
                    self.root.after(0, fertig)
                except Exception:
                    pass
            threading.Thread(target=worker, daemon=True).start()

        spiele_index(0)

    def _abc_kaestchen_oeffnen(self, wort, sprache, vok=None, bearbeitbar=False, beim_schliessen=None,
                                nur_sound=False, alle_geklickt_callback=None):
        """Oeffnet ein Popup mit dem Wort ganz oben und darunter das Wort in
        Silben zerlegt als anklickbare Kaestchen. Klick auf ein Kaestchen
        laesst es kurz gruen aufleuchten und spielt in genau diesem Moment
        die Silbe einzeln ab; danach wird es wieder schwarz.
        Wenn bearbeitbar=True (Bearbeitungsmodus), gibt es zusaetzlich einen
        'Verändern'-Button neben 'Zurück': ein Klick darauf zeigt ein Textfeld
        mit den Silben im Bindestrich-Format (z.B. 'Well-en-sitt-ich'), das von
        Hand angepasst und gespeichert werden kann; das Ergebnis wird in
        vok['silben'] gespeichert.
        Wenn nur_sound=True, wird statt des Silben-Textes nur ein Sound-Symbol
        pro Silbe angezeigt (z.B. fuer den TEST-Bereich).
        alle_geklickt_callback wird aufgerufen, sobald jede Silbe mindestens
        einmal angeklickt wurde (z.B. um einen Pflicht-Weiter-Button freizuschalten)."""
        popup = tk.Toplevel(self.root)
        try:
            popup.iconbitmap(os.path.join(BASE_DIR, "heart.ico"))
        except Exception:
            pass
        popup.title("ABC")
        popup.configure(bg=CLR["popup_bg"])
        popup.transient(self.root)
        popup.grab_set()
        popup.resizable(False, False)
        popup.minsize(340, 0)

        if not nur_sound:
            titel_lbl = tk.Label(popup, text=wort.upper(), font=("Arial", 26, "bold"),
                     bg=CLR["popup_bg"], fg=CLR["text"], cursor="hand2")
            titel_lbl.pack(padx=24, pady=(20, 6))

        rahmen = tk.Frame(popup, bg=CLR["popup_bg"])
        rahmen.pack(padx=20, pady=(6, 4))

        silben_liste = silben_liste_holen(vok) if vok is not None else silben_automatisch_trennen(wort)
        buchstaben_gesamt = "".join(silben_liste)
        grenzen = []
        pos = 0
        for s in silben_liste[:-1]:
            pos += len(s)
            grenzen.append(pos)

        geklickt = set()
        editier_frame = {"widget": None}
        aktuelle_labels = []

        def pruefe_alle_geklickt(gesamt_anzahl):
            if alle_geklickt_callback is not None and len(geklickt) >= gesamt_anzahl:
                alle_geklickt_callback()

        def aktuelle_silben_akt():
            silben_akt = []
            letzte = 0
            for g in grenzen:
                silben_akt.append(buchstaben_gesamt[letzte:g])
                letzte = g
            silben_akt.append(buchstaben_gesamt[letzte:])
            return silben_akt

        def neu_aufbauen():
            for w in rahmen.winfo_children():
                w.destroy()
            silben_akt = aktuelle_silben_akt()
            aktuelle_labels.clear()

            row = tk.Frame(rahmen, bg=CLR["popup_bg"])
            row.pack()
            for i, silbe in enumerate(silben_akt):
                anzeige_text = "🔊" if nur_sound else silbe
                lbl = tk.Label(row, text=anzeige_text, font=("Arial", 20, "bold"),
                              bg=CLR["white"], fg="black",
                              highlightbackground=CLR["card_border"], highlightthickness=2,
                              cursor="hand2", padx=8, pady=6)
                lbl.pack(side="left", padx=3, pady=3)
                aktuelle_labels.append(lbl)

                def klick(e, s=silbe, l=lbl, i=i):
                    geklickt.add(i)
                    self._silbe_einzeln_abspielen(s, sprache, l, wort=wort)
                    pruefe_alle_geklickt(len(silben_akt))
                lbl.bind("<Button-1>", klick)

        if not nur_sound:
            def titel_klick(e):
                if not PYGAME_OK:
                    messagebox.showinfo("Audio", "pygame nicht installiert.\npip install pygame")
                    return
                dateiname = vok.get("audio", "") if vok is not None else ""
                pfad = audio_pfad(dateiname)
                if pfad and os.path.exists(pfad):
                    try:
                        pygame.mixer.music.load(pfad)
                        pygame.mixer.music.play()
                    except Exception:
                        pass
                else:
                    messagebox.showinfo("Audio", t(self.ui, "test_kein_audio", folder=AUDIO_DIR))
            titel_lbl.bind("<Button-1>", titel_klick)

            tempo_zustand_wort = self._tempo_regler_bauen(popup)

            def silben_kette_klick():
                self._wort_kette_abspielen(aktuelle_silben_akt(), sprache, wort=wort,
                                            label_widgets=aktuelle_labels,
                                            tempo=tempo_zustand_wort["wert"])

        def speichern_silben():
            if vok is None:
                return
            silben_akt = aktuelle_silben_akt()
            vok["silben"] = "-".join(silben_akt)
            liste = vokabeln_laden(sprache)
            wort_key = vok.get("nativ", "")
            for v in liste:
                if v.get("nativ", "") == wort_key and v.get("lern", "") == vok.get("lern", ""):
                    v["silben"] = vok["silben"]
                    break
            vokabeln_speichern(sprache, liste)

        def editier_schliessen():
            if editier_frame["widget"] is not None:
                editier_frame["widget"].destroy()
                editier_frame["widget"] = None

        def editier_speichern(entry):
            text = entry.get().strip()
            if not text:
                return
            neue_silben = [s for s in text.split("-") if s.strip()]
            if not neue_silben:
                return
            nonlocal buchstaben_gesamt, grenzen
            buchstaben_gesamt = "".join(neue_silben)
            grenzen = []
            pos = 0
            for s in neue_silben[:-1]:
                pos += len(s)
                grenzen.append(pos)
            speichern_silben()
            editier_schliessen()
            neu_aufbauen()

        def veraendern_oeffnen():
            if editier_frame["widget"] is not None:
                editier_schliessen()
                return
            frame = tk.Frame(popup, bg=CLR["popup_bg"])
            frame.pack(pady=(4, 0), padx=20, fill="x")
            editier_frame["widget"] = frame

            tk.Label(frame, text="Silben mit '-' getrennt eintippen:",
                     font=("Arial", 9), bg=CLR["popup_bg"], fg=CLR["sub"]).pack(anchor="w")
            entry_var = tk.StringVar(value="-".join(aktuelle_silben_akt()))
            entry = tk.Entry(frame, textvariable=entry_var, font=("Arial", 14, "bold"),
                             justify="center", fg=CLR["entry_fg"], bg=CLR["entry_bg"],
                             insertbackground=CLR["entry_ins"], bd=1, relief="solid")
            entry.pack(fill="x", pady=(2, 6))
            entry.bind("<Return>", lambda e: editier_speichern(entry))

            btn_row = tk.Frame(frame, bg=CLR["popup_bg"])
            btn_row.pack(pady=(0, 6))
            tk.Button(btn_row, text="💾 Speichern", font=("Arial", 10, "bold"),
                      bg=CLR["green"], fg="white", relief="flat", padx=10, pady=4,
                      cursor="hand2", command=lambda: editier_speichern(entry)).pack(side="left", padx=4)
            tk.Button(btn_row, text="Abbrechen", font=("Arial", 10, "bold"),
                      bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=10, pady=4,
                      cursor="hand2", command=editier_schliessen).pack(side="left", padx=4)
            entry.focus()
            entry.icursor(tk.END)

        neu_aufbauen()

        def schliessen():
            popup.destroy()
            if beim_schliessen is not None:
                beim_schliessen()

        btn_row_unten = tk.Frame(popup, bg=CLR["popup_bg"])
        btn_row_unten.pack(pady=(14, 18))
        tk.Button(btn_row_unten, text=t(self.ui, "zurueck"), font=("Arial", 11, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=14, pady=6,
                  cursor="hand2", command=schliessen).pack(side="left", padx=4)
        if not nur_sound:
            tk.Button(btn_row_unten, text="A", font=("Arial", 11, "bold"),
                      bg="#27ae60", fg="white", relief="flat", padx=14, pady=6,
                      cursor="hand2", command=silben_kette_klick).pack(side="left", padx=4)
        if bearbeitbar:
            tk.Button(btn_row_unten, text="❤️ Verändern", font=("Arial", 11, "bold"),
                      bg=CLR["purple"], fg="white", relief="flat", padx=14, pady=6,
                      cursor="hand2", command=veraendern_oeffnen).pack(side="left", padx=4)
        popup.protocol("WM_DELETE_WINDOW", schliessen)

        self.root.update_idletasks()
        popup.update_idletasks()
        x = self.root.winfo_x() + self.root.winfo_width()  // 2 - popup.winfo_reqwidth()  // 2
        y = self.root.winfo_y() + self.root.winfo_height() // 2 - popup.winfo_reqheight() // 2
        popup.geometry(f"+{x}+{y}")

    def _satz_abc_kaestchen_oeffnen(self, satz_item, sprache, bearbeitbar=False,
                                     beim_schliessen=None, nur_sound=False,
                                     alle_geklickt_callback=None):
        """Oeffnet ein Popup fuer einen ganzen Satz: jedes Wort des Satzes wird
        einzeln in Silben zerlegt und als eigene Wort-Gruppe von Kaestchen
        angezeigt (gleiche Gruen-Ton-Logik wie bei einzelnen Vokabeln).
        satz_item ist das Dict aus der Saetze-Liste; 'silben' darin speichert
        pro Wort die Trennung, getrennt durch '|' zwischen Woertern und '-'
        zwischen Silben, z.B. 'Well-en|sitt-ich'.
        Wenn bearbeitbar=True (Bearbeitungsmodus), gibt es zusaetzlich einen
        'Verändern'-Button neben 'Zurück': ein Klick darauf zeigt fuer jedes
        Wort ein eigenes Textfeld mit den Silben im Bindestrich-Format
        (z.B. 'Well-en-sitt-ich'), das von Hand angepasst und gespeichert
        werden kann."""
        satz_text = satz_item.get("lern", "")
        woerter = [w for w in satz_text.split(" ") if w]

        gespeichert = satz_item.get("silben", "")
        wort_silben = []
        if gespeichert.strip():
            teile = gespeichert.split("|")
            for i, w in enumerate(woerter):
                if i < len(teile) and teile[i].strip():
                    wort_silben.append([s for s in teile[i].split("-") if s])
                else:
                    wort_silben.append(silben_automatisch_trennen(w))
        else:
            wort_silben = [silben_automatisch_trennen(w) for w in woerter]

        popup = tk.Toplevel(self.root)
        try:
            popup.iconbitmap(os.path.join(BASE_DIR, "heart.ico"))
        except Exception:
            pass
        popup.title("ABC")
        popup.configure(bg=CLR["popup_bg"])
        popup.transient(self.root)
        popup.grab_set()
        popup.resizable(False, False)
        popup.minsize(380, 0)

        titel_lbl = tk.Label(popup, text=satz_text, font=("Arial", 16, "bold"),
                 bg=CLR["popup_bg"], fg=CLR["text"], wraplength=440,
                 justify="center", cursor="hand2")
        titel_lbl.pack(padx=24, pady=(20, 10))

        rahmen = tk.Frame(popup, bg=CLR["popup_bg"])
        rahmen.pack(padx=20, pady=(6, 4))

        geklickt = set()
        gesamt_silben = sum(len(s) for s in wort_silben)
        editier_frame = {"widget": None}
        alle_labels_flach = []
        wort_rows = []

        def pruefe_alle_geklickt():
            if alle_geklickt_callback is not None and len(geklickt) >= gesamt_silben and gesamt_silben > 0:
                alle_geklickt_callback()

        def speichern_silben():
            if not bearbeitbar:
                return
            teile = ["-".join(s) for s in wort_silben]
            satz_item["silben"] = "|".join(teile)
            liste = saetze_laden(sprache)
            for s in liste:
                if s.get("nativ", "") == satz_item.get("nativ", "") and \
                   s.get("lern", "") == satz_item.get("lern", ""):
                    s["silben"] = satz_item["silben"]
                    break
            saetze_speichern(sprache, liste)

        def neu_aufbauen_rahmen():
            for w in rahmen.winfo_children():
                w.destroy()
            laufender_index = [0]
            alle_labels_flach.clear()
            wort_rows.clear()
            for wort_idx, (wort, silben_akt) in enumerate(zip(woerter, wort_silben)):
                wort_row = tk.Frame(rahmen, bg=CLR["popup_bg"])
                wort_row.pack(pady=(0, 8))
                wort_rows.append(wort_row)
                for i, silbe in enumerate(silben_akt):
                    anzeige_text = "🔊" if nur_sound else silbe
                    lbl = tk.Label(wort_row, text=anzeige_text, font=("Arial", 16, "bold"),
                                  bg=CLR["white"], fg="black",
                                  highlightbackground=CLR["card_border"], highlightthickness=2,
                                  cursor="hand2", padx=6, pady=5)
                    lbl.pack(side="left", padx=(2, 2), pady=2)
                    alle_labels_flach.append((silbe, lbl))
                    globaler_idx = laufender_index[0]
                    laufender_index[0] += 1

                    def klick(e, s=silbe, l=lbl, gi=globaler_idx, w=wort):
                        geklickt.add(gi)
                        self._silbe_einzeln_abspielen(s, sprache, l, wort=w)
                        pruefe_alle_geklickt()
                    lbl.bind("<Button-1>", klick)

        if not nur_sound:
            def satz_titel_klick(e):
                if not woerter:
                    return
                self._woerter_kette_abspielen(woerter, sprache, wort_widgets=wort_rows)
            titel_lbl.bind("<Button-1>", satz_titel_klick)

            tempo_zustand_satz = self._tempo_regler_bauen(popup)

            def satz_silben_kette_klick():
                if not alle_labels_flach:
                    return
                silben_flach = [s for s, l in alle_labels_flach]
                labels_flach = [l for s, l in alle_labels_flach]
                self._wort_kette_abspielen(silben_flach, sprache, wort=satz_text,
                                            label_widgets=labels_flach,
                                            tempo=tempo_zustand_satz["wert"])

        def editier_schliessen():
            if editier_frame["widget"] is not None:
                editier_frame["widget"].destroy()
                editier_frame["widget"] = None

        def editier_speichern(entries):
            neu_gesamt = 0
            for wi, entry in enumerate(entries):
                text = entry.get().strip()
                if not text:
                    continue
                neue_silben = [s for s in text.split("-") if s.strip()]
                if neue_silben:
                    wort_silben[wi] = neue_silben
            speichern_silben()
            editier_schliessen()
            neu_aufbauen_rahmen()

        def veraendern_oeffnen():
            if editier_frame["widget"] is not None:
                editier_schliessen()
                return
            frame = tk.Frame(popup, bg=CLR["popup_bg"])
            frame.pack(pady=(4, 0), padx=20, fill="x")
            editier_frame["widget"] = frame

            tk.Label(frame, text="Pro Wort die Silben mit '-' getrennt eintippen:",
                     font=("Arial", 9), bg=CLR["popup_bg"], fg=CLR["sub"]).pack(anchor="w")

            entries = []
            for wi, (wort, silben_akt) in enumerate(zip(woerter, wort_silben)):
                zeile = tk.Frame(frame, bg=CLR["popup_bg"])
                zeile.pack(fill="x", pady=(4, 0))
                tk.Label(zeile, text=wort, font=("Arial", 9, "bold"),
                         bg=CLR["popup_bg"], fg=CLR["sub"], width=12, anchor="w").pack(side="left")
                entry_var = tk.StringVar(value="-".join(silben_akt))
                entry = tk.Entry(zeile, textvariable=entry_var, font=("Arial", 13, "bold"),
                                 justify="center", fg=CLR["entry_fg"], bg=CLR["entry_bg"],
                                 insertbackground=CLR["entry_ins"], bd=1, relief="solid")
                entry.pack(side="left", fill="x", expand=True, padx=(4, 0))
                entries.append(entry)

            if entries:
                entries[-1].bind("<Return>", lambda e: editier_speichern(entries))

            btn_row = tk.Frame(frame, bg=CLR["popup_bg"])
            btn_row.pack(pady=(6, 6))
            tk.Button(btn_row, text="💾 Speichern", font=("Arial", 10, "bold"),
                      bg=CLR["green"], fg="white", relief="flat", padx=10, pady=4,
                      cursor="hand2", command=lambda: editier_speichern(entries)).pack(side="left", padx=4)
            tk.Button(btn_row, text="Abbrechen", font=("Arial", 10, "bold"),
                      bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=10, pady=4,
                      cursor="hand2", command=editier_schliessen).pack(side="left", padx=4)
            if entries:
                entries[0].focus()
                entries[0].icursor(tk.END)

        neu_aufbauen_rahmen()

        if bearbeitbar:
            speichern_silben()

        def schliessen():
            popup.destroy()
            if beim_schliessen is not None:
                beim_schliessen()

        btn_row_unten = tk.Frame(popup, bg=CLR["popup_bg"])
        btn_row_unten.pack(pady=(14, 18))
        tk.Button(btn_row_unten, text=t(self.ui, "zurueck"), font=("Arial", 11, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=14, pady=6,
                  cursor="hand2", command=schliessen).pack(side="left", padx=4)
        if not nur_sound:
            tk.Button(btn_row_unten, text="A", font=("Arial", 11, "bold"),
                      bg="#27ae60", fg="white", relief="flat", padx=14, pady=6,
                      cursor="hand2", command=satz_silben_kette_klick).pack(side="left", padx=4)
        if bearbeitbar:
            tk.Button(btn_row_unten, text="❤️ Verändern", font=("Arial", 11, "bold"),
                      bg=CLR["purple"], fg="white", relief="flat", padx=14, pady=6,
                      cursor="hand2", command=veraendern_oeffnen).pack(side="left", padx=4)
        popup.protocol("WM_DELETE_WINDOW", schliessen)

        self.root.update_idletasks()
        popup.update_idletasks()
        x = self.root.winfo_x() + self.root.winfo_width()  // 2 - popup.winfo_reqwidth()  // 2
        y = self.root.winfo_y() + self.root.winfo_height() // 2 - popup.winfo_reqheight() // 2
        popup.geometry(f"+{x}+{y}")

    def _test_abc_kaestchen_oeffnen(self):
        if self.test_index >= len(self.test_liste):
            return
        vok = self.test_liste[self.test_index]
        wort = vok.get(self.test_key_loesung, "")
        sprache = self.ls if self.test_key_loesung == "lern" else self.ui
        self._abc_kaestchen_oeffnen(wort, sprache, vok=vok, bearbeitbar=False, nur_sound=True)

    def _test_zurueck(self):
        self._session_beenden()
        self.zeige_hauptmenue()

    def test_naechste(self):
        ui = self.ui
        if self.test_index >= len(self.test_liste):
            self._test_abschluss()
            return
        self.test_versuche_z = 0
        self.joker_genutzt_runde = False
        if getattr(self, "btn_joker", None) is not None:
            self.btn_joker.config(text=t(ui, "joker_btn"), bg="#8e44ad", state="normal")
        vok = self.test_liste[self.test_index]

        if self.test_umgekehrt == "gemischt":
            key_oben = random.choice(["nativ", "lern"])
            self.test_key_oben    = key_oben
            self.test_key_loesung = "lern" if key_oben == "nativ" else "nativ"
            mutter = muttersprache_label(ui)
            if key_oben == "nativ":
                self.lbl_test_label_oben.config(text=mutter.upper())
                self.lbl_test_label_eingabe.config(text=langname(ui, self.ls).upper())
            else:
                self.lbl_test_label_oben.config(text=langname(ui, self.ls).upper())
                self.lbl_test_label_eingabe.config(text=mutter.upper())

        elif self.test_umgekehrt == "mix":
            umgekehrt_jetzt = (self.test_mix_zaehler % 2 == 1)
            self.test_mix_zaehler += 1
            mutter = muttersprache_label(ui)
            if umgekehrt_jetzt:
                self.test_key_oben    = "lern"
                self.test_key_loesung = "nativ"
                self.lbl_test_label_oben.config(text=langname(ui, self.ls).upper())
                self.lbl_test_label_eingabe.config(text=mutter.upper())
            else:
                self.test_key_oben    = "nativ"
                self.test_key_loesung = "lern"
                self.lbl_test_label_oben.config(text=mutter.upper())
                self.lbl_test_label_eingabe.config(text=langname(ui, self.ls).upper())

        self.lbl_test_a.config(text=vok[self.test_key_oben])
        self.lbl_test_nr.config(
            text=t(ui, "test_frage", i=self.test_index+1, n=len(self.test_liste)))
        self.lbl_test_vers.config(text=t(ui, "test_versuche", v=3))
        self.lbl_test_feedback.config(text="")
        if self.test_streak >= 5 and self.streak_bonus_aktiv:
            self.lbl_streak.config(text=t(ui, "streak", n=self.test_streak) + " 2x XP!")
        elif self.test_streak >= 3:
            self.lbl_streak.config(text=t(ui, "streak", n=self.test_streak))
        else:
            self.lbl_streak.config(text="")
        # Sonderzeichen-Buttons: nur anzeigen wenn Deutsch eingetippt werden muss
        mutter_sprache = self.ui  # ui ist die Muttersprache
        loesung_ist_deutsch = (self.test_key_loesung == "nativ" and mutter_sprache == "de") or \
                               (self.test_key_loesung == "lern" and self.ls == "de")
        if hasattr(self, "sz_row"):
            if loesung_ist_deutsch:
                self.sz_row.pack(pady=(SKAL.s(0), SKAL.s(4)))
            else:
                self.sz_row.pack_forget()
        self.test_eingabe.config(state="normal")
        self.test_eingabe.delete(0, tk.END)
        self.btn_pruefen.config(state="normal")

        if hasattr(self, "f_abc_test"):
            self.f_abc_test.pack(padx=SKAL.s(40), fill="x", pady=(SKAL.s(0), SKAL.s(6)))

        self.test_eingabe.focus()

    def test_pruefen(self):
        if self.test_eingabe.cget("state") == "disabled":
            return
        ui      = self.ui
        antwort = self.test_eingabe.get().strip().lower()
        vok     = self.test_liste[self.test_index]
        loesung = vok[self.test_key_loesung]
        wort_key = vok.get("nativ", "")

        if antwort == loesung.lower():
            self.test_richtig_n += 1
            self.test_streak += 1
            xp_gewinn = self._xp_fuer_richtig()
            coins_gewinn = shop_coins_effektiv(1)
            self._update_wort_stats(wort_key, richtig=True, xp=xp_gewinn)
            feedback = t(ui, "test_richtig") + f"  {t(ui,'xp_gewinn', xp=xp_format(xp_gewinn))}  +{coins_gewinn} \U0001FA99"
            self.lbl_test_feedback.config(text=feedback, fg="#27ae60")
            self.lbl_test_status.config(text=self._status_zeile_text())
            self.test_eingabe.config(state="disabled")
            self.btn_pruefen.config(state="disabled")
            self.root.after(900, self._test_weiter)
        else:
            self.test_versuche_z += 1
            verbleibend = 3 - self.test_versuche_z
            if self.test_versuche_z >= 3:
                self.test_falsch_n += 1
                self.test_streak = 0
                xp_verlust = self._xp_verlust()
                self._update_wort_stats(wort_key, richtig=False, xp=xp_verlust)
                self.lbl_test_feedback.config(
                    text=t(ui, "test_falsch_end") + f"  {t(ui,'xp_verlust', xp=xp_format(xp_verlust))}",
                    fg=CLR["red"])
                self.lbl_test_status.config(text=self._status_zeile_text())
                self.test_eingabe.config(state="disabled")
                self.btn_pruefen.config(state="disabled")
                self._zeige_weiter_button(loesung)
            else:
                e_suf = "e" if verbleibend > 1 else ""
                self.lbl_test_feedback.config(
                    text=t(ui, "test_falsch_n", v=verbleibend, e=e_suf), fg=CLR["red"])
                self.lbl_test_vers.config(text=t(ui, "test_versuche", v=verbleibend))
                self.test_eingabe.delete(0, tk.END)
                self.test_eingabe.focus()

    def _xp_fuer_richtig(self):
        basis = 10
        if self.test_streak >= 5 and self.streak_bonus_aktiv:
            basis = int(basis * 2)
        return basis * self.xp_multiplikator + shop_trank_xp_bonus()

    def _status_zeile_text(self):
        """Baut den Status-Text mit aktuellem Level, Coins-Bestand,
        aktuellem XP im Level und XP bis zum naechsten Level - wird nach
        jeder richtigen Antwort im Test unter dem Feedback angezeigt."""
        s = stats_laden()
        lvl, xp_ak, xp_nx = xp_fortschritt(s.get("level_xp", 0))
        coins = shop_laden().get("coins", 0)
        return (f"⭐ Level {lvl}   |   \U0001FA99 {coins} Coins   |   "
                f"{xp_format(xp_ak)} / {xp_format(xp_nx)} XP")

    def _xp_verlust(self):
        basis = self._xp_fuer_richtig()
        verlust = max(1, basis // 2)
        return verlust

    def _update_wort_stats(self, key, richtig, xp=10):
        s  = stats_laden()
        ws = s.setdefault("wort_stats", {})
        ws.setdefault(key, {"richtig": 0, "falsch": 0})
        if richtig:
            ws[key]["richtig"] += 1
            s["richtig"]   = s.get("richtig", 0) + 1
            s["level_xp"]  = s.get("level_xp", 0) + xp
            shop_coins_hinzufuegen(1)
            tracking_senden("xp_aenderung", sprache=self.ls, vokabel=key, xp_veraendert_um=xp,
                            xp_gesamt=s["level_xp"], modus=getattr(self, "aktueller_modus", ""))
        else:
            ws[key]["falsch"] += 1
            s["falsch"] = s.get("falsch", 0) + 1
            tracking_senden("wort_falsch", sprache=self.ls, vokabel=key,
                            modus=getattr(self, "aktueller_modus", ""))
            if xp > 0:
                s["level_xp"] = max(0, s.get("level_xp", 0) - xp)
                lvl_neu = berechne_level(s["level_xp"])
                frei    = get_freigeschaltet(s)
                min_lvl = 1
                for (req, k, _, _) in FREISCHALTUNGEN["de"]:
                    if k in frei:
                        min_lvl = max(min_lvl, req)
                if lvl_neu < min_lvl:
                    s["level_xp"] = xp_fuer_level(min_lvl)
                tracking_senden("xp_aenderung", sprache=self.ls, vokabel=key, xp_veraendert_um=-xp,
                                xp_gesamt=s["level_xp"], modus=getattr(self, "aktueller_modus", ""))

        if "freigeschaltet" not in s:
            s["freigeschaltet"] = []
        neu = check_neue_freischaltungen(s, ui=self.ui)
        stats_speichern(s)

        if neu and richtig:
            self.root.after(1200, lambda: self._zeige_freischaltung_popup(neu, s))

    def _zeige_freischaltung_popup(self, neu_liste, s):
        ui = self.ui
        lvl = berechne_level(s.get("level_xp", 0))
        tracking_senden("level_up", sprache=self.ls, level=lvl)
        for key in neu_liste:
            tracking_senden("freischaltung_neu", sprache=self.ls, option=key, level=lvl)
            shop_level_belohnung_geben()
        self._inventar_falls_offen_aktualisieren()
        if getattr(self, "lbl_shop_coins", None) is not None:
            try:
                self._shop_anzeige_aktualisieren()
            except Exception:
                pass
        popup = tk.Toplevel(self.root)
        try:
            popup.iconbitmap(os.path.join(BASE_DIR, "heart.ico"))
        except Exception:
            pass
        popup.title("🎉 Level Up!")
        popup.resizable(False, False)
        popup.configure(bg=CLR["popup_bg"])
        popup.grab_set()

        tk.Label(popup, text=t(ui, "level_auf", lvl=lvl),
                 font=fnt(14, "bold"), bg=CLR["popup_bg"], fg=CLR["xp"]).pack(pady=(SKAL.s(20), SKAL.s(8)), padx=SKAL.s(30))

        for (key, beschr, icon, req_lvl) in neu_liste:
            tk.Label(popup, text=f"{icon}  {beschr}",
                     font=fnt(12), bg=CLR["popup_bg"], fg=CLR["text"]).pack(pady=SKAL.s(4), padx=SKAL.s(30))
            tk.Label(popup, text="🎁  +500 Coins, +2 🃏, +2 🧪, +2 🟡, +5 Packs",
                     font=fnt(9), bg=CLR["popup_bg"], fg=CLR["sub"]).pack(pady=(0, SKAL.s(4)), padx=SKAL.s(30))

        tk.Label(popup,
                 text="👉 Aktiviere es unter 'Freischaltungen'!",
                 font=fnt(10, "italic"), bg=CLR["popup_bg"], fg=CLR["sub"]).pack(pady=(SKAL.s(4), SKAL.s(0)), padx=SKAL.s(30))

        tk.Button(popup, text="OK  🎉", font=fnt(12, "bold"),
                  bg=CLR["xp"], fg="white", relief="flat", padx=SKAL.s(20), pady=SKAL.s(8),
                  cursor="hand2", command=popup.destroy).pack(pady=(SKAL.s(12), SKAL.s(20)))

        self.root.update_idletasks()
        x = self.root.winfo_x() + self.root.winfo_width()  // 2 - 180
        y = self.root.winfo_y() + self.root.winfo_height() // 2 - 120
        popup.geometry(f"360x{100 + len(neu_liste)*68}+{x}+{y}")

    def _test_weiter(self):
        self.test_index += 1
        self.test_naechste()

    def _test_abschluss(self):
        self._session_beenden()
        ui = self.ui
        g  = len(self.test_liste)
        r  = self.test_richtig_n
        f  = self.test_falsch_n
        p  = int((r / g) * 100) if g else 0
        s  = stats_laden()
        lvl = berechne_level(s.get("level_xp", 0))
        tracking_senden("test_ende", sprache=self.ls, richtig=r, falsch=f,
                        modus=getattr(self, "aktueller_modus", "test"), level=lvl)
        messagebox.showinfo("🎉",
            t(ui, "test_ergebnis", r=r, g=g, p=p, f=f) +
            f"\n\n{t(ui,'stat_level')} {lvl}")
        self.zeige_hauptmenue()

    def _zeige_weiter_button(self, loesung):
        """Zeigt die Loesung im Feedback-Label und verwandelt den bestehenden
        Pruefen-Button in einen Weiter-Button (kein separates Popup-Fenster,
        damit es unter Windows keine Fokus-/Sichtbarkeitsprobleme geben kann)."""
        ui = self.ui
        aktueller_text = self.lbl_test_feedback.cget("text")
        self.lbl_test_feedback.config(
            text=aktueller_text + "\n" + t(ui, "test_loesung") + " " + loesung,
            fg=CLR["red"])

        self.btn_pruefen.config(
            text=t(ui, "weiter"), bg=CLR["orange"], state="normal",
            command=self._weiter_nach_3_fehlern)
        self.root.bind("<Return>", lambda e: self._weiter_nach_3_fehlern())
        self.btn_pruefen.focus_set()

    def _weiter_nach_3_fehlern(self):
        self.btn_pruefen.config(
            text=t(self.ui, "test_prufen"), bg=CLR["orange"],
            command=self.test_pruefen)
        self.root.bind("<Return>", lambda e: self.test_pruefen())
        self.test_index += 1
        self.test_naechste()


    def zeige_blitz(self, umgekehrt=False, auswahl=None):
        self._session_starten()
        self.aktueller_modus = "blitz"
        tracking_senden("blitz_start", sprache=self.ls)
        ui, ls = self.ui, self.ls
        mutter = muttersprache_label(ui)

        self._aktuelle_ansicht = lambda: self.zeige_blitz(umgekehrt, auswahl=auswahl)
        self.clear()
        if self.root.winfo_width() <= 1:
            self.root.geometry("460x480")
            SKAL.setze_basis(460, 480)
        self._blitz_after = None

        vok_liste = auswahl if auswahl is not None else vokabeln_fuer_test(ls)
        self.test_liste      = vok_liste[:]
        random.shuffle(self.test_liste)
        self.test_index      = 0
        self.test_richtig_n  = 0
        self.test_falsch_n   = 0
        self.test_umgekehrt  = umgekehrt
        self.test_key_oben    = "nativ"
        self.test_key_loesung = "lern"
        self.test_streak     = 0
        self.xp_multiplikator = 1.5 if hat_freischaltung("xp_multiplikator") else 1.0
        self.streak_bonus_aktiv = hat_freischaltung("streak_bonus")
        self.joker_verfuegbar   = False
        self._blitz_zeit_rest   = 5

        tk.Label(self.root, text=t(ui, "blitz_titel"), font=fnt(16, "bold"),
                 bg=CLR["bg"], fg=CLR["red"]).pack(pady=(16, 2))

        self.lbl_test_nr = tk.Label(self.root, text="", font=fnt(11),
                                    bg=CLR["bg"], fg=CLR["sub"])
        self.lbl_test_nr.pack()

        self.lbl_blitz_timer = tk.Label(self.root, text="⏱ 5s",
                                         font=fnt(18, "bold"),
                                         bg=CLR["bg"], fg=CLR["red"])
        self.lbl_blitz_timer.pack()

        self.lbl_streak = tk.Label(self.root, text="", font=fnt(11, "bold"),
                                   bg=CLR["bg"], fg="#e74c3c")
        self.lbl_streak.pack()

        f_a = tk.Frame(self.root, bg=CLR["white"],
                       highlightbackground=CLR["card_border"], highlightthickness=2)
        f_a.pack(padx=SKAL.s(40), fill="x", pady=(8, 6))
        tk.Label(f_a, text=mutter.upper(), font=fnt(11, "bold"),
                 bg=CLR["white"], fg=CLR["text"]).pack(pady=(8, 2))
        self.lbl_test_a = tk.Label(f_a, text="", font=fnt(22, "bold"),
                                   bg=CLR["white"], fg=CLR["text"])
        self.lbl_test_a.pack(pady=(0, 10))

        f_b = tk.Frame(self.root, bg=CLR["white"],
                       highlightbackground=CLR["card_border"], highlightthickness=2)
        f_b.pack(padx=SKAL.s(40), fill="x", pady=(0, 6))
        tk.Label(f_b, text=langname(ui, ls).upper(), font=fnt(11, "bold"),
                 bg=CLR["white"], fg=CLR["text"]).pack(pady=(8, 2))
        self.test_eingabe = tk.Entry(f_b, font=fnt(20, "bold"), justify="center",
                                     fg=CLR["entry_fg"], bd=0, highlightthickness=0,
                                     bg=CLR["entry_bg"], insertbackground=CLR["entry_ins"])
        self.test_eingabe.pack(fill="x", padx=SKAL.s(12), pady=(0, 8))

        self.lbl_test_feedback = tk.Label(self.root, text="", font=fnt(12),
                                          bg=CLR["bg"])
        self.lbl_test_feedback.pack(pady=(0, 4))

        self.lbl_test_status = tk.Label(self.root, text=self._status_zeile_text(), font=fnt(9, "bold"),
                                        bg=CLR["bg"], fg=CLR["sub"])
        self.lbl_test_status.pack(pady=(0, 4))

        row = make_frame(self.root)
        row.pack()
        self.btn_pruefen = tk.Button(row, text=t(ui, "test_prufen"),
                                     font=fnt(12, "bold"),
                                     bg=CLR["red"], fg="white", relief="flat",
                                     padx=SKAL.s(20), pady=SKAL.s(8), cursor="hand2",
                                     command=self._blitz_pruefen)
        self.btn_pruefen.pack(side="left", padx=SKAL.s(4))
        tk.Button(row, text=t(ui, "zurueck"), font=fnt(12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=SKAL.s(14), pady=SKAL.s(8),
                  cursor="hand2", command=self._test_zurueck).pack(side="left", padx=SKAL.s(4))
        tk.Button(row, text="\U0001F392", font=("Segoe UI Emoji", SKAL.s(12), "bold"),
                  bg=CLR["light"], fg=CLR["text"], relief="flat", padx=SKAL.s(14), pady=SKAL.s(8),
                  cursor="hand2", command=self.zeige_inventar).pack(side="left", padx=SKAL.s(4))

        self.root.bind("<Return>", lambda e: self._blitz_pruefen())
        self._blitz_naechste()

    def _blitz_naechste(self):
        ui = self.ui
        if self.test_index >= len(self.test_liste):
            self._test_abschluss()
            return
        vok = self.test_liste[self.test_index]
        self.lbl_test_a.config(text=vok[self.test_key_oben])
        self.lbl_test_nr.config(
            text=t(ui, "test_frage", i=self.test_index+1, n=len(self.test_liste)))
        self.lbl_test_feedback.config(text="")
        self.test_eingabe.config(state="normal")
        self.test_eingabe.delete(0, tk.END)
        self.btn_pruefen.config(state="normal")
        self.test_eingabe.focus()
        self._blitz_zeit_rest = 5
        self._blitz_tick()

    def _blitz_tick(self):
        if self._blitz_zeit_rest <= 0:
            ui = self.ui
            vok = self.test_liste[self.test_index]
            wort_key = vok.get("nativ", "")
            self.test_falsch_n += 1
            self.test_streak = 0
            xp_v = self._xp_verlust()
            self._update_wort_stats(wort_key, richtig=False, xp=xp_v)
            self.lbl_test_feedback.config(text=t(ui, "blitz_abgelaufen"), fg=CLR["red"])
            self.test_eingabe.config(state="disabled")
            self.btn_pruefen.config(state="disabled")
            self.root.after(1200, lambda: (self.__dict__.update({"test_index": self.test_index+1}),
                                           self._blitz_naechste()))
            return
        self.lbl_blitz_timer.config(
            text=f"⏱ {self._blitz_zeit_rest}s",
            fg=CLR["red"] if self._blitz_zeit_rest <= 2 else CLR["orange"])
        self._blitz_zeit_rest -= 1
        self._blitz_after = self.root.after(1000, self._blitz_tick)

    def _blitz_pruefen(self):
        if self.test_eingabe.cget("state") == "disabled":
            return
        if self._blitz_after:
            self.root.after_cancel(self._blitz_after)
            self._blitz_after = None
        ui      = self.ui
        antwort = self.test_eingabe.get().strip().lower()
        vok     = self.test_liste[self.test_index]
        loesung = vok[self.test_key_loesung]
        wort_key = vok.get("nativ", "")

        if antwort == loesung.lower():
            self.test_richtig_n += 1
            self.test_streak += 1
            xp_g = self._xp_fuer_richtig()
            coins_g = shop_coins_effektiv(1)
            self._update_wort_stats(wort_key, richtig=True, xp=xp_g)
            self.lbl_test_feedback.config(
                text=t(ui, "test_richtig") + f"  +{xp_format(xp_g)} XP  +{coins_g} \U0001FA99", fg="#27ae60")
            self.lbl_test_status.config(text=self._status_zeile_text())
            self.test_eingabe.config(state="disabled")
            self.btn_pruefen.config(state="disabled")
            self.test_index += 1
            self.root.after(700, self._blitz_naechste)
        else:
            self.test_falsch_n += 1
            self.test_streak = 0
            xp_v = self._xp_verlust()
            self._update_wort_stats(wort_key, richtig=False, xp=xp_v)
            self.lbl_test_feedback.config(
                text=t(ui, "test_falsch_end") + f"  -{xp_format(xp_v)} XP  ✓{loesung}",
                fg=CLR["red"])
            self.lbl_test_status.config(text=self._status_zeile_text())
            self.test_eingabe.config(state="disabled")
            self.btn_pruefen.config(state="disabled")
            self.test_index += 1
            self.root.after(1400, self._blitz_naechste)

    def zeige_mc(self, auswahl=None):
        self._session_starten()
        self.aktueller_modus = "mc"
        tracking_senden("mc_start", sprache=self.ls)
        ui, ls = self.ui, self.ls
        mutter = muttersprache_label(ui)

        self._aktuelle_ansicht = lambda: self.zeige_mc(auswahl=auswahl)
        self.clear()
        if self.root.winfo_width() <= 1:
            self.root.geometry("460x500")
            SKAL.setze_basis(460, 500)

        alle = vokabeln_laden(ls)
        vok_liste = auswahl if auswahl is not None else vokabeln_fuer_test(ls)
        if len(alle) < 4:
            messagebox.showinfo("", "Für Multiple Choice mindestens 4 Vokabeln nötig!")
            self.zeige_hauptmenue()
            return
        self.test_liste = vok_liste[:]
        random.shuffle(self.test_liste)
        self.test_index     = 0
        self.test_richtig_n = 0
        self.test_falsch_n  = 0
        self.test_streak    = 0
        self.xp_multiplikator    = 1.5 if hat_freischaltung("xp_multiplikator") else 1.0
        self.streak_bonus_aktiv  = hat_freischaltung("streak_bonus")

        tk.Label(self.root, text=t(ui, "mc_titel"), font=fnt(16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(16, 4))

        self.lbl_test_nr = tk.Label(self.root, text="", font=fnt(11),
                                    bg=CLR["bg"], fg=CLR["sub"])
        self.lbl_test_nr.pack()
        self.lbl_streak = tk.Label(self.root, text="", font=fnt(11, "bold"),
                                   bg=CLR["bg"], fg="#e74c3c")
        self.lbl_streak.pack()

        f_a = tk.Frame(self.root, bg=CLR["white"],
                       highlightbackground=CLR["card_border"], highlightthickness=2)
        f_a.pack(padx=SKAL.s(40), fill="x", pady=(8, 12))
        tk.Label(f_a, text=mutter.upper(), font=fnt(11, "bold"),
                 bg=CLR["white"], fg=CLR["text"]).pack(pady=(8, 2))
        self.lbl_mc_frage = tk.Label(f_a, text="", font=fnt(22, "bold"),
                                      bg=CLR["white"], fg=CLR["text"])
        self.lbl_mc_frage.pack(pady=(0, 10))

        self.lbl_test_feedback = tk.Label(self.root, text="", font=fnt(12),
                                          bg=CLR["bg"])
        self.lbl_test_feedback.pack()

        self.lbl_test_status = tk.Label(self.root, text=self._status_zeile_text(), font=fnt(9, "bold"),
                                        bg=CLR["bg"], fg=CLR["sub"])
        self.lbl_test_status.pack()

        self.mc_btn_frame = make_frame(self.root)
        self.mc_btn_frame.pack(padx=SKAL.s(40), fill="x", pady=8)

        tk.Button(self.root, text=t(ui, "zurueck"), font=fnt(12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=SKAL.s(14), pady=SKAL.s(8),
                  cursor="hand2", command=self._test_zurueck).pack(pady=8)

        tk.Button(self.root, text="\U0001F392", font=("Segoe UI Emoji", SKAL.s(12), "bold"),
                  bg=CLR["light"], fg=CLR["text"], relief="flat", padx=SKAL.s(14), pady=SKAL.s(6),
                  cursor="hand2", command=self.zeige_inventar).pack(pady=(0, 8))

        self._mc_naechste(alle)

    def _mc_naechste(self, alle):
        ui = self.ui
        if self.test_index >= len(self.test_liste):
            self._test_abschluss()
            return
        vok = self.test_liste[self.test_index]
        richtig = vok.get("lern", "")
        self.lbl_mc_frage.config(text=vok.get("nativ", ""))
        self.lbl_test_nr.config(
            text=t(ui, "test_frage", i=self.test_index+1, n=len(self.test_liste)))
        self.lbl_test_feedback.config(text="")
        if self.test_streak >= 5 and self.streak_bonus_aktiv:
            self.lbl_streak.config(text=t(ui, "streak", n=self.test_streak) + " 2x XP!")
        elif self.test_streak >= 3:
            self.lbl_streak.config(text=t(ui, "streak", n=self.test_streak))
        else:
            self.lbl_streak.config(text="")

        falsche = [v.get("lern","") for v in alle if v.get("lern","") != richtig]
        random.shuffle(falsche)
        optionen = [richtig] + falsche[:3]
        random.shuffle(optionen)

        for w in self.mc_btn_frame.winfo_children():
            w.destroy()

        for opt in optionen:
            btn = tk.Button(self.mc_btn_frame, text=opt, font=fnt(13, "bold"),
                            bg=CLR["white"], fg=CLR["text"],
                            relief="flat", bd=0,
                            highlightbackground=CLR["card_border"], highlightthickness=2,
                            padx=10, pady=10, cursor="hand2",
                            wraplength=340,
                            command=lambda o=opt, r=richtig, v=vok: self._mc_antwort(o, r, v, alle))
            btn.pack(fill="x", pady=3)

    def _mc_antwort(self, antwort, richtig, vok, alle):
        ui = self.ui
        wort_key = vok.get("nativ", "")
        if antwort == richtig:
            self.test_richtig_n += 1
            self.test_streak += 1
            xp_g = self._xp_fuer_richtig()
            coins_g = shop_coins_effektiv(1)
            self._update_wort_stats(wort_key, richtig=True, xp=xp_g)
            self.lbl_test_feedback.config(
                text=t(ui, "test_richtig") + f"  +{xp_format(xp_g)} XP  +{coins_g} \U0001FA99", fg="#27ae60")
            self.lbl_test_status.config(text=self._status_zeile_text())
            for btn in self.mc_btn_frame.winfo_children():
                btn.config(state="disabled",
                           bg="#27ae60" if btn.cget("text") == richtig else CLR["white"])
            self.test_index += 1
            self.root.after(900, lambda: self._mc_naechste(alle))
        else:
            self.test_falsch_n += 1
            self.test_streak = 0
            xp_v = self._xp_verlust()
            self._update_wort_stats(wort_key, richtig=False, xp=xp_v)
            self.lbl_test_feedback.config(
                text=t(ui, "test_falsch_end") + f"  -{xp_format(xp_v)} XP", fg=CLR["red"])
            self.lbl_test_status.config(text=self._status_zeile_text())
            for btn in self.mc_btn_frame.winfo_children():
                btn.config(state="disabled",
                           bg="#27ae60" if btn.cget("text") == richtig else
                           (CLR["red"] if btn.cget("text") == antwort else CLR["white"]))
            self.test_index += 1
            self.root.after(1400, lambda: self._mc_naechste(alle))

    def zeige_artikel(self, auswahl=None):
        self._session_starten()
        self.aktueller_modus = "artikel"
        tracking_senden("artikel_start", sprache=self.ls)
        ui, ls = self.ui, self.ls

        self._aktuelle_ansicht = lambda: self.zeige_artikel(auswahl=auswahl)
        self.clear()
        if self.root.winfo_width() <= 1:
            self.root.geometry("460x500")
            SKAL.setze_basis(460, 500)

        alle = vokabeln_mit_artikel(ls)
        if auswahl is not None:
            auswahl_keys = {(v.get("nativ",""), v.get("lern","")) for v in auswahl}
            vok_liste = [v for v in alle
                         if (v.get("nativ",""), v.get("lern","")) in auswahl_keys]
        else:
            vok_liste = alle
        if len(alle) < 2:
            messagebox.showinfo("", "Für den Artikel-Modus mindestens 2 passende Vokabeln nötig!")
            self.zeige_hauptmenue()
            return
        if not vok_liste:
            vok_liste = alle

        self.test_liste = vok_liste[:]
        random.shuffle(self.test_liste)
        self.test_index     = 0
        self.test_richtig_n = 0
        self.test_falsch_n  = 0
        self.test_streak    = 0
        self.xp_multiplikator    = 1.5 if hat_freischaltung("xp_multiplikator") else 1.0
        self.streak_bonus_aktiv  = hat_freischaltung("streak_bonus")

        tk.Label(self.root, text=t(ui, "artikel_titel"), font=fnt(16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(16, 4))

        self.lbl_test_nr = tk.Label(self.root, text="", font=fnt(11),
                                    bg=CLR["bg"], fg=CLR["sub"])
        self.lbl_test_nr.pack()
        self.lbl_streak = tk.Label(self.root, text="", font=fnt(11, "bold"),
                                   bg=CLR["bg"], fg="#e74c3c")
        self.lbl_streak.pack()

        f_a = tk.Frame(self.root, bg=CLR["white"],
                       highlightbackground=CLR["card_border"], highlightthickness=2)
        f_a.pack(padx=SKAL.s(40), fill="x", pady=(8, 12))
        self.lbl_artikel_frage = tk.Label(f_a, text="", font=fnt(22, "bold"),
                                          bg=CLR["white"], fg=CLR["text"])
        self.lbl_artikel_frage.pack(pady=(10, 10))

        self.lbl_test_feedback = tk.Label(self.root, text="", font=fnt(12),
                                          bg=CLR["bg"])
        self.lbl_test_feedback.pack()

        self.lbl_test_status = tk.Label(self.root, text=self._status_zeile_text(), font=fnt(9, "bold"),
                                        bg=CLR["bg"], fg=CLR["sub"])
        self.lbl_test_status.pack()

        self.artikel_btn_frame = make_frame(self.root)
        self.artikel_btn_frame.pack(padx=SKAL.s(40), fill="x", pady=8)

        tk.Button(self.root, text=t(ui, "zurueck"), font=fnt(12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=SKAL.s(14), pady=SKAL.s(8),
                  cursor="hand2", command=self._test_zurueck).pack(pady=8)

        tk.Button(self.root, text="\U0001F392", font=("Segoe UI Emoji", SKAL.s(12), "bold"),
                  bg=CLR["light"], fg=CLR["text"], relief="flat", padx=SKAL.s(14), pady=SKAL.s(6),
                  cursor="hand2", command=self.zeige_inventar).pack(pady=(0, 8))

        self._artikel_naechste(alle)

    def _artikel_naechste(self, alle):
        ui = self.ui
        if self.test_index >= len(self.test_liste):
            self._test_abschluss()
            return
        vok = self.test_liste[self.test_index]
        richtige_artikel = [a.lower() for a in vok.get("_artikel", [])]
        self.lbl_artikel_frage.config(text=vok.get("_artikel_wort", ""))
        self.lbl_test_nr.config(
            text=t(ui, "test_frage", i=self.test_index+1, n=len(self.test_liste)))
        self.lbl_test_feedback.config(text="")
        if self.test_streak >= 5 and self.streak_bonus_aktiv:
            self.lbl_streak.config(text=t(ui, "streak", n=self.test_streak) + " 2x XP!")
        elif self.test_streak >= 3:
            self.lbl_streak.config(text=t(ui, "streak", n=self.test_streak))
        else:
            self.lbl_streak.config(text="")

        if len(richtige_artikel) >= 2:
            # Doppel-Artikel-Wort: beide hinterlegten Artikel sind richtig,
            # der Rest wird mit zufälligen falschen Artikeln auf 4 aufgefüllt.
            basis = list(dict.fromkeys(vok.get("_artikel", [])))[:2]
        else:
            # Einzel-Artikel-Wort: nur 1 Artikel ist richtig.
            basis = [vok.get("_artikel", [""])[0]]

        optionen = basis[:]
        ablenker_pool = [a for a in ARTIKEL_WOERTER if a not in richtige_artikel]
        random.shuffle(ablenker_pool)
        for a in ablenker_pool:
            if len(optionen) >= 4:
                break
            optionen.append(a.capitalize())
        random.shuffle(optionen)

        for w in self.artikel_btn_frame.winfo_children():
            w.destroy()

        for opt in optionen:
            ist_richtig = opt.lower() in richtige_artikel
            btn = tk.Button(self.artikel_btn_frame, text=opt, font=fnt(13, "bold"),
                            bg=CLR["white"], fg=CLR["text"],
                            relief="flat", bd=0,
                            highlightbackground=CLR["card_border"], highlightthickness=2,
                            padx=10, pady=10, cursor="hand2",
                            wraplength=340,
                            command=lambda o=opt, ri=ist_richtig, v=vok: self._artikel_antwort(o, ri, v, alle))
            btn.pack(fill="x", pady=3)

    def _artikel_antwort(self, antwort, ist_richtig, vok, alle):
        ui = self.ui
        wort_key = vok.get("nativ", "")
        if ist_richtig:
            self.test_richtig_n += 1
            self.test_streak += 1
            xp_g = self._xp_fuer_richtig()
            coins_g = shop_coins_effektiv(1)
            self._update_wort_stats(wort_key, richtig=True, xp=xp_g)
            self.lbl_test_feedback.config(
                text=t(ui, "test_richtig") + f"  +{xp_format(xp_g)} XP  +{coins_g} \U0001FA99", fg="#27ae60")
            self.lbl_test_status.config(text=self._status_zeile_text())
            for btn in self.artikel_btn_frame.winfo_children():
                btn.config(state="disabled")
                if btn.cget("text") == antwort:
                    btn.config(bg="#27ae60")
            self.test_index += 1
            self.root.after(900, lambda: self._artikel_naechste(alle))
        else:
            self.test_falsch_n += 1
            self.test_streak = 0
            xp_v = self._xp_verlust()
            self._update_wort_stats(wort_key, richtig=False, xp=xp_v)
            self.lbl_test_feedback.config(
                text=t(ui, "test_falsch_end") + f"  -{xp_format(xp_v)} XP", fg=CLR["red"])
            self.lbl_test_status.config(text=self._status_zeile_text())
            richtige_artikel = [a.lower() for a in vok.get("_artikel", [])]
            for btn in self.artikel_btn_frame.winfo_children():
                btn.config(state="disabled")
                if btn.cget("text").lower() in richtige_artikel:
                    btn.config(bg="#27ae60")
                elif btn.cget("text") == antwort:
                    btn.config(bg=CLR["red"])
            self.test_index += 1
            self.root.after(1400, lambda: self._artikel_naechste(alle))

    def zeige_bearbeiten(self):
        self._aktuelle_ansicht = self.zeige_bearbeiten
        self.clear()
        if self.root.winfo_width() <= 1:
            self.root.geometry("660x560")
            SKAL.setze_basis(660, 560)
        ui, ls = self.ui, self.ls

        titel_row = tk.Frame(self.root, bg=CLR["bg"])
        titel_row.pack(pady=(16, 6))
        tk.Label(titel_row, text="❤️", font=("Segoe UI Emoji", 16), bg=CLR["bg"], fg="#ff0000").pack(side="left", padx=(0, 6))
        tk.Label(titel_row, text=t(ui, "bear_titel").replace("❤️", "").strip(), font=fnt(16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(side="left")

        such_frame = make_frame(self.root)
        such_frame.pack(padx=SKAL.s(20), fill="x", pady=(0, 8))

        such_outer = tk.Frame(such_frame, bg=CLR["border"],
                              highlightbackground=CLR["border"], highlightthickness=2)
        such_outer.pack(fill="x")

        self.such_var  = tk.StringVar()
        such_entry = tk.Entry(such_outer, textvariable=self.such_var,
                              font=fnt(12, "bold"), fg=CLR["entry_fg"],
                              bg=CLR["entry_bg"],
                              bd=0, relief="flat", highlightthickness=0,
                              insertbackground=CLR["entry_ins"])
        such_entry.pack(fill="x", ipady=8, padx=SKAL.s(6))

        placeholder = t(ui, "bear_suche")
        such_entry.insert(0, placeholder)
        such_entry.config(fg=CLR["sub"])
        self._such_placeholder_aktiv = True

        def on_focus_in(e):
            if self._such_placeholder_aktiv:
                such_entry.delete(0, tk.END)
                such_entry.config(fg=CLR["entry_fg"])
                such_outer.config(highlightbackground=CLR["blue"])
                self._such_placeholder_aktiv = False

        def on_focus_out(e):
            if not such_entry.get().strip():
                such_entry.insert(0, placeholder)
                such_entry.config(fg=CLR["sub"])
                such_outer.config(highlightbackground=CLR["border"])
                self._such_placeholder_aktiv = True

        def on_key(_=None):
            if self._such_placeholder_aktiv:
                return
            q = such_entry.get().strip()
            self.bear_aufbauen(q)

        such_entry.bind("<FocusIn>",  on_focus_in)
        such_entry.bind("<FocusOut>", on_focus_out)
        such_entry.bind("<KeyRelease>", lambda e: self.root.after(10, on_key))

        self._bear_nur_falsche = getattr(self, "_bear_nur_falsche", tk.BooleanVar(value=False))
        def _filter_umschalten():
            q = "" if self._such_placeholder_aktiv else such_entry.get().strip()
            self.bear_aufbauen(q)
        tk.Checkbutton(such_frame, text=t(ui, "bear_nur_falsche"),
                       variable=self._bear_nur_falsche, font=fnt(10, "bold"),
                       bg=CLR["bg"], fg=CLR["red"], activebackground=CLR["bg"],
                       selectcolor=CLR["bg"], cursor="hand2",
                       command=_filter_umschalten).pack(anchor="w", pady=(SKAL.s(4), SKAL.s(0)))

        container = make_frame(self.root)
        container.pack(padx=SKAL.s(16), fill="both", expand=True)
        canvas    = tk.Canvas(container, bg=CLR["bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.scroll_frame = make_frame(canvas)
        self.scroll_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            try:
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except Exception:
                pass
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self.bear_aufbauen()

        btn_row = make_frame(self.root)
        btn_row.pack(pady=SKAL.s(8))
        tk.Button(btn_row, text=t(ui, "bear_alle_audios_laden"), font=fnt(11, "bold"),
                  bg="#16a085", fg="white", relief="flat", padx=SKAL.s(12), pady=SKAL.s(8),
                  cursor="hand2", command=self.bear_audios_nachladen).pack(side="left", padx=SKAL.s(6))
        tk.Button(btn_row, text=t(ui, "bear_reset_audio"), font=fnt(11, "bold"),
                  bg="#c0392b", fg="white", relief="flat", padx=SKAL.s(12), pady=SKAL.s(8),
                  cursor="hand2", command=self.bear_audio_reset).pack(side="left", padx=SKAL.s(6))
        tk.Button(btn_row, text=t(ui, "zurueck"), font=fnt(12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=SKAL.s(14), pady=SKAL.s(8),
                  cursor="hand2", command=self._bear_zurueck).pack(side="left", padx=SKAL.s(6))

        tk.Frame(btn_row, bg=CLR["border"], width=2).pack(side="left", fill="y", padx=SKAL.s(12))

        def _seite_wechseln(delta):
            self._bear_seite += delta
            self.bear_aufbauen(suche=self._bear_letzte_suche, seite_reset=False)

        self._bear_btn_zurueck = tk.Button(btn_row, text=t(ui, "bear_zurueck_kurz"), font=fnt(11, "bold"),
                  bg=CLR["blue"], fg="white", relief="flat", padx=SKAL.s(14), pady=SKAL.s(6),
                  cursor="hand2", command=lambda: _seite_wechseln(-1))
        self._bear_btn_zurueck.pack(side="left", padx=SKAL.s(6))

        self._bear_lbl_seite = tk.Label(btn_row, text=t(ui, "bear_seite", i=1, n=1),
                 font=fnt(11, "bold"), bg=CLR["bg"], fg=CLR["sub"])
        self._bear_lbl_seite.pack(side="left", padx=SKAL.s(10))

        self._bear_btn_weiter = tk.Button(btn_row, text=t(ui, "bear_weiter_kurz"), font=fnt(11, "bold"),
                  bg=CLR["blue"], fg="white", relief="flat", padx=SKAL.s(14), pady=SKAL.s(6),
                  cursor="hand2", command=lambda: _seite_wechseln(1))
        self._bear_btn_weiter.pack(side="left", padx=SKAL.s(6))

        self._bear_pagination_aktualisieren()

    def _bear_zurueck(self):
        self._bear_play_abbrechen = True
        self.zeige_hauptmenue()

    def bear_audio_reset(self):
        """Loescht KOMPLETT alle Audio-Dateien und -Ordner (Haupt-Audio-Ordner
        UND kompletten Silben-Wurzelordner, unabhaengig von Lernsprache) und
        leert 'audio' + 'silben' bei allen Vokabeln, damit ueber 'Alle
        fehlenden Audios laden' wirklich ALLES (Hauptwort, Silben, geteilte
        Woerter) komplett neu heruntergeladen wird."""
        ui, ls = self.ui, self.ls
        if not messagebox.askyesno(t(ui, "bear_titel"),
                                    t(ui, "bear_reset_frage")):
            return

        def _ordner_komplett_leeren(pfad):
            if not os.path.isdir(pfad):
                return
            for wurzel, ordner_liste, datei_liste in os.walk(pfad, topdown=False):
                for datei in datei_liste:
                    try:
                        os.remove(os.path.join(wurzel, datei))
                    except Exception:
                        pass
                for unterordner in ordner_liste:
                    try:
                        os.rmdir(os.path.join(wurzel, unterordner))
                    except Exception:
                        pass

        _ordner_komplett_leeren(AUDIO_DIR)

        for sprache_ls in ("de", "en", "fi"):
            try:
                liste = vokabeln_laden(sprache_ls)
            except Exception:
                continue
            for v in liste:
                v["audio"] = ""
                v["silben"] = ""
            vokabeln_speichern(sprache_ls, liste)

        os.makedirs(AUDIO_DIR, exist_ok=True)
        os.makedirs(GETEILT_ORDNER, exist_ok=True)

        aktive_suche = ""
        if hasattr(self, "such_var") and not getattr(self, "_such_placeholder_aktiv", True):
            aktive_suche = self.such_var.get().strip()
        self.bear_aufbauen(aktive_suche)
        messagebox.showinfo(t(ui, "bear_titel"), t(ui, "bear_reset_fertig"))

    def bear_audios_nachladen(self):
        ui, ls = self.ui, self.ls
        liste = vokabeln_laden(ls)

        fehlend = [i for i, v in enumerate(liste)
                   if not v.get("audio", "").strip()
                   or not os.path.exists(audio_pfad(v.get("audio", "").strip()))
                   or not alle_silben_audios_vorhanden(v, ls)
                   or not v.get("silben", "").strip()]
        if not fehlend:
            messagebox.showinfo(t(ui, "bear_titel"), t(ui, "bear_audio_vorhanden"))
            return

        # Gesamtzahl der tatsaechlichen Einzel-Downloads vorab berechnen
        # (1 pro fehlendem Wort-Audio + 1 pro fehlender Silben-Datei),
        # damit die Anzeige die echte Anzahl an Schritten zeigt statt nur
        # die Anzahl betroffener Vokabeln.
        gesamt_schritte = 0
        for v in liste:
            wort = v.get("lern", "")
            if (not v.get("audio", "").strip() or not os.path.exists(audio_pfad(v.get("audio", "").strip()))) and wort.strip():
                gesamt_schritte += 1
            if wort.strip():
                silben = silben_liste_holen(v)
                for s in silben:
                    ordner = _silben_wort_ordner(s if s.strip().lower() in ARTIKEL_WOERTER else wort)
                    pfad = os.path.join(ordner, gtts_dateiname_silbe(s, ls))
                    if not os.path.exists(pfad):
                        gesamt_schritte += 1
        if gesamt_schritte == 0:
            gesamt_schritte = len(fehlend)

        popup = tk.Toplevel(self.root)
        try:
            popup.iconbitmap(os.path.join(BASE_DIR, "heart.ico"))
        except Exception:
            pass
        popup.title(t(ui, "bear_lade_titel"))
        popup.configure(bg=CLR["popup_bg"])
        popup.transient(self.root)
        popup.grab_set()
        popup.resizable(False, False)

        lbl_status = tk.Label(popup, text=t(ui, "bear_downloads_status", geschafft=0, gesamt=gesamt_schritte),
                              font=("Arial", 13, "bold"),
                              bg=CLR["popup_bg"], fg=CLR["text"])
        lbl_status.pack(padx=30, pady=(24, 2))

        lbl_wortzahl_hinweis = tk.Label(popup, text=t(ui, "bear_woerter_hinweis", n=len(fehlend)),
                              font=("Arial", 9), bg=CLR["popup_bg"], fg=CLR["sub"])
        lbl_wortzahl_hinweis.pack(padx=30, pady=(0, 6))

        lbl_detail = tk.Label(popup, text="", font=("Arial", 10),
                              bg=CLR["popup_bg"], fg=CLR["sub"],
                              wraplength=320)
        lbl_detail.pack(padx=30, pady=(0, 20))

        self.root.update_idletasks()
        x = self.root.winfo_x() + self.root.winfo_width()  // 2 - 190
        y = self.root.winfo_y() + self.root.winfo_height() // 2 - 60
        popup.geometry(f"380x140+{x}+{y}")

        abgebrochen = {"flag": False}
        popup.protocol("WM_DELETE_WINDOW", lambda: abgebrochen.__setitem__("flag", True))

        def worker():
            erfolgreich = 0
            fehlgeschlagen = 0
            geschafft = 0
            downloads_seit_pause = 0
            fehlschlaege_in_folge = 0
            fehlgeschlagene_namen = []
            liste_aktuell = vokabeln_laden(ls)

            def update_ui(wort, ok=True):
                lbl_status.config(text=t(ui, "bear_downloads_status", geschafft=geschafft, gesamt=gesamt_schritte))
                if fehlschlaege_in_folge > 0:
                    lbl_detail.config(
                        text=t(ui, "bear_fehlschlaege_folge", wort=wort, n=fehlschlaege_in_folge),
                        fg=CLR["red"])
                else:
                    lbl_detail.config(text=wort, fg=CLR["sub"])

            def update_pause_ui(sekunden_rest):
                lbl_status.config(text=t(ui, "bear_downloads_status", geschafft=geschafft, gesamt=gesamt_schritte))
                lbl_detail.config(text=t(ui, "bear_pause_text", s=sekunden_rest))

            def pause_einlegen():
                # Alle 500 tatsaechlichen Downloads eine 10-Sekunden-Pause,
                # damit Google TTS nicht wegen zu vieler Anfragen kurzzeitig blockt.
                for rest in range(10, 0, -1):
                    if abgebrochen["flag"]:
                        return
                    try:
                        self.root.after(0, update_pause_ui, rest)
                    except Exception:
                        pass
                    time.sleep(1)

            for i in fehlend:
                if abgebrochen["flag"]:
                    break
                if i >= len(liste_aktuell):
                    continue
                vok = liste_aktuell[i]
                wort = vok.get("lern", "")

                audio_ok = bool(vok.get("audio", "").strip()) and os.path.exists(audio_pfad(vok.get("audio", "").strip()))
                neuer_audio_name = vok.get("audio", "").strip() if audio_ok else None

                if not audio_ok and wort.strip():
                    auto_name = gtts_dateiname(wort, ls)
                    if gtts_herunterladen(wort, ls, auto_name):
                        neuer_audio_name = auto_name
                        audio_ok = True
                        fehlschlaege_in_folge = 0
                    else:
                        fehlgeschlagen += 1
                        fehlschlaege_in_folge += 1
                        fehlgeschlagene_namen.append(f"{wort}  [Wort-Audio]")
                    geschafft += 1
                    downloads_seit_pause += 1
                    try:
                        self.root.after(0, update_ui, wort)
                    except Exception:
                        pass
                    if downloads_seit_pause >= 500:
                        downloads_seit_pause = 0
                        pause_einlegen()
                    elif fehlschlaege_in_folge >= 20:
                        # Google blockt offenbar schon deutlich vor 500 -
                        # sofort eine laengere Pause einlegen statt stur
                        # weiter Anfragen zu senden, die eh fehlschlagen.
                        fehlschlaege_in_folge = 0
                        downloads_seit_pause = 0
                        pause_einlegen()

                silben_ok = True
                neue_silben_str = vok.get("silben", "").strip() or None

                if wort.strip() and audio_ok and (not alle_silben_audios_vorhanden(vok, ls) or not vok.get("silben", "").strip()):
                    silben = silben_liste_holen(vok)
                    for silbe in silben:
                        ordner = _silben_wort_ordner(silbe if silbe.strip().lower() in ARTIKEL_WOERTER else wort)
                        pfad_vorher = os.path.join(ordner, gtts_dateiname_silbe(silbe, ls))
                        war_da = os.path.exists(pfad_vorher)
                        silbe_ok = bool(audio_silbe_pfad_sicherstellen(silbe, ls, wort))
                        if not war_da:
                            if not silbe_ok:
                                fehlgeschlagen += 1
                                fehlgeschlagene_namen.append(f"{wort} \u2192 Silbe '{silbe}'  [Silben-Audio]")
                            geschafft += 1
                            downloads_seit_pause += 1
                            try:
                                self.root.after(0, update_ui, wort)
                            except Exception:
                                pass
                            if downloads_seit_pause >= 500:
                                downloads_seit_pause = 0
                                pause_einlegen()
                    # Am Ende einmal wirklich gegen die Festplatte pruefen, ob
                    # ausnahmslos alle Silben-Dateien da sind - nicht nur den
                    # Rueckgabewert jedes einzelnen Downloads vertrauen.
                    silben_ok = all(
                        os.path.exists(os.path.join(
                            _silben_wort_ordner(s if s.strip().lower() in ARTIKEL_WOERTER else wort),
                            gtts_dateiname_silbe(s, ls)
                        )) for s in silben
                    )
                    if silben_ok and silben:
                        neue_silben_str = "-".join(silben)
                elif not audio_ok:
                    silben_ok = False

                # Erst wenn Audio UND Silben komplett erfolgreich waren, wird
                # fuer dieses Wort in einem Rutsch geschrieben. Bei jedem
                # Fehlschlag bleibt der Eintrag unveraendert/leer, damit die
                # Vokabel beim naechsten Klick auf den Button wieder korrekt
                # als fehlend erkannt und der Rest automatisch nachgeladen wird.
                if audio_ok and silben_ok:
                    if neuer_audio_name:
                        liste_aktuell[i]["audio"] = neuer_audio_name
                    if neue_silben_str:
                        liste_aktuell[i]["silben"] = neue_silben_str
                    vokabeln_speichern(ls, liste_aktuell)
                    erfolgreich += 1

            def fertig():
                try:
                    popup.destroy()
                except Exception:
                    pass
                self.bear_aufbauen(self.such_var.get().strip()
                                   if hasattr(self, "such_var") and not getattr(self, "_such_placeholder_aktiv", True)
                                   else "")
                # Echte Nachpruefung gegen die Festplatte: wie viele Woerter
                # haben JETZT (nach dem Lauf) tatsaechlich noch eine fehlende
                # Audio- oder Silben-Datei? Das ist die einzig verlaessliche
                # Zahl, da geschafft/gesamt_schritte auseinanderdriften koennen
                # (z.B. wenn ein Wort-Audio fehlschlaegt und dessen Silben nie
                # versucht werden, aber vorab schon mitgezaehlt wurden).
                liste_kontrolle = vokabeln_laden(ls)
                noch_fehlend = [v for v in liste_kontrolle
                                if not v.get("audio", "").strip()
                                or not os.path.exists(audio_pfad(v.get("audio", "").strip()))
                                or not alle_silben_audios_vorhanden(v, ls)
                                or not v.get("silben", "").strip()]
                anzahl_noch_fehlend = len(noch_fehlend)

                if anzahl_noch_fehlend > 0:
                    # Liste der fehlgeschlagenen Woerter/Silben in eine eigene
                    # Datei schreiben, damit man alle sehen kann statt nur die
                    # Anzahl. Wird bei jedem Lauf komplett neu geschrieben.
                    fehl_pfad = os.path.join(BASE_DIR, "audio_fehlgeschlagen.txt")
                    try:
                        with open(fehl_pfad, "w", encoding="utf-8") as f:
                            f.write(f"Fehlgeschlagene Audio-Downloads - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write(f"Lernsprache: {ls}\n")
                            f.write("=" * 50 + "\n\n")
                            for eintrag in fehlgeschlagene_namen:
                                f.write(eintrag + "\n")
                    except Exception:
                        pass
                    vorschau = "\n".join(fehlgeschlagene_namen[:15])
                    if len(fehlgeschlagene_namen) > 15:
                        vorschau += f"\n… und {len(fehlgeschlagene_namen) - 15} weitere"
                    erfolgreich_echt = len(fehlend) - anzahl_noch_fehlend
                    msg = t(ui, "bear_fertig_mit_fehlern",
                            erfolgreich=erfolgreich_echt,
                            gesamt=len(fehlend),
                            fehlgeschlagen=anzahl_noch_fehlend)
                    msg = t(ui, "bear_woerter_zusammenfassung", n=len(fehlend), gesamt=gesamt_schritte) + "\n\n" + msg
                    msg += f"\n\n{t(ui, 'bear_betroffen')}\n{vorschau}\n\n{t(ui, 'bear_volle_liste')}"
                else:
                    msg = t(ui, "bear_fertig_ergebnis", erfolgreich=len(fehlend), gesamt=len(fehlend))
                    msg = t(ui, "bear_woerter_zusammenfassung", n=len(fehlend), gesamt=gesamt_schritte) + "\n\n" + msg
                messagebox.showinfo(t(ui, "bear_titel"), msg)
            try:
                self.root.after(0, fertig)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def bear_aufbauen(self, suche="", seite_reset=True):
        # Schutz gegen Race Condition: Wenn schnell zurück -> rein geklickt wurde,
        # kann clear() das scroll_frame bereits zerstört haben, während ein
        # verzögerter Callback (z.B. after(10, on_key)) noch aussteht.
        if not hasattr(self, "scroll_frame") or not self.scroll_frame.winfo_exists():
            return

        ui, ls = self.ui, self.ls
        lsname = langname(ui, ls)
        mutter = muttersprache_label(ui)

        for w in self.scroll_frame.winfo_children():
            w.destroy()

        alle  = vokabeln_laden(ls)
        alle_sortiert = sorted(alle, key=lambda v: v.get("nativ","").lower())

        if getattr(self, "_bear_nur_falsche", None) is not None and self._bear_nur_falsche.get():
            s  = stats_laden()
            ws = s.get("wort_stats", {})
            falsche_keys = {k for k, st in ws.items() if st.get("falsch", 0) > 0}
            alle_sortiert = [v for v in alle_sortiert if v.get("nativ", "") in falsche_keys]

        q     = suche.lower().strip()
        liste_gesamt = [v for v in alle_sortiert
                 if q in v.get("nativ","").lower() or q in v.get("lern","").lower()] \
                if q else alle_sortiert

        if seite_reset:
            self._bear_seite = 0
            self._bear_letzte_suche = suche
        self._bear_seite = getattr(self, "_bear_seite", 0)
        PRO_SEITE = 10
        gesamt_seiten = max(1, (len(liste_gesamt) + PRO_SEITE - 1) // PRO_SEITE)
        self._bear_seite = max(0, min(self._bear_seite, gesamt_seiten - 1))
        start = self._bear_seite * PRO_SEITE
        liste = liste_gesamt[start:start + PRO_SEITE]

        hdr = tk.Frame(self.scroll_frame, bg=CLR["hdr_bg"])
        hdr.pack(fill="x", pady=(0, 2))
        audio_spalte_txt = t(ui, "bear_audio_spalte")
        for txt, w in [(mutter, 13), (langname(ui, ls), 13),
                       (audio_spalte_txt, 5), ("", 5), ("", 2), (t(ui,"bear_aktion"), 20)]:
            tk.Label(hdr, text=txt, font=fnt(11, "bold"),
                     bg=CLR["hdr_bg"], fg=CLR["hdr_fg"], width=w, anchor="w").pack(side="left", padx=SKAL.s(6), pady=SKAL.s(5))
            if txt == audio_spalte_txt:
                tk.Label(hdr, text="❤️", font=fnt(11, "bold"),
                         bg=CLR["hdr_bg"], fg="#ff0000", width=3, anchor="w").pack(side="left", padx=SKAL.s(6), pady=SKAL.s(5))

        if not liste_gesamt:
            msg = t(ui, "bear_keine_treffer", q=suche) if suche else t(ui, "bear_leer")
            tk.Label(self.scroll_frame, text=msg,
                     font=fnt(12), bg=CLR["bg"], fg=CLR["sub"]).pack(pady=SKAL.s(20))
            return

        def orig_idx(vok):
            for i, v in enumerate(alle):
                if v is vok:
                    return i
            return -1

        for i, vok in enumerate(liste):
            idx = orig_idx(vok)
            bg  = CLR["row_a"] if i % 2 == 0 else CLR["row_b"]
            zeile = tk.Frame(self.scroll_frame, bg=bg,
                             highlightbackground=CLR["card_border"], highlightthickness=2)
            zeile.pack(fill="x", pady=SKAL.s(1))
            tk.Label(zeile, text=vok.get("nativ",""), font=fnt(11, "bold"),
                     bg=bg, fg=CLR["text"], width=13, anchor="w").pack(side="left", padx=SKAL.s(6), pady=SKAL.s(5))
            tk.Label(zeile, text=vok.get("lern",""), font=fnt(11, "bold"),
                     bg=bg, fg=CLR["text"], width=13, anchor="w").pack(side="left", padx=SKAL.s(6))

            hat_audio = bool(vok.get("audio",""))
            tk.Label(zeile, text="🎵" if hat_audio else "—", font=fnt(12),
                     bg=bg, fg=CLR["green"] if hat_audio else CLR["sub"],
                     width=5).pack(side="left", padx=SKAL.s(4))

            gewusst = bool(vok.get("gewusst", False))
            herz_btn = tk.Label(zeile, text="♥" if gewusst else "♡", font=fnt(16, "bold"),
                                bg=bg, fg=CLR["red"] if gewusst else CLR["sub"],
                                width=3, cursor="hand2")
            herz_btn.pack(side="left", padx=SKAL.s(2))
            herz_btn.bind("<Button-1>", lambda e, i=idx: self.bear_gewusst_umschalten(i))

            ist_abc = bool(vok.get("abc", False))
            abc_btn = tk.Label(zeile, text="☑" if ist_abc else "☐", font=fnt(13),
                               bg=bg, fg=CLR["green"] if ist_abc else CLR["sub"],
                               width=3, cursor="hand2")
            abc_btn.pack(side="left", padx=SKAL.s(2))
            abc_btn.bind("<Button-1>", lambda e, i=idx: self.bear_abc_umschalten(i))

            abc_label = tk.Label(zeile, text="🔤", font=fnt(13),
                                 bg=bg, fg=CLR["blue"], width=2, cursor="hand2")
            abc_label.pack(side="left", padx=SKAL.s(1))
            abc_label.bind("<Button-1>", lambda e, i=idx: self.bear_abc_fenster_oeffnen(i))

            play_btn = tk.Label(zeile, text="▶", font=fnt(13),
                                bg=bg, fg=CLR["blue"] if hat_audio else CLR["sub"],
                                width=2, cursor="hand2")
            play_btn.pack(side="left", padx=SKAL.s(1))
            play_btn.bind("<Button-1>", lambda e, v=vok: self._wort_abspielen(
                v.get("lern", ""), self.ls, vorhandene_datei=v.get("audio", "")))

            btn_r = tk.Frame(zeile, bg=bg)
            btn_r.pack(side="left", padx=SKAL.s(6))
            tk.Button(btn_r, text=t(ui,"bear_aendern"), font=fnt(10, "bold"),
                      bg=CLR["purple"], fg="white", relief="flat", padx=SKAL.s(7), pady=SKAL.s(3),
                      cursor="hand2",
                      command=lambda i=idx: self.bear_aendern(i)).pack(side="left", padx=SKAL.s(2))
            tk.Button(btn_r, text=t(ui,"bear_loeschen"), font=fnt(10, "bold"),
                      bg=CLR["red"], fg="white", relief="flat", padx=SKAL.s(7), pady=SKAL.s(3),
                      cursor="hand2",
                      command=lambda i=idx: self.bear_loeschen(i)).pack(side="left", padx=SKAL.s(2))

        self._bear_gesamt_seiten = gesamt_seiten
        if hasattr(self, "_bear_lbl_seite"):
            self._bear_pagination_aktualisieren()

    def _bear_pagination_aktualisieren(self):
        # Schutz gegen Race Condition: Wenn schnell zurück -> rein geklickt wurde,
        # kann clear() diese Widgets bereits zerstört haben, während ein
        # verzögerter Callback (z.B. after(10, on_key)) noch aussteht.
        if not hasattr(self, "_bear_lbl_seite") or not self._bear_lbl_seite.winfo_exists():
            return
        gesamt_seiten = getattr(self, "_bear_gesamt_seiten", 1)
        self._bear_lbl_seite.config(text=t(self.ui, "bear_seite", i=self._bear_seite + 1, n=gesamt_seiten))
        self._bear_btn_zurueck.config(state="normal" if self._bear_seite > 0 else "disabled")
        self._bear_btn_weiter.config(state="normal" if self._bear_seite < gesamt_seiten - 1 else "disabled")

    def bear_gewusst_umschalten(self, index):
        ls = self.ls
        liste = vokabeln_laden(ls)
        if 0 <= index < len(liste):
            liste[index]["gewusst"] = not liste[index].get("gewusst", False)
            vokabeln_speichern(ls, liste)
            aktive_suche = ""
            if hasattr(self, "such_var") and not getattr(self, "_such_placeholder_aktiv", True):
                aktive_suche = self.such_var.get().strip()
            self.bear_aufbauen(aktive_suche)

    def bear_abc_fenster_oeffnen(self, index):
        ls = self.ls
        liste = vokabeln_laden(ls)
        if not (0 <= index < len(liste)):
            return
        vok = liste[index]
        aktive_suche = ""
        if hasattr(self, "such_var") and not getattr(self, "_such_placeholder_aktiv", True):
            aktive_suche = self.such_var.get().strip()
        self._abc_kaestchen_oeffnen(vok.get("lern", ""), ls, vok=vok, bearbeitbar=True,
                                    beim_schliessen=lambda: self.bear_aufbauen(aktive_suche))

    def bear_abc_umschalten(self, index):
        ls = self.ls
        liste = vokabeln_laden(ls)
        if 0 <= index < len(liste):
            liste[index]["abc"] = not liste[index].get("abc", False)
            vokabeln_speichern(ls, liste)
            aktive_suche = ""
            if hasattr(self, "such_var") and not getattr(self, "_such_placeholder_aktiv", True):
                aktive_suche = self.such_var.get().strip()
            self.bear_aufbauen(aktive_suche)

    def bear_aendern(self, index):
        ui, ls = self.ui, self.ls
        lsname = langname(ui, ls)
        mutter = muttersprache_label(ui)
        liste  = vokabeln_laden(ls)
        vok    = liste[index]

        aktive_suche = ""
        if hasattr(self, "such_var") and not getattr(self, "_such_placeholder_aktiv", True):
            aktive_suche = self.such_var.get().strip()

        popup = tk.Toplevel(self.root)
        try:
            popup.iconbitmap(os.path.join(BASE_DIR, "heart.ico"))
        except Exception:
            pass
        popup.title(t(ui, "bear_dlg_titel"))
        popup.resizable(False, False)
        popup.configure(bg=CLR["popup_bg"])
        popup.grab_set()

        def lbl(txt):
            tk.Label(popup, text=txt, font=("Arial", 11, "bold"),
                     bg=CLR["popup_bg"], fg=CLR["text"]).pack(pady=(14, 4), padx=30, anchor="w")

        def eingabe_kasten(parent, initial_value=""):
            outer = tk.Frame(parent, bg=CLR["blue"])
            outer.pack(fill="x", padx=30, pady=(0, 4))
            inner = tk.Frame(outer, bg=CLR["entry_bg"])
            inner.pack(fill="x", padx=2, pady=2)
            entry = tk.Entry(inner, font=("Arial", 14, "bold"), fg=CLR["entry_fg"],
                             bg=CLR["entry_bg"], insertbackground=CLR["entry_ins"],
                             bd=0, highlightthickness=0, relief="flat")
            entry.pack(fill="x", padx=8, pady=8)
            entry.insert(0, initial_value)

            def on_focus_in(e):
                outer.config(bg=CLR["blue"])
            def on_focus_out(e):
                outer.config(bg=CLR["border"])

            outer.config(bg=CLR["border"])
            entry.bind("<FocusIn>",  on_focus_in)
            entry.bind("<FocusOut>", on_focus_out)
            return entry

        lbl(f"{mutter}:")
        ein_a = eingabe_kasten(popup, vok.get("nativ",""))

        lbl(t(ui, "bear_dlg_b", lang=lsname))
        ein_b = eingabe_kasten(popup, vok.get("lern",""))

        lbl(t(ui, "bear_dlg_audio"))
        audio_var = tk.StringVar(value=vok.get("audio",""))
        af = tk.Frame(popup, bg=CLR["popup_bg"])
        af.pack(fill="x", padx=30, pady=(0, 6))

        def kurz(pfad):
            return os.path.basename(pfad) if pfad else t(ui, "audio_keine")

        audio_lbl = tk.Label(af, text=kurz(audio_var.get()),
                             font=("Arial", 9, "bold"), bg=CLR["popup_bg"], fg=CLR["text"],
                             anchor="w", width=28)
        audio_lbl.pack(side="left")

        def waehle_audio():
            pfad = filedialog.askopenfilename(
                title="MP3 aus audio/-Ordner wählen",
                initialdir=AUDIO_DIR,
                filetypes=[("MP3-Dateien", "*.mp3"), ("Alle Dateien", "*.*")])
            if pfad:
                name = os.path.basename(pfad)
                audio_var.set(name)
                audio_lbl.config(text=name)

        tk.Button(af, text=t(ui, "bear_dlg_audio_btn"), font=("Arial", 10, "bold"),
                  bg=CLR["blue"], fg="white", relief="flat", padx=8, pady=3,
                  cursor="hand2", command=waehle_audio).pack(side="left", padx=6)

        def speichern():
            a_neu = ein_a.get().strip()
            b_neu = ein_b.get().strip()
            if a_neu and b_neu:
                audio_neu = audio_var.get().strip()
                if not audio_neu:
                    auto_name = gtts_dateiname(b_neu, ls)
                    if gtts_herunterladen(b_neu, ls, auto_name):
                        audio_neu = auto_name
                liste[index] = {"nativ": a_neu, "lern": b_neu,
                                "audio": audio_neu,
                                "abc": vok.get("abc", False),
                                "silben": vok.get("silben", ""),
                                "gewusst": vok.get("gewusst", False)}
                vokabeln_speichern(ls, liste)
                popup.destroy()
                self.bear_aufbauen(aktive_suche, seite_reset=False)

        btn_r = tk.Frame(popup, bg=CLR["popup_bg"])
        btn_r.pack(pady=(8, 18))
        tk.Button(btn_r, text=t(ui,"bear_dlg_save"), font=("Arial", 11, "bold"),
                  bg=CLR["purple"], fg="white", relief="flat", padx=16, pady=6,
                  cursor="hand2", command=speichern).pack(side="left", padx=6)
        tk.Button(btn_r, text=t(ui,"bear_dlg_abbruch"), font=("Arial", 11, "bold"),
                  bg=CLR["gray"], fg=CLR["text"], relief="flat", padx=14, pady=6,
                  cursor="hand2", command=popup.destroy).pack(side="left", padx=6)

        self.root.update_idletasks()
        x = self.root.winfo_x() + self.root.winfo_width()  // 2 - 200
        y = self.root.winfo_y() + self.root.winfo_height() // 2 - 180
        popup.geometry(f"400x420+{x}+{y}")
        ein_a.focus()
        popup.bind("<Return>", lambda e: speichern())

    def bear_loeschen(self, index):
        ui, ls = self.ui, self.ls
        liste  = vokabeln_laden(ls)
        wort   = liste[index].get("nativ","")
        aktive_suche = ""
        if hasattr(self, "such_var") and not getattr(self, "_such_placeholder_aktiv", True):
            aktive_suche = self.such_var.get().strip()
        if messagebox.askyesno(t(ui,"bear_del_titel"), t(ui,"bear_del_frage", w=wort)):
            liste.pop(index)
            vokabeln_speichern(ls, liste)
            self.bear_aufbauen(aktive_suche, seite_reset=False)

    def zeige_statistik(self):
        self._aktuelle_ansicht = self.zeige_statistik
        self.clear()
        if self.root.winfo_width() <= 1:
            self.root.geometry("500x620")
            SKAL.setze_basis(500, 620)
        ui = self.ui
        s  = stats_laden()

        richtig = s.get("richtig", 0)
        falsch  = s.get("falsch",  0)
        gesamt  = richtig + falsch
        genau   = f"{int(richtig/gesamt*100)} %" if gesamt else "—"

        sek = s.get("lernzeit_sek", 0)
        zeit_str = f"{sek // 60} {t(ui,'stat_min')}" if sek < 3600 \
                   else f"{sek/3600:.1f} {t(ui,'stat_std')}"

        xp  = s.get("level_xp", 0)
        lvl, xp_ak, xp_nx = xp_fortschritt(xp)

        tk.Button(self.root, text=t(ui,"zurueck"), font=fnt(12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=SKAL.s(14), pady=SKAL.s(8),
                  cursor="hand2", command=self.zeige_hauptmenue).pack(pady=(10, 0))

        container = make_frame(self.root)
        container.pack(fill="both", expand=True)
        canvas    = tk.Canvas(container, bg=CLR["bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scroll_frame = make_frame(canvas)
        scroll_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        _stat_window = canvas.create_window((0, 0), window=scroll_frame, anchor="n")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _stat_center(event):
            canvas.itemconfig(_stat_window, width=event.width)
        canvas.bind("<Configure>", _stat_center)

        def _on_mousewheel(event):
            try:
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except Exception:
                pass
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        tk.Label(scroll_frame, text=t(ui, "stat_titel"), font=fnt(17, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(10, 12))

        lvl_f = tk.Frame(scroll_frame, bg=CLR["xp"])
        lvl_f.pack(padx=SKAL.s(40), fill="x", pady=(0, 12))
        tk.Label(lvl_f, text=f"⭐  {t(ui,'stat_level')} {lvl}",
                 font=fnt(22, "bold"), bg=CLR["xp"], fg="white").pack(pady=(12, 2))
        tk.Label(lvl_f,
                 text=f"{xp_ak} / {xp_nx} XP  →  {t(ui,'stat_naechstes')}: {t(ui,'stat_level')} {lvl+1}",
                 font=fnt(10), bg=CLR["xp"], fg="white").pack(pady=(0, 6))
        bar_bg = tk.Frame(lvl_f, bg="white", height=SKAL.s(10), width=360)
        bar_bg.pack(pady=(0, 12))
        bar_bg.pack_propagate(False)
        perc  = xp_ak / xp_nx if xp_nx else 1
        bar_w = int(360 * perc)
        if bar_w > 0:
            tk.Frame(bar_bg, bg="#e67e22", height=SKAL.s(10), width=bar_w).place(x=0, y=0)

        def stat_row(label, wert, col=CLR["text"]):
            f = tk.Frame(scroll_frame, bg=CLR["white"],
                         highlightbackground=CLR["card_border"], highlightthickness=2)
            f.pack(padx=SKAL.s(40), fill="x", pady=SKAL.s(3))
            tk.Label(f, text=label, font=fnt(11, "bold"), bg=CLR["white"],
                     fg=CLR["text"], anchor="w").pack(side="left", padx=SKAL.s(12), pady=SKAL.s(8))
            tk.Label(f, text=wert, font=fnt(13, "bold"), bg=CLR["white"],
                     fg=col, anchor="e").pack(side="right", padx=SKAL.s(12))

        stat_row(t(ui,"stat_richtig"),    str(richtig), "#27ae60")
        stat_row(t(ui,"stat_falsch"),     str(falsch),  CLR["red"])
        stat_row(t(ui,"stat_genauigkeit"), genau,       CLR["blue"])
        stat_row(t(ui,"stat_lernzeit"),   zeit_str,     CLR["orange"])
        stat_row(t(ui,"stat_xp"),         str(xp),      CLR["xp"])

        tk.Label(scroll_frame, text=t(ui,"stat_top_falsch"), font=fnt(12, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(14, 4))

        ws = s.get("wort_stats", {})
        if not ws:
            tk.Label(scroll_frame, text=t(ui,"stat_keine"),
                     font=fnt(11, "bold"), bg=CLR["bg"], fg=CLR["text"]).pack()
        else:
            sortiert = sorted(ws.items(),
                              key=lambda kv: kv[1].get("falsch",0), reverse=True)[:5]
            for wort, st in sortiert:
                r2, f2 = st.get("richtig",0), st.get("falsch",0)
                ff = tk.Frame(scroll_frame, bg=CLR["white"],
                              highlightbackground=CLR["card_border"], highlightthickness=2)
                ff.pack(padx=SKAL.s(40), fill="x", pady=SKAL.s(2))
                tk.Label(ff, text=wort, font=fnt(11, "bold"),
                         bg=CLR["white"], fg=CLR["text"], anchor="w").pack(side="left", padx=SKAL.s(10), pady=SKAL.s(6))
                tk.Label(ff, text=f"✓{r2}  ✗{f2}",
                         font=fnt(10, "bold"), bg=CLR["white"], fg=CLR["text"],
                         anchor="e").pack(side="right", padx=SKAL.s(10))

    def zeige_freischaltungen(self):
        self._aktuelle_ansicht = self.zeige_freischaltungen
        self.clear()
        if self.root.winfo_width() <= 1:
            self.root.geometry("540x680")
            SKAL.setze_basis(540, 680)
        ui = self.ui
        s  = stats_laden()
        xp  = s.get("level_xp", 0)
        lvl = berechne_level(xp)

        tk.Label(self.root, text=t(ui, "freisch_titel"), font=fnt(17, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(18, 2))
        tk.Label(self.root, text=f"⭐ {t(ui,'stat_level')} {lvl}",
                 font=fnt(13, "bold"), bg=CLR["bg"], fg=CLR["xp"]).pack(pady=(0, 8))

        container = make_frame(self.root)
        container.pack(padx=SKAL.s(16), fill="both", expand=True)
        canvas    = tk.Canvas(container, bg=CLR["bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        sf = make_frame(canvas)
        sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        sf_fenster_id = canvas.create_window((0, 0), window=sf, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(sf_fenster_id, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            try:
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except Exception:
                pass
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def aufbauen():
            for w in sf.winfo_children():
                w.destroy()

            s2       = stats_laden()
            frei2    = get_freigeschaltet(s2)
            aktiv2   = get_aktiviert(s2)

            for (req_lvl, key, beschr, icon) in FREISCHALTUNGEN[ui]:
                ist_frei   = key in frei2
                ist_aktiv  = key in aktiv2
                gesperrt   = not ist_frei

                if gesperrt:
                    bg_card = CLR["gray"]
                    fg_card = CLR["sub"]
                    border  = CLR["border"]
                elif ist_aktiv:
                    bg_card = CLR["white"]
                    fg_card = CLR["text"]
                    border  = "#27ae60"
                else:
                    bg_card = CLR["white"]
                    fg_card = CLR["text"]
                    border  = CLR["blue"]

                card = tk.Frame(sf, bg=bg_card,
                                highlightbackground=border, highlightthickness=2)
                card.pack(fill="x", padx=SKAL.s(10), pady=SKAL.s(5))

                top = tk.Frame(card, bg=bg_card)
                top.pack(fill="x", padx=SKAL.s(12), pady=(10, 4))

                tk.Label(top, text=icon, font=fnt(20), bg=bg_card).pack(side="left", padx=(0, 10))

                info = tk.Frame(top, bg=bg_card)
                info.pack(side="left", fill="x", expand=True)

                tk.Label(info, text=beschr, font=fnt(11, "bold"),
                         bg=bg_card, fg=fg_card, anchor="w", wraplength=280).pack(anchor="w")

                if gesperrt:
                    tk.Label(info, text=t(ui, "freisch_gesperrt", lvl=req_lvl),
                             font=fnt(10, "bold"), bg=bg_card, fg=CLR["sub"], anchor="w").pack(anchor="w")
                else:
                    status_txt = t(ui, "freisch_an") if ist_aktiv else t(ui, "freisch_aus")
                    tk.Label(info, text=f"{t(ui, 'freisch_frei')}  ·  {status_txt}",
                             font=fnt(10, "bold"),
                             bg=bg_card,
                             fg="#27ae60" if ist_aktiv else CLR["sub"],
                             anchor="w").pack(anchor="w")

                if not gesperrt:
                    btn_txt  = t(ui, "freisch_deaktivieren") if ist_aktiv else t(ui, "freisch_aktivieren")
                    btn_col  = "#e74c3c" if ist_aktiv else "#27ae60"

                    def mache_toggle(k=key):
                        an = toggle_aktivierung(k)
                        if k == "thema_nacht":
                            if an:
                                CLR.update(CLR_DARK)
                            else:
                                CLR.update(CLR_LIGHT)
                            self.root.configure(bg=CLR["bg"])
                        aufbauen()

                    tk.Button(top, text=btn_txt,
                              font=fnt(10, "bold"),
                              bg=btn_col, fg="white", relief="flat",
                              padx=SKAL.s(12), pady=SKAL.s(6), cursor="hand2",
                              command=mache_toggle).pack(side="right", padx=(8, 0))

                if gesperrt:
                    prog = min(1.0, lvl / req_lvl)
                    bar_bg_f = tk.Frame(card, bg=CLR["border"], height=SKAL.s(6), width=460)
                    bar_bg_f.pack(padx=SKAL.s(12), pady=(0, 4))
                    bar_bg_f.pack_propagate(False)
                    bar_w = int(460 * prog)
                    if bar_w > 0:
                        tk.Frame(bar_bg_f, bg=CLR["xp"], height=SKAL.s(6), width=bar_w).place(x=0, y=0)
                    tk.Label(card, text=f"Level {lvl} / {req_lvl}",
                             font=fnt(9, "bold"), bg=bg_card, fg=CLR["sub"]).pack(anchor="e", padx=SKAL.s(12), pady=(0, 6))
                else:
                    tk.Frame(card, bg=bg_card, height=SKAL.s(6)).pack()

        aufbauen()

        tk.Button(self.root, text=t(ui, "zurueck"), font=fnt(12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=SKAL.s(14), pady=SKAL.s(8),
                  cursor="hand2", command=self.zeige_hauptmenue).pack(pady=(8, 4))

    # ─── SHOP / DRAGONBALLS ─────────────────────────────────
    DRAGONBALL_ICONS = ["\U0001F7E0", "\U0001F7E1", "\U0001F7E0", "\U0001F7E1", "\U0001F7E0", "\U0001F7E1", "\U0001F7E0"]

    def _shop_zurueck(self):
        """Verlaesst den Shop: schliesst zuvor automatisch das Inventar-Fenster,
        falls es noch offen ist (der Nutzer kann es aber auch selbst vorher
        per eigenem Zurueck-Button im Inventar schliessen)."""
        fenster = getattr(self, "_inventar_fenster", None)
        if fenster is not None:
            try:
                if fenster.winfo_exists():
                    fenster.destroy()
            except Exception:
                pass
            self._inventar_fenster = None
        self.zeige_hauptmenue()

    def zeige_shop(self):
        self._aktuelle_ansicht = self.zeige_shop
        self.clear()
        if self.root.winfo_width() <= 1:
            self.root.geometry("460x680")
            SKAL.setze_basis(460, 680)
        ui = self.ui

        _shop_canvas = tk.Canvas(self.root, bg=CLR["bg"], highlightthickness=0)
        _shop_scrollbar = tk.Scrollbar(self.root, orient="vertical", command=_shop_canvas.yview)
        _shop_inner = tk.Frame(_shop_canvas, bg=CLR["bg"])

        _shop_inner.bind("<Configure>", lambda e: _shop_canvas.configure(scrollregion=_shop_canvas.bbox("all")))
        _shop_window = _shop_canvas.create_window((0, 0), window=_shop_inner, anchor="n")
        _shop_canvas.configure(yscrollcommand=_shop_scrollbar.set)

        def _shop_center(event):
            _shop_canvas.itemconfig(_shop_window, width=event.width)
        _shop_canvas.bind("<Configure>", _shop_center)

        def _shop_mousewheel(event):
            _shop_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        _shop_canvas.bind_all("<MouseWheel>", _shop_mousewheel)

        _shop_canvas.pack(side="left", fill="both", expand=True)
        _shop_scrollbar.pack(side="right", fill="y")

        root = self.root
        self.root = _shop_inner

        tk.Label(self.root, text=t(ui, "shop_titel"), font=fnt(18, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(SKAL.s(18), SKAL.s(10)))

        self.lbl_shop_coins = tk.Label(self.root, text="", font=fnt(14, "bold"),
                                       bg=CLR["bg"], fg="#f39c12")
        self.lbl_shop_coins.pack(pady=(SKAL.s(0), SKAL.s(10)))

        # Regal: 7 Dragonball-Slots (nur Anzeige, NICHT klickbar - das Oeffnen
        # passiert ausschliesslich ueber die Pack-Box im Inventar)
        ball_groesse = SKAL.s(40)
        self._shop_ball_imgs = [None] * 7
        if PIL_OK:
            for i, pfad in enumerate(DRAGONBALL_STERN_BILDER):
                if os.path.exists(pfad):
                    try:
                        bimg = Image.open(pfad).convert("RGBA").resize((ball_groesse, ball_groesse), Image.LANCZOS)
                        self._shop_ball_imgs[i] = ImageTk.PhotoImage(bimg)
                    except Exception:
                        self._shop_ball_imgs[i] = None

        self.shop_ball_labels = []
        balls_frame = tk.Frame(self.root, bg=CLR["bg"])
        balls_frame.pack(pady=(SKAL.s(0), SKAL.s(4)))
        for i in range(7):
            lbl = tk.Label(balls_frame, text="", font=("Segoe UI Emoji", SKAL.s(22)),
                          bg=CLR["white"], fg=CLR["sub"],
                          highlightbackground=CLR["card_border"], highlightthickness=2,
                          width=2, padx=SKAL.s(4), pady=SKAL.s(4))
            lbl.grid(row=0, column=i, padx=SKAL.s(3))
            self.shop_ball_labels.append(lbl)

        self.lbl_pack_ziehung_status = tk.Label(balls_frame, text="", font=fnt(10, "bold"),
                                                bg=CLR["bg"], fg=CLR["text"], wraplength=160,
                                                justify="left")
        self.lbl_pack_ziehung_status.grid(row=0, column=7, padx=(SKAL.s(10), 0))

        preis_row = tk.Frame(self.root, bg=CLR["bg"])
        preis_row.pack(pady=(SKAL.s(2), SKAL.s(4)))

        preis_bild_groesse = SKAL.s(44)

        def _preis_box(parent, bild_pfad, fallback_emoji, preis, farbe):
            box = tk.Frame(parent, bg=CLR["bg"])
            box.pack(side="left", padx=SKAL.s(10))
            img = None
            if PIL_OK and os.path.exists(bild_pfad):
                try:
                    im = Image.open(bild_pfad).resize((preis_bild_groesse, preis_bild_groesse), Image.LANCZOS)
                    img = ImageTk.PhotoImage(im)
                except Exception:
                    img = None
            if img is not None:
                lbl_img = tk.Label(box, image=img, bg=CLR["bg"])
                lbl_img.image = img
                lbl_img.pack(side="left", padx=(0, SKAL.s(4)))
            else:
                tk.Label(box, text=fallback_emoji, font=("Segoe UI Emoji", SKAL.s(20)),
                         bg=CLR["bg"], fg=farbe).pack(side="left", padx=(0, SKAL.s(4)))
            tk.Label(box, text=t(ui, "shop_coins", n=preis),
                     font=fnt(9, "bold"), bg=CLR["bg"], fg=farbe).pack(side="left")

        _preis_box(preis_row, JOKER_BILD, "\U0001F0CF", SHOP_JOKER_PREIS, "#8e44ad")
        _preis_box(preis_row, XP_TRANK_BILD, "\U0001F9EA", SHOP_TRANK_PREIS, "#16a085")
        _preis_box(preis_row, DOUBLE_COIN_BILD, "\U0001F7E1", SHOP_DOUBLE_COIN_PREIS, "#e1a100")

        self.shop_status_frame = tk.Frame(self.root, bg=CLR["bg"])
        self.shop_status_frame.pack(pady=(SKAL.s(0), SKAL.s(2)))
        self._shop_status_bild_cache = None
        self.lbl_shop_status_img = tk.Label(self.shop_status_frame, bg=CLR["bg"])
        self.lbl_shop_status_img.pack(side="left", padx=(0, SKAL.s(6)))
        self.lbl_shop_status_img.pack_forget()
        self.lbl_shop_status = tk.Label(self.shop_status_frame, text="", font=fnt(11, "bold"),
                                        bg=CLR["bg"], fg=CLR["text"], wraplength=380, justify="center")
        self.lbl_shop_status.pack(side="left")

        hinweis_row = tk.Frame(self.root, bg=CLR["bg"])
        hinweis_row.pack(pady=(0, SKAL.s(4)))

        self._shop_hinweis_img = None
        if PIL_OK and os.path.exists(DRAGONBALL_PACK_BILD):
            try:
                himg = Image.open(DRAGONBALL_PACK_BILD).convert("RGB").resize((SKAL.s(24), SKAL.s(24)), Image.LANCZOS)
                self._shop_hinweis_img = ImageTk.PhotoImage(himg)
            except Exception:
                self._shop_hinweis_img = None

        if self._shop_hinweis_img is not None:
            tk.Label(hinweis_row, image=self._shop_hinweis_img,
                     bg=CLR["bg"]).pack(side="left", padx=(0, SKAL.s(4)))
        else:
            tk.Label(hinweis_row, text="\U0001F7E0", font=("Segoe UI Emoji", SKAL.s(16)),
                     bg=CLR["bg"], fg=CLR["sub"]).pack(side="left", padx=(0, SKAL.s(4)))

        tk.Label(hinweis_row,
                 text=t(ui, "shop_pack_hinweis", preis=DRAGONBALL_PACK_PREIS),
                 font=fnt(9), bg=CLR["bg"], fg=CLR["sub"], wraplength=340, justify="left").pack(side="left")

        # Pack-Button mit dem Dragonball-Pack-Bild.
        pack_groesse = SKAL.s(90)
        self._shop_pack_img = None
        if PIL_OK and os.path.exists(DRAGONBALL_PACK_BILD):
            try:
                img = Image.open(DRAGONBALL_PACK_BILD).resize((pack_groesse, pack_groesse), Image.LANCZOS)
                self._shop_pack_img = ImageTk.PhotoImage(img)
            except Exception:
                self._shop_pack_img = None

        if self._shop_pack_img is not None:
            self.lbl_shop_pack_btn = tk.Label(self.root, image=self._shop_pack_img,
                          bg=CLR["bg"], cursor="hand2")
        else:
            self.lbl_shop_pack_btn = tk.Label(self.root, text="\U0001F7E0 Pack", font=fnt(12, "bold"),
                          bg=CLR["white"], fg=CLR["text"],
                          highlightbackground=CLR["card_border"], highlightthickness=2,
                          padx=SKAL.s(10), pady=SKAL.s(10), cursor="hand2")
        self.lbl_shop_pack_btn.pack(pady=(SKAL.s(0), SKAL.s(4)))
        self.lbl_shop_pack_btn.bind("<Button-1>", lambda e: self._shop_pack_kaufen())

        # Joker- und Trank-Kaestchen: ganz ans Ende, eigene Reihe.
        kauf_frame = tk.Frame(self.root, bg=CLR["bg"])
        kauf_frame.pack(pady=(SKAL.s(0), SKAL.s(4)))

        kaestchen_groesse = SKAL.s(44)
        self._shop_joker_img = None
        if PIL_OK and os.path.exists(JOKER_BILD):
            try:
                img = Image.open(JOKER_BILD).resize((kaestchen_groesse, kaestchen_groesse), Image.LANCZOS)
                self._shop_joker_img = ImageTk.PhotoImage(img)
            except Exception:
                self._shop_joker_img = None

        if self._shop_joker_img is not None:
            self.lbl_shop_joker = tk.Label(kauf_frame, image=self._shop_joker_img,
                          bg=CLR["white"],
                          highlightbackground="#8e44ad", highlightthickness=2,
                          cursor="hand2")
        else:
            self.lbl_shop_joker = tk.Label(kauf_frame, text="\U0001F0CF", font=("Segoe UI Emoji", SKAL.s(22)),
                          bg=CLR["white"], fg=CLR["text"],
                          highlightbackground="#8e44ad", highlightthickness=2,
                          width=2, padx=SKAL.s(4), pady=SKAL.s(4), cursor="hand2")
        self.lbl_shop_joker.grid(row=0, column=0, padx=SKAL.s(6))
        self.lbl_shop_joker.bind("<Button-1>", lambda e: self._shop_joker_kaufen())

        self._shop_trank_img = None
        if PIL_OK and os.path.exists(XP_TRANK_BILD):
            try:
                img = Image.open(XP_TRANK_BILD).resize((kaestchen_groesse, kaestchen_groesse), Image.LANCZOS)
                self._shop_trank_img = ImageTk.PhotoImage(img)
            except Exception:
                self._shop_trank_img = None

        if self._shop_trank_img is not None:
            self.lbl_shop_trank = tk.Label(kauf_frame, image=self._shop_trank_img,
                          bg=CLR["white"],
                          highlightbackground="#16a085", highlightthickness=2,
                          cursor="hand2")
        else:
            self.lbl_shop_trank = tk.Label(kauf_frame, text="\U0001F9EA", font=("Segoe UI Emoji", SKAL.s(22)),
                          bg=CLR["white"], fg=CLR["text"],
                          highlightbackground="#16a085", highlightthickness=2,
                          width=2, padx=SKAL.s(4), pady=SKAL.s(4), cursor="hand2")
        self.lbl_shop_trank.grid(row=0, column=1, padx=SKAL.s(6))
        self.lbl_shop_trank.bind("<Button-1>", lambda e: self._shop_trank_kaufen())

        self._shop_double_coin_img = None
        if PIL_OK and os.path.exists(DOUBLE_COIN_BILD):
            try:
                img = Image.open(DOUBLE_COIN_BILD).resize((kaestchen_groesse, kaestchen_groesse), Image.LANCZOS)
                self._shop_double_coin_img = ImageTk.PhotoImage(img)
            except Exception:
                self._shop_double_coin_img = None

        if self._shop_double_coin_img is not None:
            self.lbl_shop_double_coin = tk.Label(kauf_frame, image=self._shop_double_coin_img,
                          bg=CLR["white"],
                          highlightbackground="#e1a100", highlightthickness=2,
                          cursor="hand2")
        else:
            self.lbl_shop_double_coin = tk.Label(kauf_frame, text="\U0001F7E1", font=("Segoe UI Emoji", SKAL.s(22)),
                          bg=CLR["white"], fg=CLR["text"],
                          highlightbackground="#e1a100", highlightthickness=2,
                          width=2, padx=SKAL.s(4), pady=SKAL.s(4), cursor="hand2")
        self.lbl_shop_double_coin.grid(row=0, column=2, padx=SKAL.s(6))
        self.lbl_shop_double_coin.bind("<Button-1>", lambda e: self._shop_double_coin_kaufen())

        unten_row = tk.Frame(self.root, bg=CLR["bg"])
        unten_row.pack(pady=(SKAL.s(4), SKAL.s(10)))

        tk.Button(unten_row, text=t(ui, "zurueck"), font=fnt(12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=SKAL.s(14), pady=SKAL.s(8),
                  cursor="hand2", command=self._shop_zurueck).pack(side="left", padx=SKAL.s(6))

        tk.Button(unten_row, text=t(ui, "inv_titel"), font=fnt(12, "bold"),
                  bg="#2c3e50", fg="white", relief="flat", padx=SKAL.s(14), pady=SKAL.s(8),
                  cursor="hand2", command=lambda: self.zeige_inventar(aus_shop=True)).pack(side="left", padx=SKAL.s(6))

        self.root = root

        self._shop_anzeige_aktualisieren()

    def zeige_inventar(self, aus_shop=False):
        """Oeffnet ein eigenes Fenster mit Joker-, XP-Trank- und Dragonball-Bestand.
        Die Pack-Box ist nur klickbar (zum Oeffnen der Packs), wenn das Inventar
        aus dem Shop heraus geoeffnet wurde (aus_shop=True); von ueberall sonst
        (Test, Hauptmenue, etc.) ist sie reine Anzeige."""
        if getattr(self, "_inventar_fenster", None) is not None:
            try:
                self._inventar_fenster.destroy()
            except Exception:
                pass
            self._inventar_fenster = None

        s = shop_laden()
        inv = s.get("inventar", {})
        dragonball_anzahl = s.get("packs_gekauft", 0)
        ui = self.ui
        fenster = tk.Toplevel(self.root)
        self._inventar_fenster = fenster
        fenster.title(t(ui, "inv_titel"))
        fenster.geometry("520x400")
        fenster.configure(bg=CLR["bg"])

        tk.Label(fenster, text=t(ui, "inv_titel"), font=fnt(16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(SKAL.s(16), SKAL.s(14)))

        row = tk.Frame(fenster, bg=CLR["bg"])
        row.pack(pady=SKAL.s(10))

        inv_bild_groesse = SKAL.s(36)
        self._inv_joker_img = None
        if PIL_OK and os.path.exists(JOKER_BILD):
            try:
                img = Image.open(JOKER_BILD).resize((inv_bild_groesse, inv_bild_groesse), Image.LANCZOS)
                self._inv_joker_img = ImageTk.PhotoImage(img)
            except Exception:
                self._inv_joker_img = None

        self._inv_trank_img = None
        if PIL_OK and os.path.exists(XP_TRANK_BILD):
            try:
                img = Image.open(XP_TRANK_BILD).resize((inv_bild_groesse, inv_bild_groesse), Image.LANCZOS)
                self._inv_trank_img = ImageTk.PhotoImage(img)
            except Exception:
                self._inv_trank_img = None

        self._inv_pack_img = None
        if PIL_OK and os.path.exists(DRAGONBALL_PACK_BILD):
            try:
                img = Image.open(DRAGONBALL_PACK_BILD).resize((inv_bild_groesse, inv_bild_groesse), Image.LANCZOS)
                self._inv_pack_img = ImageTk.PhotoImage(img)
            except Exception:
                self._inv_pack_img = None

        self._inv_double_coin_img = None
        if PIL_OK and os.path.exists(DOUBLE_COIN_BILD):
            try:
                img = Image.open(DOUBLE_COIN_BILD).resize((inv_bild_groesse, inv_bild_groesse), Image.LANCZOS)
                self._inv_double_coin_img = ImageTk.PhotoImage(img)
            except Exception:
                self._inv_double_coin_img = None

        joker_box = tk.Frame(row, bg=CLR["white"],
                              highlightbackground="#8e44ad", highlightthickness=2)
        joker_box.pack(side="left", padx=SKAL.s(12))
        if self._inv_joker_img is not None:
            tk.Label(joker_box, image=self._inv_joker_img,
                     bg=CLR["white"]).pack(side="left", padx=(SKAL.s(10), SKAL.s(4)), pady=SKAL.s(10))
        else:
            tk.Label(joker_box, text="\U0001F0CF", font=("Segoe UI Emoji", SKAL.s(26)),
                     bg=CLR["white"], fg=CLR["text"]).pack(side="left", padx=(SKAL.s(10), SKAL.s(4)), pady=SKAL.s(10))
        lbl_joker_anzahl = tk.Label(joker_box, text=str(inv.get("joker", 0)), font=fnt(16, "bold"),
                 bg=CLR["white"], fg="#8e44ad")
        lbl_joker_anzahl.pack(side="left", padx=(SKAL.s(4), SKAL.s(10)), pady=SKAL.s(10))
        self._inv_lbl_joker_anzahl = lbl_joker_anzahl

        trank_box = tk.Frame(row, bg=CLR["white"],
                              highlightbackground="#16a085", highlightthickness=2, cursor="hand2")
        trank_box.pack(side="left", padx=SKAL.s(12))
        if self._inv_trank_img is not None:
            lbl_trank_img = tk.Label(trank_box, image=self._inv_trank_img, bg=CLR["white"])
        else:
            lbl_trank_img = tk.Label(trank_box, text="\U0001F9EA", font=("Segoe UI Emoji", SKAL.s(26)),
                     bg=CLR["white"], fg=CLR["text"])
        lbl_trank_img.pack(side="left", padx=(SKAL.s(10), SKAL.s(4)), pady=SKAL.s(10))
        trank_info = tk.Frame(trank_box, bg=CLR["white"])
        trank_info.pack(side="left", padx=(SKAL.s(4), SKAL.s(10)), pady=SKAL.s(10))
        lbl_trank_anzahl = tk.Label(trank_info, text=str(inv.get("traenke", 0)), font=fnt(16, "bold"),
                 bg=CLR["white"], fg="#16a085")
        lbl_trank_anzahl.pack()
        lbl_trank_timer = tk.Label(trank_info, text="", font=fnt(9, "bold"),
                 bg=CLR["white"], fg="#16a085")
        lbl_trank_timer.pack()
        self._inv_lbl_trank_anzahl = lbl_trank_anzahl
        self._inv_lbl_trank_timer = lbl_trank_timer

        def _trank_aktivieren(event=None):
            erfolg, verlaengert, s2 = shop_trank_aktivieren()
            if erfolg:
                tracking_senden("boost_aktiviert", sprache=self.ls, bereich="vokabeln",
                                boost_typ="xp", modus="trank", wert=0.25)
            self._inventar_falls_offen_aktualisieren()

        trank_box.bind("<Button-1>", _trank_aktivieren)
        lbl_trank_img.bind("<Button-1>", _trank_aktivieren)
        lbl_trank_anzahl.bind("<Button-1>", _trank_aktivieren)

        pack_zeile = tk.Frame(fenster, bg=CLR["bg"])
        pack_zeile.pack(pady=SKAL.s(12))

        pack_box = tk.Frame(pack_zeile, bg=CLR["white"],
                             highlightbackground=CLR["card_border"], highlightthickness=2)
        pack_box.pack(side="left", padx=SKAL.s(12))
        if self._inv_pack_img is not None:
            lbl_pack_img = tk.Label(pack_box, image=self._inv_pack_img, bg=CLR["white"])
        else:
            lbl_pack_img = tk.Label(pack_box, text="\U0001F7E0", font=("Segoe UI Emoji", SKAL.s(26)),
                                     bg=CLR["white"], fg=CLR["text"])
        lbl_pack_img.pack(side="left", padx=(SKAL.s(10), SKAL.s(4)), pady=SKAL.s(10))

        lbl_pack_anzahl = tk.Label(pack_box, text=str(dragonball_anzahl), font=fnt(16, "bold"),
                                    bg=CLR["white"], fg=CLR["text"])
        lbl_pack_anzahl.pack(side="left", padx=(SKAL.s(4), SKAL.s(10)), pady=SKAL.s(10))
        self._inv_lbl_pack_anzahl = lbl_pack_anzahl

        double_coin_box = tk.Frame(pack_zeile, bg=CLR["white"],
                              highlightbackground="#e1a100", highlightthickness=2, cursor="hand2")
        double_coin_box.pack(side="left", padx=SKAL.s(12))
        if self._inv_double_coin_img is not None:
            lbl_double_coin_img = tk.Label(double_coin_box, image=self._inv_double_coin_img, bg=CLR["white"])
        else:
            lbl_double_coin_img = tk.Label(double_coin_box, text="\U0001F7E1", font=("Segoe UI Emoji", SKAL.s(26)),
                     bg=CLR["white"], fg=CLR["text"])
        lbl_double_coin_img.pack(side="left", padx=(SKAL.s(10), SKAL.s(4)), pady=SKAL.s(10))
        double_coin_info = tk.Frame(double_coin_box, bg=CLR["white"])
        double_coin_info.pack(side="left", padx=(SKAL.s(4), SKAL.s(10)), pady=SKAL.s(10))
        lbl_double_coin_anzahl = tk.Label(double_coin_info, text=str(inv.get("double_coin", 0)), font=fnt(16, "bold"),
                 bg=CLR["white"], fg="#e1a100")
        lbl_double_coin_anzahl.pack()
        lbl_double_coin_timer = tk.Label(double_coin_info, text="", font=fnt(9, "bold"),
                 bg=CLR["white"], fg="#e1a100")
        lbl_double_coin_timer.pack()
        self._inv_lbl_double_coin_anzahl = lbl_double_coin_anzahl
        self._inv_lbl_double_coin_timer = lbl_double_coin_timer

        def _double_coin_aktivieren(event=None):
            erfolg, verlaengert, s2 = shop_double_coin_aktivieren()
            if erfolg:
                tracking_senden("boost_aktiviert", sprache=self.ls, bereich="vokabeln",
                                boost_typ="coins", modus="double_coin", wert=1)
            self._inventar_falls_offen_aktualisieren()

        double_coin_box.bind("<Button-1>", _double_coin_aktivieren)
        lbl_double_coin_img.bind("<Button-1>", _double_coin_aktivieren)
        lbl_double_coin_anzahl.bind("<Button-1>", _double_coin_aktivieren)

        # Pack-Box im Inventar ist nur klickbar, wenn das Inventar aus dem
        # Shop heraus geoeffnet wurde (aus_shop=True) - dort koennen die
        # gezogenen Baelle direkt in den Dragonball-Kaestchen angezeigt werden.
        # Von ueberall sonst (Test, Hauptmenue, etc.) dient die Box nur als
        # reine Anzeige des Bestands, da dort kein Shop-Screen im Hintergrund
        # existiert, um die Ziehung darzustellen.

        def _inventar_schliessen():
            self._inventar_fenster = None
            self._inv_lbl_joker_anzahl = None
            self._inv_lbl_trank_anzahl = None
            self._inv_lbl_trank_timer = None
            self._inv_lbl_double_coin_anzahl = None
            self._inv_lbl_double_coin_timer = None
            self._inv_lbl_pack_anzahl = None
            fenster.destroy()

        if aus_shop:
            def _pack_oeffnen(event=None):
                aktuell = shop_laden().get("packs_gekauft", 0)
                if aktuell <= 0:
                    return
                self._pack_im_shop_anzeigen()
                self._inventar_falls_offen_aktualisieren()

            pack_box.config(cursor="hand2", highlightbackground="#e67e22")
            lbl_pack_img.config(cursor="hand2")
            lbl_pack_anzahl.config(cursor="hand2")
            pack_box.bind("<Button-1>", _pack_oeffnen)
            lbl_pack_img.bind("<Button-1>", _pack_oeffnen)
            lbl_pack_anzahl.bind("<Button-1>", _pack_oeffnen)

        tk.Button(fenster, text=t(self.ui, "zurueck"), font=fnt(12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=SKAL.s(14), pady=SKAL.s(8),
                  cursor="hand2", command=_inventar_schliessen).pack(pady=(SKAL.s(24), SKAL.s(10)))

        self._inventar_timer_tick()

    def _format_timer_sek(self, sekunden):
        sekunden = max(0, int(sekunden))
        m, s = divmod(sekunden, 60)
        return f"\u23f1 {m}:{s:02d}"

    def _inventar_falls_offen_aktualisieren(self):
        """Aktualisiert Joker-, Traenke-, Double-Coin- und Pack-Anzahl sowie
        die laufenden Timer im Inventar-Fenster sofort, falls es gerade offen
        ist (wird nach jedem Shop-Kauf/-Aktivierung aufgerufen, damit man das
        Inventar nicht neu oeffnen muss). Verbraucht zudem abgelaufene Timer."""
        fenster = getattr(self, "_inventar_fenster", None)
        if fenster is None or not fenster.winfo_exists():
            return
        s_vorher = shop_laden()
        dc_lief = s_vorher.get("double_coin_bis", 0) > 0
        tr_lief = s_vorher.get("trank_bis", 0) > 0
        s = shop_timer_pruefen_und_verbrauchen()
        if dc_lief and s.get("double_coin_bis", 0) == 0:
            tracking_senden("shop_verbrauch", sprache=self.ls, item="double_coin")
        if tr_lief and s.get("trank_bis", 0) == 0:
            tracking_senden("shop_verbrauch", sprache=self.ls, item="trank")
        inv = s.get("inventar", {})
        if getattr(self, "_inv_lbl_joker_anzahl", None) is not None:
            self._inv_lbl_joker_anzahl.config(text=str(inv.get("joker", 0)))
        if getattr(self, "_inv_lbl_trank_anzahl", None) is not None:
            self._inv_lbl_trank_anzahl.config(text=str(inv.get("traenke", 0)))
        if getattr(self, "_inv_lbl_double_coin_anzahl", None) is not None:
            self._inv_lbl_double_coin_anzahl.config(text=str(inv.get("double_coin", 0)))
        if getattr(self, "_inv_lbl_pack_anzahl", None) is not None:
            self._inv_lbl_pack_anzahl.config(text=str(s.get("packs_gekauft", 0)))

        trank_bis = s.get("trank_bis", 0)
        if getattr(self, "_inv_lbl_trank_timer", None) is not None:
            if trank_bis > time.time():
                self._inv_lbl_trank_timer.config(text=self._format_timer_sek(trank_bis - time.time()))
            else:
                self._inv_lbl_trank_timer.config(text="")

        dc_bis = s.get("double_coin_bis", 0)
        if getattr(self, "_inv_lbl_double_coin_timer", None) is not None:
            if dc_bis > time.time():
                self._inv_lbl_double_coin_timer.config(text=self._format_timer_sek(dc_bis - time.time()))
            else:
                self._inv_lbl_double_coin_timer.config(text="")

    def _inventar_timer_tick(self):
        """Wird jede Sekunde aufgerufen solange das Inventar-Fenster offen
        ist, um die Countdown-Anzeigen zu aktualisieren."""
        fenster = getattr(self, "_inventar_fenster", None)
        if fenster is None or not fenster.winfo_exists():
            return
        self._inventar_falls_offen_aktualisieren()
        fenster.after(1000, self._inventar_timer_tick)

    def _shop_anzeige_aktualisieren(self):
        s = shop_laden()
        self.lbl_shop_coins.config(text=t(self.ui, "shop_coins", n=s.get('coins', 0)))
        for i, lbl in enumerate(self.shop_ball_labels):
            gesammelt = s["dragonballs"][i]
            if gesammelt and self._shop_ball_imgs[i] is not None:
                lbl.config(image=self._shop_ball_imgs[i], text="", bg=CLR["white"], width=0)
            elif gesammelt:
                lbl.config(image="", text="", fg=CLR["text"], bg=CLR["white"], width=2)
            else:
                lbl.config(image="", text="", fg=CLR["sub"], bg=CLR["light"], width=2)
        self.lbl_shop_joker.config(text="\U0001F0CF")
        self.lbl_shop_trank.config(text="\U0001F9EA")
        self.lbl_shop_double_coin.config(text="\U0001F7E1")

    def _pack_im_shop_anzeigen(self):
        """Wird beim Klick auf die Pack-Box im Inventar aufgerufen: zieht die
        Baelle eines bereits bezahlten Packs (gewichtet, 5 haeufige + 2
        seltene, mit Pity-System gegen Duplikat-Pech-Serien). Man bekommt
        immer mindestens 1 Ball; mit 35%/15%/1% Chance (exklusiv) werden es
        2/3/7 Baelle auf einmal. Duplikate sind erlaubt und geben 5 Coins
        statt eines neuen Balls. Zieht keine erneuten Coins ab (das Pack
        wurde schon beim Kauf bezahlt)."""
        s = shop_laden()
        if s.get("packs_gekauft", 0) <= 0:
            return []
        s["packs_gekauft"] = s.get("packs_gekauft", 0) - 1
        gezogen = _dragonball_pack_ziehen_mit_pity(s)

        alle_komplett = all(s["dragonballs"])
        if alle_komplett:
            if not s.get("dragonballs_eingeloest", False):
                s["coins"] = s.get("coins", 0) + 5000
                s["dragonballs_eingeloest"] = True
            s["inventar"]["joker"] = s["inventar"].get("joker", 0) + 10
            s["inventar"]["traenke"] = s["inventar"].get("traenke", 0) + 10
            s["inventar"]["double_coin"] = s["inventar"].get("double_coin", 0) + 10
            s["dragonballs"] = [False] * 7

        shop_speichern(s)
        self._shop_anzeige_aktualisieren()
        self._pack_ziehung_status_setzen(gezogen, alle_komplett)
        return gezogen

    def _pack_ziehung_status_setzen(self, gezogen, alle_komplett):
        """Zeigt neben der Dragonball-Reihe an, ob neue Baelle gezogen
        wurden oder nur Duplikate, und feiert mit einem Yippie-Text,
        wenn dadurch alle 7 Baelle komplett wurden."""
        lbl = getattr(self, "lbl_pack_ziehung_status", None)
        if lbl is None:
            return
        ui = self.ui
        if alle_komplett:
            lbl.config(text=t(ui, "shop_alle_7_yippie"), fg="#e1a100")
            return
        n = len(gezogen)
        if n > 0:
            suf = "" if n == 1 else "e"
            suf2 = "" if n == 1 else "s"
            lbl.config(text=t(ui, "shop_neue_erhalten", n=n, suf=suf, suf2=suf2), fg="#27ae60")
        else:
            lbl.config(text=t(ui, "shop_nur_duplikate"), fg=CLR["sub"])

    def _shop_status_setzen(self, text, fg, bild_pfad=None, bild_groesse=None):
        """Setzt den Status-Text im Shop. Wenn bild_pfad angegeben ist, wird
        zusaetzlich links davon das entsprechende Bild angezeigt (statt eines
        Emojis); sonst wird das Bild-Label ausgeblendet."""
        self.lbl_shop_status.config(text=text, fg=fg)
        if bild_pfad and PIL_OK and os.path.exists(bild_pfad):
            try:
                groesse = bild_groesse or SKAL.s(18)
                im = Image.open(bild_pfad).convert("RGB").resize((groesse, groesse), Image.LANCZOS)
                self._shop_status_bild_cache = ImageTk.PhotoImage(im)
                self.lbl_shop_status_img.config(image=self._shop_status_bild_cache)
                self.lbl_shop_status_img.pack(side="left", padx=(0, SKAL.s(6)))
                self.lbl_shop_status_img.pack_configure(before=self.lbl_shop_status)
            except Exception:
                self._shop_status_bild_cache = None
                self.lbl_shop_status_img.pack_forget()
        else:
            self._shop_status_bild_cache = None
            self.lbl_shop_status_img.pack_forget()

    def _shop_pack_kaufen(self):
        ui = self.ui
        erfolg, s = shop_pack_kaufen_nur()
        if not erfolg:
            self._shop_status_setzen(
                t(ui, "shop_nicht_genug", n=DRAGONBALL_PACK_PREIS),
                CLR["red"])
            self._shop_anzeige_aktualisieren()
            return

        self._shop_status_setzen(
            t(ui, "shop_pack_gekauft", n=s.get('packs_gekauft', 0)),
            "#27ae60", bild_pfad=DRAGONBALL_PACK_BILD)
        tracking_senden("shop_kauf", sprache=self.ls, item="dragonball_pack",
                        preis=DRAGONBALL_PACK_PREIS, coins_danach=s.get("coins", 0),
                        ist_special=True)
        self._shop_anzeige_aktualisieren()
        self._inventar_falls_offen_aktualisieren()

    def _shop_joker_kaufen(self):
        ui = self.ui
        erfolg, s = shop_joker_kaufen()
        if not erfolg:
            self._shop_status_setzen(
                t(ui, "shop_nicht_genug", n=SHOP_JOKER_PREIS),
                CLR["red"])
        else:
            self._shop_status_setzen(
                t(ui, "shop_joker_gekauft", n=s['inventar']['joker']),
                "#27ae60", bild_pfad=JOKER_BILD)
            tracking_senden("shop_kauf", sprache=self.ls, item="joker",
                            preis=SHOP_JOKER_PREIS, coins_danach=s.get("coins", 0))
        self._shop_anzeige_aktualisieren()
        self._inventar_falls_offen_aktualisieren()

    def _shop_trank_kaufen(self):
        ui = self.ui
        erfolg, s = shop_trank_kaufen()
        if not erfolg:
            self._shop_status_setzen(
                t(ui, "shop_nicht_genug", n=SHOP_TRANK_PREIS),
                CLR["red"])
        else:
            self._shop_status_setzen(
                t(ui, "shop_trank_gekauft", n=s['inventar']['traenke']),
                "#27ae60", bild_pfad=XP_TRANK_BILD)
            tracking_senden("shop_kauf", sprache=self.ls, item="trank",
                            preis=SHOP_TRANK_PREIS, coins_danach=s.get("coins", 0))
        self._shop_anzeige_aktualisieren()
        self._inventar_falls_offen_aktualisieren()

    def _shop_double_coin_kaufen(self):
        ui = self.ui
        erfolg, s = shop_double_coin_kaufen()
        if not erfolg:
            self._shop_status_setzen(
                t(ui, "shop_nicht_genug", n=SHOP_DOUBLE_COIN_PREIS),
                CLR["red"])
        else:
            self._shop_status_setzen(
                t(ui, "shop_double_coin_gekauft", n=s['inventar']['double_coin']),
                "#27ae60", bild_pfad=DOUBLE_COIN_BILD)
            tracking_senden("shop_kauf", sprache=self.ls, item="double_coin",
                            preis=SHOP_DOUBLE_COIN_PREIS, coins_danach=s.get("coins", 0))
        self._shop_anzeige_aktualisieren()
        self._inventar_falls_offen_aktualisieren()

    # ─── GANZE SÄTZE ───────────────────────────────────────
    def zeige_saetze_menue(self):
        self._aktuelle_ansicht = self.zeige_saetze_menue
        self.clear()
        self.root.geometry("460x460")
        ui, ls = self.ui, self.ls

        tk.Label(self.root, text=t(ui, "saetze_titel"), font=("Arial", 16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(28, 4))

        saetze = saetze_laden(ls)
        tk.Label(self.root, text=t(ui, "saetze_gespeichert", n=len(saetze)),
                 font=("Arial", 11), bg=CLR["bg"], fg=CLR["sub"]).pack(pady=(0, 20))

        btn_cfg = {"font": ("Arial", 13, "bold"), "relief": "flat",
                   "padx": 0, "pady": 13, "cursor": "hand2", "width": 22}
        tk.Button(self.root, text=t(ui, "saetze_ein_titel"), bg=CLR["blue"], fg="white",
                  command=self.zeige_saetze_eintragen, **btn_cfg).pack(pady=4)
        tk.Button(self.root, text=t(ui, "saetze_lern_titel"), bg=CLR["green"], fg="white",
                  command=self.zeige_saetze_richtung_lernen, **btn_cfg).pack(pady=4)
        tk.Button(self.root, text=t(ui, "saetze_test_titel"), bg="#d35400", fg="white",
                  command=self.zeige_saetze_richtung_test, **btn_cfg).pack(pady=4)
        tk.Button(self.root, text=t(ui, "saetze_bear_btn"), bg=CLR["purple"], fg="white",
                  command=self.zeige_saetze_bearbeiten, **btn_cfg).pack(pady=4)
        tk.Button(self.root, text=t(ui, "zurueck"), font=("Arial", 12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=14, pady=8,
                  cursor="hand2", command=self.zeige_hauptmenue).pack(pady=(16, 0))

    def zeige_saetze_richtung_lernen(self):
        ui, ls = self.ui, self.ls
        saetze = saetze_laden(ls)
        if not saetze:
            messagebox.showinfo(t(ui, "saetze_kein_titel"), t(ui, "saetze_kein"))
            return
        self._aktuelle_ansicht = self.zeige_saetze_richtung_lernen
        self.clear()
        self.root.geometry("460x360")
        mutter  = muttersprache_label(ui)
        lsname  = langname(ui, ls)
        flag_ls = {"de": "🇩🇪", "en": "🇬🇧", "fi": "🇫🇮"}[ls]
        flag_ui = {"de": "🇩🇪", "en": "🇬🇧", "fi": "🇫🇮"}[ui]

        tk.Label(self.root, text="📚  Sätze Lernen", font=("Arial", 16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(28, 4))
        tk.Label(self.root, text=t(ui, "richtung_titel"),
                 font=("Arial", 11), bg=CLR["bg"], fg=CLR["sub"]).pack(pady=(0, 14))

        def karte(zeile1, zeile2, col, cb):
            f = tk.Frame(self.root, bg=CLR["white"],
                         highlightbackground=col, highlightthickness=2, cursor="hand2")
            f.pack(padx=40, fill="x", pady=6)
            inner = tk.Frame(f, bg=CLR["white"])
            inner.pack(padx=16, pady=13)
            l1 = tk.Label(inner, text=zeile1, font=("Arial", 13, "bold"),
                          bg=CLR["white"], fg=CLR["text"])
            l1.pack()
            l2 = tk.Label(inner, text=zeile2, font=("Arial", 10),
                          bg=CLR["white"], fg=CLR["sub"])
            l2.pack()
            for w in [f, inner, l1, l2]:
                w.bind("<Button-1>", lambda e: cb())

        karte(f"{flag_ui} {mutter}   →   {flag_ls} {lsname}",
              "Deutsch sehen, Übersetzung aufdecken", CLR["green"],
              lambda: self.zeige_saetze_lernen(umgekehrt=False))
        karte(f"{flag_ls} {lsname}   →   {flag_ui} {mutter}",
              "Übersetzung sehen, Deutsch aufdecken", CLR["orange"],
              lambda: self.zeige_saetze_lernen(umgekehrt=True))

        tk.Button(self.root, text=t(ui, "zurueck"), font=("Arial", 12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=20, pady=10,
                  cursor="hand2", command=self.zeige_saetze_menue).pack(pady=(10, 6))

    def zeige_saetze_richtung_test(self):
        ui, ls = self.ui, self.ls
        saetze = saetze_laden(ls)
        if not saetze:
            messagebox.showinfo(t(ui, "saetze_kein_titel"), t(ui, "saetze_kein"))
            return
        self._aktuelle_ansicht = self.zeige_saetze_richtung_test
        self.clear()
        self.root.geometry("460x360")
        mutter  = muttersprache_label(ui)
        lsname  = langname(ui, ls)
        flag_ls = {"de": "🇩🇪", "en": "🇬🇧", "fi": "🇫🇮"}[ls]
        flag_ui = {"de": "🇩🇪", "en": "🇬🇧", "fi": "🇫🇮"}[ui]

        tk.Label(self.root, text=t(ui, "saetze_test_titel"), font=("Arial", 16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(28, 4))
        tk.Label(self.root, text=t(ui, "richtung_titel"),
                 font=("Arial", 11), bg=CLR["bg"], fg=CLR["sub"]).pack(pady=(0, 14))

        def karte(zeile1, zeile2, col, cb):
            f = tk.Frame(self.root, bg=CLR["white"],
                         highlightbackground=col, highlightthickness=2, cursor="hand2")
            f.pack(padx=40, fill="x", pady=6)
            inner = tk.Frame(f, bg=CLR["white"])
            inner.pack(padx=16, pady=13)
            l1 = tk.Label(inner, text=zeile1, font=("Arial", 13, "bold"),
                          bg=CLR["white"], fg=CLR["text"])
            l1.pack()
            l2 = tk.Label(inner, text=zeile2, font=("Arial", 10),
                          bg=CLR["white"], fg=CLR["sub"])
            l2.pack()
            for w in [f, inner, l1, l2]:
                w.bind("<Button-1>", lambda e: cb())

        karte(f"{flag_ui} {mutter}   →   {flag_ls} {lsname}",
              f"{lsname} eintippen", CLR["green"],
              lambda: self._saetze_sprache_abfragen(False))
        karte(f"{flag_ls} {lsname}   →   {flag_ui} {mutter}",
              f"{mutter} eintippen", CLR["orange"],
              lambda: self._saetze_sprache_abfragen(True))

        tk.Button(self.root, text=t(ui, "zurueck"), font=("Arial", 12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=20, pady=10,
                  cursor="hand2", command=self.zeige_saetze_menue).pack(pady=(10, 6))

    def _saetze_sprache_abfragen(self, umgekehrt):
        ui, ls = self.ui, self.ls
        mutter = muttersprache_label(ui)
        lsname = langname(ui, ls)
        popup = tk.Toplevel(self.root)
        try:
            popup.iconbitmap(os.path.join(BASE_DIR, "heart.ico"))
        except Exception:
            pass
        popup.title("Schreibsprache wählen")
        popup.resizable(False, False)
        popup.configure(bg=CLR["popup_bg"])
        popup.grab_set()
        tk.Label(popup, text="❤️  In welcher Sprache schreiben?",
                 font=("Arial", 13, "bold"), bg=CLR["popup_bg"], fg=CLR["text"]).pack(pady=(22, 12), padx=30)
        def starten(deutsch):
            popup.destroy()
            self._satz_schreibe_deutsch = deutsch
            self.zeige_saetze_test(umgekehrt=umgekehrt)
        btn_cfg = {"font": ("Arial", 12, "bold"), "relief": "flat",
                   "padx": 0, "pady": 12, "cursor": "hand2", "width": 22}
        tk.Button(popup, text="🇩🇪   Deutsch", bg=CLR["blue"], fg="white",
                  command=lambda: starten(True), **btn_cfg).pack(pady=4)
        tk.Button(popup, text=f"🇫🇮   {lsname}", bg=CLR["red"], fg="white",
                  command=lambda: starten(False), **btn_cfg).pack(pady=(4, 20))
        self.root.update_idletasks()
        x = self.root.winfo_x() + self.root.winfo_width()  // 2 - 175
        y = self.root.winfo_y() + self.root.winfo_height() // 2 - 110
        popup.geometry(f"350x220+{x}+{y}")

    def zeige_saetze_lernen(self, umgekehrt=False):
        ui, ls = self.ui, self.ls
        saetze = saetze_laden(ls)
        if not saetze:
            messagebox.showinfo(t(ui, "saetze_kein_titel"), t(ui, "saetze_kein"))
            return
        self._session_starten()
        self.aktueller_modus = "saetze"
        tracking_senden("saetze_start", sprache=self.ls, modus="lernen")
        self._aktuelle_ansicht = lambda: self.zeige_saetze_lernen(umgekehrt)
        self.clear()
        self.root.geometry("560x500")
        mutter = muttersprache_label(ui)
        lsname = langname(ui, ls)

        self.satz_lern_liste     = saetze[:]
        random.shuffle(self.satz_lern_liste)
        self.satz_lern_index     = 0
        self.satz_lern_aufgedeckt = False
        self.satz_lern_audio_gespielt = False

        if umgekehrt:
            self.satz_lern_key_oben  = "lern"
            self.satz_lern_key_unten = "nativ"
            label_oben  = lsname.upper()
        else:
            self.satz_lern_key_oben  = "nativ"
            self.satz_lern_key_unten = "lern"
            label_oben  = mutter.upper()

        tk.Label(self.root, text="📚  Sätze Lernen", font=("Arial", 16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(16, 2))
        tk.Label(self.root, text="🔤 Alle Silben anklicken ist Pflicht vor dem Weitergehen!",
                 font=("Arial", 10, "bold"), bg=CLR["bg"], fg=CLR["red"]).pack(pady=(0, 8))

        self.lbl_satz_lern_nr = tk.Label(self.root, text="", font=("Arial", 11),
                                          bg=CLR["bg"], fg=CLR["sub"])
        self.lbl_satz_lern_nr.pack()

        f_a = tk.Frame(self.root, bg=CLR["white"],
                       highlightbackground=CLR["card_border"], highlightthickness=2)
        f_a.pack(padx=20, fill="x", pady=(6, 6))
        tk.Label(f_a, text=label_oben, font=("Arial", 10, "bold"),
                 bg=CLR["white"], fg=CLR["text"]).pack(pady=(6, 2))
        self.lbl_satz_lern_a = tk.Label(f_a, text="", font=("Arial", 14, "bold"),
                                         bg=CLR["white"], fg=CLR["text"],
                                         wraplength=480, justify="center")
        self.lbl_satz_lern_a.pack(padx=12, pady=(0, 10))

        self.f_satz_lern_b = tk.Frame(self.root, bg=CLR["light"],
                                       highlightbackground=CLR["card_border"], highlightthickness=2,
                                       cursor="hand2")
        self.f_satz_lern_b.pack(padx=20, fill="x", pady=(0, 10))
        self.lbl_satz_lern_b = tk.Label(self.f_satz_lern_b,
                                         text="❓  Klicken zum Aufdecken",
                                         font=("Arial", 13), bg=CLR["light"], fg=CLR["sub"])
        self.lbl_satz_lern_b.pack(pady=(10, 14))
        for w in [self.f_satz_lern_b, self.lbl_satz_lern_b]:
            w.bind("<Button-1>", lambda e: self._satz_lern_toggle())

        row = make_frame(self.root)
        row.pack(pady=6)
        self.btn_satz_lern_audio = tk.Button(row, text="🔤  Silben PFLICHT",
                                              font=("Arial", 12, "bold"),
                                              bg=CLR["red"], fg="white", relief="flat",
                                              padx=14, pady=8, cursor="hand2",
                                              command=self._satz_lern_play_audio)
        self.btn_satz_lern_audio.pack(side="left", padx=4)

        self.btn_satz_lern_weiter = tk.Button(row, text=t(ui, "weiter"),
                                               font=("Arial", 12, "bold"),
                                               bg=CLR["gray"], fg=CLR["sub"], relief="flat",
                                               padx=20, pady=8, cursor="hand2",
                                               command=self._satz_lern_weiter,
                                               state="disabled")
        self.btn_satz_lern_weiter.pack(side="left", padx=4)

        self.satz_lern_bearbeiten_aktiv = False
        row2 = make_frame(self.root)
        row2.pack(pady=(4, 0))
        self.btn_satz_lern_bearbeiten = tk.Button(row2, text="❤️  Bearbeiten", font=("Arial", 11, "bold"),
                  bg=CLR["gray"], fg=CLR["text"], relief="flat", padx=12, pady=6,
                  cursor="hand2", command=self._satz_lern_bearbeiten_umschalten)
        self.btn_satz_lern_bearbeiten.pack(side="left", padx=6)

        tk.Button(self.root, text=t(ui, "zurueck"), font=("Arial", 12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=20, pady=8,
                  cursor="hand2", command=self._satz_lern_zurueck).pack(pady=(4, 0))

        tk.Button(self.root, text="\U0001F392", font=("Segoe UI Emoji", 12, "bold"),
                  bg=CLR["light"], fg=CLR["text"], relief="flat", padx=14, pady=6,
                  cursor="hand2", command=self.zeige_inventar).pack(pady=(4, 0))

        self._satz_lern_zeige()

    def _satz_lern_bearbeiten_umschalten(self):
        self.satz_lern_bearbeiten_aktiv = not self.satz_lern_bearbeiten_aktiv
        if self.satz_lern_bearbeiten_aktiv:
            self.btn_satz_lern_bearbeiten.config(text="❤️  Bearbeiten ✓", bg=CLR["purple"], fg="white")
        else:
            self.btn_satz_lern_bearbeiten.config(text="❤️  Bearbeiten", bg=CLR["gray"], fg=CLR["text"])
        self._satz_lern_zeige()

    def _satz_lern_feld_speichern(self, feld_key, neuer_text):
        if self.satz_lern_index >= len(self.satz_lern_liste):
            return
        satz = self.satz_lern_liste[self.satz_lern_index]
        satz[feld_key] = neuer_text
        liste = saetze_laden(self.ls)
        for s in liste:
            if s is satz or (s.get("nativ", "") == satz.get("nativ", "") and
                             s.get("lern", "") == satz.get("lern", "")):
                s[feld_key] = neuer_text
                break
        saetze_speichern(self.ls, liste)

    def _satz_lern_zeige(self):
        ui = self.ui
        if self.satz_lern_index >= len(self.satz_lern_liste):
            self._session_beenden()
            tracking_senden("saetze_ende", sprache=self.ls, modus="lernen",
                            richtig=len(self.satz_lern_liste))
            messagebox.showinfo("🎉", f"Du hast alle {len(self.satz_lern_liste)} Sätze durchgelernt!")
            self.zeige_saetze_menue()
            return
        satz = self.satz_lern_liste[self.satz_lern_index]
        self.lbl_satz_lern_nr.config(
            text=f"Satz {self.satz_lern_index+1} von {len(self.satz_lern_liste)}")

        bearb = getattr(self, "satz_lern_bearbeiten_aktiv", False)

        if hasattr(self, "_satz_lern_entry_oben") and self._satz_lern_entry_oben is not None:
            self._satz_lern_entry_oben.destroy()
            self._satz_lern_entry_oben = None
        if hasattr(self, "_satz_lern_entry_unten") and self._satz_lern_entry_unten is not None:
            self._satz_lern_entry_unten.destroy()
            self._satz_lern_entry_unten = None

        if bearb:
            self.lbl_satz_lern_a.pack_forget()
            entry_a = tk.Text(self.lbl_satz_lern_a.master, font=("Arial", 13, "bold"),
                              fg=CLR["text"], bg=CLR["white"], height=2, wrap="word",
                              bd=0, highlightthickness=0)
            entry_a.insert("1.0", satz[self.satz_lern_key_oben])
            entry_a.pack(padx=12, pady=(0, 10), fill="x")
            key_oben = self.satz_lern_key_oben
            entry_a.bind("<FocusOut>", lambda e: self._satz_lern_feld_speichern(key_oben, entry_a.get("1.0", tk.END).strip()))
            self._satz_lern_entry_oben = entry_a

            self.lbl_satz_lern_b.config(text="", bg=CLR["white"])
            self.f_satz_lern_b.config(bg=CLR["white"])
            entry_b = tk.Text(self.f_satz_lern_b, font=("Arial", 13, "bold"),
                              fg=CLR["text"], bg=CLR["white"], height=2, wrap="word",
                              bd=0, highlightthickness=0)
            entry_b.insert("1.0", satz[self.satz_lern_key_unten])
            entry_b.pack(padx=12, pady=(10, 14), fill="x")
            key_unten = self.satz_lern_key_unten
            entry_b.bind("<FocusOut>", lambda e: self._satz_lern_feld_speichern(key_unten, entry_b.get("1.0", tk.END).strip()))
            self._satz_lern_entry_unten = entry_b

            self.satz_lern_aufgedeckt = True
            self.satz_lern_audio_gespielt = True
            self.btn_satz_lern_audio.config(bg="#2980b9", text="🔤  Silben bearbeiten")
            self.btn_satz_lern_weiter.config(state="normal", bg=CLR["green"], fg="white")
            return

        self.lbl_satz_lern_a.config(text=satz[self.satz_lern_key_oben])
        self.lbl_satz_lern_a.pack(padx=12, pady=(0, 10))
        self.satz_lern_aufgedeckt = False
        self.satz_lern_audio_gespielt = False
        self.btn_satz_lern_audio.config(bg=CLR["red"], text="🔤  Silben PFLICHT")
        self.btn_satz_lern_weiter.config(state="disabled", bg=CLR["gray"], fg=CLR["sub"])
        self.lbl_satz_lern_b.config(text="❓  Klicken zum Aufdecken",
                                     fg=CLR["sub"], font=("Arial", 13))
        self.f_satz_lern_b.config(bg=CLR["light"])
        self.lbl_satz_lern_b.config(bg=CLR["light"])

    def _satz_lern_play_audio(self):
        if self.satz_lern_index >= len(self.satz_lern_liste):
            return
        satz = self.satz_lern_liste[self.satz_lern_index]
        bearb = getattr(self, "satz_lern_bearbeiten_aktiv", False)

        def alle_geklickt():
            self.satz_lern_audio_gespielt = True
            self.btn_satz_lern_audio.config(bg="#16a085", text="🔤  Silben ✓")
            self.btn_satz_lern_weiter.config(state="normal", bg=CLR["green"], fg="white")

        self._satz_abc_kaestchen_oeffnen(
            satz, self.ls, bearbeitbar=bearb,
            beim_schliessen=self._satz_lern_zeige if bearb else None,
            alle_geklickt_callback=alle_geklickt)

    def _satz_lern_toggle(self):
        if self.satz_lern_index >= len(self.satz_lern_liste):
            return
        satz = self.satz_lern_liste[self.satz_lern_index]
        if not self.satz_lern_aufgedeckt:
            self.lbl_satz_lern_b.config(text=satz[self.satz_lern_key_unten],
                                         fg=CLR["text"], font=("Arial", 14, "bold"))
            self.f_satz_lern_b.config(bg=CLR["white"])
            self.lbl_satz_lern_b.config(bg=CLR["white"])
            self.satz_lern_aufgedeckt = True
        else:
            self.lbl_satz_lern_b.config(text="❓  Klicken zum Aufdecken",
                                         fg=CLR["sub"], font=("Arial", 13))
            self.f_satz_lern_b.config(bg=CLR["light"])
            self.lbl_satz_lern_b.config(bg=CLR["light"])
            self.satz_lern_aufgedeckt = False

    def _satz_lern_weiter(self):
        if not self.satz_lern_audio_gespielt:
            messagebox.showwarning("Silben Pflicht!",
                "Bitte zuerst alle Silben anklicken!\n(🔤 Silben PFLICHT Button)")
            return
        self.satz_lern_index += 1
        self._satz_lern_zeige()

    def _satz_lern_zurueck(self):
        self._session_beenden()
        self.zeige_saetze_menue()

    def zeige_saetze_bearbeiten(self):
        ui, ls = self.ui, self.ls
        self._aktuelle_ansicht = self.zeige_saetze_bearbeiten
        self.clear()
        self.root.geometry("660x560")

        tk.Label(self.root, text=t(ui, "saetze_bear_titel"), font=("Arial", 16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(16, 6))

        container = make_frame(self.root)
        container.pack(padx=16, fill="both", expand=True)
        canvas    = tk.Canvas(container, bg=CLR["bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.satz_scroll_frame = make_frame(canvas)
        self.satz_scroll_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.satz_scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        self._saetze_bear_aufbauen()

        tk.Button(self.root, text=t(ui, "zurueck"), font=("Arial", 12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=14, pady=8,
                  cursor="hand2", command=self.zeige_saetze_menue).pack(pady=8)

    def _saetze_bear_aufbauen(self):
        ui, ls = self.ui, self.ls
        mutter = muttersprache_label(ui)

        for w in self.satz_scroll_frame.winfo_children():
            w.destroy()

        liste = saetze_laden(ls)

        if not liste:
            tk.Label(self.satz_scroll_frame, text=t(ui, "saetze_bear_leer"),
                     font=("Arial", 12), bg=CLR["bg"], fg=CLR["sub"]).pack(pady=20)
            return

        hdr = tk.Frame(self.satz_scroll_frame, bg=CLR["hdr_bg"])
        hdr.pack(fill="x", pady=(0, 2))
        for txt, w in [(mutter, 15), (langname(ui, ls), 15), (t(ui, "bear_audio_spalte"), 5), ("", 5), (t(ui, "saetze_bear_aktion"), 14)]:
            tk.Label(hdr, text=txt, font=("Arial", 11, "bold"),
                     bg=CLR["hdr_bg"], fg=CLR["hdr_fg"], width=w, anchor="w").pack(side="left", padx=6, pady=5)

        for i, satz in enumerate(liste):
            bg = CLR["row_a"] if i % 2 == 0 else CLR["row_b"]
            zeile = tk.Frame(self.satz_scroll_frame, bg=bg,
                             highlightbackground=CLR["card_border"], highlightthickness=2)
            zeile.pack(fill="x", pady=1)
            tk.Label(zeile, text=satz.get("nativ", ""), font=("Arial", 11, "bold"),
                     bg=bg, fg=CLR["text"], width=15, anchor="w",
                     wraplength=180).pack(side="left", padx=6, pady=5)
            tk.Label(zeile, text=satz.get("lern", ""), font=("Arial", 11, "bold"),
                     bg=bg, fg=CLR["text"], width=15, anchor="w",
                     wraplength=180).pack(side="left", padx=6)
            hat_audio = bool(satz.get("audio", ""))
            tk.Label(zeile, text="🎵" if hat_audio else "—", font=("Arial", 12),
                     bg=bg, fg=CLR["green"] if hat_audio else CLR["sub"],
                     width=5).pack(side="left", padx=4)

            ist_abc = bool(satz.get("abc", False))
            abc_btn = tk.Label(zeile, text="☑" if ist_abc else "☐", font=("Arial", 13),
                               bg=bg, fg=CLR["green"] if ist_abc else CLR["sub"],
                               width=3, cursor="hand2")
            abc_btn.pack(side="left", padx=2)
            abc_btn.bind("<Button-1>", lambda e, idx=i: self._satz_abc_umschalten(idx))

            play_buchst_btn = tk.Label(zeile, text="🔤", font=("Arial", 13),
                                bg=bg, fg=CLR["blue"], width=2, cursor="hand2")
            play_buchst_btn.pack(side="left", padx=1)
            play_buchst_btn.bind("<Button-1>", lambda e, idx=i: self._satz_abc_fenster_oeffnen(idx))

            btn_r = tk.Frame(zeile, bg=bg)
            btn_r.pack(side="left", padx=6)
            tk.Button(btn_r, text=t(ui, "saetze_bear_aendern"), font=("Arial", 10, "bold"),
                      bg=CLR["purple"], fg="white", relief="flat", padx=7, pady=3,
                      cursor="hand2",
                      command=lambda idx=i: self._satz_aendern(idx)).pack(side="left", padx=2)
            tk.Button(btn_r, text=t(ui, "saetze_bear_loeschen"), font=("Arial", 10, "bold"),
                      bg=CLR["red"], fg="white", relief="flat", padx=7, pady=3,
                      cursor="hand2",
                      command=lambda idx=i: self._satz_loeschen(idx)).pack(side="left", padx=2)

    def _satz_abc_umschalten(self, index):
        ls = self.ls
        liste = saetze_laden(ls)
        if 0 <= index < len(liste):
            liste[index]["abc"] = not liste[index].get("abc", False)
            saetze_speichern(ls, liste)
            self._saetze_bear_aufbauen()

    def _satz_abc_fenster_oeffnen(self, index):
        ls = self.ls
        liste = saetze_laden(ls)
        if not (0 <= index < len(liste)):
            return
        satz_item = liste[index]
        self._satz_abc_kaestchen_oeffnen(satz_item, ls, bearbeitbar=True,
                                         beim_schliessen=self._saetze_bear_aufbauen)

    def _satz_aendern(self, index):
        ui, ls = self.ui, self.ls
        lsname = langname(ui, ls)
        mutter = muttersprache_label(ui)
        liste  = saetze_laden(ls)
        satz   = liste[index]

        popup = tk.Toplevel(self.root)
        try:
            popup.iconbitmap(os.path.join(BASE_DIR, "heart.ico"))
        except Exception:
            pass
        popup.title(t(ui, "saetze_bear_aendern_titel"))
        popup.resizable(False, False)
        popup.configure(bg=CLR["popup_bg"])
        popup.grab_set()

        def lbl(txt):
            tk.Label(popup, text=txt, font=("Arial", 11, "bold"),
                     bg=CLR["popup_bg"], fg=CLR["text"]).pack(pady=(14, 4), padx=30, anchor="w")

        def text_kasten(parent, initial_value=""):
            outer = tk.Frame(parent, bg=CLR["border"])
            outer.pack(fill="x", padx=30, pady=(0, 4))
            inner = tk.Frame(outer, bg=CLR["entry_bg"])
            inner.pack(fill="x", padx=2, pady=2)
            txt = tk.Text(inner, font=("Arial", 13, "bold"), height=3, wrap="word",
                          fg=CLR["entry_fg"], bg=CLR["entry_bg"],
                          insertbackground=CLR["entry_ins"],
                          bd=0, relief="flat", highlightthickness=0, padx=8, pady=6)
            txt.pack(fill="x")
            txt.insert("1.0", initial_value)

            def on_focus_in(e):
                outer.config(bg=CLR["blue"])
            def on_focus_out(e):
                outer.config(bg=CLR["border"])

            txt.bind("<FocusIn>",  on_focus_in)
            txt.bind("<FocusOut>", on_focus_out)
            return txt

        lbl(f"{mutter}:")
        ein_a = text_kasten(popup, satz.get("nativ", ""))

        lbl(f"{lsname}:")
        ein_b = text_kasten(popup, satz.get("lern", ""))

        lbl(t(ui, "saetze_bear_audio"))
        satz_audio_var = tk.StringVar(value=satz.get("audio", ""))
        af = tk.Frame(popup, bg=CLR["popup_bg"])
        af.pack(fill="x", padx=30, pady=(0, 6))

        def kurz_s(pfad):
            return os.path.basename(pfad) if pfad else t(ui, "audio_keine")

        satz_audio_lbl = tk.Label(af, text=kurz_s(satz_audio_var.get()),
                                  font=("Arial", 9, "bold"), bg=CLR["popup_bg"], fg=CLR["text"],
                                  anchor="w", width=28)
        satz_audio_lbl.pack(side="left")

        def waehle_satz_audio():
            pfad = filedialog.askopenfilename(
                title="MP3 wählen",
                initialdir=AUDIO_DIR,
                filetypes=[("MP3-Dateien", "*.mp3"), ("Alle Dateien", "*.*")])
            if pfad:
                name = os.path.basename(pfad)
                satz_audio_var.set(name)
                satz_audio_lbl.config(text=name)

        tk.Button(af, text=t(ui, "saetze_bear_audio_btn"), font=("Arial", 10, "bold"),
                  bg=CLR["blue"], fg="white", relief="flat", padx=8, pady=3,
                  cursor="hand2", command=waehle_satz_audio).pack(side="left", padx=6)

        def speichern():
            a = ein_a.get("1.0", tk.END).strip()
            b = ein_b.get("1.0", tk.END).strip()
            if a and b:
                liste[index] = {"nativ": a, "lern": b, "audio": satz_audio_var.get().strip()}
                saetze_speichern(ls, liste)
                popup.destroy()
                self._saetze_bear_aufbauen()

        row = tk.Frame(popup, bg=CLR["popup_bg"])
        row.pack(pady=(12, 20))
        tk.Button(row, text=t(ui, "saetze_bear_speichern"), font=("Arial", 11, "bold"),
                  bg=CLR["purple"], fg="white", relief="flat", padx=14, pady=6,
                  cursor="hand2", command=speichern).pack(side="left", padx=6)
        tk.Button(row, text=t(ui, "saetze_bear_abbruch"), font=("Arial", 11, "bold"),
                  bg=CLR["gray"], fg=CLR["text"], relief="flat", padx=12, pady=6,
                  cursor="hand2", command=popup.destroy).pack(side="left", padx=6)

        self.root.update_idletasks()
        x = self.root.winfo_x() + self.root.winfo_width()  // 2 - 220
        y = self.root.winfo_y() + self.root.winfo_height() // 2 - 220
        popup.geometry(f"440x480+{x}+{y}")
        ein_a.focus()

    def _satz_loeschen(self, index):
        ui, ls = self.ui, self.ls
        liste = saetze_laden(ls)
        wort  = liste[index].get("nativ", "")
        if messagebox.askyesno(t(ui, "saetze_bear_loeschen_titel"), t(ui, "saetze_bear_loeschen_frage", w=wort)):
            liste.pop(index)
            saetze_speichern(ls, liste)
            tracking_senden("satz_geloescht", sprache=ls, satz=wort)
            self._saetze_bear_aufbauen()

    def zeige_saetze_eintragen(self):
        self._aktuelle_ansicht = self.zeige_saetze_eintragen
        self.clear()
        self.root.geometry("500x620")
        ui, ls = self.ui, self.ls
        lsname = langname(ui, ls)
        mutter = muttersprache_label(ui)

        tk.Label(self.root, text=t(ui, "saetze_ein_titel"), font=("Arial", 16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(22, 2))
        tk.Label(self.root, text=t(ui, "saetze_ein_hinweis"),
                 font=("Arial", 10), bg=CLR["bg"], fg=CLR["sub"]).pack(pady=(0, 14))

        f_a = tk.Frame(self.root, bg=CLR["white"],
                       highlightbackground=CLR["card_border"], highlightthickness=2)
        f_a.pack(padx=30, fill="x", pady=(0, 10))
        tk.Label(f_a, text=mutter.upper(), font=("Arial", 11, "bold"),
                 bg=CLR["white"], fg=CLR["text"]).pack(pady=(8, 2))
        self.satz_ein_a = tk.Text(f_a, font=("Arial", 14, "bold"), height=3, wrap="word",
                                   fg=CLR["entry_fg"], bd=0, highlightthickness=0,
                                   bg=CLR["entry_bg"], padx=10,
                                   insertbackground=CLR["entry_ins"])
        self.satz_ein_a.pack(fill="x", padx=6, pady=(0, 10))

        f_b = tk.Frame(self.root, bg=CLR["white"],
                       highlightbackground=CLR["card_border"], highlightthickness=2)
        f_b.pack(padx=30, fill="x", pady=(0, 10))
        tk.Label(f_b, text=lsname.upper(), font=("Arial", 11, "bold"),
                 bg=CLR["white"], fg=CLR["text"]).pack(pady=(8, 2))
        self.satz_ein_b = tk.Text(f_b, font=("Arial", 14, "bold"), height=3, wrap="word",
                                   fg=CLR["entry_fg"], bd=0, highlightthickness=0,
                                   bg=CLR["entry_bg"], padx=10,
                                   insertbackground=CLR["entry_ins"])
        self.satz_ein_b.pack(fill="x", padx=6, pady=(0, 10))

        f_audio_s = tk.Frame(self.root, bg=CLR["white"],
                             highlightbackground=CLR["card_border"], highlightthickness=2)
        f_audio_s.pack(padx=30, fill="x", pady=(0, 10))
        tk.Label(f_audio_s, text=t(ui, "audio_titel"), font=("Arial", 11, "bold"),
                 bg=CLR["white"], fg=CLR["text"]).pack(pady=(8, 2))
        self.satz_audio_var = tk.StringVar(value="")
        saf_row = tk.Frame(f_audio_s, bg=CLR["white"])
        saf_row.pack(fill="x", padx=12, pady=(0, 10))
        self.satz_audio_lbl = tk.Label(saf_row, text=t(ui, "audio_keine"),
                                       font=("Arial", 10), bg=CLR["white"],
                                       fg=CLR["sub"], anchor="w")
        self.satz_audio_lbl.pack(side="left", fill="x", expand=True)

        def waehle_satz_ein_audio():
            pfad = filedialog.askopenfilename(
                title="MP3-Datei wählen",
                initialdir=AUDIO_DIR,
                filetypes=[("MP3-Dateien", "*.mp3"), ("Alle Dateien", "*.*")])
            if pfad:
                name = os.path.basename(pfad)
                self.satz_audio_var.set(name)
                self.satz_audio_lbl.config(text=name, fg=CLR["green"])

        def satz_audio_loeschen():
            self.satz_audio_var.set("")
            self.satz_audio_lbl.config(text=t(ui, "audio_keine"), fg=CLR["sub"])

        tk.Button(saf_row, text=t(ui, "audio_waehlen"), font=("Arial", 10, "bold"),
                  bg=CLR["blue"], fg="white", relief="flat", padx=8, pady=3,
                  cursor="hand2", command=waehle_satz_ein_audio).pack(side="left", padx=(6, 2))
        tk.Button(saf_row, text="✕", font=("Arial", 10, "bold"),
                  bg=CLR["red"], fg="white", relief="flat", padx=6, pady=3,
                  cursor="hand2", command=satz_audio_loeschen).pack(side="left", padx=(2, 0))

        self.lbl_satz_status = tk.Label(self.root, text="", font=("Arial", 11),
                                        bg=CLR["bg"], fg="#27ae60")
        self.lbl_satz_status.pack(pady=(0, 8))

        row = make_frame(self.root)
        row.pack()
        tk.Button(row, text=t(ui, "speichern"), font=("Arial", 12, "bold"),
                  bg=CLR["blue"], fg="white", relief="flat", padx=18, pady=8,
                  cursor="hand2", command=self._satz_speichern).pack(side="left", padx=6)
        tk.Button(row, text=t(ui, "zurueck"), font=("Arial", 12, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=14, pady=8,
                  cursor="hand2", command=self.zeige_saetze_menue).pack(side="left", padx=6)

        self.satz_ein_a.focus()

    def _satz_speichern(self):
        ui, ls = self.ui, self.ls
        a = self.satz_ein_a.get("1.0", tk.END).strip()
        b = self.satz_ein_b.get("1.0", tk.END).strip()
        if not a or not b:
            self.lbl_satz_status.config(text=t(ui, "saetze_ein_fehler"), fg=CLR["red"])
            return
        audio = self.satz_audio_var.get().strip() if hasattr(self, 'satz_audio_var') else ""
        liste = saetze_laden(ls)
        liste.append({"nativ": a, "lern": b, "audio": audio})
        saetze_speichern(ls, liste)
        self.lbl_satz_status.config(text=t(ui, "saetze_ein_ok"), fg="#27ae60")
        self.satz_ein_a.delete("1.0", tk.END)
        self.satz_ein_b.delete("1.0", tk.END)
        self.satz_audio_var.set("")
        self.satz_audio_lbl.config(text=t(ui, "audio_keine"), fg=CLR["sub"])
        self.satz_ein_a.focus()

    def zeige_saetze_test(self, umgekehrt=False):
        ui, ls = self.ui, self.ls
        saetze = saetze_laden(ls)
        if not saetze:
            messagebox.showinfo(t(ui, "saetze_kein_titel"), t(ui, "saetze_kein"))
            return

        self._session_starten()
        self.aktueller_modus = "saetze"
        tracking_senden("saetze_start", sprache=self.ls, modus="test")
        self._aktuelle_ansicht = lambda: self.zeige_saetze_test(umgekehrt)
        self.clear()
        self.root.geometry("780x760")
        lsname = langname(ui, ls)
        mutter = muttersprache_label(ui)

        self.satz_liste      = saetze[:]
        random.shuffle(self.satz_liste)
        self.satz_index      = 0
        self.satz_richtig_w  = 0
        self.satz_falsch_w   = 0
        self.satz_versuche   = 0
        self.satz_max_vers   = 5
        self.satz_bereits_richtig = []
        self.satz_audio_gespielt = False
        self.xp_multiplikator    = 1.5 if hat_freischaltung("xp_multiplikator") else 1.0
        self.streak_bonus_aktiv  = hat_freischaltung("streak_bonus")

        if umgekehrt:
            label_frage   = lsname.upper()
            label_eingabe = mutter.upper()
            self.satz_key_frage   = "lern"
            self.satz_key_loesung = "nativ"
        else:
            label_frage   = mutter.upper()
            label_eingabe = lsname.upper()
            self.satz_key_frage   = "nativ"
            self.satz_key_loesung = "lern"

        tk.Label(self.root, text=t(ui, "saetze_test_titel"), font=("Arial", 16, "bold"),
                 bg=CLR["bg"], fg=CLR["text"]).pack(pady=(14, 2))
        tk.Label(self.root, text="🔤 Silben PFLICHT vor Weiter!",
                 font=("Arial", 10, "bold"), bg=CLR["bg"], fg=CLR["red"]).pack(pady=(0, 4))

        info_row = make_frame(self.root)
        info_row.pack()
        self.lbl_satz_nr = tk.Label(info_row, text="", font=("Arial", 11),
                                    bg=CLR["bg"], fg=CLR["sub"])
        self.lbl_satz_nr.pack(side="left", padx=8)
        self.lbl_satz_vers = tk.Label(info_row, text="", font=("Arial", 11, "bold"),
                                      bg=CLR["bg"], fg=CLR["orange"])
        self.lbl_satz_vers.pack(side="left", padx=8)

        f_a = tk.Frame(self.root, bg=CLR["white"],
                       highlightbackground=CLR["card_border"], highlightthickness=2)
        f_a.pack(padx=12, fill="x", pady=(6, 6))
        tk.Label(f_a, text=label_frage, font=("Arial", 10, "bold"),
                 bg=CLR["white"], fg=CLR["text"]).pack(pady=(6, 2))
        self.lbl_satz_frage = tk.Label(f_a, text="", font=("Arial", 15, "bold"),
                                        bg=CLR["white"], fg=CLR["text"],
                                        wraplength=700, justify="left")
        self.lbl_satz_frage.pack(padx=12, pady=(0, 10))

        f_b = tk.Frame(self.root, bg=CLR["white"],
                       highlightbackground=CLR["card_border"], highlightthickness=2)
        f_b.pack(padx=12, fill="x", pady=(0, 4))
        tk.Label(f_b, text=label_eingabe, font=("Arial", 10, "bold"),
                 bg=CLR["white"], fg=CLR["text"]).pack(pady=(6, 2))
        self.satz_eingabe = tk.Text(f_b, font=("Arial", 14, "bold"), height=3, wrap="word",
                                    fg=CLR["entry_fg"], bd=0, highlightthickness=0,
                                    bg=CLR["entry_bg"], padx=10,
                                    insertbackground=CLR["entry_ins"])
        self.satz_eingabe.pack(fill="x", padx=6, pady=(0, 10))

        # Sonderzeichen wenn Deutsch einzugeben (aus Sprachauswahl-Popup oder umgekehrt)
        zeige_sz = getattr(self, '_satz_schreibe_deutsch', umgekehrt)
        if zeige_sz:
            sz_row = make_frame(self.root)
            sz_row.pack(pady=(0, 4))
            for zeichen in ["ß", "Ü", "Ä", "Ö"]:
                tk.Button(sz_row, text=zeichen, font=("Arial", 15, "bold"),
                          bg=CLR["blue"], fg="white", relief="flat",
                          padx=16, pady=6, cursor="hand2",
                          command=lambda z=zeichen: self._satz_sonderzeichen(z)).pack(side="left", padx=4)

        fb_outer = tk.Frame(self.root, bg=CLR["white"],
                            highlightbackground=CLR["card_border"], highlightthickness=2)
        fb_outer.pack(padx=12, fill="x", pady=(0, 4))
        tk.Label(fb_outer, text=t(ui, "satz_fb_titel"),
                 font=("Arial", 9, "bold"), bg=CLR["white"], fg=CLR["sub"]).pack(pady=(6, 2))
        fb_scroll_frame = tk.Frame(fb_outer, bg=CLR["white"])
        fb_scroll_frame.pack(fill="x", padx=6, pady=(0, 6))
        fb_canvas = tk.Canvas(fb_scroll_frame, bg=CLR["white"], highlightthickness=0, height=110)
        fb_sb = tk.Scrollbar(fb_scroll_frame, orient="horizontal", command=fb_canvas.xview)
        fb_canvas.configure(xscrollcommand=fb_sb.set)
        fb_sb.pack(side="bottom", fill="x")
        fb_canvas.pack(side="top", fill="x")
        self.fb_canvas = fb_canvas
        self.fb_inner = tk.Frame(fb_canvas, bg=CLR["white"])
        fb_canvas.create_window((0, 0), window=self.fb_inner, anchor="nw")
        self.fb_inner.bind("<Configure>",
            lambda e: fb_canvas.configure(scrollregion=fb_canvas.bbox("all")))

        row = make_frame(self.root)
        row.pack(pady=6)
        self.btn_satz_audio = tk.Button(row, text="🔊  Silben PFLICHT",
                                         font=("Arial", 12, "bold"),
                                         bg=CLR["red"], fg="white", relief="flat",
                                         padx=14, pady=10, cursor="hand2",
                                         command=self._satz_play_audio)
        self.btn_satz_audio.pack(side="left", padx=5)
        self.btn_satz_pruefen = tk.Button(row, text=t(ui, "satz_test_prufen"),
                                          font=("Arial", 12, "bold"),
                                          bg="#d35400", fg="white", relief="flat",
                                          padx=16, pady=8, cursor="hand2",
                                          command=self._satz_pruefen)
        self.btn_satz_pruefen.pack(side="left", padx=3)
        self.btn_satz_weiter = tk.Button(row, text=t(ui, "weiter"),
                                          font=("Arial", 12, "bold"),
                                          bg=CLR["gray"], fg=CLR["sub"], relief="flat",
                                          padx=16, pady=8, cursor="hand2",
                                          command=self._satz_weiter,
                                          state="disabled")
        self.btn_satz_weiter.pack(side="left", padx=3)
        tk.Button(row, text=t(ui, "zurueck"), font=("Arial", 11, "bold"),
                  bg=CLR["back_bg"], fg=CLR["back_fg"], relief="flat", padx=10, pady=8,
                  cursor="hand2", command=self._satz_zurueck).pack(side="left", padx=3)
        tk.Button(row, text="\U0001F392", font=("Segoe UI Emoji", 11, "bold"),
                  bg=CLR["light"], fg=CLR["text"], relief="flat", padx=10, pady=8,
                  cursor="hand2", command=self.zeige_inventar).pack(side="left", padx=3)

        self.root.bind("<Return>", lambda e: self._satz_pruefen()
                       if self.btn_satz_pruefen["state"] == "normal" else None)
        self._satz_naechste()

    def _satz_fb_aufbauen(self, w_loesung, w_antwort):
        for w in self.fb_inner.winfo_children():
            w.destroy()

        for i, soll in enumerate(w_loesung):
            bereits_ok = i in self.satz_bereits_richtig
            ist = w_antwort[i] if i < len(w_antwort) else ""
            korrekt = bereits_ok or (ist == soll)

            if i > 0:
                tk.Label(self.fb_inner, text="│", font=("Arial", 18),
                         bg=CLR["white"], fg=CLR["sub"]).pack(side="left", padx=1)

            kachel = tk.Frame(self.fb_inner, bg=CLR["white"])
            kachel.pack(side="left", padx=3, pady=6)

            if korrekt:
                box = tk.Frame(kachel, bg=CLR["white"],
                               highlightbackground="#27ae60", highlightthickness=2)
                box.pack()
                tk.Label(box, text="✅", font=("Arial", 10), bg=CLR["white"]).pack(pady=(4, 0))
                tk.Label(box, text=soll, font=("Arial", 13, "bold"),
                         bg=CLR["white"], fg="#27ae60").pack(padx=10, pady=(2, 6))
            else:
                box = tk.Frame(kachel, bg=CLR["white"],
                               highlightbackground=CLR["red"], highlightthickness=2)
                box.pack()
                tk.Label(box, text="❌", font=("Arial", 10), bg=CLR["white"]).pack(pady=(4, 0))
                tk.Label(box, text="?", font=("Arial", 13, "bold"),
                         bg=CLR["white"], fg="#c0392b").pack(padx=14, pady=(2, 6))

        for j in range(len(w_loesung), len(w_antwort)):
            tk.Label(self.fb_inner, text="│", font=("Arial", 18),
                     bg=CLR["white"], fg=CLR["sub"]).pack(side="left", padx=1)
            kachel = tk.Frame(self.fb_inner, bg=CLR["white"])
            kachel.pack(side="left", padx=3, pady=6)
            box = tk.Frame(kachel, bg=CLR["white"],
                           highlightbackground=CLR["red"], highlightthickness=2)
            box.pack()
            tk.Label(box, text="❌ extra", font=("Arial", 9),
                     bg=CLR["white"], fg=CLR["red"]).pack(padx=6, pady=(4, 0))
            tk.Label(box, text=w_antwort[j], font=("Arial", 12, "bold"),
                     bg=CLR["white"], fg=CLR["red"]).pack(padx=8, pady=(0, 6))

        self.fb_canvas.update_idletasks()
        self.fb_canvas.configure(scrollregion=self.fb_canvas.bbox("all"))

    def _satz_sonderzeichen(self, z):
        try:
            self.satz_eingabe.insert(tk.INSERT, z)
        except Exception:
            self.satz_eingabe.insert(tk.END, z)
        self.satz_eingabe.focus()

    def _satz_play_audio(self):
        if self.satz_index >= len(self.satz_liste):
            return
        satz = self.satz_liste[self.satz_index]

        def alle_geklickt():
            self.satz_audio_gespielt = True
            self.btn_satz_audio.config(bg="#16a085", text="🔊  Silben ✓")
            if self.btn_satz_pruefen["state"] == "disabled":
                self.btn_satz_weiter.config(state="normal", bg=CLR["green"], fg="white",
                                             text=t(self.ui, "weiter"))
                self.btn_satz_weiter.focus()

        self._satz_abc_kaestchen_oeffnen(satz, self.ls, bearbeitbar=False,
                                         nur_sound=True, alle_geklickt_callback=alle_geklickt)

    def _satz_naechste(self):
        ui = self.ui
        if self.satz_index >= len(self.satz_liste):
            self._satz_abschluss()
            return
        satz = self.satz_liste[self.satz_index]
        self.satz_versuche = 0
        self.satz_bereits_richtig = []
        self.satz_audio_gespielt = False
        self.lbl_satz_nr.config(
            text=t(ui, "test_frage", i=self.satz_index+1, n=len(self.satz_liste)))
        self.lbl_satz_vers.config(
            text=t(ui, "satz_vers_uebrig", v=self.satz_max_vers - self.satz_versuche))
        self.lbl_satz_frage.config(text=satz[self.satz_key_frage])
        for w in self.fb_inner.winfo_children():
            w.destroy()
        self.satz_eingabe.config(state="normal")
        self.satz_eingabe.delete("1.0", tk.END)
        self.btn_satz_pruefen.config(state="normal")
        self.btn_satz_weiter.config(state="disabled", bg=CLR["gray"], fg=CLR["sub"])
        self.btn_satz_audio.config(bg=CLR["red"], text="🔊  Silben PFLICHT")
        self.satz_eingabe.focus()

    def _satz_pruefen(self):
        if self.btn_satz_pruefen["state"] == "disabled":
            return
        ui  = self.ui
        satz     = self.satz_liste[self.satz_index]
        loesung  = satz[self.satz_key_loesung]
        antwort  = self.satz_eingabe.get("1.0", tk.END).strip()

        w_loesung = loesung.split()
        w_antwort = antwort.split()

        richtig_count = sum(1 for i, soll in enumerate(w_loesung)
                            if i < len(w_antwort) and w_antwort[i] == soll)
        falsch_count  = len(w_loesung) - richtig_count
        falsch_count += max(0, len(w_antwort) - len(w_loesung))

        falsche_woerter = [soll for i, soll in enumerate(w_loesung)
                           if not (i < len(w_antwort) and w_antwort[i] == soll)]
        if falsche_woerter:
            tracking_senden("wort_falsch", sprache=self.ls, vokabel=", ".join(falsche_woerter),
                            modus="saetze")

        for i, soll in enumerate(w_loesung):
            if i not in self.satz_bereits_richtig:
                ist = w_antwort[i] if i < len(w_antwort) else ""
                if ist == soll:
                    self.satz_bereits_richtig.append(i)

        self._satz_fb_aufbauen(w_loesung, w_antwort)

        self.satz_versuche += 1
        verbleibend = self.satz_max_vers - self.satz_versuche

        alle_richtig = (falsch_count == 0)
        versuche_vorbei = (self.satz_versuche >= self.satz_max_vers)

        if alle_richtig or versuche_vorbei:
            self.satz_richtig_w += richtig_count
            self.satz_falsch_w  += falsch_count

            xp_g = int(richtig_count * 2 * self.xp_multiplikator)
            xp_g = xp_g + (richtig_count * shop_trank_xp_bonus())
            xp_v = falsch_count
            s = stats_laden()
            s["richtig"]  = s.get("richtig", 0) + richtig_count
            s["falsch"]   = s.get("falsch",  0) + falsch_count
            s["level_xp"] = max(0, s.get("level_xp", 0) + xp_g - xp_v)
            neu = check_neue_freischaltungen(s, ui=self.ui)
            stats_speichern(s)
            if richtig_count > 0:
                shop_coins_hinzufuegen(richtig_count)
            if neu:
                self.root.after(800, lambda: self._zeige_freischaltung_popup(neu, s))

            if alle_richtig:
                e_suf = "en" if self.satz_versuche > 1 else ""
                self.lbl_satz_vers.config(
                    text=t(ui, "satz_vers_perfekt", v=self.satz_versuche, e=e_suf),
                    fg="#27ae60")
            else:
                self.lbl_satz_vers.config(
                    text=t(ui, "satz_vers_auf"),
                    fg=CLR["red"])
                for w in self.fb_inner.winfo_children():
                    w.destroy()
                for i, soll in enumerate(w_loesung):
                    if i > 0:
                        tk.Label(self.fb_inner, text="│", font=("Arial", 18),
                                 bg=CLR["white"], fg=CLR["sub"]).pack(side="left", padx=1)
                    kachel = tk.Frame(self.fb_inner, bg=CLR["white"])
                    kachel.pack(side="left", padx=3, pady=6)
                    ist = w_antwort[i] if i < len(w_antwort) else ""
                    korrekt = (ist == soll)
                    bg_k = CLR["white"]
                    rand  = "#27ae60" if korrekt else "#f39c12"
                    icon  = "✅" if korrekt else "💡"
                    box = tk.Frame(kachel, bg=bg_k,
                                   highlightbackground=rand, highlightthickness=2)
                    box.pack()
                    tk.Label(box, text=icon, font=("Arial", 10), bg=bg_k).pack(pady=(4, 0))
                    tk.Label(box, text=soll, font=("Arial", 13, "bold"),
                             bg=bg_k, fg=rand).pack(padx=10, pady=(2, 6))
                self.fb_canvas.update_idletasks()
                self.fb_canvas.configure(scrollregion=self.fb_canvas.bbox("all"))

            self.satz_eingabe.config(state="disabled")
            self.btn_satz_pruefen.config(state="disabled")
            if self.satz_audio_gespielt:
                self.btn_satz_weiter.config(state="normal", bg=CLR["green"], fg="white",
                                             text=t(self.ui, "weiter"))
                self.btn_satz_weiter.focus()
            else:
                self.btn_satz_weiter.config(state="disabled", bg=CLR["red"], fg="white",
                                             text="🔤 Silben PFLICHT → dann Weiter")
        else:
            e_suf = "e" if verbleibend != 1 else ""
            self.lbl_satz_vers.config(
                text=t(ui, "satz_vers_fehler", f=falsch_count, v=verbleibend, e=e_suf),
                fg=CLR["orange"])
            self.satz_eingabe.delete("1.0", tk.END)
            self.satz_eingabe.focus()

    def _satz_weiter(self):
        if self.btn_satz_weiter["state"] == "disabled":
            return
        if not self.satz_audio_gespielt:
            messagebox.showwarning("Silben Pflicht!",
                "Bitte zuerst alle Silben anklicken!\n(🔤 Silben PFLICHT Button)")
            return
        self.btn_satz_weiter.config(text=t(self.ui, "weiter"))
        self.satz_index += 1
        self._satz_naechste()

    def _satz_zurueck(self):
        self._session_beenden()
        self.zeige_hauptmenue()

    def _satz_abschluss(self):
        self._session_beenden()
        ui  = self.ui
        r   = self.satz_richtig_w
        f   = self.satz_falsch_w
        g   = r + f
        p   = int(r / g * 100) if g else 0
        tracking_senden("saetze_ende", sprache=self.ls, modus="test", richtig=r, falsch=f)
        messagebox.showinfo("🎉", t(ui, "saetze_ergebnis", r=r, g=g, p=p, f=f))
        self.zeige_saetze_richtung_test()


# ============================================================
def _update_check_im_hintergrund(root):
    if not AUTO_UPDATE_AKTIV:
        return
    def worker():
        ergebnis = update_pruefen()
        if not ergebnis:
            return
        neue_version, download_url = ergebnis

        def starte_install():
            _update_installieren_mit_hinweis(root, download_url, neue_version)
        try:
            root.after(0, starte_install)
        except Exception:
            pass
    threading.Thread(target=worker, daemon=True).start()

def _update_installieren_mit_hinweis(root, download_url, neue_version):
    hinweis = tk.Toplevel(root)
    hinweis.title("Update wird installiert …")
    hinweis.configure(bg="#1e1e1e")
    hinweis.resizable(False, False)
    tk.Label(hinweis, text="🔄 Update wird geladen und installiert …",
             font=("Arial", 12, "bold"), bg="#1e1e1e", fg="white").pack(padx=30, pady=24)
    root.update_idletasks()
    x = root.winfo_x() + root.winfo_width()  // 2 - 170
    y = root.winfo_y() + root.winfo_height() // 2 - 40
    hinweis.geometry(f"340x90+{x}+{y}")

    def worker():
        erfolg, fehlertext = update_herunterladen_und_installieren(download_url, neue_version)

        def fertig():
            if erfolg:
                update_neustart()
            else:
                hinweis.destroy()
                messagebox.showerror("Update fehlgeschlagen",
                    "Das Update konnte nicht installiert werden.\n\n"
                    f"Grund: {fehlertext}")
        try:
            root.after(0, fertig)
        except Exception:
            pass
    threading.Thread(target=worker, daemon=True).start()

if __name__ == "__main__":
    import traceback

    UNSAUBER_FLAG = os.path.join(BASE_DIR, "unsauber_beendet.flag")

    # Wurde beim letzten Programmstart die Flag-Datei nicht entfernt (weil das
    # Programm nicht ueber den normalen Weg beendet wurde: Fenster hart zu,
    # Prozess gekillt, Absturz ohne Exception-Handler), dann war der letzte
    # Exit unsauber. Wird jetzt gemeldet und die Flag fuer diesen Lauf neu gesetzt.
    war_unsauber = os.path.exists(UNSAUBER_FLAG)
    try:
        with open(UNSAUBER_FLAG, "w", encoding="utf-8") as f:
            f.write(time.strftime("%d.%m.%Y %H:%M:%S"))
    except Exception:
        pass

    def _fehler_anzeigen(exc_type, exc_value, exc_tb):
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            with open(os.path.join(BASE_DIR, "VilmaLearn_fehler.log"), "a", encoding="utf-8") as f:
                f.write("\n" + "="*60 + "\n" + time.strftime("%d.%m.%Y %H:%M:%S") + "\n" + text)
        except Exception:
            pass
        fehler_typ_name = exc_type.__name__ if exc_type else ""
        fehler_kurz = str(exc_value)[:500]
        tracking_senden("absturz",
                        fehlermeldung=f"{fehler_typ_name}: {fehler_kurz}".strip(": "))
        try:
            messagebox.showerror("Fehler aufgetreten", text[-1500:])
        except Exception:
            print(text)

    root = tk.Tk()
    root.report_callback_exception = _fehler_anzeigen
    app = App(root)
    _update_check_im_hintergrund(root)
    tracking_senden("start", sprache=getattr(app, "ls", ""), letzter_exit_unsauber=war_unsauber)
    if war_unsauber:
        tracking_senden("unsauberes_beenden")
    root.mainloop()
    tracking_senden("stop")
    # Sauberer Exit erreicht -> Flag wieder entfernen, damit der naechste Start
    # nicht faelschlich als "nach Absturz" gilt.
    try:
        if os.path.exists(UNSAUBER_FLAG):
            os.remove(UNSAUBER_FLAG)
    except Exception:
        pass
