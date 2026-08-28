"""Il lettore di football-data: le parti che si possono provare senza rete.

Scaricare davvero un CSV dentro i test li renderebbe lenti e dipendenti da un
sito che non controlliamo. Qui si prova la lettura, che e' dove stanno gli
errori veri: date in formati diversi, celle vuote, colonne che spariscono
quando un bookmaker chiude.
"""

from datetime import date

import pytest

from engine.dati.football_data import (
    CODICI,
    PartitaStorica,
    _data,
    _quota,
    leggi,
    stagioni,
)
from engine.core.types import Incontro


def test_le_date_si_leggono_in_entrambi_i_formati():
    """Nei file veri convivono gg/mm/aa e gg/mm/aaaa, anche nella stessa stagione."""
    assert _data("23/08/2025") == date(2025, 8, 23)
    assert _data("23/08/25") == date(2025, 8, 23)
    assert _data(" 01/01/2026 ") == date(2026, 1, 1)


def test_una_data_illeggibile_non_alza_eccezioni():
    assert _data("") is None
    assert _data("boh") is None
    assert _data("2025-08-23") is None


def test_le_quote_si_leggono():
    riga = {"PSCH": "1.75", "PSCD": "3.48", "PSCA": "5.88"}
    assert _quota(riga, ("PSCH", "PSCD", "PSCA")) == (1.75, 3.48, 5.88)


@pytest.mark.parametrize(
    "riga",
    [
        {"A": "", "B": "3.4", "C": "5.9"},          # cella vuota
        {"A": "1.75", "B": "3.4"},                  # colonna assente
        {"A": "1.75", "B": "-", "C": "5.9"},        # segnaposto non numerico
        {"A": "1.0", "B": "3.4", "C": "5.9"},       # quota 1.00: non è una quota
    ],
)
def test_una_terna_incompleta_o_assurda_diventa_None(riga):
    """Meglio nessuna quota che una quota inventata: il libro viene saltato."""
    assert _quota(riga, ("A", "B", "C")) is None


def test_i_codici_coprono_gli_otto_campionati_del_sito():
    assert set(CODICI) == {
        "serie-a", "premier-league", "laliga", "bundesliga",
        "ligue-1", "eredivisie", "primeira-liga", "superlig",
    }


def test_i_codici_stagione():
    assert stagioni(2021, 2026) == ["2122", "2223", "2324", "2425", "2526"]
    assert stagioni(1999, 2001) == ["9900", "0001"]


def test_leggi_scarta_le_righe_senza_esito(tmp_path):
    """In coda ai file di stagione ci sono righe vuote: non devono passare."""
    csv = tmp_path / "prova.csv"
    csv.write_text(
        "Date,HomeTeam,AwayTeam,FTHG,FTAG,PSCH,PSCD,PSCA\n"
        "23/08/2025,Genoa,Lecce,0,0,1.75,3.48,5.88\n"
        "24/08/2025,Inter,Roma,,,2.10,3.30,3.50\n"      # partita non giocata
        ",,,,,,,\n"                                       # riga vuota
        "25/08/2025,Milan,Lazio,2,1,1.90,3.60,4.10\n",
        encoding="utf-8",
    )
    partite = leggi(csv, "serie-a")
    assert len(partite) == 2
    assert [p.incontro.casa for p in partite] == ["Genoa", "Milan"]


def test_esito_e_riferimento():
    def costruisci(gc, go, quote):
        return PartitaStorica(
            incontro=Incontro("x", date(2025, 8, 23), "A", "B", gc, go, "Serie A"),
            quote=quote,
        )

    assert costruisci(2, 1, {}).esito == 0
    assert costruisci(1, 1, {}).esito == 1
    assert costruisci(0, 3, {}).esito == 2

    # Betfair ha la precedenza su Pinnacle: è un mercato, non un listino.
    p = costruisci(1, 0, {"pinnacle": (2.0, 3.0, 4.0), "betfair": (2.1, 3.1, 4.1)})
    assert p.riferimento() == (2.1, 3.1, 4.1)

    # Senza Betfair si ripiega su Pinnacle.
    p = costruisci(1, 0, {"pinnacle": (2.0, 3.0, 4.0), "media": (1.9, 2.9, 3.9)})
    assert p.riferimento() == (2.0, 3.0, 4.0)

    # Senza nessuno dei due la partita non è utilizzabile: la media non basta.
    p = costruisci(1, 0, {"media": (1.9, 2.9, 3.9)})
    assert p.riferimento() is None
