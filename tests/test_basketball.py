"""Basket: forze, ritmo, e i mercati che escono dalla normale."""

from datetime import datetime, timezone

import numpy as np
import pytest

from engine.core.types import Fixture
from engine.sports.basketball.model import ModelloBasket
from tests.conftest import (
    SIGMA_MARGINE_VERO,
    SQUADRE_BASKET,
    TOTALE_BASE_VERO,
    VANTAGGIO_CASA_BASKET,
)


def test_ritrova_forze_e_vantaggio_del_campo(stagione_basket):
    """Come nel calcio, si stima senza decadimento: le forze simulate sono fisse."""
    m = ModelloBasket(xi=0.0).fit(stagione_basket)

    assert m.vantaggio_casa == pytest.approx(VANTAGGIO_CASA_BASKET, abs=1.0)
    assert m.sigma_margine == pytest.approx(SIGMA_MARGINE_VERO, rel=0.10)

    veri = np.array([dict((n, f) for n, f, _ in SQUADRE_BASKET)[s] for s in m.squadre])
    stimati = np.array([float(m.forza[m._indice[s]]) for s in m.squadre])
    r = float(np.corrcoef(veri, stimati)[0, 1])
    scarto = float(np.abs(stimati - veri).mean())
    assert r > 0.93, f"forze ricostruite male: r = {r:.2f}"
    # Meno di un punto e mezzo di errore medio su rating che vanno da -5,5 a +7,5.
    assert scarto < 1.5, f"forze imprecise: scarto medio {scarto:.2f} punti"


def test_ritrova_il_ritmo_e_il_totale_base(stagione_basket):
    """Il ritmo e' un modello separato, con segnale piu' debole e piu' rumore.

    Ci si aspetta meno precisione che sulle forze: e' la ragione per cui usa
    una regolarizzazione piu' forte, non un difetto da nascondere.
    """
    m = ModelloBasket(xi=0.0).fit(stagione_basket)

    veri = {nome: ritmo for nome, _, ritmo in SQUADRE_BASKET}
    stimati = {s: float(m.ritmo[m._indice[s]]) for s in m.squadre}
    r = np.corrcoef([veri[s] for s in m.squadre], [stimati[s] for s in m.squadre])[0, 1]
    assert r > 0.85, f"ritmi ricostruiti male: r = {r:.2f}"

    # Due squadre di ritmo medio devono dare un totale vicino alla base vera:
    # e' il controllo che il ricentraggio non abbia spostato il livello.
    _, totale = m.attese("Venezia", "Reggio")
    assert totale == pytest.approx(TOTALE_BASE_VERO, abs=4.0)


def test_i_mercati_sommano_a_uno(stagione_basket):
    m = ModelloBasket().fit(stagione_basket)
    f = Fixture(
        id="b-test",
        data=datetime(2026, 3, 1, 18, 0, tzinfo=timezone.utc),
        casa="Milano",
        ospite="Pistoia",
        campionato="LBA",
    )
    p = m.predict(f)
    p.verifica()
    assert p.sport == "basket"
    # Milano in casa contro l'ultima: nettamente favorita.
    assert p.probabilita("ml", "casa") > 0.85


def test_l_handicap_e_monotono_nella_linea(stagione_basket):
    """Piu' punti devi dare, meno e' probabile che copra. Se non vale, c'e' un segno girato."""
    m = ModelloBasket().fit(stagione_basket)
    f = Fixture(
        id="b-hcp",
        data=datetime(2026, 3, 1, 18, 0, tzinfo=timezone.utc),
        casa="Milano",
        ospite="Cremona",
    )
    p = m.predict(f, handicap=(-12.5, -5.5, 0.5, 5.5))
    prob = [p.probabilita(f"hcp_{l:+g}", "copre") for l in (-12.5, -5.5, 0.5, 5.5)]
    assert prob == sorted(prob), f"handicap non monotono: {prob}"


def test_l_over_e_monotono_nella_soglia(stagione_basket):
    m = ModelloBasket().fit(stagione_basket)
    f = Fixture(
        id="b-ou",
        data=datetime(2026, 3, 1, 18, 0, tzinfo=timezone.utc),
        casa="Trento",
        ospite="Trieste",
    )
    p = m.predict(f, linee_totale=(150.5, 165.5, 180.5))
    prob = [p.probabilita(f"ou_{l:g}", "over") for l in (150.5, 165.5, 180.5)]
    assert prob == sorted(prob, reverse=True), f"over non monotono: {prob}"


def test_il_campo_neutro_conta(stagione_basket):
    m = ModelloBasket().fit(stagione_basket)
    con_campo, _ = m.attese("Venezia", "Brescia", neutro=False)
    senza, _ = m.attese("Venezia", "Brescia", neutro=True)
    assert con_campo - senza == pytest.approx(m.vantaggio_casa)


def test_i_punti_attesi_tornano_col_totale(stagione_basket):
    """punti_casa + punti_ospite deve fare il totale, e la differenza il margine."""
    m = ModelloBasket().fit(stagione_basket)
    f = Fixture(
        id="b-somma",
        data=datetime(2026, 3, 1, 18, 0, tzinfo=timezone.utc),
        casa="Bologna",
        ospite="Napoli",
    )
    d = m.predict(f).dettaglio
    assert d["punti_attesi_casa"] + d["punti_attesi_ospite"] == pytest.approx(
        d["totale_atteso"]
    )
    assert d["punti_attesi_casa"] - d["punti_attesi_ospite"] == pytest.approx(
        d["margine_atteso"]
    )


def test_squadra_sconosciuta(stagione_basket):
    m = ModelloBasket().fit(stagione_basket)
    with pytest.raises(KeyError):
        m.attese("Milano", "Real Madrid")
