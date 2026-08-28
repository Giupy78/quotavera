"""Lettore dei calendari di openfootball.

football-data.co.uk pubblica solo una settimana di partite future: per il
calendario completo della stagione serve un'altra fonte. openfootball la
pubblica su GitHub, gratis, in un formato di testo pensato per essere letto da
una persona — e con una cosa che a noi manca: **il numero di giornata scritto
esplicitamente**, invece che dedotto.

    ▪ Matchday 2
      Fri Aug 28
        20:45  AC Milan                v Venezia FC
      Sat Aug 29
        18:30  US Sassuolo Calcio      v Torino FC
               AC Monza                v Udinese Calcio

Due dettagli del formato che vanno gestiti e che non si vedono a colpo d'occhio:
l'anno compare solo sulla prima data di una serie, e l'orario vale anche per le
righe successive che lo omettono.

Il problema vero pero' non e' il formato: **i nomi delle squadre sono diversi**
da quelli di football-data. Qui e' "FC Internazionale Milano", li' e' "Inter".
Per questo si legge anche il file degli alias del progetto, che per fortuna
elenca proprio le forme brevi che ci servono.
"""

from __future__ import annotations

import re
import unicodedata
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

CARTELLA = Path(__file__).resolve().parents[2] / "data" / "grezzi"
BASE = "https://raw.githubusercontent.com/openfootball"

# I nostri slug verso il file di openfootball. Solo questi: gli altri
# campionati che copriamo non hanno la stagione in corso su openfootball, e per
# quelli il calendario resta quello corto di football-data.
FONTI = {
    "serie-a": ("italy", "1-seriea.txt"),
    "premier-league": ("england", "1-premierleague.txt"),
    "championship": ("england", "2-championship.txt"),
    "laliga": ("espana", "1-liga.txt"),
    "bundesliga": ("deutschland", "1-bundesliga.txt"),
    # Il Belgio c'e' su openfootball ma il suo file usa un formato diverso,
    # senza i marcatori `Matchday`: uscirebbero 306 partite tutte alla giornata
    # zero. Meglio lasciarlo al calendario corto di football-data che
    # pubblicare un calendario senza giornate.
}

# I file di alias, per paese. Piu' d'uno dove serve: in Championship giocano
# tre squadre gallesi (Cardiff, Swansea, Wrexham) e nel file inglese non ci
# sono, perche' openfootball le cataloga per nazione e non per campionato.
ALIAS: dict[str, tuple[str, ...]] = {
    "italy": ("europe/italy/it.clubs.txt",),
    "england": ("europe/england/eng.clubs.txt", "europe/wales/wal.clubs.txt"),
    "espana": ("europe/spain/es.clubs.txt",),
    "deutschland": ("europe/germany/de.clubs.txt",),
    "belgium": ("europe/belgium/be.clubs.txt",),
}

MESI = {m: n for n, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}

_DATA = re.compile(
    r"^\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\w{3})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$"
)
_GIORNATA = re.compile(r"^\s*[^\w\s]?\s*Matchday\s+(\d+)", re.IGNORECASE)
# L'orario, oppure il segnaposto `--:--` che openfootball usa quando non e'
# ancora stato fissato. Senza il secondo caso il segnaposto finisce dentro il
# nome della squadra di casa, e la partita non si riconcilia piu' con niente.
_ORA = re.compile(r"^\s*(?:(\d{1,2}:\d{2})|-{1,2}:-{1,2})\s+(.*)$")
_PUNTEGGIO = re.compile(r"\s+(\d+)\s*-\s*(\d+)(?:\s*\([^)]*\))?\s*$")


@dataclass(frozen=True, slots=True)
class Incontro:
    """Una partita del calendario ufficiale."""

    giornata: int
    data: date
    ora: str
    casa: str
    ospite: str
    gol_casa: int | None = None
    gol_ospite: int | None = None

    @property
    def giocata(self) -> bool:
        return self.gol_casa is not None


def _scarica(percorso: str, nome: str, forza: bool = True) -> str:
    """Scarica un file grezzo da GitHub, con cache su disco."""
    CARTELLA.mkdir(parents=True, exist_ok=True)
    locale = CARTELLA / nome
    if locale.exists() and not forza:
        return locale.read_text(encoding="utf-8", errors="replace")
    richiesta = urllib.request.Request(
        f"{BASE}/{percorso}",
        headers={"User-Agent": "QuotaVera/0.1 (progetto personale)"},
    )
    with urllib.request.urlopen(richiesta, timeout=60) as risposta:
        testo = risposta.read().decode("utf-8", errors="replace")
    locale.write_text(testo, encoding="utf-8")
    return testo


def leggi_alias(testo: str) -> dict[str, str]:
    """Da ogni nome alternativo al nome canonico di openfootball.

    Nel file il nome canonico apre la riga, e le righe successive che cominciano
    con `|` elencano le altre forme. Le varianti marcate con una lingua diversa
    dall'inglese si scartano: a noi servono quelle che usa football-data, che
    sono le brevi inglesi o italiane.
    """
    fuori: dict[str, str] = {}
    canonico = None
    for riga in testo.splitlines():
        nuda = riga.strip()
        if not nuda or nuda.startswith(("#", "=")):
            continue
        if not riga.startswith((" ", "\t")) and not nuda.startswith("|"):
            canonico = nuda.split(",")[0].strip()
            if canonico:
                fuori[_chiave(canonico)] = canonico
            continue
        if canonico and nuda.startswith("|"):
            for pezzo in nuda.lstrip("|").split("|"):
                alias = pezzo.strip()
                if not alias:
                    continue
                lingua = re.search(r"\[(\w{2})\]$", alias)
                if lingua and lingua.group(1) != "en":
                    continue
                alias = re.sub(r"\s*\[\w{2}\]$", "", alias).strip()
                # Un anno di fondazione fra il nome e la citta' finisce qui:
                # non e' un alias, e' rumore del formato.
                if alias and not alias.isdigit():
                    fuori.setdefault(_chiave(alias), canonico)
    return fuori


