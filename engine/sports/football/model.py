"""Calcio: modello Dixon-Coles.

L'idea, in una riga: ogni squadra ha una forza d'attacco e una di difesa, i gol
segnati dalle due squadre sono due Poisson quasi indipendenti, e il "quasi" e'
la correzione di Dixon e Coles (1997) sui punteggi bassi — perche' 0-0 e 1-1
succedono piu' spesso di quanto due Poisson indipendenti prevedano.

Da quella singola matrice escono tutti i mercati: 1X2, over/under, gol/gol.
Non sono stime separate, sono somme di celle. E' il motivo per cui i mercati
restano coerenti fra loro senza doverli aggiustare a mano.

Riferimento: Dixon & Coles, "Modelling Association Football Scores and
Inefficiencies in the Football Betting Market", Applied Statistics 46(2), 1997.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln

from engine.core.types import (
    MERCATO_1X2,
    MERCATO_BTTS,
    MERCATO_OU,
    Fixture,
    Incontro,
    Prediction,
)

# Meta' vita di un risultato, in giorni: dopo ~385 giorni una partita pesa la
# meta'. Dixon e Coles proponevano un'emivita piu' corta; sul calcio moderno,
# con le rose che cambiano meno di quanto sembri, allungarla riduce il rumore.
XI_DEFAULT = 0.0018

# Oltre gli 8 gol per squadra la probabilita' e' sotto il milionesimo: la
# matrice si tronca li' e si rinormalizza.
MAX_GOL = 8


@dataclass(frozen=True, slots=True)
class ForzaSquadra:
    """Le due coordinate di una squadra. Sono i dati del grafico attacco/difesa."""

    squadra: str
    attacco: float      # scala log: 0 e' la media del campionato
    difesa: float       # scala log: piu' alto = subisce meno
    gol_attesi_fatti: float     # per 90', contro un avversario medio in campo neutro
    gol_attesi_subiti: float


class ModelloCalcio:
    """Stima le forze delle squadre e produce le probabilita' di una partita.

    Uso:
        m = ModelloCalcio().fit(incontri)
        p = m.predict(fixture)
    """

    sport = "calcio"
    nome = "dixon-coles"

    def __init__(self, xi: float = XI_DEFAULT, max_gol: int = MAX_GOL) -> None:
        self.xi = xi
        self.max_gol = max_gol
        self.squadre: list[str] = []
        self._indice: dict[str, int] = {}
        self.attacco: np.ndarray = np.array([])
        self.difesa: np.ndarray = np.array([])
        self.vantaggio_casa: float = 0.0
        self.rho: float = 0.0
        self.riferimento: date | None = None
        self.log_verosimiglianza: float = float("nan")
        self.partite_usate: int = 0

    # ------------------------------------------------------------------ stima

    def fit(
        self, incontri: Sequence[Incontro], riferimento: date | None = None
    ) -> "ModelloCalcio":
        """Stima i parametri a massima verosimiglianza pesata nel tempo.

        `riferimento` e' la data rispetto a cui si calcola l'eta' delle partite:
        di norma oggi, ma va passata esplicitamente quando si rifa' la storia
        all'indietro, altrimenti il backtest vede il futuro.
        """
        if len(incontri) < 20:
            raise ValueError(
                f"servono almeno 20 partite per una stima sensata, ne ho {len(incontri)}"
            )

        self.riferimento = riferimento or max(i.data for i in incontri)
        self.squadre = sorted({i.casa for i in incontri} | {i.ospite for i in incontri})
        self._indice = {s: k for k, s in enumerate(self.squadre)}
        n = len(self.squadre)

        casa = np.array([self._indice[i.casa] for i in incontri])
        ospite = np.array([self._indice[i.ospite] for i in incontri])
        gol_casa = np.array([i.punti_casa for i in incontri], dtype=float)
        gol_ospite = np.array([i.punti_ospite for i in incontri], dtype=float)
        giorni = np.array(
            [(self.riferimento - i.data).days for i in incontri], dtype=float
        )
        peso = np.exp(-self.xi * np.maximum(giorni, 0.0))
        in_neutro = np.array([i.neutro for i in incontri], dtype=bool)

        # Le costanti fattoriali non dipendono dai parametri: fuori dal ciclo.
        costante = -(gammaln(gol_casa + 1.0) + gammaln(gol_ospite + 1.0))

        def spacchetta(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
            # L'ultimo attacco e' vincolato: la somma degli attacchi fa 0.
            # Senza questo vincolo il modello ha un grado di liberta' di troppo
            # (si puo' sommare una costante a tutti gli attacchi e toglierla
            # alle difese senza cambiare nulla) e l'ottimizzatore va a spasso.
            att_liberi = x[: n - 1]
            att = np.concatenate([att_liberi, [-att_liberi.sum()]])
            dif = x[n - 1 : 2 * n - 1]
            return att, dif, float(x[-2]), float(x[-1])

        def neg_log_lik(x: np.ndarray) -> float:
            att, dif, home, rho = spacchetta(x)
            vantaggio = np.where(in_neutro, 0.0, home)
            log_lh = att[casa] - dif[ospite] + vantaggio
            log_la = att[ospite] - dif[casa]
            lh = np.exp(np.clip(log_lh, -6.0, 3.0))
            la = np.exp(np.clip(log_la, -6.0, 3.0))

            ll = costante + gol_casa * np.log(lh) - lh + gol_ospite * np.log(la) - la
            tau = _tau(gol_casa, gol_ospite, lh, la, rho)
            if np.any(tau <= 0):
                return 1e10  # rho ha reso negativa una probabilita': zona vietata
            ll = ll + np.log(tau)
            return float(-(peso * ll).sum())

        x0 = np.concatenate(
            [np.zeros(n - 1), np.zeros(n), [0.25], [-0.05]]
        )
        limiti = (
            [(-3.0, 3.0)] * (n - 1)
            + [(-3.0, 3.0)] * n
            + [(-1.0, 1.0), (-0.2, 0.2)]
        )

        esito = minimize(
            neg_log_lik, x0, method="L-BFGS-B", bounds=limiti,
            options={"maxiter": 2000, "ftol": 1e-10},
        )

        att, dif, home, rho = spacchetta(esito.x)
        self.attacco = att
        self.difesa = dif
        self.vantaggio_casa = home
        self.rho = rho
        self.log_verosimiglianza = -float(esito.fun)
        self.partite_usate = len(incontri)
        if not esito.success:
            # Non alziamo un'eccezione: L-BFGS-B dichiara spesso fallimento per
            # tolleranze minime pur avendo converso. Lo si scrive e si guarda.
            self.avviso = str(esito.message)
        return self

    # ---------------------------------------------------------------- previsione

    def _lambde(self, casa: str, ospite: str, neutro: bool = False) -> tuple[float, float]:
        if casa not in self._indice:
            raise KeyError(f"squadra sconosciuta al modello: {casa!r}")
        if ospite not in self._indice:
            raise KeyError(f"squadra sconosciuta al modello: {ospite!r}")
        c, o = self._indice[casa], self._indice[ospite]
        vantaggio = 0.0 if neutro else self.vantaggio_casa
        lh = float(np.exp(self.attacco[c] - self.difesa[o] + vantaggio))
        la = float(np.exp(self.attacco[o] - self.difesa[c]))
        return lh, la

    def matrice(self, casa: str, ospite: str, neutro: bool = False) -> np.ndarray:
        """La tabella dei risultati esatti: `m[i][j]` = probabilita' di i-j."""
        lh, la = self._lambde(casa, ospite, neutro)
        return matrice_da_lambde(lh, la, self.rho, self.max_gol)

    def predict(self, fixture: Fixture) -> Prediction:
        """Tutti i mercati di una partita, da un'unica matrice."""
        lh, la = self._lambde(fixture.casa, fixture.ospite, fixture.neutro)
        m = matrice_da_lambde(lh, la, self.rho, self.max_gol)

        mercati = {MERCATO_1X2: esiti_1x2(m), MERCATO_BTTS: gol_gol(m)}
        for soglia in (1.5, 2.5, 3.5):
            mercati[f"{MERCATO_OU}_{soglia}"] = over_under(m, soglia)

        indici = np.dstack(np.unravel_index(np.argsort(-m, axis=None), m.shape))[0][:5]
        risultati_probabili = [
            {"risultato": f"{int(i)}-{int(j)}", "p": float(m[i, j])} for i, j in indici
        ]

        p = Prediction(
            fixture_id=fixture.id,
            sport=self.sport,
            modello=self.nome,
            generato_il=datetime.now(timezone.utc),
            mercati=mercati,
            dettaglio={
                "gol_attesi_casa": lh,
                "gol_attesi_ospite": la,
                "rho": self.rho,
                "matrice": m.tolist(),
                "risultati_probabili": risultati_probabili,
            },
        )
        p.verifica()
        return p

    # ------------------------------------------------------------------- forze

    def forze(self) -> list[ForzaSquadra]:
        """La tabella attacco/difesa, ordinata dalla piu' forte. Alimenta il grafico."""
        media_att = float(self.attacco.mean())
        media_dif = float(self.difesa.mean())
        fuori = []
        for s, k in self._indice.items():
            fatti = float(np.exp(self.attacco[k] - media_dif))
            subiti = float(np.exp(media_att - self.difesa[k]))
            fuori.append(
                ForzaSquadra(
                    squadra=s,
                    attacco=float(self.attacco[k]),
                    difesa=float(self.difesa[k]),
                    gol_attesi_fatti=fatti,
                    gol_attesi_subiti=subiti,
                )
            )
        fuori.sort(key=lambda f: f.gol_attesi_fatti - f.gol_attesi_subiti, reverse=True)
        return fuori


