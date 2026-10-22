"""I risultati e le statistiche da ESPN, per colmare il ritardo di football-data.

Il problema che risolve.
------------------------
football-data.co.uk e' la nostra spina dorsale storica: ha anni di partite e,
soprattutto, le quote di chiusura di molti operatori — cose che non si trovano
gratis da nessun'altra parte. Ma pubblica i risultati *a turno concluso*, e a
volte con giorni di ritardo: le intestazioni HTTP dei suoi file lo dicono senza
ambiguita'. Per un sito che si aggiorna ogni notte questo significa restare
fermi mentre il campionato va avanti, che e' esattamente il modo in cui un
lettore smette di tornare.

ESPN espone un endpoint pubblico, senza chiave, con i risultati finali entro
pochi minuti dal fischio. Non e' documentato come API pubblica: e' quello che
alimenta il loro sito. Va trattato per quello che e' — puo' cambiare forma
senza preavviso — e infatti qui ogni accesso e' difensivo: se ESPN non
risponde, restano i dati di football-data e il sito esce lo stesso.

Il regalo inatteso.
-------------------
Il riepilogo di ESPN porta ventisette statistiche per squadra contro le sette
di football-data. Arrivano possesso palla, passaggi riusciti, cross, contrasti,
intercetti, respinte, parate: roba che football-data non ha mai avuto. E' il
motivo per cui questo modulo non e' solo un cerotto sul ritardo.

Cosa NON fa.
------------
Non tocca le quote. Quelle restano football-data, che le ha storiche e da piu'
operatori. Qui si prendono risultati e statistiche di gioco, niente altro.
"""

from __future__ import annotations

import difflib
import json
import re
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

UTC = timezone.utc
# ESPN dichiara sempre l'ora in UTC ("2026-09-04T18:45Z"). Il lettore e'
# italiano: la si converte una volta sola, qui, e non ci si pensa piu'.
ROMA = ZoneInfo("Europe/Rome")

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

# Quante partite al massimo si scaricano per campionato in un turno. Serve
# quando si aggiunge un dato nuovo e bisogna ripassare tutto lo storico: senza
# tetto, duemila richieste di fila a un servizio gratuito.
MASSIMO_RECUPERI = 120
CARTELLA = Path(__file__).resolve().parents[2] / "dati" / "espn"

# I nostri slug verso quelli di ESPN. Le due serie minori scozzesi non ci sono:
# per quelle resta football-data, e va bene cosi'.
LEGHE = {
    "serie-a": "ita.1", "serie-b": "ita.2",
    "premier-league": "eng.1", "championship": "eng.2", "league-one": "eng.3",
    "league-two": "eng.4", "national-league": "eng.5",
    "laliga": "esp.1", "laliga-2": "esp.2",
    "bundesliga": "ger.1", "bundesliga-2": "ger.2",
    "ligue-1": "fra.1", "ligue-2": "fra.2",
    "eredivisie": "ned.1", "primeira-liga": "por.1", "superlig": "tur.1",
    "jupiler": "bel.1", "super-league-grecia": "gre.1",
    "premiership": "sco.1", "championship-scozia": "sco.2",
}

