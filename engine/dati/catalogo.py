"""I campionati coperti, e cosa sappiamo di ognuno.

Sono quelli che football-data.co.uk pubblica gratuitamente: ventidue divisioni
in undici paesi. Non e' una lista di desideri — e' esattamente cio' per cui
esistono sia lo storico con le quote di chiusura sia il calendario delle
partite future.

**Le coppe non ci sono**, e non e' una dimenticanza: football-data copre solo
campionati nazionali. Champions, Europa League e Coppa Italia richiedono
un'altra fonte, a pagamento. Sta scritto qui perche' non venga riscoperto ogni
volta.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Campionato:
    slug: str
    codice: str        # come lo chiama football-data
    nome: str
    paese: str
    bandiera: str
    livello: int       # 1 = massima serie
    principale: bool   # se sta nel menu principale del sito

    @property
    def etichetta(self) -> str:
        return f"{self.bandiera} {self.nome}"


CAMPIONATI: list[Campionato] = [
    # --- prime divisioni, quelle che vanno nel menu -------------------------
    Campionato("serie-a", "I1", "Serie A", "Italia", "🇮🇹", 1, True),
    Campionato("premier-league", "E0", "Premier League", "Inghilterra", "🏴", 1, True),
    Campionato("laliga", "SP1", "LaLiga", "Spagna", "🇪🇸", 1, True),
    Campionato("bundesliga", "D1", "Bundesliga", "Germania", "🇩🇪", 1, True),
    Campionato("ligue-1", "F1", "Ligue 1", "Francia", "🇫🇷", 1, True),
    Campionato("eredivisie", "N1", "Eredivisie", "Paesi Bassi", "🇳🇱", 1, True),
    Campionato("primeira-liga", "P1", "Primeira Liga", "Portogallo", "🇵🇹", 1, True),
    Campionato("superlig", "T1", "Süper Lig", "Turchia", "🇹🇷", 1, True),
    Campionato("jupiler", "B1", "Pro League", "Belgio", "🇧🇪", 1, True),
    Campionato("super-league-grecia", "G1", "Super League", "Grecia", "🇬🇷", 1, True),
    Campionato("premiership", "SC0", "Premiership", "Scozia", "🏴", 1, True),

    # --- seconde divisioni e minori -----------------------------------------
    # Ci sono e sono gratis. Contano piu' di quanto sembri: il mercato le
    # prezza peggio, e le statistiche di squadra ci sono lo stesso.
    Campionato("serie-b", "I2", "Serie B", "Italia", "🇮🇹", 2, False),
    Campionato("championship", "E1", "Championship", "Inghilterra", "🏴", 2, False),
    Campionato("league-one", "E2", "League One", "Inghilterra", "🏴", 3, False),
    Campionato("league-two", "E3", "League Two", "Inghilterra", "🏴", 4, False),
    Campionato("national-league", "EC", "National League", "Inghilterra", "🏴", 5, False),
    Campionato("laliga-2", "SP2", "LaLiga 2", "Spagna", "🇪🇸", 2, False),
    Campionato("bundesliga-2", "D2", "2. Bundesliga", "Germania", "🇩🇪", 2, False),
    Campionato("ligue-2", "F2", "Ligue 2", "Francia", "🇫🇷", 2, False),
    Campionato("championship-scozia", "SC1", "Championship", "Scozia", "🏴", 2, False),
    Campionato("league-one-scozia", "SC2", "League One", "Scozia", "🏴", 3, False),
    Campionato("league-two-scozia", "SC3", "League Two", "Scozia", "🏴", 4, False),
]

PER_SLUG = {c.slug: c for c in CAMPIONATI}
PER_CODICE = {c.codice: c for c in CAMPIONATI}
PRINCIPALI = [c for c in CAMPIONATI if c.principale]


def dal_codice(codice: str) -> Campionato | None:
    """Da 'I1' al campionato. None se e' una divisione che non copriamo."""
    return PER_CODICE.get(codice.strip())
