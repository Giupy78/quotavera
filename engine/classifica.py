"""Le classifiche: quella vera e quella che il gioco avrebbe meritato.

La prima e' aritmetica e la sa fare chiunque. La seconda e' il motivo per cui
vale la pena costruirle noi.

**La classifica attesa** rifa' il campionato sostituendo ai gol i tiri in
porta. Per ogni partita si stima quante reti le due squadre avrebbero segnato
alla conversione media, si calcola con quale probabilita' quella partita
sarebbe finita in vittoria, pareggio o sconfitta, e si assegnano i punti
*attesi*: 3 x P(vittoria) + 1 x P(pareggio).

Sommandoli su tutta la stagione si ottiene la classifica che il gioco avrebbe
prodotto se i gol fossero caduti secondo le occasioni create. Le squadre molto
sopra la loro posizione attesa hanno raccolto piu' di quanto seminato, e sulla
distanza tendono a rientrare; quelle molto sotto sono le sottovalutate.

E' la stessa idea di "chi segna piu' di quanto crea", portata dai gol ai punti
— che e' la moneta con cui il campionato si misura davvero.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from engine.dati.football_data import PartitaStorica
from engine.sports.football.model import esiti_1x2, matrice_da_lambde
from engine.statistiche import CONVERSIONE_TIPICA

# Sotto questa soglia di reti attese la Poisson diventa instabile e la partita
# non dice niente: capita quando una squadra non ha tirato in porta nemmeno una
# volta. Si tiene un minimo per non far esplodere il conto.
MINIMO_RETI_ATTESE = 0.05


@dataclass
class Riga:
    """Una riga di classifica."""

    squadra: str
    giocate: int = 0
    vinte: int = 0
    pareggiate: int = 0
    perse: int = 0
    fatti: int = 0
    subiti: int = 0
    punti: int = 0
    # Punti attesi dai tiri in porta: la colonna che nessun altro pubblica.
    punti_attesi: float = 0.0
    reti_attese_fatte: float = 0.0
    reti_attese_subite: float = 0.0
    con_statistiche: int = 0

    @property
    def differenza(self) -> int:
        return self.fatti - self.subiti

    @property
    def scarto_punti(self) -> float:
        """Punti veri meno punti attesi. Positivo = ha raccolto piu' del gioco."""
        return self.punti - self.punti_attesi

    @property
    def punti_partita(self) -> float:
        return self.punti / self.giocate if self.giocate else 0.0


def punti_attesi(reti_casa: float, reti_ospite: float) -> tuple[float, float]:
    """I punti che le due squadre si aspettano da una partita, date le reti attese.

    Non si assegna la vittoria a chi ha creato di piu': si pesa ogni esito per
    la sua probabilita'. Una partita da 1,4 contro 1,2 reti attese non e' una
    vittoria di misura — e' una partita quasi pari, e i punti attesi lo dicono.
    """
    lh = max(reti_casa, MINIMO_RETI_ATTESE)
    la = max(reti_ospite, MINIMO_RETI_ATTESE)
    p = esiti_1x2(matrice_da_lambde(lh, la, rho=0.0))
    casa = 3.0 * p["1"] + 1.0 * p["X"]
    ospite = 3.0 * p["2"] + 1.0 * p["X"]
    return casa, ospite


def calcola(
    partite: list[PartitaStorica], conversione: float = CONVERSIONE_TIPICA
) -> list[Riga]:
    """La classifica, ordinata come si ordina una classifica vera.

    Punti, poi differenza reti, poi reti fatte. In Serie A il primo criterio a
    parita' di punti sarebbe lo scontro diretto, ma serve solo a dirimere ex
    aequo e complica il codice senza cambiare quasi mai l'ordine: qui si usa la
    convenzione internazionale, ed e' scritto perche' non sembri una svista.
    """
    righe: dict[str, Riga] = defaultdict(lambda: Riga(""))

    for p in partite:
        i = p.incontro
        casa = righe[i.casa]
        ospite = righe[i.ospite]
        casa.squadra, ospite.squadra = i.casa, i.ospite

        casa.giocate += 1
        ospite.giocate += 1
        casa.fatti += i.punti_casa
        casa.subiti += i.punti_ospite
        ospite.fatti += i.punti_ospite
        ospite.subiti += i.punti_casa

        if i.punti_casa > i.punti_ospite:
            casa.vinte += 1
            ospite.perse += 1
            casa.punti += 3
        elif i.punti_casa < i.punti_ospite:
            ospite.vinte += 1
            casa.perse += 1
            ospite.punti += 3
        else:
            casa.pareggiate += 1
            ospite.pareggiate += 1
            casa.punti += 1
            ospite.punti += 1

        if not p.stat.completa:
            continue
        rc = p.stat.in_porta[0] * conversione
        ro = p.stat.in_porta[1] * conversione
        pa_casa, pa_ospite = punti_attesi(rc, ro)
        casa.punti_attesi += pa_casa
        ospite.punti_attesi += pa_ospite
        casa.reti_attese_fatte += rc
        casa.reti_attese_subite += ro
        ospite.reti_attese_fatte += ro
        ospite.reti_attese_subite += rc
        casa.con_statistiche += 1
        ospite.con_statistiche += 1

    return sorted(
        righe.values(),
        key=lambda r: (r.punti, r.differenza, r.fatti),
        reverse=True,
    )


def posizioni_attese(classifica: list[Riga]) -> dict[str, int]:
    """Che posizione occuperebbe ogni squadra ordinando per punti attesi."""
    per_attesi = sorted(classifica, key=lambda r: r.punti_attesi, reverse=True)
    return {r.squadra: n for n, r in enumerate(per_attesi, start=1)}


def ultimi_risultati(
    partite: list[PartitaStorica], quanti: int = 20
) -> list[PartitaStorica]:
    """Le partite giocate piu' di recente, dalla piu' recente."""
    return sorted(partite, key=lambda p: p.incontro.data, reverse=True)[:quanti]


def giornate(partite: list[PartitaStorica]) -> dict[str, int]:
    """A quale giornata appartiene ogni partita.

    football-data non pubblica il numero di giornata, e raggrupparle per data
    non funziona: un turno si spalma su tre giorni e i recuperi finiscono
    ovunque. Si deduce invece contando, per ogni squadra, quante partite ha
    gia' giocato: una partita appartiene alla giornata successiva a quella piu'
    avanzata fra le due squadre in campo.

    E' lo stesso criterio con cui si legge una classifica — la colonna "G" — e
    regge anche con i recuperi: una partita rinviata e giocata dopo resta
    assegnata alla sua giornata, non a quella in cui e' stata recuperata.
    """
    giocate: dict[str, int] = defaultdict(int)
    fuori: dict[str, int] = {}
    for p in sorted(partite, key=lambda x: x.incontro.data):
        i = p.incontro
        # L'etichetta e' la giornata piu' avanzata fra le due squadre, ma il
        # contatore di ciascuna sale di uno e basta. Assegnando `n` a entrambe,
        # la squadra rimasta indietro per un rinvio farebbe un salto e da li' in
        # poi tutte le sue giornate sarebbero sfalsate — in Serie A comparivano
        # una giornata 39 e una 40, che non esistono.
        fuori[i.id] = max(giocate[i.casa], giocate[i.ospite]) + 1
        giocate[i.casa] += 1
        giocate[i.ospite] += 1
    return fuori