# Le irregolarita' che nessuna regola generale prende: sigle storiche, nomi
# accorciati da football-data in modi tutti suoi, citta' al posto del club.
ALIAS = {
    "internazionale": "Inter", "hellas verona": "Verona",
    "brighton hove albion": "Brighton", "manchester city": "Man City",
    "manchester united": "Man United", "nottingham forest": "Nott'm Forest",
    "preston north end": "Preston", "queens park rangers": "QPR",
    "west bromwich albion": "West Brom", "wolverhampton wanderers": "Wolves",
    "plymouth argyle": "Plymouth", "accrington stanley": "Accrington",
    "crewe alexandra": "Crewe", "kidderminster harriers": "Kidderminster",
    "solihull moors": "Solihull",
    "athletic club": "Ath Bilbao", "atletico madrid": "Ath Madrid",
    "celta vigo": "Celta", "deportivo": "La Coruna",
    "racing santander": "Santander", "rayo vallecano": "Vallecano",
    "rc celta fortuna": "Celta B", "sporting gijon": "Sp Gijon",
    "bayer leverkusen": "Leverkusen", "borussia monchengladbach": "M'gladbach",
    "eintracht frankfurt": "Ein Frankfurt", "fc cologne": "FC Koln",
    "1 fc heidenheim 1846": "Heidenheim", "arminia bielefeld": "Bielefeld",
    "dynamo dresden": "Dresden", "energie cottbus": "Cottbus",
    "hertha berlin": "Hertha", "tsv eintracht braunschweig": "Braunschweig",
    "paris saint germain": "Paris SG", "stade rennais": "Rennes",
    "as nancy lorraine": "Nancy", "clermont foot": "Clermont",
    "dijon fco": "Dijon", "rodez aveyron": "Rodez",
    "ajax amsterdam": "Ajax", "feyenoord rotterdam": "Feyenoord",
    "pec zwolle": "Zwolle",
    "sporting cp": "Sp Lisbon", "vitoria de guimaraes": "Guimaraes",
    "amed sfk": "Amedspor", "caykur rizespor": "Rizespor",
    "erzurum bb": "Erzurumspor", "istanbul basaksehir": "Buyuksehyr",
    "oh leuven": "Oud-Heverlee Leuven", "racing genk": "Genk",
    "sint truidense": "St Truiden", "standard liege": "Standard",
    "union st gilloise": "St. Gilloise", "waasland beveren": "Beveren",
    "zulte waregem": "Waregem",
    "aek athens": "AEK", "heart of midlothian": "Hearts",
    "greenock morton": "Morton", "inverness caledonian thistle": "Inverness C",
    "partick thistle": "Partick", "raith rovers": "Raith Rvs",
}

# Parole che descrivono il *tipo* di societa', non la sua identita'. Toglierle
# avvicina "Tottenham Hotspur" a "Tottenham" — ma attenzione: toglierle rende
# anche "Bristol City" e "Bristol Rovers" lo stesso nome, ed e' per questo che
# l'abbinamento accetta solo accoppiate univoche (vedi `abbina`).
ORPELLI = {
    "fc", "afc", "ac", "as", "us", "ss", "ssc", "sc", "cf", "cd", "rc", "sv",
    "tsg", "vfb", "vfl", "bsc", "fsv", "sg", "spvgg", "kv", "rsc", "kaa", "kvc",
    "fk", "sk", "ik", "bk", "if", "aik", "calcio", "club", "cp", "sad",
    "city", "united", "utd", "town", "rovers", "wanderers", "albion",
    "athletic", "county", "hotspur", "the", "and", "de", "real", "royal",
    "borussia", "stade", "olympique", "association", "sportive", "spor",
    "kulubu", "koninklijke",
}

# Le statistiche del riepilogo ESPN che teniamo, col nome che usiamo noi.
# Ne arrivano ventisette: queste sono quelle che dicono qualcosa a un lettore.
VOCI = {
    "totalShots": "tiri",
    "shotsOnTarget": "in_porta",
    "blockedShots": "tiri_respinti",
    "wonCorners": "corner",
    "foulsCommitted": "falli",
    "yellowCards": "gialli",
    "redCards": "rossi",
    "offsides": "fuorigioco",
    "saves": "parate",
    "possessionPct": "possesso",
    "totalPasses": "passaggi",
    "accuratePasses": "passaggi_riusciti",
    "totalCrosses": "cross",
    "accurateCrosses": "cross_riusciti",
    "totalTackles": "contrasti",
    "effectiveTackles": "contrasti_riusciti",
    "interceptions": "intercetti",
    "totalClearance": "respinte",
    "totalLongBalls": "lanci",
    "accurateLongBalls": "lanci_riusciti",
}


