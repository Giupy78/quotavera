"""Le statistiche che si danno da leggere, e quelle che si danno da usare.

Sono due cose diverse e vale la pena tenerle distinte.

Le prime sono descrittive — gol fatti, subiti, over, gol/gol — e servono a
raccontare una squadra. Le seconde sono quelle che dicono qualcosa su cosa
succedera': e quasi sempre non sono i gol.

Il motivo e' che i gol sono pochi. Una squadra ne segna uno o due a partita, e
su dieci partite la differenza fra una buona e una fortunata sta dentro il
rumore. I tiri in porta sono cinque volte tanti e raccontano la stessa storia
con un quinto dell'incertezza: e' per quello che la "forma" calcolata sui
risultati delle ultime cinque e' quasi sempre una sciocchezza, mentre quella
calcolata sui tiri no.

Da qui esce anche l'osservazione piu' utile che possiamo dare a un lettore:
**chi sta segnando piu' di quanto crea**. Quelle squadre, statisticamente,
rientrano — e il mercato se ne accorge tardi.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from engine.dati.football_data import PartitaStorica

# Quanti gol vale, in media, un tiro in porta. Si ricalcola sui dati veri in
# `conversione_media`: questo e' solo il valore di partenza per i casi vuoti.
CONVERSIONE_TIPICA = 0.31


@dataclass
class Ruolo:
    """I numeri di una squadra in un ruolo solo: in casa, o in trasferta."""

    partite: int = 0
    gol_fatti: int = 0
    gol_subiti: int = 0
    tiri: int = 0
    tiri_subiti: int = 0
    in_porta: int = 0
    in_porta_subiti: int = 0
    corner: int = 0
    corner_subiti: int = 0
    falli: int = 0
    falli_subiti: int = 0
    gialli: int = 0
    rossi: int = 0
    gol_pt_fatti: int = 0
    gol_pt_subiti: int = 0
    con_statistiche: int = 0

    # Dal tabellino ESPN, che football-data non ha. Hanno un contatore tutto
    # loro perche' esistono solo da questa stagione: dividere per
    # `con_statistiche` farebbe medie schiacciate su partite che quei numeri
    # non li avevano proprio.
    tiri_respinti: int = 0
    fuorigioco: int = 0
    parate: int = 0
    possesso: float = 0.0
    passaggi: int = 0
    passaggi_riusciti: int = 0
    cross: int = 0
    cross_riusciti: int = 0
    contrasti: int = 0
    contrasti_riusciti: int = 0
    intercetti: int = 0
    respinte: int = 0
    lanci: int = 0
    lanci_riusciti: int = 0
    con_avanzate: int = 0
    over_25: int = 0
    gol_gol: int = 0
    clean_sheet: int = 0
    a_secco: int = 0

    def _per_partita(self, valore: int) -> float:
        return valore / self.partite if self.partite else 0.0

    @property
    def gol_fatti_partita(self) -> float:
        return self._per_partita(self.gol_fatti)

    @property
    def gol_subiti_partita(self) -> float:
        return self._per_partita(self.gol_subiti)

    @property
    def tiri_partita(self) -> float:
        return self.tiri / self.con_statistiche if self.con_statistiche else 0.0

    @property
    def in_porta_partita(self) -> float:
        return self.in_porta / self.con_statistiche if self.con_statistiche else 0.0

    @property
    def in_porta_subiti_partita(self) -> float:
        return self.in_porta_subiti / self.con_statistiche if self.con_statistiche else 0.0

    @property
    def corner_partita(self) -> float:
        return self.corner / self.con_statistiche if self.con_statistiche else 0.0

    @property
    def tiri_subiti_partita(self) -> float:
        return self.tiri_subiti / self.con_statistiche if self.con_statistiche else 0.0

    @property
    def corner_subiti_partita(self) -> float:
        return self.corner_subiti / self.con_statistiche if self.con_statistiche else 0.0

    @property
    def falli_partita(self) -> float:
        return self.falli / self.con_statistiche if self.con_statistiche else 0.0

    @property
    def cartellini_partita(self) -> float:
        return (self.gialli + self.rossi) / self.con_statistiche if self.con_statistiche else 0.0

    def _avanzata(self, valore: float) -> float:
        return valore / self.con_avanzate if self.con_avanzate else 0.0

    @property
    def possesso_medio(self) -> float:
        return self._avanzata(self.possesso)

    @property
    def passaggi_partita(self) -> float:
        return self._avanzata(self.passaggi)

    @property
    def precisione_passaggi(self) -> float:
        return self.passaggi_riusciti / self.passaggi if self.passaggi else 0.0

    @property
    def precisione_cross(self) -> float:
        return self.cross_riusciti / self.cross if self.cross else 0.0

    @property
    def precisione_lanci(self) -> float:
        return self.lanci_riusciti / self.lanci if self.lanci else 0.0

    @property
    def contrasti_partita(self) -> float:
        return self._avanzata(self.contrasti)

    @property
    def intercetti_partita(self) -> float:
        return self._avanzata(self.intercetti)

    @property
    def respinte_partita(self) -> float:
        return self._avanzata(self.respinte)

    @property
    def parate_partita(self) -> float:
        return self._avanzata(self.parate)

    @property
    def fuorigioco_partita(self) -> float:
        return self._avanzata(self.fuorigioco)

    @property
    def tiri_respinti_partita(self) -> float:
        return self._avanzata(self.tiri_respinti)

    @property
    def precisione_tiri(self) -> float:
        """Quanti dei tiri finiscono nello specchio. Dice la qualita' della conclusione."""
        return self.in_porta / self.tiri if self.tiri else 0.0

    @property
    def quota_over_25(self) -> float:
        return self._per_partita(self.over_25)

    @property
    def quota_gol_gol(self) -> float:
        return self._per_partita(self.gol_gol)

    @property
    def quota_clean_sheet(self) -> float:
        return self._per_partita(self.clean_sheet)

    @property
    def quota_a_secco(self) -> float:
        return self._per_partita(self.a_secco)

    @property
    def conversione(self) -> float:
        """Gol segnati per tiro in porta. È il numero che smaschera la fortuna."""
        return self.gol_fatti / self.in_porta if self.in_porta else 0.0

    @property
    def gol_attesi_dai_tiri(self) -> float:
        """Quanti gol *avrebbe dovuto* segnare, a conversione media.

        Confrontarlo con i gol veri dice se una squadra sta andando meglio o
        peggio di come gioca. È l'informazione che un lettore non trova
        altrove, e quella che regge meglio alla prova del tempo.
        """
        return self.in_porta * CONVERSIONE_TIPICA


