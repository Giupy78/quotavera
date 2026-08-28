"""Tennis: dal punto al match, e l'Elo che tiene i due mondi coerenti."""

from datetime import datetime, timezone

import pytest

from engine.core.types import Fixture
from engine.sports.tennis.model import (
    ModelloTennis,
    _servizi_da_elo,
    prob_game,
    prob_match,
    prob_set,
)


# ------------------------------------------------------------------- il game


def test_il_game_a_meta_punti_e_una_moneta():
    assert prob_game(0.5) == pytest.approx(0.5)


def test_il_game_amplifica_il_vantaggio_sul_punto():
    """E' il fatto centrale del tennis: un punto in piu' su cento vale molto di piu'.

    Con il 65% dei punti al servizio — la media del circuito — si tiene il
    servizio circa l'83% delle volte. Il punteggio moltiplica le differenze.
    """
    assert prob_game(0.65) == pytest.approx(0.830, abs=0.01)
    assert prob_game(0.60) == pytest.approx(0.736, abs=0.01)
    assert prob_game(0.55) == pytest.approx(0.623, abs=0.01)


def test_il_game_e_monotono():
    valori = [prob_game(p) for p in (0.40, 0.50, 0.60, 0.70, 0.80)]
    assert valori == sorted(valori)


# ------------------------------------------------------------- set e match


def test_fra_pari_il_set_e_quasi_una_moneta():
    """Non esattamente: chi serve per primo ha un vantaggio piccolo ma reale."""
    p = prob_set(0.65, 0.65)
    assert 0.50 <= p < 0.53


def test_il_set_amplifica_ancora():
    """Quattro punti percentuali sul servizio diventano tredici sul set.

    0.67 contro 0.63 vuol dire tenere il servizio l'85,5% contro il 79%: sembra
    poco, ma sul set diventa circa 63-37. E' il moltiplicatore del punteggio.
    """
    p = prob_set(0.67, 0.63)
    assert 0.60 < p < 0.66
    assert p > prob_game(0.67) - prob_game(0.63) + 0.5  # amplifica, non somma


def test_il_match_amplifica_piu_del_set():
    p_set = prob_set(0.67, 0.63)
    p_3 = prob_match(0.67, 0.63, al_meglio_di=3)
    p_5 = prob_match(0.67, 0.63, al_meglio_di=5)
    assert p_3 > p_set
    assert p_5 > p_3, "al meglio di 5 il favorito deve stare ancora meglio"


def test_il_match_e_monotono_nel_servizio():
    valori = [prob_match(p, 0.65) for p in (0.60, 0.63, 0.65, 0.67, 0.70)]
    assert valori == sorted(valori)


def test_al_meglio_di_quanti():
    with pytest.raises(ValueError):
        prob_match(0.65, 0.65, al_meglio_di=4)


# ------------------------------------------------------------------- da Elo


def test_l_elo_e_il_modello_a_punti_dicono_la_stessa_cosa():
    """La bisezione deve chiudere il cerchio: se non torna, i due mondi divergono."""
    for scarto in (0, 50, 150, 300):
        atteso = 1.0 / (1.0 + 10.0 ** (-scarto / 400.0))
        p, q = _servizi_da_elo(1500 + scarto, 1500, "cemento", 3)
        assert prob_match(p, q, 3) == pytest.approx(atteso, abs=0.005)


def test_la_superficie_cambia_il_peso_del_servizio():
    """Sull'erba il servizio pesa di piu': stesso Elo, servizi piu' alti."""
    p_erba, _ = _servizi_da_elo(1600, 1500, "erba", 3)
    p_terra, _ = _servizi_da_elo(1600, 1500, "terra", 3)
    assert p_erba > p_terra


# ---------------------------------------------------------------- il modello


def test_l_elo_ordina_i_giocatori_come_le_loro_forze(storico_tennis):
    """Dati solo vittorie e sconfitte, l'Elo deve ricostruire la gerarchia."""
    m = ModelloTennis().fit(storico_tennis)
    classifica = [g for g, _, _ in m.classifica("cemento")]
    # I giocatori sono G00 (il piu' forte) ... G19 (il piu' debole).
    assert classifica[0] in {"G00", "G01", "G02"}
    assert classifica[-1] in {"G17", "G18", "G19"}

    import numpy as np

    posizione_vera = [int(g[1:]) for g in classifica]
    r = np.corrcoef(posizione_vera, range(len(classifica)))[0, 1]
    assert r > 0.90, f"gerarchia ricostruita male: r = {r:.2f}"


def test_la_previsione_somma_a_uno(storico_tennis):
    m = ModelloTennis().fit(storico_tennis)
    f = Fixture(
        id="t-test",
        data=datetime(2026, 5, 20, 13, 0, tzinfo=timezone.utc),
        casa="G00",
        ospite="G19",
        campionato="cemento",
    )
    p = m.predict(f, al_meglio_di=3)
    p.verifica()
    assert p.sport == "tennis"
    assert p.probabilita("ml", "casa") > 0.90
    assert p.dettaglio["servizio_casa"] > p.dettaglio["servizio_ospite"]


def test_giocatore_sconosciuto(storico_tennis):
    m = ModelloTennis().fit(storico_tennis)
    f = Fixture(
        id="t-x",
        data=datetime(2026, 5, 20, 13, 0, tzinfo=timezone.utc),
        casa="G00",
        ospite="Sconosciuto",
    )
    with pytest.raises(KeyError):
        m.predict(f)
