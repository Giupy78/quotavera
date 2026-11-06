"""Le coppe europee: Champions, Europa e Conference League.

Per mesi questo progetto ha scritto che le coppe richiedevano una fonte a
pagamento. Era vero quando l'unica fonte era football-data, e ha smesso di
esserlo il giorno in cui e' entrato ESPN, ma la frase e' rimasta. L'endpoint
gratuito da' risultati, 28 statistiche per squadra, formazioni, gol e cartellini,
stadio, le quote di un operatore e la classifica.

Quello che **non** c'e', e la pagina lo dice: il confronto fra operatori, perche'
football-data non copre le coppe, e le probabilita', perche' il modello stima un
campionato alla volta e non sa confrontare squadre di paesi diversi.

Tre scelte che vale la pena conoscere.

**Le squadre si riconoscono dal codice ESPN, non dal nome.** Nelle coppe giocano
squadre di tutta Europa, e abbinare per somiglianza contro i nostri ventidue
campionati e' un invito all'errore: "AEK Larnaca" assomiglia al nostro "AEK",
"Red Star Belgrade" al nostro "Red Star" francese. L'abbinamento per nome si fa
una volta sola, campionato per campionato dove e' sicuro, e il risultato e' una
tabella codice -> nostra squadra. Una squadra che non e' li' dentro non e' un
errore: e' una squadra che non seguiamo in campionato.

**L'archivio non perde mai niente.** Una partita che esce dal calendario di ESPN,
perche' rinviata o perche' l'endpoint ha cambiato idea, resta nell'archivio, e la
sua pagina resta in piedi. Una partita finita non torna indietro. Se ESPN e' giu'
il sito si costruisce con quello che c'e'.

**Ogni indirizzo si assegna una volta sola** e si scrive nell'archivio. Non si
ricalcola a ogni giro: se un giorno cambia il nome con cui mostriamo una squadra,
la pagina resta dov'e'. E' la lezione dei 404 di ottobre.

Le coppe restano fuori dalle statistiche di campionato: sono altre partite,
contro altri avversari, e mescolarle sporcherebbe le medie delle pagine squadra.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from engine.dati import espn

CARTELLA = Path(__file__).resolve().parents[2] / "dati" / "coppe"

# Il primo giro scarica una stagione intera, quelli dopo solo le partite nuove.
MASSIMO_RECUPERI = 300

# La tabella codice ESPN -> nostra squadra si rifa' ogni tanto: le squadre di un
# campionato non cambiano durante la stagione, e sono venti richieste.
GIORNI_VALIDITA_SQUADRE = 7

STANDINGS = "https://site.api.espn.com/apis/v2/sports/soccer"


@dataclass(frozen=True, slots=True)
class Coppa:
    slug: str
    espn: str
    nome: str


COPPE = [
    Coppa("champions-league", "uefa.champions", "Champions League"),
    Coppa("europa-league", "uefa.europa", "Europa League"),
    Coppa("conference-league", "uefa.europa.conf", "Conference League"),
]

# I nomi delle fasi come li scrive ESPN. Quelli che non conosciamo restano senza
# etichetta: meglio niente che una parola inglese in mezzo alla pagina.
FASI = {
    "league-phase": "Fase a girone unico",
    "knockout-round-playoffs": "Spareggi",
    "playoffs": "Spareggi",
    "round-of-16": "Ottavi di finale",
    "rd-of-16": "Ottavi di finale",
    "quarterfinals": "Quarti di finale",
    "semifinals": "Semifinali",
    "final": "Finale",
}

# Le statistiche che finiscono nelle medie di squadra.
VOCI_MEDIE = ("tiri", "in_porta", "corner", "falli", "gialli", "rossi",
              "possesso", "passaggi", "parate")


def lumaca(nome: str) -> str:
    """La stessa regola di `lumacaSquadra` nel sito: "Man City" -> "man-city"."""
    n = unicodedata.normalize("NFKD", nome)
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = n.lower().replace("'", "").replace(".", "")
    return re.sub(r"[^a-z0-9]+", "-", n).strip("-")


# --- lettura delle risposte di ESPN --------------------------------------

def leggi_evento(e: dict) -> dict | None:
    """Una partita dal calendario. None se manca qualcosa di essenziale."""
    gare = e.get("competitions") or []
    if not gare:
        return None
    g = gare[0]
    lati = {c.get("homeAway"): c for c in g.get("competitors", [])}
    if "home" not in lati or "away" not in lati:
        return None

    tipo = (g.get("status") or {}).get("type") or {}
    nome_stato = (tipo.get("name") or "").upper()
    # `completed` e non STATUS_FULL_TIME: nelle fasi a eliminazione esistono
    # anche i supplementari e i rigori, che hanno un altro stato.
    if any(x in nome_stato for x in ("POSTPON", "CANCEL", "ABANDON", "SUSPEND")):
        stato = "rinviata"
    elif tipo.get("completed"):
        stato = "finita"
    else:
        stato = "in_programma"

    try:
        # ESPN scrive sempre in UTC; la pagina parla all'ora italiana.
        quando = datetime.fromisoformat(e["date"].replace("Z", "+00:00")).astimezone(espn.ROMA)
        fuori = {
            "id": str(e["id"]),
            "data": quando.date().isoformat(),
            "ora": quando.strftime("%H:%M"),
            "stato": stato,
            "fase": (e.get("season") or {}).get("slug") or "",
            "casa_id": str(lati["home"]["team"]["id"]),
            "ospite_id": str(lati["away"]["team"]["id"]),
            "casa_espn": lati["home"]["team"]["displayName"],
            "ospite_espn": lati["away"]["team"]["displayName"],
            "stadio": espn._stadio(g),
            "quote": espn._quote_1x2(g),
        }
        if stato == "finita":
            fuori["gol_casa"] = int(lati["home"]["score"])
            fuori["gol_ospite"] = int(lati["away"]["score"])
            rigori = [lati[x].get("shootoutScore") for x in ("home", "away")]
            if all(r is not None for r in rigori):
                fuori["rigori"] = [int(r) for r in rigori]
    except (KeyError, TypeError, ValueError):
        return None
    return fuori


def leggi_classifica(d: dict) -> list[dict]:
    """La classifica, una riga per squadra. Vuota se la risposta non la contiene."""
    def intero(v) -> int:
        try:
            return int(str(v).replace("+", ""))
        except (TypeError, ValueError):
            return 0

    righe = []
    for gruppo in d.get("children") or []:
        for r in (gruppo.get("standings") or {}).get("entries") or []:
            s = {x.get("name"): x.get("displayValue") for x in r.get("stats") or []}
            t = r.get("team") or {}
            if not t.get("id"):
                continue
            righe.append({
                "squadra_id": str(t["id"]),
                "squadra_espn": t.get("displayName"),
                "posizione": intero(s.get("rank")),
                "giocate": intero(s.get("gamesPlayed")),
                "vinte": intero(s.get("wins")),
                "pareggiate": intero(s.get("ties")),
                "perse": intero(s.get("losses")),
                "fatti": intero(s.get("pointsFor")),
                "subiti": intero(s.get("pointsAgainst")),
                "differenza": intero(s.get("pointDifferential")),
                "punti": intero(s.get("points")),
            })
    return sorted(righe, key=lambda r: r["posizione"] or 999)


# --- l'archivio -----------------------------------------------------------

def fondi(partite: dict[str, dict], eventi: list[dict]) -> dict[str, dict]:
    """Le notizie di oggi sopra quello che sappiamo gia'.

    Una partita finita non torna indietro; quote e stadio non si cancellano
    perche' una risposta non li riporta; una partita assente dagli eventi di
    oggi resta dov'e'.
    """
    fuori = dict(partite)
    for ev in eventi:
        vecchio = fuori.get(ev["id"])
        if vecchio and vecchio.get("stato") == "finita" and ev["stato"] != "finita":
            continue
        nuovo = {**(vecchio or {}), **ev}
        if vecchio:
            for campo in ("quote", "stadio"):
                if not ev.get(campo) and vecchio.get(campo):
                    nuovo[campo] = vecchio[campo]
        fuori[ev["id"]] = nuovo
    return fuori


def da_completare(partite: dict[str, dict]) -> list[str]:
    """Le partite finite di cui non abbiamo ancora il tabellino, dalla piu' vecchia."""
    mancano = [p for p in partite.values() if p.get("stato") == "finita" and not p.get("stat")]
    return [p["id"] for p in sorted(mancano, key=lambda p: (p["data"], p["ora"], p["id"]))]


