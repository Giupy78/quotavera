"""Classifica vera e classifica attesa."""

from datetime import date, timedelta

import pytest

from engine.classifica import calcola, posizioni_attese, punti_attesi, ultimi_risultati
from engine.core.types import Incontro
from engine.dati.football_data import PartitaStorica, Statistiche


def partita(casa, ospite, gc, go, giorno=1, in_porta=(5, 5), completa=True):
    return PartitaStorica(
        incontro=Incontro(f"m{giorno}", date(2025, 9, 1) + timedelta(days=giorno),
                          casa, ospite, gc, go, "Serie A"),
        quote={},
        stat=Statistiche(tiri=(12, 10), in_porta=in_porta, corner=(5, 4),
                         falli=(11, 12), gialli=(2, 1), rossi=(0, 0),
                         gol_primo_tempo=(0, 0), completa=completa),
    )


def test_i_punti_sono_tre_e_uno():
    partite = [
        partita("Inter", "Como", 2, 0, 1),      # Inter +3
        partita("Roma", "Inter", 1, 1, 2),      # entrambe +1
        partita("Inter", "Lazio", 0, 1, 3),     # Lazio +3
    ]
    c = {r.squadra: r for r in calcola(partite)}
    assert c["Inter"].punti == 4
    assert c["Inter"].vinte == 1 and c["Inter"].pareggiate == 1 and c["Inter"].perse == 1
    assert c["Inter"].giocate == 3
    assert c["Como"].punti == 0
    assert c["Lazio"].punti == 3


def test_gol_fatti_e_subiti_da_entrambi_i_lati():
    c = {r.squadra: r for r in calcola([partita("Inter", "Como", 3, 1, 1)])}
    assert (c["Inter"].fatti, c["Inter"].subiti) == (3, 1)
    assert (c["Como"].fatti, c["Como"].subiti) == (1, 3)
    assert c["Inter"].differenza == 2
    assert c["Como"].differenza == -2


def test_l_ordine_e_punti_poi_differenza_poi_gol_fatti():
    partite = [
        partita("A", "B", 5, 0, 1),      # A: 3 punti, +5
        partita("C", "D", 1, 0, 2),      # C: 3 punti, +1
        partita("E", "F", 2, 1, 3),      # E: 3 punti, +1 ma 2 gol fatti
    ]
    ordine = [r.squadra for r in calcola(partite)]
    assert ordine[0] == "A"                  # stessa quota punti, differenza migliore
    assert ordine.index("E") < ordine.index("C")   # pari differenza, piu' gol fatti


def test_i_punti_attesi_di_una_partita_pari_sono_uguali():
    casa, ospite = punti_attesi(1.3, 1.3)
    assert casa == pytest.approx(ospite)
    # Una partita perfettamente equilibrata vale poco piu' di un punto a testa.
    assert 1.0 < casa < 1.6


def test_chi_crea_di_piu_prende_piu_punti_attesi():
    casa, ospite = punti_attesi(2.4, 0.6)
    assert casa > 2.0
    assert ospite < 0.6
    assert casa > ospite


def test_i_punti_attesi_non_sono_mai_tre_pieni():
    """Anche dominando, resta la possibilita' di non vincere: e' il punto."""
    casa, _ = punti_attesi(4.0, 0.3)
    assert casa < 3.0


def test_la_classifica_attesa_smaschera_chi_ha_raccolto_troppo():
    """Vince 1-0 tirando in porta molto meno: punti veri 3, attesi pochi."""
    partite = [partita("Fortunata", "Sfortunata", 1, 0, 1, in_porta=(2, 9))]
    c = {r.squadra: r for r in calcola(partite, conversione=0.30)}

    assert c["Fortunata"].punti == 3
    assert c["Sfortunata"].punti == 0
    # Il gioco diceva l'opposto.
    assert c["Fortunata"].punti_attesi < c["Sfortunata"].punti_attesi
    assert c["Fortunata"].scarto_punti > 1.5      # ha raccolto molto piu' del dovuto
    assert c["Sfortunata"].scarto_punti < -1.0


def test_le_posizioni_attese_riordinano_per_punti_attesi():
    partite = [
        partita("Fortunata", "Sfortunata", 1, 0, 1, in_porta=(2, 9)),
        partita("Fortunata", "Terza", 1, 0, 2, in_porta=(2, 8)),
    ]
    classifica = calcola(partite, conversione=0.30)
    attese = posizioni_attese(classifica)
    # Prima in classifica vera...
    assert classifica[0].squadra == "Fortunata"
    # ...ma non nella classifica del gioco.
    assert attese["Fortunata"] > 1


