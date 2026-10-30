"""I confronti fra campionati.

Finiscono in un articolo con il titolo "i campionati con piu' gol", quindi un
errore qui non e' un numero sbagliato in una tabella: e' un titolo falso.
"""

from datetime import date, timedelta

from engine import fra_campionati as fc
from engine.core.types import Incontro
from engine.dati.football_data import PartitaStorica


class Lega:
    def __init__(self, slug, nome="X"):
        self.slug, self.nome = slug, nome
        self.paese, self.bandiera, self.livello = "Italia", "🇮🇹", 1


def partita(gc, go, giorno: date):
    return PartitaStorica(
        incontro=Incontro("m", giorno, "A", "B", gc, go, "X"),
        quote={},
    )


def stagione(anno: int, risultati: list[tuple[int, int]]):
    """Partite di una stagione, distribuite da settembre in avanti."""
    inizio = date(anno, 9, 1)
    return [partita(c, o, inizio + timedelta(days=i)) for i, (c, o) in enumerate(risultati)]


def test_luglio_fa_da_confine_fra_le_stagioni():
    assert fc.inizio_stagione(date(2025, 8, 20)) == 2025
    assert fc.inizio_stagione(date(2026, 5, 30)) == 2025
    assert fc.inizio_stagione(date(2026, 7, 1)) == 2026
    assert fc.etichetta(2025) == "2025/26"
    assert fc.etichetta(2009) == "2009/10"


def test_le_medie_sono_totale_diviso_totale():
    m = fc.conta([partita(3, 1, date(2025, 9, 1)), partita(0, 0, date(2025, 9, 2))])
    assert m["partite"] == 2
    assert m["gol"] == 2.0
    assert m["gol_casa"] == 1.5 and m["gol_ospite"] == 0.5
    assert m["almeno_tre"] == 0.5          # 3-1 si', 0-0 no
    assert m["zero_a_zero"] == 0.5
    assert m["entrambe"] == 0.5            # 3-1 si', 0-0 no
    assert m["vittorie_casa"] == 0.5 and m["pareggi"] == 0.5 and m["vittorie_ospite"] == 0


def test_la_stagione_in_corso_non_entra_nella_classifica():
    # Un campionato con poche partite pazze nella stagione in corso: se
    # entrassero nel conto lo porterebbero in testa.
    tranquillo = stagione(2025, [(1, 0)] * 120)
    pazzo_adesso = stagione(2025, [(1, 0)] * 120) + stagione(2026, [(5, 5)] * 10)
    vivace = stagione(2025, [(2, 1)] * 120)

    out = fc.per_campionato(
        [(Lega("a"), tranquillo), (Lega("b"), pazzo_adesso), (Lega("c"), vivace)],
        stagione_in_corso=2026)

    ordine = [r["slug"] for r in out["campionati"]]
    assert ordine[0] == "c"
    b = next(r for r in out["campionati"] if r["slug"] == "b")
    assert b["totale"]["gol"] == 1.0
    assert b["in_corso"]["gol"] == 10.0     # si mostra, ma a parte
    assert out["stagione_in_corso"] == "2026/27"


def test_una_stagione_troppo_corta_non_conta():
    # 2024/25 ha solo 30 partite: la fonte ne ha pubblicato un pezzo.
    partite = stagione(2024, [(4, 4)] * 30) + stagione(2025, [(1, 1)] * 150)
    out = fc.per_campionato([(Lega("a"), partite)], stagione_in_corso=2026)
    r = out["campionati"][0]
    assert r["stagioni"] == ["2025/26"]
    assert r["totale"]["gol"] == 2.0


def test_le_stagioni_comuni_sono_quelle_che_hanno_tutti():
    a = stagione(2023, [(1, 1)] * 150) + stagione(2024, [(1, 1)] * 150)
    b = stagione(2024, [(1, 1)] * 150)
    out = fc.per_campionato([(Lega("a"), a), (Lega("b"), b)], stagione_in_corso=2026)
    assert out["stagioni_comuni"] == ["2024/25"]


def test_le_posizioni_seguono_i_gol():
    out = fc.per_campionato(
        [(Lega("poco"), stagione(2025, [(0, 1)] * 120)),
         (Lega("tanto"), stagione(2025, [(3, 2)] * 120))],
        stagione_in_corso=2026)
    assert [(r["slug"], r["posizione_gol"]) for r in out["campionati"]] == [("tanto", 1), ("poco", 2)]
