"""Tennis: dal punto alla partita.

Il tennis e' l'unico dei tre sport dove conviene scendere sotto il risultato,
fino al singolo punto — e il motivo e' che il punteggio non e' lineare. Un
giocatore puo' vincere piu' punti dell'avversario e perdere la partita, e
succede spesso: sono i punti *importanti* a decidere.

Quindi si stima una cosa sola, la probabilita' che un giocatore vinca un punto
al proprio servizio, e da li' si risale per ricorsione a game, tie-break, set e
match. Le formule sono classiche (Barnett & Clarke, 2005) e l'assunzione forte
e' che i punti siano indipendenti: e' falsa, ma sbaglia poco.

L'Elo per superficie serve a stimare quella probabilita' di partenza quando i
dati punto-per-punto non ci sono — cioe' quasi sempre fuori dai tornei maggiori.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache

from engine.core.types import MERCATO_ML, Fixture, Incontro, Prediction

# Quanto un punto di Elo sposta il servizio. Tarato perche' 100 punti di Elo di
# differenza valgano circa 1,5 punti percentuali sul servizio: e' l'ordine di
# grandezza che si osserva nei dati ATP.
ELO_SCALA = 400.0

# Probabilita' media di vincere il punto al servizio. Cambia parecchio con la
# superficie: sull'erba il servizio pesa molto di piu' che sulla terra.
SERVIZIO_MEDIO = {"erba": 0.680, "cemento": 0.650, "terra": 0.625, "": 0.650}


@dataclass(slots=True)
class Giocatore:
    id: str
    elo: float = 1500.0
    partite: int = 0
    elo_superficie: dict[str, float] = field(default_factory=dict)

    def elo_su(self, superficie: str) -> float:
        """Elo misto: superficie dove c'e' storia, generale dove non c'e'."""
        if superficie and superficie in self.elo_superficie:
            return 0.6 * self.elo_superficie[superficie] + 0.4 * self.elo
        return self.elo


# ------------------------------------------------------------------ ricorsioni


def prob_game(p: float) -> float:
    """Probabilita' che chi serve vinca il game, dato p sul punto.

    Forma chiusa: i quattro modi di chiudere entro il 40-30, piu' il deuce, da
    cui si esce con probabilita' p^2 / (p^2 + q^2).
    """
    if not 0.0 < p < 1.0:
        return float(p >= 1.0)
    q = 1.0 - p
    entro_il_40 = p**4 * (1.0 + 4.0 * q + 10.0 * q * q)
    ai_vantaggi = 20.0 * p**3 * q**3 * (p * p / (p * p + q * q))
    return entro_il_40 + ai_vantaggi


def _serve_a(punti_giocati: int, primo_a: bool) -> bool:
    """Chi serve il prossimo punto del tie-break.

    Il primo punto lo serve uno, poi si alterna a coppie: A B B A A B B ...
    Contando i punti dall'1, il primo servitore serve quando (n // 2) e' pari.
    """
    n = punti_giocati + 1
    tocca_al_primo = (n // 2) % 2 == 0
    return tocca_al_primo if primo_a else not tocca_al_primo


@lru_cache(maxsize=None)
def _tiebreak(a: int, b: int, p: float, q: float, primo_a: bool, fino_a: int) -> float:
    """Probabilita' che A vinca il tie-break dallo stato (a, b)."""
    if a >= fino_a and a - b >= 2:
        return 1.0
    if b >= fino_a and b - a >= 2:
        return 0.0
    # Sul 6-6 si continua a due punti di scarto: lo stato si ripete, e la
    # ricorsione si chiude sulla forma limite invece di scendere all'infinito.
    if a >= fino_a - 1 and b >= fino_a - 1:
        # In due punti consecutivi ne serve uno per parte, sempre.
        pa = p * (1.0 - q)          # A tiene il suo e strappa quello di B
        pb = (1.0 - p) * q          # A perde il suo e B tiene
        if pa + pb == 0:
            return 0.5
        return pa / (pa + pb)

    prob_punto = p if _serve_a(a + b, primo_a) else 1.0 - q
    return prob_punto * _tiebreak(a + 1, b, p, q, primo_a, fino_a) + (
        1.0 - prob_punto
    ) * _tiebreak(a, b + 1, p, q, primo_a, fino_a)


@lru_cache(maxsize=None)
def _set(a: int, b: int, p: float, q: float, serve_a: bool, tiebreak: bool) -> float:
    """Probabilita' che A vinca il set dallo stato (game a, game b)."""
    if a >= 6 and a - b >= 2:
        return 1.0
    if b >= 6 and b - a >= 2:
        return 0.0
    if a == 6 and b == 6:
        if not tiebreak:  # set lungo: si continua a due game di scarto
            g_a, g_b = prob_game(p), prob_game(q)
            vince = g_a * (1.0 - g_b)
            perde = (1.0 - g_a) * g_b
            return 0.5 if vince + perde == 0 else vince / (vince + perde)
        # Il tie-break lo apre chi avrebbe servito il game successivo.
        return _tiebreak(0, 0, p, q, serve_a, 7)
    if a == 7 or b == 7:
        return 1.0 if a == 7 else 0.0

    tiene = prob_game(p) if serve_a else 1.0 - prob_game(q)
    return tiene * _set(a + 1, b, p, q, not serve_a, tiebreak) + (1.0 - tiene) * _set(
        a, b + 1, p, q, not serve_a, tiebreak
    )


