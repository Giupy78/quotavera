"""Lettore dei dati storici di football-data.co.uk.

E' la prima fonte di dati veri del progetto, ed e' gratuita. I file CSV
contengono, per ogni partita giocata, il risultato e **le quote di chiusura**
di piu' bookmaker — comprese quelle di Pinnacle e del Betfair Exchange, che
sono i due riferimenti seri del mercato.

La quota di chiusura e' la cosa importante. E' il prezzo che il mercato espone
poco prima del fischio d'inizio, quando tutte le informazioni sono arrivate e
tutti i soldi sono stati mossi: e' la migliore stima di probabilita' che
esista, ed e' contro quella che un modello va misurato. Misurarsi contro le
quote di apertura, o contro la media di tutti i libri, e' il modo elegante di
darsi ragione da soli.

    from engine.dati.football_data import scarica, leggi
    percorso = scarica("serie-a", "2526")
    partite = leggi(percorso)
"""

from __future__ import annotations

import csv
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from engine.core.types import Incontro

BASE = "https://www.football-data.co.uk/mmz4281"
CARTELLA = Path(__file__).resolve().parents[2] / "data" / "grezzi"

# I nostri slug verso i codici di football-data. Sono gli otto campionati del
# sito: la corrispondenza e' completa, non abbiamo dovuto rinunciare a nessuno.
CODICI = {
    "serie-a": "I1",
    "premier-league": "E0",
    "laliga": "SP1",
    "bundesliga": "D1",
    "ligue-1": "F1",
    "eredivisie": "N1",
    "primeira-liga": "P1",
    "superlig": "T1",
}

# I libri che leggiamo, in ordine di quanto ci fidiamo del loro prezzo.
#
# Betfair Exchange e Pinnacle non sono "altri due bookmaker": sono i due
# riferimenti. Il primo e' un mercato vero, dove il prezzo e' quello che
# qualcuno e' davvero disposto a bancare; il secondo vive di volume e accetta i
# giocatori vincenti invece di limitarli. Gli altri li copiano.
LIBRI = {
    "betfair": ("BFECH", "BFECD", "BFECA"),
    "pinnacle": ("PSCH", "PSCD", "PSCA"),
    "bet365": ("B365CH", "B365CD", "B365CA"),
    "massimo": ("MaxCH", "MaxCD", "MaxCA"),
    "media": ("AvgCH", "AvgCD", "AvgCA"),
}

RIFERIMENTO = ("betfair", "pinnacle")


@dataclass(frozen=True, slots=True)
class PartitaStorica:
    """Una partita giocata, con il risultato e le quote di chiusura."""

    incontro: Incontro
    quote: dict[str, tuple[float, float, float]]

    @property
    def esito(self) -> int:
        """0 = vince la casa, 1 = pareggio, 2 = vince l'ospite."""
        c, o = self.incontro.punti_casa, self.incontro.punti_ospite
        return 0 if c > o else (1 if c == o else 2)

    def riferimento(self) -> tuple[float, float, float] | None:
        """Le quote del libro piu' affidabile fra quelli presenti.

        Betfair per primo, Pinnacle come riserva. Se manca anche quella la
        partita non e' utilizzabile per misurare il modello: si potrebbe
        ripiegare sulla media di tutti i libri, ma sarebbe un riferimento piu'
        debole, e mescolarlo agli altri falserebbe il confronto senza che si
        veda. Meglio perdere la partita.
        """
        for libro in RIFERIMENTO:
            if libro in self.quote:
                return self.quote[libro]
        return None


