"""Il mercato: togliere il margine, misurare il valore."""

import pytest

from engine.core.market import (
    kelly,
    margine,
    probabilita_implicite,
    quota_equa,
    valore_atteso,
    valore_di_chiusura,
)


def test_margine_di_un_libro_tipico():
    # Un 1X2 di Serie A con circa il 4% di margine.
    quote = [2.15, 3.40, 3.55]
    assert margine(quote) == pytest.approx(0.041, abs=0.005)


@pytest.mark.parametrize("metodo", ["shin", "moltiplicativo", "additivo"])
def test_le_probabilita_sommano_a_uno(metodo):
    p = probabilita_implicite([2.15, 3.40, 3.55], metodo=metodo)
    assert sum(p) == pytest.approx(1.0)
    assert all(0.0 < x < 1.0 for x in p)


def test_shin_e_meno_generoso_sugli_esiti_lunghi():
    """Il punto per cui Shin e' il default.

    Sul metodo moltiplicativo il margine viene spalmato in proporzione, e
    l'esito improbabile finisce con una probabilita' gonfiata. Shin gliene
    assegna meno, che e' quello che i dati dicono succeda davvero.
    """
    quote = [1.20, 6.50, 15.0]
    molt = probabilita_implicite(quote, metodo="moltiplicativo")
    shin = probabilita_implicite(quote, metodo="shin")
    assert shin[2] < molt[2]      # il piu' lungo scende
    assert shin[0] > molt[0]      # il favorito sale


def test_un_libro_senza_margine_resta_invariato():
    quote = [2.0, 2.0]
    p = probabilita_implicite(quote)
    assert p == pytest.approx([0.5, 0.5])


def test_quote_non_valide():
    with pytest.raises(ValueError):
        probabilita_implicite([0.95, 3.0])
    with pytest.raises(ValueError):
        probabilita_implicite([2.0])


def test_quota_equa_e_inversa_della_probabilita():
    assert quota_equa(0.25) == pytest.approx(4.0)


def test_valore_atteso():
    # Probabilita' 0.35 a quota 3.25: +13,75% per euro giocato.
    assert valore_atteso(0.35, 3.25) == pytest.approx(0.1375)
    # Nessun vantaggio: valore atteso esattamente zero alla quota equa.
    assert valore_atteso(0.40, 2.5) == pytest.approx(0.0)


def test_kelly_e_zero_senza_vantaggio():
    assert kelly(0.40, 2.50) == 0.0
    assert kelly(0.30, 2.00) == 0.0


def test_kelly_frazionario_e_col_tetto():
    # p=0.35 a quota 3.25: b=2.25, Kelly pieno (0.35*2.25 - 0.65)/2.25 = 0.0611.
    # Un quarto fa 0.0153: meno del 2% del bankroll su un vantaggio del 13,75%.
    assert kelly(0.35, 3.25, frazione=0.25, cap=0.05) == pytest.approx(0.015278, abs=1e-5)
    # Vantaggio enorme: interviene il tetto.
    assert kelly(0.90, 3.00, frazione=0.25, cap=0.05) == 0.05


def test_valore_di_chiusura():
    # Presa a 2.10 e chiusa a 2.00: hai battuto la linea del 5%.
    assert valore_di_chiusura(2.10, 2.00) == pytest.approx(0.05)
    assert valore_di_chiusura(1.90, 2.00) == pytest.approx(-0.05)
