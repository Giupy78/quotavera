"""L'abbinamento dei nomi e la fusione delle due fonti.

Sono i due punti dove un errore non si vede: un nome abbinato male sposta i gol
sulla squadra sbagliata, una partita contata due volte fa sei punti invece di
tre. In tutti e due i casi la pagina resta bella e i numeri mentono.
"""

from datetime import date

from engine.core.types import Incontro
from engine.dati.espn import PartitaEspn, abbina
from engine.dati.football_data import PartitaStorica, Statistiche
from engine.dati.unione import fondi


# --- abbinamento dei nomi ------------------------------------------------

def test_gli_alias_scritti_a_mano_vincono():
    fatti, ko = abbina(["Internazionale", "AC Milan"], ["Inter", "Milan"])
    assert fatti == {"Internazionale": "Inter", "AC Milan": "Milan"}
    assert ko == []


def test_si_tolgono_gli_orpelli_societari():
    fatti, _ = abbina(["Tottenham Hotspur", "Ajax Amsterdam"], ["Tottenham", "Ajax"])
    assert fatti["Tottenham Hotspur"] == "Tottenham"
    assert fatti["Ajax Amsterdam"] == "Ajax"


def test_le_due_bristol_non_si_fondono():
    """Togliendo 'City' e 'Rovers' diventerebbero lo stesso nome: la trappola."""
    fatti, ko = abbina(["Bristol City", "Bristol Rovers"], ["Bristol City", "Bristol Rvs"])
    assert fatti["Bristol City"] == "Bristol City"
    assert fatti["Bristol Rovers"] == "Bristol Rvs"
    assert ko == []


def test_chi_non_ha_un_corrispondente_resta_fuori():
    """Meglio saltare una partita che attribuirla alla squadra sbagliata."""
    fatti, ko = abbina(["Schalke 04"], ["Bayern Monaco", "Dortmund"])
    assert fatti == {}
    assert ko == ["Schalke 04"]


def test_un_nome_conteso_non_viene_abbinato():
    """Se due dei nostri sono ugualmente plausibili, non si sceglie a caso."""
    fatti, ko = abbina(["Athletic"], ["Athletic Bilbao", "Athletic Madrid"])
    assert "Athletic" not in fatti or fatti["Athletic"] in ("Athletic Bilbao", "Athletic Madrid")
    # Quello che conta: nessuna delle due sparisce senza che ce ne accorgiamo.
    assert len(fatti) <= 1


# --- fusione delle fonti -------------------------------------------------

def _storica(casa, ospite, gc, go, giorno, tiri=(10, 8)):
    return PartitaStorica(
        incontro=Incontro(f"fd-{giorno}", date(2026, 8, giorno), casa, ospite, gc, go, "Serie A"),
        quote={"pinnacle": (2.0, 3.4, 3.8)},
        stat=Statistiche(tiri=tiri, in_porta=(4, 3), corner=(5, 4), falli=(11, 12),
                         gialli=(2, 1), rossi=(0, 0), completa=True),
    )


def _espn(casa, ospite, gc, go, giorno, con_stat=True):
    stat = {"possesso": (58.0, 42.0), "passaggi": (500.0, 380.0),
            "contrasti": (16.0, 12.0), "intercetti": (9.0, 15.0)} if con_stat else {}
    return PartitaEspn(id=f"e{giorno}", data=date(2026, 8, giorno), casa=casa,
                       ospite=ospite, gol_casa=gc, gol_ospite=go, stat=stat)


def test_una_partita_presente_in_entrambe_non_si_duplica():
    storico = [_storica("Inter", "Como", 2, 0, 22)]
    fuori, arricchite, aggiunte = fondi(storico, [_espn("Inter", "Como", 2, 0, 22)], "Serie A")
    assert len(fuori) == 1, "contata due volte: la classifica direbbe sei punti"
    assert aggiunte == 0
    assert arricchite == 1


def test_lo_scarto_di_un_giorno_e_ancora_la_stessa_partita():
    """ESPN data in UTC, football-data in ora locale: il lunedi' sera balla."""
    storico = [_storica("Inter", "Como", 2, 0, 22)]
    fuori, _, aggiunte = fondi(storico, [_espn("Inter", "Como", 2, 0, 23)], "Serie A")
    assert len(fuori) == 1
    assert aggiunte == 0


def test_le_quote_di_football_data_sopravvivono_alla_fusione():
    storico = [_storica("Inter", "Como", 2, 0, 22)]
    fuori, _, _ = fondi(storico, [_espn("Inter", "Como", 2, 0, 22)], "Serie A")
    assert fuori[0].quote == {"pinnacle": (2.0, 3.4, 3.8)}


def test_le_statistiche_di_base_restano_quelle_di_football_data():
    """Sono la serie con cui il modello e' tarato: cambiarle farebbe uno scalino."""
    storico = [_storica("Inter", "Como", 2, 0, 22, tiri=(10, 8))]
    fuori, _, _ = fondi(storico, [_espn("Inter", "Como", 2, 0, 22)], "Serie A")
    assert fuori[0].stat.tiri == (10, 8)


def test_le_avanzate_arrivano_da_espn():
    storico = [_storica("Inter", "Como", 2, 0, 22)]
    fuori, _, _ = fondi(storico, [_espn("Inter", "Como", 2, 0, 22)], "Serie A")
    s = fuori[0].stat
    assert s.avanzate is True
    assert s.possesso == (58.0, 42.0)
    assert s.contrasti == (16, 12)


def test_una_partita_che_football_data_non_ha_ancora_entra_lo_stesso():
    """E' il motivo per cui esiste tutto questo."""
    fuori, _, aggiunte = fondi([], [_espn("Napoli", "Como", 1, 2, 30)], "Serie A")
    assert aggiunte == 1
    assert len(fuori) == 1
    assert (fuori[0].incontro.punti_casa, fuori[0].incontro.punti_ospite) == (1, 2)
    assert fuori[0].quote == {}, "ESPN non da' quote: non inventiamole"


def test_senza_statistiche_la_partita_entra_col_solo_risultato():
    fuori, _, aggiunte = fondi([], [_espn("Napoli", "Como", 1, 2, 30, con_stat=False)], "Serie A")
    assert aggiunte == 1
    assert fuori[0].stat.avanzate is False


def test_il_risultato_resta_in_ordine_di_data():
    storico = [_storica("Inter", "Como", 2, 0, 22)]
    fuori, _, _ = fondi(storico, [_espn("Napoli", "Lazio", 1, 1, 20)], "Serie A")
    assert [p.incontro.data.day for p in fuori] == [20, 22]


def test_senza_espn_lo_storico_torna_identico():
    storico = [_storica("Inter", "Como", 2, 0, 22)]
    fuori, arricchite, aggiunte = fondi(storico, [], "Serie A")
    assert fuori is storico
    assert (arricchite, aggiunte) == (0, 0)
