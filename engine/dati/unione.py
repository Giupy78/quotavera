"""Mettere insieme football-data ed ESPN senza contarci due volte le partite.

Le due fonti si sovrappongono, e ognuna ha qualcosa che l'altra non ha.

    football-data   storico lungo, quote di molti operatori, sette statistiche
                    di campo. Pubblica a turno concluso, con giorni di ritardo.

    ESPN            risultati entro minuti dal fischio, ventisette statistiche
                    per squadra. Nessuna quota, e solo la stagione in corso.

La regola di precedenza e' semplice e vale la pena dirla: **il risultato non si
tocca mai due volte**. Se una partita c'e' in tutte e due, resta quella di
football-data — che porta con se' le quote — arricchita con le statistiche
avanzate di ESPN. Se c'e' solo in ESPN, entra come partita senza quote.

L'errore da evitare a ogni costo e' il doppione: la stessa partita contata
due volte in classifica fa sei punti invece di tre, e nessuno se ne accorge
guardando la pagina. Per questo l'accoppiamento e' per squadre *e* per data con
tolleranza — ESPN data in UTC, football-data in ora locale, e una partita del
lunedi' sera puo' comparire come domenica o come martedi' a seconda del fuso.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from engine.dati.espn import PartitaEspn
from engine.dati.football_data import PartitaStorica, Statistiche
from engine.core.types import Incontro

# Quanti giorni di scarto si accettano fra le due fonti per considerare la
# stessa partita. Due bastano: oltre, il rischio e' di fondere l'andata col
# ritorno in campionati che giocano infrasettimanale.
TOLLERANZA = 2

# Le voci ESPN che finiscono nei campi corrispondenti di Statistiche.
AVANZATE = ("tiri_respinti", "fuorigioco", "parate", "possesso", "passaggi",
            "passaggi_riusciti", "cross", "cross_riusciti", "contrasti",
            "contrasti_riusciti", "intercetti", "respinte", "lanci",
            "lanci_riusciti")


def _interi(valori: tuple[float, float]) -> tuple[int, int]:
    return (int(round(valori[0])), int(round(valori[1])))


def _arricchisci(stat: Statistiche, e: PartitaEspn) -> Statistiche:
    """Le statistiche di football-data piu' quelle che solo ESPN ha.

    Le sette di base restano quelle di football-data anche quando ESPN le ha:
    sono la serie storica con cui il modello e' stato tarato, e cambiarle a
    meta' stagione introdurrebbe uno scalino nei numeri che non corrisponde a
    niente di successo in campo.
    """
    if not e.stat:
        return stat
    nuovi = {}
    for nome in AVANZATE:
        if nome in e.stat:
            v = e.stat[nome]
            nuovi[nome] = v if nome == "possesso" else _interi(v)
    if not nuovi:
        return stat
    return replace(stat, **nuovi, avanzate=True)


def _da_espn(e: PartitaEspn, campionato: str) -> PartitaStorica:
    """Una partita che football-data non ha ancora pubblicato."""
    base = {}
    for nome in AVANZATE:
        if nome in e.stat:
            v = e.stat[nome]
            base[nome] = v if nome == "possesso" else _interi(v)
    # `completa` dice se ci sono le sette di base: ESPN le ha tutte tranne i
    # gol del primo tempo, che restano a zero e non vanno lette.
    di_base = {}
    for nostro, loro in (("tiri", "tiri"), ("in_porta", "in_porta"),
                         ("corner", "corner"), ("falli", "falli"),
                         ("gialli", "gialli"), ("rossi", "rossi")):
        if loro in e.stat:
            di_base[nostro] = _interi(e.stat[loro])
    stat = Statistiche(**di_base, **base,
                       completa=len(di_base) == 6, avanzate=bool(base))
    return PartitaStorica(
        incontro=Incontro(f"espn-{e.id}", e.data, e.casa, e.ospite,
                          e.gol_casa, e.gol_ospite, campionato),
        quote={}, apertura={}, stat=stat,
    )


def fondi(storico: list[PartitaStorica], espn: list[PartitaEspn],
          campionato: str) -> tuple[list[PartitaStorica], int, int]:
    """Storico unificato. Restituisce (partite, arricchite, aggiunte)."""
    if not espn:
        return storico, 0, 0

    # Indice per coppia di squadre: le date si confrontano dopo, con tolleranza.
    per_coppia: dict[tuple[str, str], list[int]] = {}
    for i, p in enumerate(storico):
        per_coppia.setdefault((p.incontro.casa, p.incontro.ospite), []).append(i)

    fuori = list(storico)
    arricchite = aggiunte = 0
    for e in espn:
        candidati = per_coppia.get((e.casa, e.ospite), [])
        trovato = None
        for i in candidati:
            if abs((fuori[i].incontro.data - e.data).days) <= TOLLERANZA:
                trovato = i
                break
        if trovato is None:
            fuori.append(_da_espn(e, campionato))
            aggiunte += 1
        else:
            prima = fuori[trovato].stat
            dopo = _arricchisci(prima, e)
            if dopo is not prima:
                fuori[trovato] = replace(fuori[trovato], stat=dopo)
                arricchite += 1

    fuori.sort(key=lambda p: p.incontro.data)
    return fuori, arricchite, aggiunte