@dataclass
class PartitaEspn:
    """Una partita finita, coi suoi numeri, gia' coi nostri nomi di squadra."""

    id: str
    data: date
    casa: str
    ospite: str
    gol_casa: int
    gol_ospite: int
    # Per ogni voce di VOCI: (valore casa, valore ospite). Puo' essere vuoto:
    # ESPN da' il risultato subito e il riepilogo qualche minuto dopo.
    stat: dict[str, tuple[float, float]] = field(default_factory=dict)
    # La cronaca: chi ha segnato e quando, chi ha preso un cartellino, chi
    # scendeva in campo. Arriva dalla stessa richiesta del tabellino.
    gol: list[dict] = field(default_factory=list)
    cartellini: list[dict] = field(default_factory=list)
    formazioni: dict = field(default_factory=dict)

    @property
    def completa(self) -> bool:
        return bool(self.stat)


def _parole(nome: str) -> list[str]:
    n = unicodedata.normalize("NFKD", nome.lower())
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = n.replace("&", " ").replace("'", "")
    return re.sub(r"[^a-z0-9 ]", " ", n).split()


def _livelli(nome: str) -> list[str]:
    """Tre forme, dalla piu' fedele alla piu' aggressiva."""
    p = _parole(nome)
    senza = [w for w in p if w not in ORPELLI] or p
    return [" ".join(p), " ".join(senza), "".join(senza)]


def abbina(loro: list[str], nostri: list[str]) -> tuple[dict[str, str], list[str]]:
    """Accoppia i nomi ESPN ai nostri. Restituisce (accoppiati, non abbinati).

    La regola che tiene tutto in piedi: si accetta un'accoppiata solo quando e'
    **univoca da entrambi i lati**. Un nome ESPN che assomiglia a due dei nostri
    non viene abbinato per niente, e un nostro nome conteso resta libero.

    E' deliberatamente conservativo. Un abbinamento sbagliato non si nota — i
    gol finiscono nella squadra sbagliata e la classifica mente in silenzio —
    mentre uno mancato lo vediamo subito nel resoconto. Fra i due sbagli
    possibili, questo sceglie sempre quello rumoroso.
    """
    fatti: dict[str, str] = {}
    liberi_l, liberi_n = list(loro), list(nostri)

    # Prima gli alias scritti a mano: sono certezze, non indizi.
    for x in list(liberi_l):
        atteso = ALIAS.get(" ".join(_parole(x)))
        if atteso and atteso in liberi_n:
            fatti[x] = atteso
            liberi_l.remove(x)
            liberi_n.remove(atteso)

    for livello in range(3):
        kl: dict[str, list[str]] = {}
        for x in liberi_l:
            kl.setdefault(_livelli(x)[livello], []).append(x)
        kn: dict[str, list[str]] = {}
        for y in liberi_n:
            kn.setdefault(_livelli(y)[livello], []).append(y)
        for k, xs in kl.items():
            ys = kn.get(k, [])
            if len(xs) == 1 and len(ys) == 1:
                fatti[xs[0]] = ys[0]
        liberi_l = [x for x in liberi_l if x not in fatti]
        liberi_n = [y for y in liberi_n if y not in fatti.values()]

    # Ultimo giro, somiglianza alta: passa solo se un candidato solo la supera.
    for x in list(liberi_l):
        cand = [y for y in liberi_n
                if difflib.SequenceMatcher(None, _livelli(x)[2], _livelli(y)[2]).ratio() > 0.82]
        if len(cand) == 1:
            fatti[x] = cand[0]
            liberi_n.remove(cand[0])
            liberi_l.remove(x)

    return fatti, liberi_l


def _chiedi(url: str, tentativi: int = 3) -> dict | None:
    """Una richiesta, con tre tentativi. Restituisce None invece di sollevare.

    Volutamente non solleva: ESPN e' un di piu', non una dipendenza critica.
    Se cade, il resto della pipeline deve continuare con football-data.

    Due cose imparate sul campo, e nessuna delle due si indovina.

    La prima: **non si manda un User-Agent**. Mettercene uno — qualunque, anche
    quello di un browser — fa rispondere 403. Con quello predefinito di urllib
    la stessa richiesta passa. E' il contrario di quello che ci si aspetta e
    costa un pomeriggio, quindi resta scritto qui.

    La seconda: un 4xx non si ritenta. E' una risposta, non un inciampo: la
    seconda richiesta identica dara' lo stesso errore, e nel frattempo il
    lavoro notturno passa il tempo ad aspettare. Si ritenta solo cio' che
    puo' andare diversamente — rete caduta, timeout, risposta troncata.
    """
    for n in range(tentativi):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500:
                return None
            if n == tentativi - 1:
                return None
            time.sleep(1.5 * (n + 1))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            if n == tentativi - 1:
                return None
            time.sleep(1.5 * (n + 1))
    return None