def assegna_indirizzi(archivio: dict, mappa: dict[str, dict]) -> None:
    """Dà un indirizzo a chi non ce l'ha ancora. Chi ce l'ha lo tiene per sempre.

    Due partite con la stessa squadra in casa e lo stesso avversario possono
    capitare nella stessa stagione, una nel girone e una a eliminazione: la
    seconda prende la data in coda. Si procede in ordine di data, quindi la
    prima, gia' indicizzata, non cambia mai indirizzo.
    """
    squadre: dict[str, str] = archivio.setdefault("indirizzi_squadre", {})
    usati = set(squadre.values())

    def indirizzo_squadra(sid: str, nome_espn: str) -> str:
        if sid not in squadre:
            base = lumaca(mappa.get(sid, {}).get("nome") or nome_espn)
            scelto = base if base not in usati else f"{base}-{sid}"
            squadre[sid] = scelto
            usati.add(scelto)
        return squadre[sid]

    presi = {p["pagina"] for p in archivio["partite"].values() if p.get("pagina")}
    in_ordine = sorted(archivio["partite"].values(), key=lambda p: (p["data"], p["ora"], p["id"]))
    for p in in_ordine:
        a = indirizzo_squadra(p["casa_id"], p["casa_espn"])
        b = indirizzo_squadra(p["ospite_id"], p["ospite_espn"])
        if p.get("pagina"):
            continue
        base = f"{a}-{b}"
        scelto = base if base not in presi else f"{base}-{p['data']}"
        p["pagina"] = scelto
        presi.add(scelto)