@dataclass
class StatSquadra:
    """Tutti i numeri di una squadra, separati per casa e trasferta."""

    squadra: str
    casa: Ruolo = field(default_factory=Ruolo)
    trasferta: Ruolo = field(default_factory=Ruolo)

    @property
    def partite(self) -> int:
        return self.casa.partite + self.trasferta.partite

    @property
    def gol_fatti_partita(self) -> float:
        n = self.partite
        return (self.casa.gol_fatti + self.trasferta.gol_fatti) / n if n else 0.0

    @property
    def gol_subiti_partita(self) -> float:
        n = self.partite
        return (self.casa.gol_subiti + self.trasferta.gol_subiti) / n if n else 0.0

    @property
    def in_porta_totali(self) -> int:
        return self.casa.in_porta + self.trasferta.in_porta

    @property
    def gol_totali(self) -> int:
        return self.casa.gol_fatti + self.trasferta.gol_fatti

    @property
    def conversione(self) -> float:
        return self.gol_totali / self.in_porta_totali if self.in_porta_totali else 0.0

    def scarto_dalla_conversione(self, media: float = CONVERSIONE_TIPICA) -> float:
        """Gol in più (o in meno) rispetto a quanti ne direbbero i tiri in porta.

        Positivo: sta segnando più di quanto crea. Va letto come un avviso, non
        come una previsione: nel campione può essere bravura del centravanti
        quanto fortuna, e le due si distinguono solo col tempo. Ma su una
        stagione, la fortuna rientra e la bravura no.
        """
        if not self.in_porta_totali:
            return 0.0
        return self.gol_totali - self.in_porta_totali * media

    @property
    def vantaggio_casa(self) -> float:
        """Quanti gol in più fa in casa rispetto a fuori, per partita."""
        return self.casa.gol_fatti_partita - self.trasferta.gol_fatti_partita