def _numero(testo: str) -> float:
    try:
        return float(str(testo).replace("%", ""))
    except (TypeError, ValueError):
        return 0.0


def _gol_e_cartellini(d: dict) -> tuple[list[dict], list[dict]]:
    """Chi ha segnato e chi e' stato ammonito, col minuto.

    `keyEvents` racconta la partita evento per evento, e il testo e' gia'
    scritto in inglese per esteso — "Goal! Parma 0, Torino 1. Giovanni Simeone
    (Torino) left footed shot... Assisted by Rafik Belghali". A noi servono i
    pezzi, non la frase: marcatore, minuto, assist, squadra.
    """
    gol, cartellini = [], []
    for e in d.get("keyEvents") or []:
        tipo = ((e.get("type") or {}).get("text") or "")
        minuto = ((e.get("clock") or {}).get("displayValue") or "").strip()
        squadra = ((e.get("team") or {}).get("displayName") or "")
        gente = [
            (x.get("athlete") or {}).get("displayName")
            for x in (e.get("participants") or [])
        ]
        gente = [x for x in gente if x]
        if e.get("scoringPlay"):
            gol.append({
                "minuto": minuto,
                "squadra": squadra,
                "marcatore": gente[0] if gente else None,
                "assist": gente[1] if len(gente) > 1 else None,
                # "Goal - Penalty", "Own Goal", "Goal - Header": il dettaglio
                # sta nel tipo, e distinguere un autogol da un gol conta.
                "tipo": tipo,
            })
        elif "Card" in tipo:
            cartellini.append({
                "minuto": minuto,
                "squadra": squadra,
                "giocatore": gente[0] if gente else None,
                "rosso": "Red" in tipo,
            })
    return gol, cartellini


def _formazioni(d: dict) -> dict:
    """Titolari, panchina e cambi, per lato.

    ESPN li da' gia' con numero di maglia, ruolo e chi e' entrato per chi: e'
    tutto nella stessa risposta del tabellino, che scarichiamo da settembre e
    di cui finora tenevamo solo le statistiche di squadra.
    """
    fuori: dict[str, dict] = {}
    for t in d.get("rosters") or []:
        lato = t.get("homeAway")
        if lato not in ("home", "away"):
            continue
        giocatori = []
        for g in t.get("roster") or []:
            a = g.get("athlete") or {}
            if not a.get("displayName"):
                continue
            giocatori.append({
                "nome": a.get("displayName"),
                "maglia": g.get("jersey"),
                "ruolo": (g.get("position") or {}).get("abbreviation"),
                "titolare": bool(g.get("starter")),
                "entrato": bool(g.get("subbedIn")),
                "uscito": bool(g.get("subbedOut")),
            })
        if giocatori:
            fuori[lato] = {
                "squadra": (t.get("team") or {}).get("displayName"),
                "modulo": t.get("formation"),
                "giocatori": giocatori,
            }
    return fuori


def dettaglio(lega_espn: str, id_evento: str) -> dict:
    """Tutto quello che ESPN sa di una partita, in **una** richiesta.

    Prima si chiedeva la stessa pagina e si teneva solo il tabellino, buttando
    via gol, cartellini e formazioni che erano li' dentro. Separarli in piu'
    richieste sarebbe stato tre volte il traffico per gli stessi dati.
    """
    d = _chiedi(f"{BASE}/{lega_espn}/summary?event={id_evento}")
    if not d:
        return {"stat": {}, "gol": [], "cartellini": [], "formazioni": {}}
    gol, cartellini = _gol_e_cartellini(d)
    return {
        "stat": _statistiche(d),
        "gol": gol,
        "cartellini": cartellini,
        "formazioni": _formazioni(d),
    }


