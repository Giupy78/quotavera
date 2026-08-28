"""Le metriche con cui il modello si giudica."""

import pytest

from engine.core.metrics import (
    brier,
    calibrazione,
    curva_rendimento,
    errore_calibrazione,
    log_loss,
    rendimento,
    ribasso_massimo,
)


def test_brier_di_un_oracolo_e_zero():
    assert brier([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], [0, 1]) == pytest.approx(0.0)


def test_brier_del_massimo_ignorante():
    """Chi dice sempre un terzo su tre esiti prende 2/3."""
    terzo = [1 / 3, 1 / 3, 1 / 3]
    assert brier([terzo] * 3, [0, 1, 2]) == pytest.approx(2 / 3)


def test_brier_punisce_chi_sbaglia_con_sicurezza():
    sicuro_e_giusto = brier([[0.9, 0.05, 0.05]], [0])
    sicuro_e_sbagliato = brier([[0.9, 0.05, 0.05]], [1])
    assert sicuro_e_sbagliato > sicuro_e_giusto


def test_log_loss_di_una_moneta():
    import math

    assert log_loss([[0.5, 0.5]], [0]) == pytest.approx(math.log(2))


def test_calibrazione_di_un_modello_onesto():
    """Se dico 30% e succede il 30% delle volte, lo scarto e' nullo."""
    dichiarate = [0.3] * 100
    avvenuti = [True] * 30 + [False] * 70
    fasce = calibrazione(dichiarate, avvenuti, fasce=10)
    assert len(fasce) == 1
    assert fasce[0].osservata == pytest.approx(0.30)
    assert fasce[0].scarto == pytest.approx(0.0)
    assert fasce[0].casi == 100


def test_calibrazione_smaschera_chi_e_troppo_sicuro():
    dichiarate = [0.8] * 100
    avvenuti = [True] * 55 + [False] * 45   # dice 80%, succede il 55%
    fasce = calibrazione(dichiarate, avvenuti)
    assert fasce[0].scarto == pytest.approx(-0.25)
    assert errore_calibrazione(fasce) == pytest.approx(0.25)


def test_calibrazione_salta_le_fasce_vuote():
    fasce = calibrazione([0.05, 0.95], [False, True], fasce=10)
    assert len(fasce) == 2


def test_rendimento_su_giocate_note():
    # Tre giocate da 1: due perse, una vinta a 4.00. Profitto +1 su 3 giocati.
    profitto, roi = rendimento([1, 1, 1], [4.0, 4.0, 4.0], [False, False, True])
    assert profitto == pytest.approx(1.0)
    assert roi == pytest.approx(1 / 3)


def test_rendimento_di_una_serie_perdente():
    profitto, roi = rendimento([1, 1], [2.0, 2.0], [False, False])
    assert profitto == pytest.approx(-2.0)
    assert roi == pytest.approx(-1.0)


def test_curva_e_ribasso():
    curva = curva_rendimento([1, 1, 1], [3.0, 3.0, 3.0], [True, False, False])
    assert curva[0] == 0.0
    assert curva[1] == pytest.approx(2.0)       # +2 su 1 giocato
    assert curva[-1] == pytest.approx(0.0)      # +2 -1 -1 su 3 giocati
    assert ribasso_massimo(curva) == pytest.approx(-2.0)


def test_ribasso_di_una_curva_sempre_in_salita():
    assert ribasso_massimo([0.0, 0.1, 0.2, 0.3]) == pytest.approx(0.0)