def _file(coppa: Coppa, anno: int) -> Path:
    return CARTELLA / f"{coppa.slug}-{anno}.json"


def carica_archivio(coppa: Coppa, anno: int) -> dict:
    f = _file(coppa, anno)
    if f.exists():
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            d.setdefault("partite", {})
            d.setdefault("classifica", [])
            return d
        except json.JSONDecodeError:
            pass
    return {"partite": {}, "classifica": []}


def salva_archivio(coppa: Coppa, anno: int, dati: dict) -> None:
    CARTELLA.mkdir(parents=True, exist_ok=True)
    _file(coppa, anno).write_text(
        json.dumps(dati, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# --- la tabella codice ESPN -> nostra squadra --------------------------------

def mappa_squadre(nomi_per_lega: dict[str, list[str]], oggi: date) -> dict[str, dict]:
    """Codice ESPN -> {nome, campionato}, per le squadre che seguiamo.

    L'abbinamento per nome si fa dentro un campionato alla volta, dove e' sicuro:
    `abbina` accetta solo le accoppiate univoche da entrambi i lati. Se ESPN non
    risponde per un campionato, per quel campionato si tiene la tabella vecchia.
    """
    f = CARTELLA / "squadre.json"
    vecchia: dict = {}
    if f.exists():
        try:
            vecchia = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            vecchia = {}
    quando = vecchia.get("generato_il")
    if quando and (oggi - date.fromisoformat(quando)).days < GIORNI_VALIDITA_SQUADRE:
        return vecchia.get("squadre", {})

    gia = vecchia.get("squadre", {})
    nuova: dict[str, dict] = {}
    for slug, nostri in nomi_per_lega.items():
        codice = espn.LEGHE.get(slug)
        if not codice or not nostri:
            continue
        d = espn._chiedi(f"{espn.BASE}/{codice}/teams?limit=100")
        try:
            elenco = [t["team"] for t in d["sports"][0]["leagues"][0]["teams"]]
        except (TypeError, KeyError, IndexError):
            nuova.update({k: v for k, v in gia.items() if v.get("campionato") == slug})
            continue
        fatti, _ = espn.abbina([t["displayName"] for t in elenco], nostri)
        for t in elenco:
            if t["displayName"] in fatti:
                nuova[str(t["id"])] = {"nome": fatti[t["displayName"]], "campionato": slug}

    CARTELLA.mkdir(parents=True, exist_ok=True)
    f.write_text(
        json.dumps({"generato_il": oggi.isoformat(), "squadre": nuova},
                   ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return nuova


# --- dai dati alla pagina --------------------------------------------------

def _intero_se_puoi(v):
    return int(v) if float(v).is_integer() else v


def statistiche_pagina(stat: dict | None) -> dict | None:
    """Il tabellino nella forma che usa la scheda di una partita giocata."""
    if not stat:
        return None
    fuori = {}
    for voce in VOCI_MEDIE:
        if voce in stat:
            fuori[voce] = [_intero_se_puoi(x) for x in stat[voce]]
    return fuori


def medie_squadre(partite: list[dict]) -> tuple[dict[str, dict], dict]:
    """Le medie a partita di ogni squadra, e quelle dell'intera coppa.

    Sempre totale diviso totale, e ogni voce con il suo denominatore: una partita
    senza tabellino conta per i gol ma non per i tiri.
    """
    grezzi: dict[str, dict] = {}

    def lato(sid: str, p: dict, indice: int) -> None:
        g = grezzi.setdefault(sid, {
            "partite": 0, "vinte": 0, "pareggiate": 0, "perse": 0,
            "gol_fatti": 0, "gol_subiti": 0, "con_tabellino": 0,
            "somme": {}, "quante": {}, "somme_subiti": {},
        })
        fatti = p["gol_casa"] if indice == 0 else p["gol_ospite"]
        subiti = p["gol_ospite"] if indice == 0 else p["gol_casa"]
        g["partite"] += 1
        g["gol_fatti"] += fatti
        g["gol_subiti"] += subiti
        g["vinte" if fatti > subiti else "perse" if fatti < subiti else "pareggiate"] += 1
        stat = p.get("stat") or {}
        if stat:
            g["con_tabellino"] += 1
        for voce in VOCI_MEDIE:
            if voce in stat:
                g["somme"][voce] = g["somme"].get(voce, 0) + stat[voce][indice]
                g["somme_subiti"][voce] = g["somme_subiti"].get(voce, 0) + stat[voce][1 - indice]
                g["quante"][voce] = g["quante"].get(voce, 0) + 1

    for p in partite:
        if p.get("stato") != "finita":
            continue
        lato(p["casa_id"], p, 0)
        lato(p["ospite_id"], p, 1)

    fuori: dict[str, dict] = {}
    for sid, g in grezzi.items():
        medie = {
            "gol_fatti": round(g["gol_fatti"] / g["partite"], 3),
            "gol_subiti": round(g["gol_subiti"] / g["partite"], 3),
        }
        for voce, n in g["quante"].items():
            medie[voce] = round(g["somme"][voce] / n, 3)
        for voce in ("tiri", "in_porta", "corner"):
            if voce in g["quante"]:
                medie[f"{voce}_subiti"] = round(g["somme_subiti"][voce] / g["quante"][voce], 3)
        fuori[sid] = {
            k: g[k] for k in ("partite", "vinte", "pareggiate", "perse",
                              "gol_fatti", "gol_subiti", "con_tabellino")
        } | {"medie": medie}

    # La media della coppa: il totale di tutte le squadre diviso le loro presenze.
    presenze = sum(g["partite"] for g in grezzi.values())
    coppa: dict = {}
    if presenze:
        coppa["gol_fatti"] = round(sum(g["gol_fatti"] for g in grezzi.values()) / presenze, 3)
        coppa["gol_subiti"] = coppa["gol_fatti"]
        for voce in VOCI_MEDIE:
            quante = sum(g["quante"].get(voce, 0) for g in grezzi.values())
            if quante:
                coppa[voce] = round(sum(g["somme"].get(voce, 0) for g in grezzi.values()) / quante, 3)
                if voce in ("tiri", "in_porta", "corner"):
                    coppa[f"{voce}_subiti"] = coppa[voce]
    return fuori, coppa


def per_il_sito(coppa: Coppa, archivio: dict, mappa: dict[str, dict], anno: int, oggi: date) -> dict:
    """Quello che serve alle pagine di una coppa."""
    partite = sorted(archivio["partite"].values(), key=lambda p: (p["data"], p["ora"], p["id"]))
    indirizzi = archivio.get("indirizzi_squadre", {})
    ieri = (oggi - timedelta(days=1)).isoformat()

    def nome(sid: str, espn_nome: str) -> str:
        return mappa.get(sid, {}).get("nome") or espn_nome

    nomi_espn: dict[str, str] = {}
    for p in partite:
        nomi_espn[p["casa_id"]] = p["casa_espn"]
        nomi_espn[p["ospite_id"]] = p["ospite_espn"]
    for r in archivio.get("classifica", []):
        nomi_espn.setdefault(r["squadra_id"], r.get("squadra_espn") or "")

    medie, media_coppa = medie_squadre(partite)
    posizioni = {r["squadra_id"]: r for r in archivio.get("classifica", [])}

    squadre = []
    for sid, espn_nome in nomi_espn.items():
        if sid not in indirizzi:
            continue
        n = nome(sid, espn_nome)
        r = posizioni.get(sid) or {}
        squadre.append({
            "id": indirizzi[sid],
            "espn_id": sid,
            "nome": n,
            "esteso": espn_nome if espn_nome != n else None,
            "campionato": mappa.get(sid, {}).get("campionato"),
            "posizione": r.get("posizione"),
            "punti": r.get("punti"),
            **(medie.get(sid) or {"partite": 0, "vinte": 0, "pareggiate": 0, "perse": 0,
                                  "gol_fatti": 0, "gol_subiti": 0, "con_tabellino": 0, "medie": {}}),
        })
    squadre.sort(key=lambda s: (s["posizione"] or 999, s["nome"]))

    righe = []
    for p in partite:
        giocata = p["stato"] == "finita"
        righe.append({
            "id": p["pagina"],
            "coppa": coppa.slug,
            "casa": nome(p["casa_id"], p["casa_espn"]),
            "ospite": nome(p["ospite_id"], p["ospite_espn"]),
            "casa_esteso": p["casa_espn"],
            "ospite_esteso": p["ospite_espn"],
            "casa_slug": indirizzi.get(p["casa_id"]),
            "ospite_slug": indirizzi.get(p["ospite_id"]),
            "data": p["data"],
            "ora": p["ora"],
            "fase": FASI.get(p.get("fase", ""), ""),
            "giocata": giocata,
            "rinviata": p["stato"] == "rinviata",
            "senza_risultato": p["stato"] == "in_programma" and p["data"] < ieri,
            "gol_casa": p.get("gol_casa"),
            "gol_ospite": p.get("gol_ospite"),
            "rigori": p.get("rigori"),
            "stadio": p.get("stadio"),
            "quote": p.get("quote") if not giocata else None,
            "statistiche": statistiche_pagina(p.get("stat")),
            "gol": p.get("gol") or [],
            "cartellini": p.get("cartellini") or [],
            "formazioni": p.get("formazioni") or {},
        })

    classifica = [
        {**r, "squadra": nome(r["squadra_id"], r.get("squadra_espn") or ""),
         "id": indirizzi.get(r["squadra_id"])}
        for r in archivio.get("classifica", [])
    ]
    giocate = [r for r in righe if r["giocata"]]
    return {
        "slug": coppa.slug,
        "nome": coppa.nome,
        "stagione": f"{anno}/{(anno + 1) % 100:02d}",
        "partite_giocate": len(giocate),
        "partite_totali": len(righe),
        "gol_a_partita": (round(sum(r["gol_casa"] + r["gol_ospite"] for r in giocate) / len(giocate), 3)
                          if giocate else None),
        "media": media_coppa,
        "classifica": classifica,
        "squadre": squadre,
        "partite": righe,
    }


# --- il giro completo --------------------------------------------------------

def _scarica(coppa: Coppa, anno: int, oggi: date, primo_giro: bool) -> list[dict]:
    """Il calendario. Al primo giro l'intera stagione, poi solo i mesi vicini:
    le partite lontane non cambiano, e sono richieste risparmiate ogni notte."""
    inizio, fine = date(anno, 7, 1), date(anno + 1, 6, 30)
    da = inizio if primo_giro else max(inizio, oggi - timedelta(days=35))
    a = fine if primo_giro else min(fine, oggi + timedelta(days=70))
    eventi: list[dict] = []
    for mese in espn._mesi(da, a):
        d = espn._chiedi(f"{espn.BASE}/{coppa.espn}/scoreboard?dates={mese}&limit=300")
        for e in (d or {}).get("events", []):
            letto = leggi_evento(e)
            if letto:
                eventi.append(letto)
    return eventi


def aggiorna_coppa(coppa: Coppa, anno: int, mappa: dict[str, dict], oggi: date) -> dict:
    """Scarica, fonde, completa i tabellini e salva. Restituisce i dati per il sito."""
    archivio = carica_archivio(coppa, anno)
    eventi = _scarica(coppa, anno, oggi, primo_giro=not archivio["partite"])
    archivio["partite"] = fondi(archivio["partite"], eventi)

    for pid in da_completare(archivio["partite"])[:MASSIMO_RECUPERI]:
        det = espn.dettaglio(coppa.espn, pid)
        if det.get("stat"):
            archivio["partite"][pid].update({
                "stat": {k: list(v) for k, v in det["stat"].items()},
                "gol": det["gol"],
                "cartellini": det["cartellini"],
                "formazioni": det["formazioni"],
            })

    d = espn._chiedi(f"{STANDINGS}/{coppa.espn}/standings")
    classifica = leggi_classifica(d) if d else []
    # Una risposta vuota non cancella la classifica che avevamo.
    if classifica:
        archivio["classifica"] = classifica

    assegna_indirizzi(archivio, mappa)
    salva_archivio(coppa, anno, archivio)
    return per_il_sito(coppa, archivio, mappa, anno, oggi)


def aggiorna_tutte(nomi_per_lega: dict[str, list[str]], anno: int, oggi: date | None = None) -> dict:
    oggi = oggi or date.today()
    mappa = mappa_squadre(nomi_per_lega, oggi)
    return {
        "generato_il": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "coppe": [aggiorna_coppa(c, anno, mappa, oggi) for c in COPPE],
    }