def _statistiche(d: dict) -> dict[str, tuple[float, float]]:
    """Le statistiche di squadra. Dizionario vuoto se ESPN non le ha."""
    squadre = d.get("boxscore", {}).get("teams", [])
    if len(squadre) != 2:
        return {}
    # L'ordine in boxscore non e' garantito: si legge da homeAway.
    per_lato: dict[str, dict[str, float]] = {}
    for s in squadre:
        lato = s.get("homeAway") or ("home" if not per_lato else "away")
        per_lato[lato] = {v.get("name"): _numero(v.get("displayValue"))
                          for v in s.get("statistics", [])}
    if "home" not in per_lato or "away" not in per_lato:
        return {}
    fuori = {}
    for chiave, nome in VOCI.items():
        c, o = per_lato["home"].get(chiave), per_lato["away"].get(chiave)
        if c is not None and o is not None:
            fuori[nome] = (c, o)
    return fuori


def _mesi(da: date, a: date) -> list[str]:
    """I mesi da interrogare, nel formato che ESPN accetta: `YYYYMM`.

    Qui c'erano gli intervalli `YYYYMMDD-YYYYMMDD`, e hanno funzionato fino a
    meta' settembre 2026. Poi ESPN ha smesso di accettarli: ogni intervallo
    risponde `400 Bad Request`, mentre la singola data continua a funzionare.
    Nessun annuncio, ovviamente — e' l'endpoint che alimenta il loro sito, non
    un'API con un contratto, ed era scritto nel commento in testa al modulo che
    poteva cambiare forma senza preavviso.

    L'effetto era subdolo: `_chiedi` non ritenta i 4xx e restituisce None, come
    deve, quindi niente si rompeva — semplicemente non arrivava piu' nessun
    risultato nuovo, in silenzio, mentre il sito continuava a pubblicare.

    Il mese e' anche meglio di prima: una richiesta copre trenta giorni dove
    gli intervalli ne coprivano dieci.
    """
    fuori, anno, mese = [], da.year, da.month
    while (anno, mese) <= (a.year, a.month):
        fuori.append(f"{anno}{mese:02d}")
        anno, mese = (anno + 1, 1) if mese == 12 else (anno, mese + 1)
    return fuori


def partite_finite(lega_espn: str, da: date, a: date) -> list[dict]:
    """Le partite concluse nell'intervallo, coi nomi ancora quelli di ESPN."""
    fuori = []
    dal, al = da.isoformat(), a.isoformat()
    for mese in _mesi(da, a):
        d = _chiedi(f"{BASE}/{lega_espn}/scoreboard?dates={mese}")
        if not d:
            continue
        for e in d.get("events", []):
            gare = e.get("competitions") or []
            if not gare:
                continue
            # Il mese restituisce tutto il mese: si tiene solo la finestra
            # chiesta, altrimenti si raccolgono partite fuori stagione.
            if not (dal <= e.get("date", "")[:10] <= al):
                continue
            g = gare[0]
            if g.get("status", {}).get("type", {}).get("name") != "STATUS_FULL_TIME":
                continue
            lati = {c.get("homeAway"): c for c in g.get("competitors", [])}
            if "home" not in lati or "away" not in lati:
                continue
            try:
                fuori.append({
                    "id": str(e["id"]),
                    "data": e["date"][:10],
                    "casa": lati["home"]["team"]["displayName"],
                    "ospite": lati["away"]["team"]["displayName"],
                    "gol_casa": int(lati["home"]["score"]),
                    "gol_ospite": int(lati["away"]["score"]),
                })
            except (KeyError, TypeError, ValueError):
                continue
    return fuori


def _americana(valore) -> float | None:
    """Da quota americana a decimale. +150 -> 2.50, -200 -> 1.50."""
    if valore in (None, ""):
        return None
    try:
        v = float(str(valore).replace("+", ""))
    except ValueError:
        return None
    if v == 0:
        return None
    return round(1 + (v / 100 if v > 0 else 100 / abs(v)), 3)


