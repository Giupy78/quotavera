"""I minuti dei gol. Finiscono in un articolo che dice "il 6% dei gol arriva
nel recupero": un gol messo nella fascia sbagliata e' una frase falsa."""

from datetime import date

from engine import minuti as mn


class Lega:
    def __init__(self, slug, nome="X"):
        self.slug, self.nome, self.paese, self.bandiera = slug, nome, "Italia", "🇮🇹"


def partita(gc, go, gol, campionato="a", data="2026-09-01"):
    return {"giocata": True, "data": data, "campionato": campionato,
            "gol_casa": gc, "gol_ospite": go,
            "gol": [{"minuto": m, "tipo": t} for m, t in gol]}


def test_leggere_il_minuto():
    assert mn.leggi_minuto("67'") == (67, 0)
    assert mn.leggi_minuto("45'+2'") == (45, 2)
    assert mn.leggi_minuto(" 90'+5' ") == (90, 5)
    assert mn.leggi_minuto("") is None and mn.leggi_minuto(None) is None
    assert mn.leggi_minuto("90+5") is None


def test_le_fasce_tengono_a_parte_il_recupero():
    assert mn.fascia(1, 0) == 0 and mn.fascia(15, 0) == 0 and mn.fascia(16, 0) == 1
    assert mn.fascia(45, 0) == 2            # il 45' e' l'ultimo quarto d'ora del primo tempo
    assert mn.fascia(45, 3) == 3            # il 45'+3' no: e' recupero
    assert mn.fascia(46, 0) == 4 and mn.fascia(75, 0) == 5 and mn.fascia(76, 0) == 6
    assert mn.fascia(90, 0) == 6
    assert mn.fascia(90, 4) == 7


def test_le_quote_e_i_tipi():
    out = mn.per_il_sito([
        partita(2, 1, [("10'", "Goal"), ("45'+1'", "Penalty - Scored"), ("90'+2'", "Own Goal")]),
        partita(1, 0, [("80'", "Goal - Header")]),
        partita(0, 0, []),
    ], date(2026, 7, 1), [Lega("a")])
    t = out["tutti"]
    assert t["partite"] == 3 and t["gol"] == 4
    assert t["recupero"] == 0.5             # 45'+1' e 90'+2'
    assert t["finale"] == 0.5               # 80' e 90'+2'
    assert t["rigori"] == 0.25 and t["autogol"] == 0.25
    assert t["senza_gol"] == round(1 / 3, 4)
    assert t["primo_gol_medio"] == 45.0     # 10' e 80'
    assert t["primo_gol_entro_15"] == round(1 / 3, 4)
    assert [f["gol"] for f in t["fasce"]] == [1, 0, 0, 1, 0, 0, 1, 1]


def test_un_campionato_con_tabellini_incompleti_resta_fuori():
    # 2-1 senza elenco dei gol: i suoi tre gol non hanno minuto.
    buone = [partita(1, 0, [("5'", "Goal")], campionato="b") for _ in range(19)]
    out = mn.per_il_sito(
        buone + [partita(2, 1, [], campionato="b")]
        + [partita(1, 0, [("5'", "Goal")], campionato="c")] * 3
        + [partita(2, 1, [], campionato="c")] * 2,
        date(2026, 7, 1), [Lega("b"), Lega("c")])
    assert [r["slug"] for r in out["campionati"]] == ["b"]     # 19 su 20 = 95%
    assert out["esclusi"] == [{"slug": "c", "nome": "X", "completezza": 0.6}]
    assert out["tutti"]["partite"] == 19                       # la partita incompleta non entra


def test_la_stagione_scorsa_non_entra():
    out = mn.per_il_sito([partita(1, 0, [("5'", "Goal")], data="2026-05-20"),
                          partita(1, 0, [("50'", "Goal")])],
                         date(2026, 7, 1), [Lega("a")])
    assert out["tutti"]["partite"] == 1
    assert out["tutti"]["secondo_tempo"] == 1.0