def test_le_partite_senza_statistiche_contano_per_i_punti_ma_non_per_gli_attesi():
    partite = [
        partita("Inter", "Como", 2, 0, 1),
        partita("Inter", "Roma", 1, 0, 2, completa=False),
    ]
    c = {r.squadra: r for r in calcola(partite)}
    assert c["Inter"].punti == 6
    assert c["Inter"].giocate == 2
    assert c["Inter"].con_statistiche == 1       # solo una ha i tiri


def test_ultimi_risultati_dal_piu_recente():
    partite = [partita("A", "B", 1, 0, 1), partita("C", "D", 2, 2, 5),
               partita("E", "F", 0, 3, 3)]
    ultimi = ultimi_risultati(partite, quanti=2)
    assert len(ultimi) == 2
    assert ultimi[0].incontro.casa == "C"        # giorno 5, il piu' recente
    assert ultimi[1].incontro.casa == "E"        # giorno 3


def test_le_giornate_si_deducono_dalle_partite_giocate():
    """football-data non le pubblica: si contano le gare di ogni squadra."""
    from engine.classifica import giornate

    partite = [
        partita("A", "B", 1, 0, 1),
        partita("C", "D", 2, 2, 1),      # stessa giornata, stesso giorno
        partita("B", "C", 0, 0, 8),      # seconda per B e per C
        partita("D", "A", 3, 1, 8),
        partita("A", "C", 1, 1, 15),     # terza
    ]
    g = giornate(partite)
    numeri = [g[p.incontro.id] for p in partite]
    assert numeri == [1, 1, 2, 2, 3]


def test_una_partita_recuperata_resta_nella_sua_giornata():
    """Il rinvio non deve spostare in avanti tutto il resto del calendario."""
    from engine.classifica import giornate

    partite = [
        partita("A", "B", 1, 0, 1),      # giornata 1
        partita("C", "D", 0, 0, 1),      # giornata 1
        partita("A", "C", 2, 0, 8),      # giornata 2 per A e C
        partita("B", "D", 1, 1, 30),     # rinviata: resta giornata 2 per B e D
    ]
    g = giornate(partite)
    assert g[partite[3].incontro.id] == 2, "il recupero deve restare alla sua giornata"


def test_le_giornate_su_un_girone_completo():
    """Quattro squadre, girone di andata: tre giornate da due partite."""
    from engine.classifica import giornate

    coppie = [("A", "B"), ("C", "D"), ("A", "C"), ("B", "D"), ("A", "D"), ("B", "C")]
    partite = [partita(c, o, 1, 0, n + 1) for n, (c, o) in enumerate(coppie)]
    g = giornate(partite)
    conteggio = {}
    for p in partite:
        conteggio.setdefault(g[p.incontro.id], 0)
        conteggio[g[p.incontro.id]] += 1
    assert conteggio == {1: 2, 2: 2, 3: 2}


def test_le_giornate_non_sforano_il_totale_del_campionato():
    """Con un rinvio, la squadra indietro non deve saltare avanti.

    Assegnando a entrambe il numero della giornata piu' avanzata, chi era
    rimasto indietro faceva un balzo e da li' in poi le sue giornate erano
    sfalsate: in Serie A comparivano una 39 e una 40.
    """
    from engine.classifica import giornate

    # Quattro squadre, girone doppio: sei giornate, nessuna oltre la sesta.
    coppie = [("A", "B"), ("C", "D"), ("A", "C"), ("B", "D"), ("A", "D"), ("B", "C"),
              ("B", "A"), ("D", "C"), ("C", "A"), ("D", "B"), ("D", "A"), ("C", "B")]
    partite = [partita(c, o, 1, 0, n + 1) for n, (c, o) in enumerate(coppie)]
    g = giornate(partite)
    assert max(g.values()) == 6, f"giornate oltre il totale: {sorted(set(g.values()))}"

    # Ogni squadra gioca esattamente sei partite, una per giornata.
    for squadra in "ABCD":
        sue = [g[p.incontro.id] for p in partite
               if squadra in (p.incontro.casa, p.incontro.ospite)]
        assert sorted(sue) == [1, 2, 3, 4, 5, 6]
