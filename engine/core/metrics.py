"""Le misure con cui il modello si giudica da solo.

Sono tre domande diverse, e vanno tenute separate:

1. le probabilita' sono calibrate?  -> calibrazione, Brier, log-loss
2. batto il mercato?                -> confronto degli stessi punteggi col banco
3. ci guadagno?                     -> rendimento, e sopra ogni cosa il CLV

Un modello puo' essere calibrato e perdere soldi (il margine se li mangia), e
puo' guadagnare per mesi essendo pessimo (varianza). Servono tutte e tre.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FasciaCalibrazione:
    """Una barra del grafico di calibrazione."""

    centro: float          # probabilita' dichiarata al centro della fascia
    dichiarata: float      # media delle probabilita' dichiarate nella fascia
    osservata: float       # frequenza con cui l'esito si e' verificato
    casi: int

    @property
    def scarto(self) -> float:
        return self.osservata - self.dichiarata


def brier(probabilita: Sequence[Sequence[float]], esiti: Sequence[int]) -> float:
    """Brier multiclasse. Piu' basso e' meglio; 0 e' la perfezione.

    `probabilita[i]` sono le probabilita' dei possibili esiti della partita i,
    `esiti[i]` e' l'indice di quello che e' successo.
    """
    if len(probabilita) != len(esiti):
        raise ValueError("lunghezze diverse")
    if not probabilita:
        raise ValueError("nessun caso")
    totale = 0.0
    for p, vero in zip(probabilita, esiti):
        for k, pk in enumerate(p):
            reale = 1.0 if k == vero else 0.0
            totale += (pk - reale) ** 2
    return totale / len(probabilita)


def log_loss(
    probabilita: Sequence[Sequence[float]], esiti: Sequence[int], eps: float = 1e-15
) -> float:
    """Log-loss. Punisce molto piu' del Brier chi e' sicuro e sbaglia."""
    if len(probabilita) != len(esiti):
        raise ValueError("lunghezze diverse")
    if not probabilita:
        raise ValueError("nessun caso")
    totale = 0.0
    for p, vero in zip(probabilita, esiti):
        totale -= math.log(max(p[vero], eps))
    return totale / len(probabilita)


def calibrazione(
    dichiarate: Sequence[float], avvenuti: Sequence[bool], fasce: int = 10
) -> list[FasciaCalibrazione]:
    """Raggruppa le previsioni in fasce e confronta dichiarato e osservato.

    E' il grafico che va messo in home page. Se i punti stanno sulla diagonale
    il modello dice la verita' sulla propria incertezza; se stanno sotto, e'
    sistematicamente troppo sicuro di se'.
    """
    if len(dichiarate) != len(avvenuti):
        raise ValueError("lunghezze diverse")
    larghezza = 1.0 / fasce
    secchi: list[list[tuple[float, bool]]] = [[] for _ in range(fasce)]
    for p, avvenuto in zip(dichiarate, avvenuti):
        indice = min(int(p / larghezza), fasce - 1)
        secchi[indice].append((p, avvenuto))

    risultato = []
    for i, secchio in enumerate(secchi):
        if not secchio:
            continue
        n = len(secchio)
        risultato.append(
            FasciaCalibrazione(
                centro=(i + 0.5) * larghezza,
                dichiarata=sum(p for p, _ in secchio) / n,
                osservata=sum(1 for _, a in secchio if a) / n,
                casi=n,
            )
        )
    return risultato


def errore_calibrazione(fasce: Sequence[FasciaCalibrazione]) -> float:
    """Expected Calibration Error: lo scarto medio, pesato sui casi.

    Un numero solo da mettere accanto al grafico. Sotto 0.02 e' buono.
    """
    totale_casi = sum(f.casi for f in fasce)
    if totale_casi == 0:
        return 0.0
    return sum(abs(f.scarto) * f.casi for f in fasce) / totale_casi


def rendimento(
    puntate: Sequence[float], quote: Sequence[float], vinte: Sequence[bool]
) -> tuple[float, float]:
    """Restituisce (profitto totale, rendimento sul giocato).

    Il rendimento e' profitto / totale puntato, non profitto / bankroll: e'
    l'unico confrontabile fra strategie con puntate diverse.
    """
    if not (len(puntate) == len(quote) == len(vinte)):
        raise ValueError("lunghezze diverse")
    if not puntate:
        return 0.0, 0.0
    profitto = 0.0
    for p, q, v in zip(puntate, quote, vinte):
        profitto += p * (q - 1.0) if v else -p
    giocato = sum(puntate)
    return profitto, (profitto / giocato if giocato else 0.0)


def curva_rendimento(
    puntate: Sequence[float], quote: Sequence[float], vinte: Sequence[bool]
) -> list[float]:
    """Il rendimento cumulato dopo ogni giocata: e' il grafico da pubblicare."""
    curva = [0.0]
    profitto = 0.0
    giocato = 0.0
    for p, q, v in zip(puntate, quote, vinte):
        profitto += p * (q - 1.0) if v else -p
        giocato += p
        curva.append(profitto / giocato if giocato else 0.0)
    return curva


def curva_profitto(
    puntate: Sequence[float], quote: Sequence[float], vinte: Sequence[bool]
) -> list[float]:
    """Il profitto cumulato in unita', giocata per giocata.

    Serve separata da `curva_rendimento` perche' il ribasso massimo va calcolato
    su questa. Sul rendimento non avrebbe senso: dopo la prima giocata persa il
    rendimento vale -100%, e un ribasso del 100% comparirebbe in ogni storia
    che comincia con una sconfitta.
    """
    curva = [0.0]
    profitto = 0.0
    for p, q, v in zip(puntate, quote, vinte):
        profitto += p * (q - 1.0) if v else -p
        curva.append(profitto)
    return curva


def ribasso_massimo(curva: Sequence[float]) -> float:
    """La peggiore discesa dal punto piu' alto. Va detto prima, non dopo.

    Va passata la curva del *profitto*, non quella del rendimento.
    """
    picco = float("-inf")
    peggio = 0.0
    for v in curva:
        picco = max(picco, v)
        peggio = min(peggio, v - picco)
    return peggio