def _quote_1x2(gara: dict) -> tuple[float, float, float] | None:
    """Le quote 1-X-2, se ESPN le espone, gia' in decimale.

    Stanno in tre posti diversi della stessa struttura — casa e trasferta sotto
    `moneyline`, il pareggio sotto `drawOdds` — e in formato americano, perche'
    l'endpoint e' quello del sito americano di ESPN.

    **Non sono un confronto fra operatori**: vengono da un solo bookmaker. Non
    sostituiscono quelle di football-data, che ne porta otto e permette di
    calcolare quanto si tiene il banco davvero; servono quando football-data e'
    indietro, che e' spesso, e il sito altrimenti non puo' dire niente sul
    mercato. Chi legge deve saperlo, e infatti la pagina lo scrive.
    """
    o = (gara.get("odds") or [None])[0]
    if not o:
        return None
    ml = o.get("moneyline") or {}
    def lato(nome):
        v = (ml.get(nome) or {})
        chiuso = (v.get("close") or v.get("open") or {})
        return _americana(chiuso.get("odds"))
    casa, ospite = lato("home"), lato("away")
    pari = _americana((o.get("drawOdds") or {}).get("moneyLine"))
    if not (casa and pari and ospite):
        return None
    return (casa, pari, ospite)


def partite_in_programma(lega_espn: str, da: date, a: date) -> list[dict]:
    """Le partite ancora da giocare, coi nomi ancora quelli di ESPN.

    Serve perche' `fixtures.csv` di football-data copre una finestra corta —
    pochi giorni — e la aggiorna quando gli pare. Il 1 settembre conteneva una
    partita sola in tutti e ventidue i campionati: un sito che dice "1 partita
    in programma" sembra spento, e lo sembra proprio mentre funziona.

    Da ESPN si prende **solo il calendario**: giorno, ora, squadre. Le quote no,
    anche se ci sono: arrivano da un operatore con tanto di link al suo sito, e
    questo sito si regge sul non averne. Le quote restano football-data.
    """
    fuori = []
    dal, al = da.isoformat(), a.isoformat()
    for mese in _mesi(da, a):
        d = _chiedi(f"{BASE}/{lega_espn}/scoreboard?dates={mese}")
        if not d:
            continue
        for e in d.get("events", []):
            gare = e.get("competitions") or []
            if not gare:
                continue
            if not (dal <= e.get("date", "")[:10] <= al):
                continue
            g = gare[0]
            if g.get("status", {}).get("type", {}).get("name") != "STATUS_SCHEDULED":
                continue
            lati = {c.get("homeAway"): c for c in g.get("competitors", [])}
            if "home" not in lati or "away" not in lati:
                continue
            try:
                quando = e["date"]          # "2026-09-04T18:45Z", sempre in UTC
                fuori.append({
                    "id": str(e["id"]),
                    "data": quando[:10],
                    "ora": quando[11:16],
                    "casa": lati["home"]["team"]["displayName"],
                    "ospite": lati["away"]["team"]["displayName"],
                    "quote": _quote_1x2(g),
                })
            except (KeyError, TypeError):
                continue
    return fuori


def in_programma(slug: str, squadre_nostre: list[str], da: date, a: date) -> list[dict]:
    """Le prossime partite di un campionato, gia' coi nostri nomi e in ora italiana.

    Restituisce dizionari e non `PartitaFutura` per non far dipendere questo
    modulo da football_data: chi chiama sa cosa costruirci.
    """
    lega = LEGHE.get(slug)
    if not lega:
        return []

    grezze = partite_in_programma(lega, da, a)
    if not grezze:
        return []

    loro = sorted({p["casa"] for p in grezze} | {p["ospite"] for p in grezze})
    mappa, _ = abbina(loro, squadre_nostre)

    fuori = []
    for p in grezze:
        casa, ospite = mappa.get(p["casa"]), mappa.get(p["ospite"])
        if not casa or not ospite:
            continue
        quando = datetime(
            *(int(x) for x in p["data"].split("-")),
            int(p["ora"][:2]), int(p["ora"][3:5]), tzinfo=UTC,
        ).astimezone(ROMA)
        fuori.append({"data": quando.date(), "ora": quando.strftime("%H:%M"),
                      "casa": casa, "ospite": ospite, "quote": p.get("quote")})
    return fuori