def prob_set(p: float, q: float, tiebreak: bool = True) -> float:
    """Probabilita' che A vinca un set, dati i due servizi. A serve per primo."""
    return _set(0, 0, round(p, 6), round(q, 6), True, tiebreak)


def prob_match(p: float, q: float, al_meglio_di: int = 3) -> float:
    """Probabilita' che A vinca il match.

    I set sono trattati come indipendenti: e' l'approssimazione standard, e
    l'errore che introduce e' piccolo rispetto a quello sulla stima di p e q.
    """
    if al_meglio_di not in (3, 5):
        raise ValueError("si gioca al meglio di 3 o di 5")
    s = prob_set(p, q)
    if al_meglio_di == 3:
        return s * s * (1.0 + 2.0 * (1.0 - s))
    return s**3 * (1.0 + 3.0 * (1.0 - s) + 6.0 * (1.0 - s) ** 2)


# ---------------------------------------------------------------- da Elo a punto


def _servizi_da_elo(
    elo_a: float, elo_b: float, superficie: str, al_meglio_di: int
) -> tuple[float, float]:
    """Trova i due servizi coerenti con la differenza di Elo.

    L'Elo da' direttamente la probabilita' di vittoria del match. Qui si cerca
    per bisezione lo scarto di servizio che, passato per game/set/match,
    riproduce quella probabilita'. Cosi' i due mondi restano coerenti: il
    modello punto-per-punto non contraddice mai il rating.
    """
    base = SERVIZIO_MEDIO.get(superficie, SERVIZIO_MEDIO[""])
    bersaglio = 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / ELO_SCALA))

    lo, hi = -0.20, 0.20
    for _ in range(60):
        d = (lo + hi) / 2.0
        p, q = base + d, base - d
        if prob_match(p, q, al_meglio_di) < bersaglio:
            lo = d
        else:
            hi = d
    d = (lo + hi) / 2.0
    return base + d, base - d


class ModelloTennis:
    """Elo per superficie, poi ricorsione dal punto al match."""

    sport = "tennis"
    nome = "elo-punto"

    def __init__(self, k: float = 24.0, k_esordienti: float = 40.0) -> None:
        self.k = k
        self.k_esordienti = k_esordienti
        self.giocatori: dict[str, Giocatore] = {}
        self.partite_usate = 0

    def fit(self, incontri: Sequence[Incontro], riferimento=None) -> "ModelloTennis":
        """Scorre le partite in ordine e aggiorna l'Elo.

        L'Elo si stima in un passaggio solo, in ordine cronologico: e' anche il
        motivo per cui e' onesto in backtest, perche' per costruzione non puo'
        guardare avanti.
        """
        for i in sorted(incontri, key=lambda x: x.data):
            superficie = i.campionato or ""
            a = self.giocatori.setdefault(i.casa, Giocatore(i.casa))
            b = self.giocatori.setdefault(i.ospite, Giocatore(i.ospite))
            ea = a.elo_su(superficie)
            eb = b.elo_su(superficie)
            atteso_a = 1.0 / (1.0 + 10.0 ** ((eb - ea) / ELO_SCALA))
            reale_a = 1.0 if i.punti_casa > i.punti_ospite else 0.0

            for g, atteso, reale in ((a, atteso_a, reale_a), (b, 1 - atteso_a, 1 - reale_a)):
                k = self.k_esordienti if g.partite < 30 else self.k
                delta = k * (reale - atteso)
                g.elo += delta
                if superficie:
                    g.elo_superficie[superficie] = (
                        g.elo_superficie.get(superficie, g.elo - delta) + delta
                    )
                g.partite += 1
            self.partite_usate += 1
        return self

    def predict(self, fixture: Fixture, al_meglio_di: int = 3) -> Prediction:
        superficie = fixture.campionato or ""
        for nome in (fixture.casa, fixture.ospite):
            if nome not in self.giocatori:
                raise KeyError(f"giocatore sconosciuto al modello: {nome!r}")
        a = self.giocatori[fixture.casa]
        b = self.giocatori[fixture.ospite]
        p, q = _servizi_da_elo(
            a.elo_su(superficie), b.elo_su(superficie), superficie, al_meglio_di
        )
        p_match = prob_match(p, q, al_meglio_di)
        p_set = prob_set(p, q)

        pred = Prediction(
            fixture_id=fixture.id,
            sport=self.sport,
            modello=self.nome,
            generato_il=datetime.now(timezone.utc),
            mercati={MERCATO_ML: {"casa": p_match, "ospite": 1.0 - p_match}},
            dettaglio={
                "elo_casa": a.elo_su(superficie),
                "elo_ospite": b.elo_su(superficie),
                "servizio_casa": p,
                "servizio_ospite": q,
                "p_set_casa": p_set,
                "superficie": superficie,
                "al_meglio_di": al_meglio_di,
            },
        )
        pred.verifica()
        return pred

    def classifica(self, superficie: str = "") -> list[tuple[str, float, int]]:
        return sorted(
            ((g.id, g.elo_su(superficie), g.partite) for g in self.giocatori.values()),
            key=lambda r: r[1],
            reverse=True,
        )
