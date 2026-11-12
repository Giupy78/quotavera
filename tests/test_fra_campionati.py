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


def test_il_vantaggio_e_vittorie_in_casa_meno_vittorie_fuori():
    m = fc.conta([partita(2, 0, date(2025, 9, 1)), partita(1, 1, date(2025, 9, 2)),
                  partita(0, 1, date(2025, 9, 3)), partita(3, 1, date(2025, 9, 4))])
    assert m["vittorie_casa"] == 0.5 and m["vittorie_ospite"] == 0.25
    assert m["vantaggio"] == 0.25


def test_la_classifica_del_fattore_campo_e_indipendente_da_quella_dei_gol():
    # "gol" segna tanto ma vince spesso fuori; "casa" segna poco ma vince in casa.
    out = fc.per_campionato(
        [(Lega("gol"), stagione(2025, [(2, 3)] * 120)),
         (Lega("casa"), stagione(2025, [(1, 0)] * 120))],
        stagione_in_corso=2026)
    per = {r["slug"]: r for r in out["campionati"]}
    assert per["gol"]["posizione_gol"] == 1 and per["gol"]["posizione_campo"] == 2
    assert per["casa"]["posizione_gol"] == 2 and per["casa"]["posizione_campo"] == 1


# --- le misure degli articoli su intervallo, cartellini, angoli e tiri ---------

from engine.dati.football_data import Statistiche


def giocata(gc, go, pt=(0, 0), giorno=date(2025, 9, 1), id_="fd", **stat):
    """Una partita con le sue statistiche. `completa` se ci sono i tiri."""
    s = Statistiche(gol_primo_tempo=pt, completa="tiri" in stat, **stat)
    return PartitaStorica(incontro=Incontro(id_, giorno, "A", "B", gc, go, "X"),
                          quote={}, stat=s)


def test_chi_e_avanti_all_intervallo():
    m = fc.intervallo([
        giocata(2, 0, pt=(1, 0)),      # casa avanti di uno, vince
        giocata(1, 1, pt=(1, 0)),      # casa avanti di uno, pareggia
        giocata(1, 2, pt=(1, 0)),      # casa avanti di uno, perde: rimonta dell'ospite
        giocata(3, 1, pt=(2, 0)),      # casa avanti di due, vince
        giocata(0, 2, pt=(0, 1)),      # ospite avanti, vince
        giocata(1, 1, pt=(0, 0)),      # pari all'intervallo, pari alla fine
    ])
    assert m["partite"] == 6
    assert m["avanti"] == round(5 / 6, 4)
    assert m["chi_avanti"] == {"partite": 5, "vince": 0.6, "pari": 0.2, "perde": 0.2}
    assert m["di_uno"]["partite"] == 4 and m["di_uno"]["vince"] == 0.5
    assert m["di_due"] == {"partite": 1, "vince": 1.0, "pari": 0.0, "perde": 0.0}
    assert m["casa_avanti"]["partite"] == 4 and m["ospite_avanti"]["vince"] == 1.0
    assert m["rimonte"] == round(1 / 6, 4)
    assert m["rimonte_ospite"] == round(1 / 6, 4) and m["rimonte_casa"] == 0
    assert m["dopo_il_pari"] == {"partite": 1, "casa": 0.0, "pari": 1.0, "ospite": 0.0}
    # 6 gol nel primo tempo su 15: gli altri 9 nella ripresa.
    assert m["gol_primo"] == 1.0
    assert m["quota_secondo"] == 0.6


def test_le_partite_solo_espn_non_hanno_il_primo_tempo():
    # ESPN non pubblica il punteggio dell'intervallo: quel 0-0 e' un buco,
    # e contarlo farebbe sembrare pari al riposo una partita finita 3-0.
    m = fc.intervallo([giocata(3, 0, pt=(2, 0)), giocata(3, 0, id_="espn-1")])
    assert m["partite"] == 1
    assert m["pari_intervallo"] == 0


