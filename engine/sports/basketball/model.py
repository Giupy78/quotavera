"""Basket: margine e totale come due normali.

Il basket e' piu' semplice del calcio, non piu' difficile: i possessi sono
tanti (~100 a testa), quindi il teorema centrale del limite fa il lavoro e il
margine finale e' ben approssimato da una normale. Non serve una matrice di
punteggi esatti — nessuno scommette sul 112-108.

Restano due domande separate, e si stimano con due regressioni distinte:

  margine = forza_casa - forza_ospite + vantaggio_campo
  totale  = base + ritmo_casa + ritmo_ospite

Da mu e sigma escono testa a testa, handicap e over/under. Il sigma non e' un
dettaglio: e' quello che decide se un handicap di 5.5 vale, e va stimato dai
residui veri, non messo a mano.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from math import erf, sqrt

import numpy as np

from engine.core.types import (
    MERCATO_HANDICAP,
    MERCATO_ML,
    MERCATO_OU,
    Fixture,
    Incontro,
    Prediction,
)

# Regolarizzazione: tira le squadre verso la media. Senza, una squadra con
# poche partite prende un rating estremo per caso.
#
# Non sono numeri messi a occhio. Per una ridge il valore che minimizza
# l'errore atteso e' sigma^2 / tau^2, dove sigma e' il rumore di una partita e
# tau la dispersione vera fra le squadre:
#
#   forza: sigma ~ 11.5 punti, tau ~ 4.5 punti  ->  132 / 20  ~  7
#   ritmo: sigma ~ 12   punti, tau ~ 2.9 punti  ->  144 / 8.4 ~ 17
#
# Il ritmo va regolarizzato molto di piu' perche' il segnale e' piu' debole a
# parita' di rumore: le squadre differiscono meno nei punti totali che nella
# forza. Un valore solo per entrambi sarebbe sbagliato due volte.
RIDGE_FORZA = 7.0
RIDGE_RITMO = 17.0

# Meta' vita in giorni. Nel basket le rose e le rotazioni cambiano piu' in
# fretta che nel calcio: si pesa il recente molto di piu'.
XI_DEFAULT = 0.0060


def _phi(z: float) -> float:
    """Normale standard cumulata."""
    return 0.5 * (1.0 + erf(z / sqrt(2.0)))


@dataclass(frozen=True, slots=True)
class ForzaSquadra:
    squadra: str
    forza: float        # punti sopra la media contro un avversario medio
    ritmo: float        # punti sopra la media che contribuisce al totale


class ModelloBasket:
    """Stima forza e ritmo, e da li' i mercati."""

    sport = "basket"
    nome = "margine-normale"

    def __init__(
        self,
        xi: float = XI_DEFAULT,
        ridge_forza: float = RIDGE_FORZA,
        ridge_ritmo: float = RIDGE_RITMO,
    ) -> None:
        self.xi = xi
        self.ridge_forza = ridge_forza
        self.ridge_ritmo = ridge_ritmo
        self.squadre: list[str] = []
        self._indice: dict[str, int] = {}
        self.forza: np.ndarray = np.array([])
        self.ritmo: np.ndarray = np.array([])
        self.vantaggio_casa: float = 0.0
        self.totale_base: float = 0.0
        self.sigma_margine: float = 0.0
        self.sigma_totale: float = 0.0
        self.partite_usate: int = 0

    def fit(self, incontri: Sequence[Incontro], riferimento=None) -> "ModelloBasket":
        if len(incontri) < 30:
            raise ValueError(
                f"servono almeno 30 partite, ne ho {len(incontri)}"
            )
        riferimento = riferimento or max(i.data for i in incontri)
        self.squadre = sorted({i.casa for i in incontri} | {i.ospite for i in incontri})
        self._indice = {s: k for k, s in enumerate(self.squadre)}
        n = len(self.squadre)
        m = len(incontri)

        casa = np.array([self._indice[i.casa] for i in incontri])
        ospite = np.array([self._indice[i.ospite] for i in incontri])
        margine = np.array(
            [i.punti_casa - i.punti_ospite for i in incontri], dtype=float
        )
        totale = np.array([i.punti_casa + i.punti_ospite for i in incontri], dtype=float)
        giorni = np.array([(riferimento - i.data).days for i in incontri], dtype=float)
        peso = np.exp(-self.xi * np.maximum(giorni, 0.0))
        in_neutro = np.array([i.neutro for i in incontri], dtype=float)

        # --- margine: X = [forza (n colonne), vantaggio campo]
        X = np.zeros((m, n + 1))
        X[np.arange(m), casa] = 1.0
        X[np.arange(m), ospite] = -1.0
        X[:, n] = 1.0 - in_neutro
        forza, hca, self.sigma_margine = _ridge_pesata(
            X, margine, peso, self.ridge_forza, n
        )
        # Il margine e' una differenza: centrare le forze non cambia le previsioni.
        self.forza = forza - forza.mean()
        self.vantaggio_casa = hca

        # --- totale: X = [ritmo (n colonne), base]
        Xt = np.zeros((m, n + 1))
        Xt[np.arange(m), casa] = 1.0
        Xt[np.arange(m), ospite] = 1.0
        Xt[:, n] = 1.0
        ritmo, base, self.sigma_totale = _ridge_pesata(
            Xt, totale, peso, self.ridge_ritmo, n
        )
        # Qui invece i due ritmi si sommano: quello che tolgo alle squadre lo
        # devo restituire alla base, due volte, o il totale atteso si sposta.
        media = float(ritmo.mean())
        self.ritmo = ritmo - media
        self.totale_base = base + 2.0 * media

        self.partite_usate = m
        return self

    def attese(self, casa: str, ospite: str, neutro: bool = False) -> tuple[float, float]:
        """(margine atteso casa-ospite, totale atteso)."""
        for s in (casa, ospite):
            if s not in self._indice:
                raise KeyError(f"squadra sconosciuta al modello: {s!r}")
        c, o = self._indice[casa], self._indice[ospite]
        mu = float(self.forza[c] - self.forza[o] + (0.0 if neutro else self.vantaggio_casa))
        tot = float(self.totale_base + self.ritmo[c] + self.ritmo[o])
        return mu, tot

    def predict(
        self,
        fixture: Fixture,
        handicap: Sequence[float] = (-5.5, -2.5, 2.5, 5.5),
        linee_totale: Sequence[float] | None = None,
    ) -> Prediction:
        mu, tot = self.attese(fixture.casa, fixture.ospite, fixture.neutro)
        sm, st = self.sigma_margine, self.sigma_totale

        # Testa a testa: nel basket il pareggio non esiste, i supplementari lo
        # risolvono. P(casa vince) = P(margine > 0).
        p_casa = _phi(mu / sm)
        mercati: dict[str, dict[str, float]] = {
            MERCATO_ML: {"casa": p_casa, "ospite": 1.0 - p_casa}
        }

        for linea in handicap:
            # La linea e' riferita alla squadra di casa: -5.5 vuol dire che deve
            # vincere di 6, +5.5 che le bastano 5 punti di sconfitta. In entrambi
            # i casi copre quando margine + linea > 0.
            p = _phi((mu + linea) / sm)
            mercati[f"{MERCATO_HANDICAP}_{linea:+g}"] = {"copre": p, "non_copre": 1.0 - p}

        if linee_totale is None:
            base = round(tot * 2) / 2
            linee_totale = (base - 5.5, base, base + 5.5)
        for linea in linee_totale:
            p_over = 1.0 - _phi((linea - tot) / st)
            mercati[f"{MERCATO_OU}_{linea:g}"] = {"over": p_over, "under": 1.0 - p_over}

        p = Prediction(
            fixture_id=fixture.id,
            sport=self.sport,
            modello=self.nome,
            generato_il=datetime.now(timezone.utc),
            mercati=mercati,
            dettaglio={
                "margine_atteso": mu,
                "totale_atteso": tot,
                "sigma_margine": sm,
                "sigma_totale": st,
                "punti_attesi_casa": (tot + mu) / 2.0,
                "punti_attesi_ospite": (tot - mu) / 2.0,
            },
        )
        p.verifica()
        return p

    def forze(self) -> list[ForzaSquadra]:
        return sorted(
            (
                ForzaSquadra(s, float(self.forza[k]), float(self.ritmo[k]))
                for s, k in self._indice.items()
            ),
            key=lambda f: f.forza,
            reverse=True,
        )


def _ridge_pesata(
    X: np.ndarray, y: np.ndarray, peso: np.ndarray, alfa: float, n_squadre: int
) -> tuple[np.ndarray, float, float]:
    """Minimi quadrati pesati con penalita' ridge sulle sole colonne squadra.

    Restituisce (coefficienti squadra, intercetta, sigma dei residui).
    L'intercetta (vantaggio campo o totale base) non va penalizzata: e' un
    livello, non una deviazione dalla media.
    """
    radice = np.sqrt(peso)
    Xw, yw = X * radice[:, None], y * radice
    P = np.eye(X.shape[1]) * alfa
    P[n_squadre, n_squadre] = 0.0
    beta = np.linalg.solve(Xw.T @ Xw + P, Xw.T @ yw)

    # Sigma dai residui pesati, corretto per i gradi di liberta' spesi.
    residui = y - X @ beta
    n, k = len(y), X.shape[1]
    varianza = float((peso * residui**2).sum() / peso.sum())
    sigma = float(np.sqrt(varianza * n / max(n - k, 1)))
    return beta[:n_squadre], float(beta[n_squadre]), sigma
