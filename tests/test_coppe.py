"""Le coppe europee.

Non si tocca la rete: si controlla come si leggono le risposte di ESPN e, soprattutto,
le tre promesse del modulo. Una partita non si perde, un indirizzo non si sposta, e
due squadre con un nome simile non si confondono.
"""

from datetime import date

from engine.dati import coppe


def evento(id_="1", stato="STATUS_FULL_TIME", completata=True, gol=("2", "1"),
           quando="2026-11-03T20:00Z", casa=("10", "Internazionale"), ospite=("20", "Ferencvaros"),
           fase="league-phase"):
    return {
        "id": id_,
        "date": quando,
        "season": {"slug": fase},
        "competitions": [{
            "status": {"type": {"name": stato, "completed": completata}},
            "venue": {"fullName": "San Siro", "address": {"city": "Milano", "country": "Italy"}},
            "competitors": [
                {"homeAway": "home", "score": gol[0], "team": {"id": casa[0], "displayName": casa[1]}},
                {"homeAway": "away", "score": gol[1], "team": {"id": ospite[0], "displayName": ospite[1]}},
            ],
        }],
    }


def letto(**k):
    return coppe.leggi_evento(evento(**k))


# --- lettura ---------------------------------------------------------------

def test_una_partita_finita_si_legge_e_l_ora_e_quella_italiana():
    p = letto()
    assert p["stato"] == "finita"
    assert (p["gol_casa"], p["gol_ospite"]) == (2, 1)
    assert p["data"] == "2026-11-03" and p["ora"] == "21:00"     # 20:00 UTC in novembre
    assert p["casa_id"] == "10" and p["stadio"]["citta"] == "Milano"


def test_mezzanotte_italiana_cambia_il_giorno():
    p = letto(quando="2026-11-03T23:30Z")
    assert p["data"] == "2026-11-04" and p["ora"] == "00:30"


def test_una_partita_da_giocare_non_ha_punteggio():
    p = letto(stato="STATUS_SCHEDULED", completata=False, gol=("0", "0"))
    assert p["stato"] == "in_programma"
    assert "gol_casa" not in p


def test_i_supplementari_contano_come_partita_finita():
    assert letto(stato="STATUS_FINAL_PEN", completata=True)["stato"] == "finita"


def test_una_partita_rinviata_non_e_finita_anche_se_espn_la_chiude():
    assert letto(stato="STATUS_POSTPONED", completata=True)["stato"] == "rinviata"
    assert letto(stato="STATUS_CANCELED", completata=True)["stato"] == "rinviata"


def test_un_evento_senza_una_squadra_si_scarta():
    e = evento()
    e["competitions"][0]["competitors"].pop()
    assert coppe.leggi_evento(e) is None


def test_la_classifica_si_legge_e_si_ordina():
    d = {"children": [{"standings": {"entries": [
        {"team": {"id": "2", "displayName": "B"},
         "stats": [{"name": "rank", "displayValue": "2"}, {"name": "points", "displayValue": "7"},
                   {"name": "pointDifferential", "displayValue": "-3"}]},
        {"team": {"id": "1", "displayName": "A"},
         "stats": [{"name": "rank", "displayValue": "1"}, {"name": "points", "displayValue": "12"},
                   {"name": "pointDifferential", "displayValue": "+15"}]},
    ]}}]}
    r = coppe.leggi_classifica(d)
    assert [x["squadra_id"] for x in r] == ["1", "2"]
    assert r[0]["differenza"] == 15 and r[1]["differenza"] == -3


# --- l'archivio non perde niente ----------------------------------------------

def test_una_partita_finita_non_torna_indietro():
    finita = letto()
    finita["stat"] = {"tiri": [10, 5]}
    archivio = coppe.fondi({}, [finita])
    dopo = coppe.fondi(archivio, [letto(stato="STATUS_SCHEDULED", completata=False)])
    assert dopo["1"]["stato"] == "finita"
    assert dopo["1"]["stat"] == {"tiri": [10, 5]}


def test_una_partita_sparita_dal_calendario_resta_nell_archivio():
    archivio = coppe.fondi({}, [letto(id_="1"), letto(id_="2")])
    assert set(coppe.fondi(archivio, [letto(id_="1")])) == {"1", "2"}


def test_una_risposta_senza_quote_non_cancella_quelle_che_avevamo():
    prima = letto(stato="STATUS_SCHEDULED", completata=False)
    prima["quote"] = [1.5, 4.0, 6.0]
    dopo = coppe.fondi(coppe.fondi({}, [prima]), [letto(stato="STATUS_SCHEDULED", completata=False)])
    assert dopo["1"]["quote"] == [1.5, 4.0, 6.0]


def test_mancano_i_tabellini_delle_sole_partite_finite():
    finita = letto(id_="1")
    completa = {**letto(id_="2"), "stat": {"tiri": [1, 2]}}
    futura = letto(id_="3", stato="STATUS_SCHEDULED", completata=False)
    assert coppe.da_completare(coppe.fondi({}, [finita, completa, futura])) == ["1"]


# --- gli indirizzi non si spostano ----------------------------------------------

MAPPA = {"10": {"nome": "Inter", "campionato": "serie-a"}}


def test_l_indirizzo_usa_il_nostro_nome_quando_seguiamo_la_squadra():
    a = {"partite": coppe.fondi({}, [letto()])}
    coppe.assegna_indirizzi(a, MAPPA)
    assert a["partite"]["1"]["pagina"] == "inter-ferencvaros"
    assert a["indirizzi_squadre"] == {"10": "inter", "20": "ferencvaros"}