def test_un_primo_tempo_impossibile_resta_fuori():
    m = fc.intervallo([giocata(1, 0, pt=(2, 0)), giocata(1, 0, pt=(1, 0))])
    assert m["partite"] == 1


def test_cartellini_senza_falli_come_la_national_league():
    # Cartellini si', tiri e falli no: la media dei cartellini c'e', i falli
    # restano None invece di diventare zero.
    m = fc.disciplina([giocata(1, 0, gialli=(2, 3), rossi=(0, 1)),
                       giocata(0, 0, gialli=(1, 2))])
    assert m["partite"] == 2
    assert m["gialli"] == 4.0 and m["gialli_casa"] == 1.5 and m["gialli_ospite"] == 2.5
    assert m["cartellini"] == 4.5 and m["rossi"] == 0.5
    assert m["falli"] is None and m["falli_per_giallo"] is None
    assert fc.campo([giocata(1, 0, gialli=(2, 3))]) is None


def test_falli_per_giallo_solo_sulle_partite_che_li_hanno():
    m = fc.disciplina([
        giocata(1, 0, tiri=(10, 8), in_porta=(4, 3), falli=(12, 12), gialli=(2, 2)),
        giocata(0, 0, gialli=(5, 5)),     # senza falli: non entra nel rapporto
    ])
    assert m["falli"] == 24.0
    assert m["falli_per_giallo"] == 6.0


def test_nessun_giallo_in_tutto_un_gruppo_e_una_colonna_che_manca():
    assert fc.disciplina([giocata(1, 0), giocata(2, 2)]) is None


def test_tiri_e_angoli():
    m = fc.campo([
        giocata(2, 0, tiri=(15, 5), in_porta=(6, 2), corner=(7, 3)),
        giocata(1, 1, tiri=(10, 10), in_porta=(3, 3), corner=(4, 6)),
    ])
    assert m["tiri"] == 20.0 and m["in_porta"] == 7.0 and m["corner"] == 10.0
    assert m["corner_casa"] == 5.5 and m["corner_ospite"] == 4.5
    assert m["precisione"] == 0.35
    assert m["gol_per_tiro_in_porta"] == round(4 / 14, 4)
    assert m["tiri_per_gol"] == 10.0


def test_i_risultati_dal_piu_frequente_con_la_casa_prima():
    r = fc.risultati([giocata(1, 0), giocata(0, 1), giocata(1, 0), giocata(1, 1)])
    assert list(r.items()) == [("1-0", 2), ("0-1", 1), ("1-1", 1)]


def test_le_fasce_contano_solo_le_partite_con_le_statistiche():
    partite = [
        giocata(3, 0, tiri=(10, 2), in_porta=(6, 1), corner=(2, 1)),
        giocata(0, 0, tiri=(5, 5), in_porta=(1, 1), corner=(8, 8)),
        giocata(5, 5),                                   # niente statistiche
    ]
    f = fc.fasce(partite, lambda p: sum(p.stat.corner), ((0, 7), (8, None)))
    assert [(x["da"], x["a"], x["partite"], x["gol"]) for x in f] == [(0, 7, 1, 3.0), (8, None, 1, 0.0)]
    assert f[0]["quota"] == 0.5


def test_tutti_i_campionati_insieme_pesano_le_partite():
    # Un campionato con 300 partite e uno con 120: il totale e' sulle partite,
    # non la media dei due campionati.
    grande = stagione(2025, [(2, 0)] * 300)
    piccolo = stagione(2025, [(0, 0)] * 120)
    out = fc.per_campionato([(Lega("g"), grande), (Lega("p"), piccolo)], stagione_in_corso=2026)
    assert out["tutti"]["partite"] == 420
    assert out["tutti"]["gol"] == round(600 / 420, 3)
    assert out["tutti_risultati"] == {"2-0": 300, "0-0": 120}
    assert next(r for r in out["campionati"] if r["slug"] == "p")["risultati"] == {"0-0": 120}