def scarica(campionato: str, stagione: str, forza: bool = False) -> Path:
    """Scarica il CSV di un campionato e lo tiene in cache su disco.

    `stagione` e' nel formato di football-data: "2526" e' la stagione
    2025/26. Il file resta in `data/grezzi/`, che non e' versionato: si
    riscarica in qualsiasi momento, e non ha senso tenerlo nel repository.
    """
    if campionato not in CODICI:
        raise KeyError(
            f"campionato sconosciuto: {campionato!r}. "
            f"Disponibili: {', '.join(sorted(CODICI))}"
        )
    CARTELLA.mkdir(parents=True, exist_ok=True)
    percorso = CARTELLA / f"{campionato}-{stagione}.csv"
    if percorso.exists() and not forza:
        return percorso

    url = f"{BASE}/{stagione}/{CODICI[campionato]}.csv"
    richiesta = urllib.request.Request(
        url, headers={"User-Agent": "QuotaVera/0.1 (progetto personale)"}
    )
    with urllib.request.urlopen(richiesta, timeout=60) as risposta:
        contenuto = risposta.read()
    percorso.write_bytes(contenuto)
    return percorso


def _data(testo: str) -> date | None:
    """Le date di football-data sono gg/mm/aa oppure gg/mm/aaaa, non sempre coerenti."""
    for formato in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(testo.strip(), formato).date()
        except ValueError:
            continue
    return None


def _quota(riga: dict[str, str], colonne: tuple[str, str, str]) -> tuple[float, float, float] | None:
    """Legge una terna di quote, o None se manca o non e' valida.

    Le celle vuote sono normali: non tutti i libri quotano tutte le partite, e
    le colonne cambiano negli anni via via che i bookmaker chiudono.
    """
    fuori = []
    for c in colonne:
        grezzo = (riga.get(c) or "").strip()
        if not grezzo:
            return None
        try:
            valore = float(grezzo)
        except ValueError:
            return None
        if valore <= 1.0:
            return None
        fuori.append(valore)
    return (fuori[0], fuori[1], fuori[2])


def leggi(percorso: Path, campionato: str = "") -> list[PartitaStorica]:
    """Legge un CSV scaricato e restituisce le partite utilizzabili.

    Scarta le righe senza risultato o senza data: nei file di fine stagione
    capitano righe vuote in coda, e una partita senza esito non serve a niente.
    """
    partite: list[PartitaStorica] = []
    with percorso.open(encoding="utf-8-sig", errors="replace", newline="") as f:
        for n, riga in enumerate(csv.DictReader(f), start=1):
            giorno = _data(riga.get("Date", ""))
            casa = (riga.get("HomeTeam") or "").strip()
            ospite = (riga.get("AwayTeam") or "").strip()
            gol_c = (riga.get("FTHG") or "").strip()
            gol_o = (riga.get("FTAG") or "").strip()
            if not (giorno and casa and ospite and gol_c and gol_o):
                continue

            quote = {}
            for nome, colonne in LIBRI.items():
                valori = _quota(riga, colonne)
                if valori:
                    quote[nome] = valori

            partite.append(
                PartitaStorica(
                    incontro=Incontro(
                        id=f"{percorso.stem}-{n}",
                        data=giorno,
                        casa=casa,
                        ospite=ospite,
                        punti_casa=int(gol_c),
                        punti_ospite=int(gol_o),
                        campionato=campionato or percorso.stem,
                    ),
                    quote=quote,
                )
            )
    return partite


def stagioni(prima: int, ultima: int) -> list[str]:
    """Genera i codici stagione: stagioni(2015, 2026) -> ['1516', ..., '2526']."""
    return [f"{a % 100:02d}{(a + 1) % 100:02d}" for a in range(prima, ultima)]


def carica(campionato: str, stagioni_volute: list[str]) -> list[PartitaStorica]:
    """Scarica e legge piu' stagioni di un campionato, in ordine di data."""
    tutte: list[PartitaStorica] = []
    for s in stagioni_volute:
        try:
            tutte.extend(leggi(scarica(campionato, s), campionato))
        except Exception as errore:      # una stagione mancante non ferma il resto
            print(f"  ! {campionato} {s}: {errore}")
    tutte.sort(key=lambda p: p.incontro.data)
    return tutte