def leggi_calendario(testo: str) -> list[Incontro]:
    """Legge un file di openfootball e restituisce le partite in ordine."""
    partite: list[Incontro] = []
    giornata = 0
    giorno: date | None = None
    anno: int | None = None
    ora = ""

    for riga in testo.splitlines():
        nuda = riga.strip()
        if not nuda or nuda.startswith(("#", "=")):
            continue

        g = _GIORNATA.match(nuda)
        if g:
            giornata = int(g.group(1))
            ora = ""
            continue

        d = _DATA.match(riga)
        if d:
            mese, numero, quattro = d.group(1), int(d.group(2)), d.group(3)
            # L'anno compare solo sulla prima data della serie: si eredita.
            if quattro:
                anno = int(quattro)
            if anno and mese in MESI:
                giorno = date(anno, MESI[mese], numero)
            ora = ""
            continue

        if " v " not in nuda or giorno is None:
            continue

        corpo = nuda
        o = _ORA.match(nuda)
        if o:
            ora = o.group(1) or ""      # vuoto se era il segnaposto
            corpo = o.group(2)

        gol_casa = gol_ospite = None
        p = _PUNTEGGIO.search(corpo)
        if p:
            gol_casa, gol_ospite = int(p.group(1)), int(p.group(2))
            corpo = corpo[: p.start()]

        casa, _, ospite = corpo.partition(" v ")
        casa, ospite = casa.strip(), ospite.strip()
        if not casa or not ospite:
            continue

        partite.append(
            Incontro(giornata, giorno, ora, casa, ospite, gol_casa, gol_ospite)
        )
    return partite


# Le squadre che i due elenchi chiamano in modi che nessuna normalizzazione
# automatica puo' avvicinare: abbreviazioni diverse, non varianti ortografiche.
# Da football-data verso la forma che compare negli alias di openfootball.
FORZATURE = {
    "man united": "manchester united",
    "ath bilbao": "athletic bilbao",
    "la coruna": "deportivo la coruna",
    "espanol": "espanyol",
    "sp gijon": "sporting gijon",
    "st gilloise": "union saint gilloise",
    "st truiden": "sint truiden",
    "fc koln": "koln",
    "cardiff": "cardiff city",
    "swansea": "swansea city",
    "wrexham": "wrexham afc",
    "sheffield weds": "sheffield wednesday",
    "nott'm forest": "nottingham forest",
    "west brom": "west bromwich albion",
    "qpr": "queens park rangers",
}


def _chiave(nome: str) -> str:
    """La forma su cui si confrontano i nomi.

    Minuscolo, senza accenti e senza punteggiatura: "Alaves" e "Alavés" devono
    coincidere, e cosi' "St. Pauli" e "St Pauli". Senza questo passaggio un
    quarto delle squadre spagnole non si riconcilia, e non per colpa loro.
    """
    nudo = nome.strip().lower()
    nudo = unicodedata.normalize("NFKD", nudo)
    nudo = "".join(c for c in nudo if not unicodedata.combining(c))
    nudo = re.sub(r"[^a-z0-9 ]+", " ", nudo)
    nudo = re.sub(r"\s+", " ", nudo).strip()
    return FORZATURE.get(nudo, nudo)


def normalizza(nome: str, alias: dict[str, str]) -> str:
    """Il nome canonico, partendo da una forma qualsiasi.

    Va applicato a **entrambi** gli elenchi prima di confrontarli: il file
    degli alias ha un suo canonico ("Atalanta Bergamo") che non coincide con
    quello del calendario ("Atalanta BC"), quindi normalizzare un lato solo
    lascia scoperte proprio le squadre piu' note.
    """
    chiave = _chiave(nome)
    # Senza alias si torna la *chiave*, non il nome grezzo: due elenchi che
    # scrivono "RAAL La Louvière" e "RAAL La Louviere" devono comunque
    # coincidere, e restituendo il nome originale non lo farebbero mai.
    return alias.get(chiave, chiave)


def carica(campionato: str, forza: bool = True) -> tuple[list[Incontro], dict[str, str]]:
    """Calendario completo e tabella degli alias di un campionato.

    Restituisce liste vuote se il campionato non e' fra quelli coperti: sono
    sei su ventidue, e il resto continua col calendario corto di football-data.
    """
    if campionato not in FONTI:
        return [], {}
    paese, file = FONTI[campionato]
    testo = _scarica(f"{paese}/master/2026-27/{file}", f"of-{campionato}.txt", forza)
    partite = leggi_calendario(testo)

    alias: dict[str, str] = {}
    for n, percorso in enumerate(ALIAS.get(paese, ())):
        try:
            nuovi = leggi_alias(
                _scarica(f"clubs/master/{percorso}", f"of-alias-{paese}-{n}.txt", forza)
            )
        except Exception:
            continue        # senza alias si ripiega sul nome per intero
        for k, v in nuovi.items():
            alias.setdefault(k, v)
    return partite, alias
