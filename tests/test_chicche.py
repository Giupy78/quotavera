"""Le chicche statistiche.

Sono numeri che finiscono in pagina scritti in grande, quindi devono essere
giusti: una serie contata male o una rimonta attribuita alla squadra sbagliata
sono errori che nessuno verifica, perche' nessun altro pubblica quel dato.
"""

from datetime import date, timedelta

from engine import chicche
from engine.core.types import Incontro
from engine.dati.football_data import PartitaStorica, Statistiche


class FintoCampionato:
    nome = "Serie A"
    bandiera = "🇮🇹"
    slug = "serie-a"


C = FintoCampionato()


def partita(casa, ospite, gc, go, giorno, pt=(0, 0), quote=None):
    return PartitaStorica(
        incontro=Incontro(f"m{giorno}", date(2026, 1, 1) + timedelta(days=giorno),
                          casa, ospite, gc, go, "Serie A"),
        quote=quote or {},
        stat=Statistiche(tiri=(10, 8), in_porta=(4, 3), corner=(5, 4),
                         falli=(11, 12), gialli=(2, 1), rossi=(0, 0),
                         gol_primo_tempo=pt, completa=True),
    )


# --- serie aperte ---------------------------------------------------------

def test_una_serie_si_conta_all_indietro_e_si_ferma_alla_prima_sconfitta():
    partite = [
        partita("A", "B", 0, 3, 1),      # A perde: la serie parte da qui in poi
        partita("A", "C", 1, 0, 2),
        partita("D", "A", 1, 1, 3),
        partita("A", "E", 2, 0, 4),
        partita("F", "A", 0, 2, 5),
        partita("A", "G", 1, 1, 6),
        partita("H", "A", 0, 1, 7),
    ]
    trovate = chicche.serie_aperte(partite, C)
    imbattuta = next((x for x in trovate if x.tipo == "imbattuta"), None)
    assert imbattuta is not None
    assert imbattuta.squadre == ["A"]
    assert imbattuta.numero == "6", "la sconfitta iniziale non va contata"


def test_una_serie_corta_non_viene_pubblicata():
    """Tre partite senza perdere non sono una notizia."""
    partite = [partita("A", "B", 1, 0, n) for n in range(1, 4)]
    assert not [x for x in chicche.serie_aperte(partite, C) if x.tipo == "imbattuta"]


def test_le_squadre_di_un_altro_campionato_restano_fuori():
    partite = [partita("Retrocessa", "B", 1, 0, n) for n in range(1, 10)]
    trovate = chicche.serie_aperte(partite, C, squadre_attuali={"B"})
    assert all("Retrocessa" not in x.squadre for x in trovate)


def test_la_porta_inviolata_conta_i_gol_subiti_non_quelli_fatti():
    partite = [partita("A", f"S{n}", 0, 0, n) for n in range(1, 6)]
    trovate = {x.tipo: x for x in chicche.serie_aperte(partite, C)}
    assert "porta_chiusa" in trovate
    assert trovate["porta_chiusa"].numero == "5"
    # Cinque 0-0 di fila sono anche cinque partite senza segnare.
    assert trovate["a_secco"].numero == "5"


# --- rimonte --------------------------------------------------------------

def test_una_rimonta_e_sotto_all_intervallo_e_vittoria_alla_fine():
    partite = [
        # A sotto 0-1 al riposo, finisce 2-1: rimonta.
        partita("A", "B", 2, 1, n, pt=(0, 1)) for n in range(1, 5)
    ] + [
        # ... e quattro volte sotto senza rimontare, per avere il campione.
        partita("A", "C", 0, 1, n, pt=(0, 1)) for n in range(5, 10)
    ]
    trovate = {x.tipo: x for x in chicche.rimonte(partite, C)}
    assert "rimonte" in trovate
    r = trovate["rimonte"]
    assert r.squadre == ["A"]
    assert r.campione == 9, "nove volte sotto al riposo"
    assert r.numero == "44%", "quattro rimonte su nove"


def test_chi_e_avanti_e_non_vince_finisce_fra_i_fragili():
    partite = [
        partita("A", "B", 1, 2, n, pt=(1, 0)) for n in range(1, 6)
    ] + [
        partita("A", "C", 2, 0, n, pt=(1, 0)) for n in range(6, 11)
    ]
    trovate = {x.tipo: x for x in chicche.rimonte(partite, C)}
    assert "fragilita" in trovate
    assert trovate["fragilita"].squadre == ["A"]
    assert trovate["fragilita"].numero == "50%"


def test_le_partite_senza_statistiche_non_entrano_nelle_rimonte():
    """Senza i gol del primo tempo non si puo' dire se era sotto."""
    senza = PartitaStorica(
        incontro=Incontro("x", date(2026, 2, 1), "A", "B", 2, 1, "Serie A"),
        quote={}, stat=Statistiche(),          # completa=False
    )
    assert chicche.rimonte([senza] * 10, C) == []


# --- sorprese del mercato -------------------------------------------------

def test_la_sorpresa_e_tale_solo_sopra_la_soglia_di_quota():
    piccola = partita("A", "B", 1, 0, 1, quote={"pinnacle": (2.0, 3.4, 3.8)})
    grande = partita("C", "D", 0, 1, 2, quote={"pinnacle": (1.2, 6.0, 11.0)})
    trovate = chicche.sorprese_del_mercato([piccola, grande], C)
    assert len(trovate) == 1
    assert trovate[0].numero == "11.00"
    assert "D" in trovate[0].squadre


def test_la_sorpresa_dice_quando_e_successa():
    """Una chicca sul passato senza data non si puo' verificare."""
    p = partita("C", "D", 0, 1, 2, quote={"pinnacle": (1.2, 6.0, 11.0)})
    testo = chicche.sorprese_del_mercato([p], C)[0].testo
    assert "2026" in testo


def test_senza_quote_credibili_non_si_inventa_una_sorpresa():
    # Margine enorme: `riferimento()` scarta il libro e non resta niente.
    p = partita("C", "D", 0, 1, 2, quote={"pinnacle": (1.1, 1.1, 1.1)})
    assert chicche.sorprese_del_mercato([p], C) == []
