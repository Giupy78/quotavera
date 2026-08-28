"""Il lettore dei calendari di openfootball, senza toccare la rete."""

from datetime import date

import pytest

from engine.dati.openfootball import (
    FONTI,
    _chiave,
    leggi_alias,
    leggi_calendario,
    normalizza,
)

CALENDARIO = """= Italian Serie A 2026/27

# Date       Sat Aug 22 2026 - Sun May 30 2027
# Teams      20


▪ Matchday 1
  Sat Aug 22 2026
    18:30  Udinese Calcio          v Como 1907                1-1 (1-0)
           FC Internazionale Milano v AC Monza                 4-1 (1-1)
    20:45  Genoa CFC               v SSC Napoli               0-2 (0-0)
  Sun Aug 23
    18:30  Frosinone Calcio        v Juventus FC              0-1 (0-1)


▪ Matchday 2
  Fri Aug 28
    20:45  AC Milan                v Venezia FC
  Sat Aug 29
    18:30  US Sassuolo Calcio      v Torino FC
           AC Monza                v Udinese Calcio
  Sun Jan 3 2027
    --:--  SS Lazio                v Genoa CFC
"""

ALIASES = """==========================================
=  Italy

FC Internazionale Milano, Milano
  | Inter | Internazionale
  | Inter Mailand [de]

Atalanta Bergamo,            Bergamo
  | Atalanta | Atalanta BC

SSC Napoli,     Napoli
  | Napoli
  | SSC Neapel [de]
"""


def test_legge_le_giornate_dichiarate():
    """openfootball le scrive: non vanno dedotte, e questo e' il suo valore."""
    p = leggi_calendario(CALENDARIO)
    assert [x.giornata for x in p] == [1, 1, 1, 1, 2, 2, 2, 2]


def test_l_anno_si_eredita_dalla_prima_data():
    """Nel formato l'anno compare una volta sola: 'Sun Aug 23' e' il 2026."""
    p = leggi_calendario(CALENDARIO)
    assert p[0].data == date(2026, 8, 22)
    assert p[3].data == date(2026, 8, 23)      # senza anno scritto
    # E quando l'anno riappare, si aggiorna: gennaio e' il 2027.
    assert p[-1].data == date(2027, 1, 3)


def test_l_orario_si_eredita_dalla_riga_precedente():
    p = leggi_calendario(CALENDARIO)
    assert p[0].ora == "18:30"
    assert p[1].ora == "18:30"       # la riga non lo ripete
    assert p[2].ora == "20:45"


def test_il_segnaposto_di_orario_non_finisce_nel_nome():
    """`--:--` significa 'ora non ancora fissata', non e' parte della squadra."""
    ultima = leggi_calendario(CALENDARIO)[-1]
    assert ultima.ora == ""
    assert ultima.casa == "SS Lazio"


def test_legge_i_punteggi_solo_dove_ci_sono():
    p = leggi_calendario(CALENDARIO)
    assert (p[0].gol_casa, p[0].gol_ospite) == (1, 1)
    assert p[0].giocata
    # Le partite future non hanno punteggio.
    assert p[4].gol_casa is None
    assert not p[4].giocata
    assert p[4].casa == "AC Milan" and p[4].ospite == "Venezia FC"


def test_gli_alias_portano_al_nome_canonico():
    a = leggi_alias(ALIASES)
    assert normalizza("Inter", a) == "FC Internazionale Milano"
    assert normalizza("Napoli", a) == "SSC Napoli"
    # Le varianti in altre lingue si scartano: servono le forme che usa
    # football-data, non quelle tedesche.
    assert normalizza("Inter Mailand", a) != "FC Internazionale Milano"


def test_normalizzare_entrambi_i_lati_riconcilia_i_canonici_diversi():
    """Il file alias dice 'Atalanta Bergamo', il calendario 'Atalanta BC'.

    E' il caso che aveva lasciato scoperte quattro squadre su venti: passando
    dalla normalizzazione un lato solo, i due nomi non si incontrano mai.
    """
    a = leggi_alias(ALIASES)
    assert normalizza("Atalanta", a) == normalizza("Atalanta BC", a)


def test_il_confronto_ignora_accenti_e_punteggiatura():
    assert _chiave("RAAL La Louvière") == _chiave("RAAL La Louviere")
    assert _chiave("St. Pauli") == _chiave("St Pauli")
    assert _chiave("Alavés") == _chiave("Alaves")


def test_senza_alias_si_ripiega_sulla_chiave_non_sul_nome_grezzo():
    """Altrimenti due grafie della stessa squadra non coinciderebbero mai."""
    assert normalizza("RAAL La Louvière", {}) == normalizza("RAAL La Louviere", {})


def test_le_fonti_sono_solo_quelle_verificate():
    """Il Belgio e' stato tolto: file in un formato senza le giornate."""
    assert "jupiler" not in FONTI
    assert set(FONTI) == {
        "serie-a", "premier-league", "championship", "laliga", "bundesliga",
    }


@pytest.mark.parametrize("testo", ["", "= Solo intestazione\n\n# niente\n"])
def test_un_file_vuoto_non_alza_eccezioni(testo):
    assert leggi_calendario(testo) == []