def _aggiorna(r: Ruolo, fatti: int, subiti: int, p: PartitaStorica, in_casa: bool) -> None:
    r.partite += 1
    r.gol_fatti += fatti
    r.gol_subiti += subiti
    if fatti + subiti > 2.5:
        r.over_25 += 1
    if fatti > 0 and subiti > 0:
        r.gol_gol += 1
    if subiti == 0:
        r.clean_sheet += 1
    if fatti == 0:
        r.a_secco += 1

    s = p.stat
    if not s.completa:
        return
    r.con_statistiche += 1
    i = 0 if in_casa else 1
    j = 1 - i
    r.tiri += s.tiri[i]
    r.tiri_subiti += s.tiri[j]
    r.in_porta += s.in_porta[i]
    r.in_porta_subiti += s.in_porta[j]
    r.corner += s.corner[i]
    r.corner_subiti += s.corner[j]
    r.falli += s.falli[i]
    r.falli_subiti += s.falli[j]
    r.gialli += s.gialli[i]
    r.rossi += s.rossi[i]
    r.gol_pt_fatti += s.gol_primo_tempo[i]
    r.gol_pt_subiti += s.gol_primo_tempo[j]

    if not s.avanzate:
        return
    r.con_avanzate += 1
    r.tiri_respinti += s.tiri_respinti[i]
    r.fuorigioco += s.fuorigioco[i]
    r.parate += s.parate[i]
    r.possesso += s.possesso[i]
    r.passaggi += s.passaggi[i]
    r.passaggi_riusciti += s.passaggi_riusciti[i]
    r.cross += s.cross[i]
    r.cross_riusciti += s.cross_riusciti[i]
    r.contrasti += s.contrasti[i]
    r.contrasti_riusciti += s.contrasti_riusciti[i]
    r.intercetti += s.intercetti[i]
    r.respinte += s.respinte[i]
    r.lanci += s.lanci[i]
    r.lanci_riusciti += s.lanci_riusciti[i]


def calcola(
    partite: list[PartitaStorica], ultime: int | None = None
) -> dict[str, StatSquadra]:
    """Statistiche per squadra.

    Con `ultime` si limita alle ultime N partite di *ogni* squadra — che non è
    lo stesso che prendere le ultime N partite del campionato: ogni squadra ha
    il suo calendario, e mescolarli darebbe a qualcuno più partite che ad altri.
    """
    per_squadra: dict[str, list[tuple[PartitaStorica, bool]]] = defaultdict(list)
    for p in sorted(partite, key=lambda x: x.incontro.data):
        per_squadra[p.incontro.casa].append((p, True))
        per_squadra[p.incontro.ospite].append((p, False))

    fuori: dict[str, StatSquadra] = {}
    for squadra, elenco in per_squadra.items():
        if ultime is not None:
            elenco = elenco[-ultime:]
        s = StatSquadra(squadra)
        for p, in_casa in elenco:
            fatti = p.incontro.punti_casa if in_casa else p.incontro.punti_ospite
            subiti = p.incontro.punti_ospite if in_casa else p.incontro.punti_casa
            _aggiorna(s.casa if in_casa else s.trasferta, fatti, subiti, p, in_casa)
        fuori[squadra] = s
    return fuori


def conversione_media(partite: list[PartitaStorica]) -> float:
    """Gol per tiro in porta sull'intero campione. È il metro del campionato."""
    gol = tiri = 0
    for p in partite:
        if not p.stat.completa:
            continue
        gol += p.incontro.punti_casa + p.incontro.punti_ospite
        tiri += p.stat.in_porta[0] + p.stat.in_porta[1]
    return gol / tiri if tiri else CONVERSIONE_TIPICA


def precedenti(
    partite: list[PartitaStorica], casa: str, ospite: str, quante: int = 10
) -> list[PartitaStorica]:
    """Gli ultimi precedenti fra due squadre, in qualunque ordine di campo."""
    coppia = {casa, ospite}
    incontri = [
        p for p in partite
        if {p.incontro.casa, p.incontro.ospite} == coppia
    ]
    incontri.sort(key=lambda p: p.incontro.data, reverse=True)
    return incontri[:quante]