def _archivio(slug: str) -> Path:
    return CARTELLA / f"{slug}.json"


def carica_archivio(slug: str) -> dict[str, dict]:
    p = _archivio(slug)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def salva_archivio(slug: str, dati: dict[str, dict]) -> None:
    CARTELLA.mkdir(parents=True, exist_ok=True)
    _archivio(slug).write_text(
        json.dumps(dati, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def aggiorna(slug: str, squadre_nostre: list[str], da: date, a: date,
             verboso: bool = True) -> tuple[list[PartitaEspn], list[str]]:
    """Scarica il nuovo, riusa il vecchio, e restituisce (partite, non abbinati).

    L'archivio su disco non e' una furbizia: il tabellino costa una richiesta a
    partita, e senza memoria il lavoro notturno riscaricherebbe tutta la
    stagione ogni volta. Committandolo nel repo sopravvive anche al fatto che
    la macchina di GitHub Actions nasce e muore ogni notte.
    """
    lega = LEGHE.get(slug)
    if not lega:
        return [], [], {}

    archivio = carica_archivio(slug)
    grezze = partite_finite(lega, da, a)
    if not grezze:
        grezze = []

    # I nomi si abbinano una volta sola, sull'insieme di tutte le squadre viste.
    loro = sorted({p["casa"] for p in grezze} | {p["ospite"] for p in grezze})
    mappa, non_abbinati = abbina(loro, squadre_nostre)

    nuove = recuperi = 0
    for p in grezze:
        gia = archivio.get(p["id"]) or {}
        # Si riscarica se manca il tabellino **oppure** se manca la parte nuova
        # — gol, cartellini, formazioni — che prima non salvavamo. Cosi' il
        # recupero dello storico avviene da solo, senza uno script a parte.
        completo = gia.get("stat") and "formazioni" in gia
        if completo:
            continue
        if recuperi >= MASSIMO_RECUPERI:
            # Lo storico si recupera in piu' notti invece che in una sola: duemila
            # richieste di fila a un servizio che ci regala i dati sono maleducazione,
            # e un turno che dura mezz'ora e' un turno che prima o poi viene ucciso.
            break
        d = dettaglio(lega, p["id"])
        archivio[p["id"]] = {
            **p,
            "stat": {k: list(v) for k, v in d["stat"].items()},
            "gol": d["gol"],
            "cartellini": d["cartellini"],
            "formazioni": d["formazioni"],
        }
        nuove += 1
        recuperi += 1
        time.sleep(0.15)          # gentilezza verso un endpoint che ci regala i dati

    if nuove:
        salva_archivio(slug, archivio)
    if verboso and non_abbinati:
        print(f"      nomi ESPN non abbinati: {', '.join(non_abbinati)}")

    fuori = []
    for id_evento, p in archivio.items():
        casa, ospite = mappa.get(p["casa"]), mappa.get(p["ospite"])
        if not casa or not ospite:
            continue          # meglio saltare che attribuire i gol alla squadra sbagliata
        fuori.append(PartitaEspn(
            id=id_evento,
            data=date.fromisoformat(p["data"]),
            casa=casa, ospite=ospite,
            gol_casa=p["gol_casa"], gol_ospite=p["gol_ospite"],
            stat={k: tuple(v) for k, v in (p.get("stat") or {}).items()},
            gol=p.get("gol") or [],
            cartellini=p.get("cartellini") or [],
            formazioni=p.get("formazioni") or {},
        ))
    fuori.sort(key=lambda x: x.data)
    # `mappa` va da ESPN ai nostri nomi; qui serve il contrario. Il nome esteso
    # di ESPN — "AFC Bournemouth", "Internazionale" — e' quello con cui la gente
    # cerca davvero su Google, mentre noi pubblichiamo la forma corta di
    # football-data. Non lo mettiamo in pagina: finisce nei dati strutturati
    # come nome alternativo, che e' esattamente il posto giusto.
    estesi = {nostro: espn for espn, nostro in mappa.items() if espn != nostro}
    return fuori, non_abbinati, estesi