def test_un_indirizzo_assegnato_non_cambia_se_cambia_il_nome():
    a = {"partite": coppe.fondi({}, [letto()])}
    coppe.assegna_indirizzi(a, MAPPA)
    coppe.assegna_indirizzi(a, {"10": {"nome": "Internazionale Milano", "campionato": "serie-a"}})
    assert a["partite"]["1"]["pagina"] == "inter-ferencvaros"
    assert a["indirizzi_squadre"]["10"] == "inter"


def test_la_stessa_partita_due_volte_tiene_il_primo_indirizzo():
    a = {"partite": coppe.fondi({}, [
        letto(id_="1", quando="2026-11-03T20:00Z"),
        letto(id_="2", quando="2027-03-10T20:00Z", fase="round-of-16"),
    ])}
    coppe.assegna_indirizzi(a, MAPPA)
    assert a["partite"]["1"]["pagina"] == "inter-ferencvaros"
    assert a["partite"]["2"]["pagina"] == "inter-ferencvaros-2027-03-10"


def test_due_squadre_con_lo_stesso_nome_non_si_confondono():
    a = {"partite": coppe.fondi({}, [
        letto(id_="1", casa=("30", "Red Star"), ospite=("31", "Benfica")),
        letto(id_="2", casa=("40", "Red Star"), ospite=("41", "Porto")),
    ])}
    coppe.assegna_indirizzi(a, {})
    assert a["indirizzi_squadre"]["30"] == "red-star"
    assert a["indirizzi_squadre"]["40"] == "red-star-40"


def test_l_indirizzo_segue_le_regole_del_sito():
    assert coppe.lumaca("Man City") == "man-city"
    assert coppe.lumaca("Bodø/Glimt") == "bod-glimt"
    assert coppe.lumaca("Atlético Madrid") == "atletico-madrid"
    assert coppe.lumaca("St. Pauli") == "st-pauli"


# --- le medie e la pagina --------------------------------------------------------

def _archivio(*partite):
    a = {"partite": coppe.fondi({}, list(partite)), "classifica": []}
    coppe.assegna_indirizzi(a, MAPPA)
    return a


def test_le_medie_sono_totale_diviso_totale_e_ogni_voce_ha_il_suo_denominatore():
    con_tabellino = {**letto(id_="1", gol=("3", "0")), "stat": {"tiri": [10, 4], "possesso": [60.0, 40.0]}}
    senza = letto(id_="2", gol=("1", "1"), quando="2026-11-10T20:00Z")
    medie, coppa = coppe.medie_squadre([con_tabellino, senza])
    inter = medie["10"]
    assert inter["partite"] == 2 and inter["vinte"] == 1 and inter["pareggiate"] == 1
    assert inter["medie"]["gol_fatti"] == 2.0             # 4 gol in 2 partite
    assert inter["medie"]["tiri"] == 10.0                 # un solo tabellino, non 5
    assert inter["medie"]["tiri_subiti"] == 4.0
    assert coppa["tiri"] == 7.0                           # (10 + 4) / 2
    assert coppa["gol_fatti"] == 1.25                     # 5 gol, 4 presenze


def test_la_scheda_usa_i_nostri_nomi_e_conserva_quelli_di_espn():
    a = _archivio({**letto(), "stat": {"tiri": [10.0, 4.0], "possesso": [52.5, 47.5]}})
    c = coppe.per_il_sito(coppe.COPPE[0], a, MAPPA, 2026, date(2026, 11, 6))
    p = c["partite"][0]
    assert p["casa"] == "Inter" and p["casa_esteso"] == "Internazionale"
    assert p["ospite"] == "Ferencvaros"
    assert p["statistiche"]["tiri"] == [10, 4]            # interi, non 10.0
    assert p["statistiche"]["possesso"] == [52.5, 47.5]
    inter = next(s for s in c["squadre"] if s["id"] == "inter")
    assert inter["campionato"] == "serie-a"
    assert next(s for s in c["squadre"] if s["id"] == "ferencvaros")["campionato"] is None
    assert c["stagione"] == "2026/27" and c["gol_a_partita"] == 3.0


def test_una_partita_passata_senza_risultato_lo_dichiara():
    a = _archivio(letto(stato="STATUS_SCHEDULED", completata=False, quando="2026-11-03T20:00Z"))
    p = coppe.per_il_sito(coppe.COPPE[0], a, MAPPA, 2026, date(2026, 11, 6))["partite"][0]
    assert p["senza_risultato"] and not p["giocata"]


def test_la_partita_di_stasera_non_e_senza_risultato():
    a = _archivio(letto(stato="STATUS_SCHEDULED", completata=False, quando="2026-11-05T20:00Z"))
    p = coppe.per_il_sito(coppe.COPPE[0], a, MAPPA, 2026, date(2026, 11, 5))["partite"][0]
    assert not p["senza_risultato"]


def test_le_quote_di_una_partita_giocata_non_si_mostrano():
    giocata = {**letto(), "quote": [1.5, 4.0, 6.0]}
    p = coppe.per_il_sito(coppe.COPPE[0], _archivio(giocata), MAPPA, 2026, date(2026, 11, 6))["partite"][0]
    assert p["quote"] is None