# --------------------------------------------------------------------- funzioni


def _tau(
    x: np.ndarray | float,
    y: np.ndarray | float,
    lh: np.ndarray | float,
    la: np.ndarray | float,
    rho: float,
) -> np.ndarray:
    """La correzione Dixon-Coles sui quattro punteggi bassi.

    Con rho negativo alza 0-0 e 1-1 e abbassa 1-0 e 0-1: e' esattamente la
    deviazione dall'indipendenza che si osserva nei dati veri.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    lh = np.asarray(lh, dtype=float)
    la = np.asarray(la, dtype=float)
    t = np.ones(np.broadcast_shapes(x.shape, y.shape, lh.shape, la.shape))
    t = np.where((x == 0) & (y == 0), 1.0 - lh * la * rho, t)
    t = np.where((x == 0) & (y == 1), 1.0 + lh * rho, t)
    t = np.where((x == 1) & (y == 0), 1.0 + la * rho, t)
    t = np.where((x == 1) & (y == 1), 1.0 - rho, t)
    return t


def matrice_da_lambde(
    lh: float, la: float, rho: float = 0.0, max_gol: int = MAX_GOL
) -> np.ndarray:
    """Costruisce la matrice dei risultati esatti e la rinormalizza a 1."""
    k = np.arange(max_gol + 1)
    log_p = k * np.log(lh) - lh - gammaln(k + 1.0)
    log_q = k * np.log(la) - la - gammaln(k + 1.0)
    m = np.exp(log_p)[:, None] * np.exp(log_q)[None, :]
    x = k[:, None] * np.ones_like(k)[None, :]
    y = np.ones_like(k)[:, None] * k[None, :]
    m = m * _tau(x, y, lh, la, rho)
    m = np.clip(m, 0.0, None)
    return m / m.sum()


def esiti_1x2(m: np.ndarray) -> dict[str, float]:
    casa = float(np.tril(m, -1).sum())
    pari = float(np.trace(m))
    ospite = float(np.triu(m, 1).sum())
    return {"1": casa, "X": pari, "2": ospite}


def over_under(m: np.ndarray, soglia: float) -> dict[str, float]:
    n = m.shape[0]
    totale = np.add.outer(np.arange(n), np.arange(n))
    over = float(m[totale > soglia].sum())
    return {"over": over, "under": 1.0 - over}


def gol_gol(m: np.ndarray) -> dict[str, float]:
    si = float(m[1:, 1:].sum())
    return {"si": si, "no": 1.0 - si}
