"""Tipi condivisi da tutti gli sport.

Il punto di questo modulo e' che una partita di calcio, una di basket e un
match di tennis escano dal motore con la stessa forma. Il sito non deve sapere
di che sport sta parlando: riceve un Prediction e disegna i mercati che trova.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Mapping


# I nomi dei mercati sono stringhe stabili: il sito ci costruisce sopra le
# etichette, e cambiarli rompe lo storico gia' salvato.
MERCATO_1X2 = "1x2"          # calcio: 1 / X / 2
MERCATO_ML = "ml"            # testa a testa senza pareggio: home / away
MERCATO_OU = "ou"            # over / under, la soglia sta nella chiave
MERCATO_BTTS = "btts"        # gol/gol, no gol
MERCATO_HANDICAP = "hcp"     # handicap, la linea sta nella chiave


@dataclass(frozen=True, slots=True)
class Squadra:
    """Un contendente: club, franchigia o singolo giocatore."""

    id: str
    nome: str


@dataclass(frozen=True, slots=True)
class Incontro:
    """Una partita gia' giocata, con il suo esito.

    `punti_casa` e `punti_ospite` sono gol nel calcio, punti nel basket,
    set vinti nel tennis. Il modello di ogni sport sa come leggerli.
    """

    id: str
    data: date
    casa: str
    ospite: str
    punti_casa: int
    punti_ospite: int
    campionato: str = ""
    neutro: bool = False


@dataclass(frozen=True, slots=True)
class Fixture:
    """Una partita ancora da giocare."""

    id: str
    data: datetime
    casa: str
    ospite: str
    campionato: str = ""
    neutro: bool = False


@dataclass(slots=True)
class Prediction:
    """Il risultato del modello per una partita.

    `mercati` e' una mappa nome-mercato -> {esito: probabilita'}. Ogni mercato
    somma a 1: e' un invariante, non una gentilezza, e c'e' un test che lo
    verifica. `dettaglio` porta quello che serve ai grafici e cambia da sport
    a sport (la matrice dei risultati nel calcio, media e sigma nel basket).
    """

    fixture_id: str
    sport: str
    modello: str
    generato_il: datetime
    mercati: dict[str, dict[str, float]] = field(default_factory=dict)
    dettaglio: dict[str, object] = field(default_factory=dict)

    def probabilita(self, mercato: str, esito: str) -> float:
        return self.mercati[mercato][esito]

    def verifica(self, tolleranza: float = 1e-6) -> None:
        """Alza AssertionError se un mercato non somma a 1."""
        for nome, esiti in self.mercati.items():
            somma = sum(esiti.values())
            if abs(somma - 1.0) > tolleranza:
                raise AssertionError(
                    f"il mercato {nome!r} di {self.fixture_id} somma a {somma:.6f}"
                )


@dataclass(frozen=True, slots=True)
class Occasione:
    """Uno scarto fra modello e mercato, congelato nel momento in cui lo vedi.

    Questo e' il record che va scritto su disco *prima* della partita e mai piu'
    toccato. Senza `quota_presa` e `visto_il` non esiste track record: si puo'
    solo raccontare.
    """

    fixture_id: str
    mercato: str
    esito: str
    p_modello: float
    p_mercato: float
    quota_presa: float
    valore_atteso: float
    kelly: float
    visto_il: datetime
    bookmaker: str = ""

    @property
    def scarto(self) -> float:
        """Punti di probabilita' fra modello e mercato ripulito."""
        return self.p_modello - self.p_mercato


def normalizza(esiti: Mapping[str, float]) -> dict[str, float]:
    """Riscala una mappa di probabilita' perche' sommi esattamente a 1."""
    totale = sum(esiti.values())
    if totale <= 0:
        raise ValueError("probabilita' non positive")
    return {k: v / totale for k, v in esiti.items()}
