"""Dalle quote alle probabilita', e ritorno.

Le quote di un bookmaker non sono probabilita': sommano a piu' di 1, e la
differenza e' il margine del banco. Toglierlo male e' il modo piu' comune di
convincersi di avere un vantaggio che non c'e', perche' il margine non e'
distribuito in modo uniforme fra gli esiti: sui piu' improbabili e' molto piu'
alto (il favourite-longshot bias).

Per questo il metodo predefinito qui e' Shin e non la divisione per la somma.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

Metodo = Literal["shin", "moltiplicativo", "additivo"]


def margine(quote: Sequence[float]) -> float:
    """Il margine del banco: quanto le probabilita' implicite eccedono 1."""
    return sum(1.0 / q for q in quote) - 1.0


def _shin_z(inverse: Sequence[float], somma: float) -> float:
    """Cerca per bisezione la z di Shin che fa sommare le probabilita' a 1."""

    def somma_prob(z: float) -> float:
        tot = 0.0
        for q in inverse:
            radice = (z * z + 4.0 * (1.0 - z) * q * q / somma) ** 0.5
            tot += (radice - z) / (2.0 * (1.0 - z))
        return tot

    lo, hi = 0.0, 0.5
    # Con z = 0 la somma vale `somma` (> 1); z cresce finche' la somma non torna a 1.
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if somma_prob(mid) > 1.0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def probabilita_implicite(
    quote: Sequence[float], metodo: Metodo = "shin"
) -> list[float]:
    """Toglie il margine del banco e restituisce probabilita' che sommano a 1.

    - `moltiplicativo`: divide per la somma. Semplice, ma sovrastima gli esiti
      improbabili perche' spalma il margine in proporzione.
    - `additivo`: sottrae a ognuno la stessa quota di margine.
    - `shin`: assume che il margine nasca dal rischio di giocatori informati.
      E' quello che si comporta meglio sugli esiti a quota alta, ed e' il
      motivo per cui e' il default.
    """
    if len(quote) < 2:
        raise ValueError("servono almeno due esiti")
    if any(q <= 1.0 for q in quote):
        raise ValueError("una quota deve essere maggiore di 1")

    inverse = [1.0 / q for q in quote]
    somma = sum(inverse)

    if metodo == "moltiplicativo":
        return [q / somma for q in inverse]

    if metodo == "additivo":
        eccesso = (somma - 1.0) / len(quote)
        grezze = [q - eccesso for q in inverse]
        if any(p <= 0 for p in grezze):  # quota lunghissima: ripiega
            return [q / somma for q in inverse]
        tot = sum(grezze)
        return [p / tot for p in grezze]

    if metodo == "shin":
        if somma <= 1.0:  # nessun margine da togliere (o quote gia' pulite)
            return [q / somma for q in inverse]
        z = _shin_z(inverse, somma)
        prob = []
        for q in inverse:
            radice = (z * z + 4.0 * (1.0 - z) * q * q / somma) ** 0.5
            prob.append((radice - z) / (2.0 * (1.0 - z)))
        tot = sum(prob)
        return [p / tot for p in prob]

    raise ValueError(f"metodo sconosciuto: {metodo!r}")


def quota_equa(p: float) -> float:
    """La quota che rende la giocata a somma zero."""
    if not 0.0 < p <= 1.0:
        raise ValueError("probabilita' fuori da (0, 1]")
    return 1.0 / p


def valore_atteso(p: float, quota: float) -> float:
    """Rendimento atteso per euro giocato. 0.10 vuol dire +10%."""
    return p * quota - 1.0


def kelly(p: float, quota: float, frazione: float = 0.25, cap: float = 0.05) -> float:
    """Quota di bankroll da rischiare, secondo Kelly frazionario.

    Kelly pieno e' matematicamente ottimo solo se le probabilita' sono giuste.
    Le nostre sono stimate, quindi si usa un quarto di Kelly e si mette comunque
    un tetto: e' la differenza fra una strategia e una scommessa sul modello.
    Restituisce 0 quando non c'e' vantaggio.
    """
    b = quota - 1.0
    if b <= 0:
        return 0.0
    f = (p * b - (1.0 - p)) / b
    # La soglia non e' pignoleria: alla quota esattamente equa f vale zero a
    # meno dell'errore di virgola mobile, e senza questo confronto uscirebbe un
    # 1e-17 che a valle diventa "c'e' vantaggio".
    if f <= 1e-12:
        return 0.0
    return min(f * frazione, cap)


def valore_di_chiusura(quota_presa: float, quota_chiusura: float) -> float:
    """Closing line value: quanto la quota presa batte quella di chiusura.

    E' la misura piu' onesta di bravura che esista nelle scommesse, perche' non
    dipende dall'esito della partita. Se e' sistematicamente positiva il
    vantaggio e' reale anche quando il rendimento e' ancora negativo.
    """
    return quota_presa / quota_chiusura - 1.0
