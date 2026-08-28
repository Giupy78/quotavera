"""Le statistiche di squadra: separazione casa/trasferta e conversione."""

from datetime import date, timedelta

import pytest

from engine.core.types import Incontro
from engine.dati.football_data import PartitaStorica, Statistiche
from engine.statistiche import calcola, conversione_media, precedenti


def partita(casa, ospite, gc, go, giorno=1, tiri=(10, 8), in_porta=(4, 3)):
    return PartitaStorica(
        incontro=Incontro(
            f"m{giorno}", date(2025, 9, 1) + timedelta(days=giorno),
            casa, ospite, gc, go, "Serie A",
        ),
        quote={},
        stat=Statistiche(tiri=tiri, in_porta=in_porta, corner=(5, 4),
                         falli=(12, 11), gialli=(2, 1), rossi=(0, 0),
                         gol_primo_tempo=(1, 0), completa=True),
    )


def test_casa_e_trasferta_restano_separate():
    """È la distinzione che serve al lettore: la media complessiva nasconde tutto."""
    partite = [
        partita("Inter", "Como", 3, 0, 1),
        partita("Inter", "Roma", 2, 1, 2),
        partita("Lazio", "Inter", 1, 0, 3),      # Inter in trasferta, perde
    ]
    s = calcola(partite)["Inter"]

    assert s.casa.partite == 2
    assert s.trasferta.partite == 1
    assert s.casa.gol_fatti_partita == pytest.approx(2.5)
    assert s.trasferta.gol_fatti_partita == pytest.approx(0.0)
    assert s.partite == 3
    assert s.gol_fatti_partita == pytest.approx(5 / 3)


def test_il_vantaggio_casa_e_la_differenza_fra_i_due_ruoli():
    partite = [partita("Inter", "Como", 3, 0, 1), partita("Lazio", "Inter", 1, 1, 2)]
    s = calcola(partite)["Inter"]
    assert s.vantaggio_casa == pytest.approx(3.0 - 1.0)


def test_over_gol_gol_e_porta_inviolata():
    partite = [
        partita("Inter", "Como", 3, 0, 1),      # over, no gol/gol, clean sheet
        partita("Inter", "Roma", 1, 1, 2),      # under, gol/gol
        partita("Inter", "Lecce", 0, 2, 3),     # under, no gol/gol, a secco
    ]
    c = calcola(partite)["Inter"].casa
    assert c.over_25 == 1
    assert c.gol_gol == 1
    assert c.clean_sheet == 1
    assert c.a_secco == 1
    assert c.quota_over_25 == pytest.approx(1 / 3)


def test_la_conversione_e_gol_su_tiri_in_porta():
    partite = [
        partita("Inter", "Como", 4, 0, 1, in_porta=(8, 2)),
        partita("Inter", "Roma", 2, 1, 2, in_porta=(4, 3)),
    ]
    s = calcola(partite)["Inter"]
    assert s.gol_totali == 6
    assert s.in_porta_totali == 12
    assert s.conversione == pytest.approx(0.5)


def test_lo_scarto_dalla_conversione_smaschera_la_fortuna():
    """Sei gol su dodici tiri in porta, contro una media del 30%: sta sopra."""
    partite = [
        partita("Inter", "Como", 4, 0, 1, in_porta=(8, 2)),
        partita("Inter", "Roma", 2, 1, 2, in_porta=(4, 3)),
    ]
    s = calcola(partite)["Inter"]
    # attesi = 12 * 0.30 = 3.6, fatti 6 -> +2.4
    assert s.scarto_dalla_conversione(0.30) == pytest.approx(2.4)

    # Una squadra che segna esattamente la media ha scarto nullo.
    magre = [partita("Empoli", "Lecce", 3, 0, 1, in_porta=(10, 2))]
    assert calcola(magre)["Empoli"].scarto_dalla_conversione(0.30) == pytest.approx(0.0)


def test_ultime_conta_le_partite_di_ogni_squadra_non_del_campionato():
    """Ogni squadra ha il suo calendario: 'ultime 2' deve valere per ciascuna."""
    partite = [
        partita("Inter", "Como", 1, 0, 1),
        partita("Roma", "Lazio", 2, 2, 2),
        partita("Inter", "Roma", 3, 0, 3),
        partita("Como", "Lazio", 0, 1, 4),
        partita("Inter", "Lazio", 1, 1, 5),
    ]
    ultime = calcola(partite, ultime=2)
    assert ultime["Inter"].partite == 2          # le sue ultime due
    assert ultime["Inter"].gol_totali == 4       # 3-0 e 1-1
    assert ultime["Como"].partite == 2
    assert ultime["Lazio"].partite == 2


def test_le_partite_senza_statistiche_contano_per_i_gol_ma_non_per_i_tiri():
    """Nelle stagioni vecchie mancano i tiri: i gol devono comunque contare."""
    con = partita("Inter", "Como", 2, 0, 1)
    senza = PartitaStorica(
        incontro=Incontro("x", date(2025, 9, 5), "Inter", "Roma", 1, 1, "Serie A"),
        quote={},
        stat=Statistiche(),      # completa=False
    )
    s = calcola([con, senza])["Inter"]
    assert s.casa.partite == 2
    assert s.casa.gol_fatti == 3
    assert s.casa.con_statistiche == 1
    # La media tiri usa solo la partita che li ha, non divide per due.
    assert s.casa.in_porta_partita == pytest.approx(4.0)


def test_conversione_media_del_campionato():
    partite = [
        partita("A", "B", 2, 1, 1, in_porta=(5, 5)),    # 3 gol su 10
        partita("C", "D", 1, 0, 2, in_porta=(6, 4)),    # 1 gol su 10
    ]
    assert conversione_media(partite) == pytest.approx(4 / 20)


def test_precedenti_prende_entrambi_i_campi():
    partite = [
        partita("Inter", "Como", 2, 0, 1),
        partita("Como", "Inter", 1, 1, 2),
        partita("Inter", "Roma", 3, 0, 3),
    ]
    p = precedenti(partite, "Inter", "Como")
    assert len(p) == 2
    # Il più recente per primo.
    assert p[0].incontro.casa == "Como"
