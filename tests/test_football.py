"""Calcio: la matrice, i mercati che ne discendono, e il recupero dei parametri."""

from datetime import datetime, timezone

import numpy as np
import pytest

from engine.core.types import Fixture
from engine.sports.football.model import (
    ModelloCalcio,
    esiti_1x2,
    gol_gol,
    matrice_da_lambde,
    over_under,
)
from tests.conftest import SQUADRE_CALCIO, VANTAGGIO_CASA_VERO


# ------------------------------------------------------------------- la matrice


def test_la_matrice_somma_a_uno():
    m = matrice_da_lambde(1.62, 1.18, rho=-0.06)
    assert m.sum() == pytest.approx(1.0)
    assert (m >= 0).all()


def test_senza_correzione_e_due_poisson_indipendenti():
    """Con rho = 0 la cella i-j deve essere il prodotto delle due Poisson."""
    lh, la = 1.4, 1.1
    m = matrice_da_lambde(lh, la, rho=0.0, max_gol=12)
    import math

    atteso = (math.exp(-lh) * lh**2 / 2) * (math.exp(-la) * la**1 / 1)
    assert m[2, 1] == pytest.approx(atteso, rel=1e-6)


def test_la_correzione_alza_i_punteggi_bassi():
    """E' tutto il senso di Dixon-Coles: 0-0 e 1-1 sono piu' frequenti."""
    lh, la = 1.5, 1.2
    senza = matrice_da_lambde(lh, la, rho=0.0)
    con = matrice_da_lambde(lh, la, rho=-0.08)
    assert con[0, 0] > senza[0, 0]
    assert con[1, 1] > senza[1, 1]
    assert con[1, 0] < senza[1, 0]
    assert con[0, 1] < senza[0, 1]


def test_i_mercati_sono_somme_della_stessa_matrice():
    m = matrice_da_lambde(1.62, 1.18, rho=-0.06)
    uno_x_due = esiti_1x2(m)
    assert sum(uno_x_due.values()) == pytest.approx(1.0)
    # La casa e' favorita quando segna di piu'.
    assert uno_x_due["1"] > uno_x_due["2"]

    ou = over_under(m, 2.5)
    assert sum(ou.values()) == pytest.approx(1.0)
    # Con 2.8 gol attesi l'over 2.5 e' poco sopra la meta'.
    assert 0.45 < ou["over"] < 0.60

    # Coerenza fra soglie: over 1.5 e' sempre piu' probabile di over 3.5.
    assert over_under(m, 1.5)["over"] > over_under(m, 3.5)["over"]

    gg = gol_gol(m)
    assert sum(gg.values()) == pytest.approx(1.0)


def test_over_e_gol_gol_non_sono_lo_stesso_mercato():
    """0-3 e' over 2.5 ma non gol/gol: se coincidessero ci sarebbe un errore."""
    m = matrice_da_lambde(1.5, 1.5, rho=-0.05)
    assert over_under(m, 2.5)["over"] != pytest.approx(gol_gol(m)["si"], abs=0.01)


# ------------------------------------------------------- il recupero dei parametri


def test_ritrova_i_parametri_da_cui_e_stata_generata_la_stagione(stagione_calcio):
    """La prova del nove: dati solo i risultati, il modello risale alle forze.

    Si stima senza decadimento nel tempo, perche' nella simulazione le forze
    sono costanti: pesare meno il passato qui butterebbe via informazione buona
    e renderebbe il test una misura del decadimento invece che dello stimatore.
    """
    m = ModelloCalcio(xi=0.0).fit(stagione_calcio)

    assert m.partite_usate == len(stagione_calcio)
    # Il vantaggio del campo vero era 0.26 in scala log.
    assert m.vantaggio_casa == pytest.approx(VANTAGGIO_CASA_VERO, abs=0.07)

    # Due controlli diversi: la correlazione dice se l'ordine e' giusto, lo
    # scarto medio se lo sono anche le distanze. Un modello con un segno girato
    # fallisce il primo; uno che schiaccia tutti verso la media, il secondo.
    veri = np.array([dict((n, a) for n, a, _ in SQUADRE_CALCIO)[s] for s in m.squadre])
    stimati = np.array([float(m.attacco[m._indice[s]]) for s in m.squadre])
    r_att = float(np.corrcoef(veri, stimati)[0, 1])
    scarto_att = float(np.abs((stimati - stimati.mean()) - (veri - veri.mean())).mean())
    assert r_att > 0.90, f"attacchi ricostruiti male: r = {r_att:.2f}"
    assert scarto_att < 0.10, f"attacchi imprecisi: scarto medio {scarto_att:.3f}"

    veri_d = np.array([dict((n, d) for n, _, d in SQUADRE_CALCIO)[s] for s in m.squadre])
    stimati_d = np.array([float(m.difesa[m._indice[s]]) for s in m.squadre])
    r_dif = float(np.corrcoef(veri_d, stimati_d)[0, 1])
    scarto_dif = float(
        np.abs((stimati_d - stimati_d.mean()) - (veri_d - veri_d.mean())).mean()
    )
    assert r_dif > 0.85, f"difese ricostruite male: r = {r_dif:.2f}"
    assert scarto_dif < 0.10, f"difese imprecise: scarto medio {scarto_dif:.3f}"


def test_il_vincolo_sugli_attacchi_e_rispettato(stagione_calcio):
    """Senza somma zero il modello e' indeterminato: qui si controlla che regga."""
    m = ModelloCalcio().fit(stagione_calcio)
    assert m.attacco.sum() == pytest.approx(0.0, abs=1e-6)


def test_il_peso_nel_tempo_segue_i_cambiamenti(calcio_con_svolta):
    """Il decadimento non e' un ornamento: e' cio' che rende il modello reattivo.

    Nella storia simulata il Lecce diventa fortissimo a meta' percorso. Il
    modello che pesa il recente deve accorgersene; quello che tratta tutte le
    partite allo stesso modo resta indietro di mezza stagione.
    """
    reattivo = ModelloCalcio(xi=0.004).fit(calcio_con_svolta)
    piatto = ModelloCalcio(xi=0.0).fit(calcio_con_svolta)

    att_reattivo = float(reattivo.attacco[reattivo._indice["Lecce"]])
    att_piatto = float(piatto.attacco[piatto._indice["Lecce"]])
    assert att_reattivo > att_piatto, (
        f"il decadimento non serve a niente: reattivo {att_reattivo:.3f} "
        f"contro piatto {att_piatto:.3f}"
    )


def test_la_previsione_e_completa_e_coerente(stagione_calcio):
    m = ModelloCalcio().fit(stagione_calcio)
    f = Fixture(
        id="test-1",
        data=datetime(2026, 9, 1, 20, 45, tzinfo=timezone.utc),
        casa="Inter",
        ospite="Lecce",
        campionato="Serie A",
    )
    p = m.predict(f)

    p.verifica()   # ogni mercato somma a 1
    assert p.sport == "calcio"
    assert set(p.mercati) >= {"1x2", "btts", "ou_2.5"}
    # L'Inter in casa contro l'ultima in classifica deve essere nettamente favorita.
    assert p.probabilita("1x2", "1") > 0.60
    assert p.dettaglio["gol_attesi_casa"] > p.dettaglio["gol_attesi_ospite"]
    assert len(p.dettaglio["risultati_probabili"]) == 5


def test_il_campo_neutro_toglie_il_vantaggio(stagione_calcio):
    m = ModelloCalcio().fit(stagione_calcio)
    normale = m.matrice("Roma", "Lazio", neutro=False)
    neutro = m.matrice("Roma", "Lazio", neutro=True)
    assert esiti_1x2(normale)["1"] > esiti_1x2(neutro)["1"]


def test_la_tabella_delle_forze_e_ordinata(stagione_calcio):
    forze = ModelloCalcio().fit(stagione_calcio).forze()
    assert len(forze) == len(SQUADRE_CALCIO)
    differenze = [f.gol_attesi_fatti - f.gol_attesi_subiti for f in forze]
    assert differenze == sorted(differenze, reverse=True)
    # Le prime tre della lista vera devono stare nella meta' alta.
    prime = {f.squadra for f in forze[: len(forze) // 2]}
    assert {"Inter", "Napoli"} <= prime


def test_squadra_sconosciuta(stagione_calcio):
    m = ModelloCalcio().fit(stagione_calcio)
    with pytest.raises(KeyError):
        m.matrice("Inter", "Real Madrid")


def test_troppe_poche_partite():
    with pytest.raises(ValueError, match="almeno 20"):
        ModelloCalcio().fit([])
