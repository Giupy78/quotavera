"""Il registro degli indirizzi pubblicati, e la sentinella che lo guarda.

Una pagina di partita pubblicata non deve sparire. È successo tre volte, ogni
volta per una squadra scritta in due modi, e ogni volta l'ha scoperto Google.
Qui si prova che il registro non dimentichi, che un indirizzo senza pagina e
senza rinvio venga detto, e che il rinvio proposto sia quello giusto — o
nessuno, quando la pagina giusta non è ovvia.
"""

import importlib.util
from pathlib import Path

import pytest

from engine import indirizzi

RADICE = Path(__file__).resolve().parents[1]


def scheda(campionato, casa, ospite, data):
    """Una scheda come la scrive genera_sito, con i soli campi che servono qui."""
    pulito = f"{casa}-{ospite}".lower()
    for a, b in ((" ", "-"), ("'", ""), (".", ""), ("/", "-")):
        pulito = pulito.replace(a, b)
    return {"id": pulito, "campionato": campionato, "casa": casa,
            "ospite": ospite, "data": data}


def modulo(nome):
    """Uno script di `scripts/`, che non è un pacchetto."""
    spec = importlib.util.spec_from_file_location(nome, RADICE / "scripts" / f"{nome}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# --- il registro cresce e basta -------------------------------------------------

def test_il_registro_cresce_e_non_toglie_mai():
    registro = {}
    assert indirizzi.aggiungi(registro, [scheda("serie-a", "Inter", "Milan", "2026-11-01"),
                                         scheda("serie-a", "Roma", "Lazio", "2026-11-02")],
                              "2026-11-01") == 2
    # Il giorno dopo Inter-Milan non c'è più fra le schede: dal registro non esce.
    assert indirizzi.aggiungi(registro, [scheda("serie-a", "Roma", "Lazio", "2026-11-02"),
                                         scheda("serie-a", "Napoli", "Como", "2026-11-03")],
                              "2026-11-02") == 1
    assert sorted(registro) == ["/calcio/serie-a/inter-milan/",
                                "/calcio/serie-a/napoli-como/",
                                "/calcio/serie-a/roma-lazio/"]
    assert registro["/calcio/serie-a/inter-milan/"]["dal"] == "2026-11-01"
    assert registro["/calcio/serie-a/napoli-como/"]["dal"] == "2026-11-02"


def test_una_partita_spostata_si_ricorda_la_data_nuova():
    """Per riconoscere la pagina che la sostituisce serve l'ultima data, non la prima."""
    registro = {}
    indirizzi.aggiungi(registro, [scheda("serie-a", "Inter", "Milan", "2026-11-01")], "2026-10-25")
    indirizzi.aggiungi(registro, [scheda("serie-a", "Inter", "Milan", "2026-11-04")], "2026-10-28")
    voce = registro["/calcio/serie-a/inter-milan/"]
    assert voce["data"] == "2026-11-04"
    assert voce["dal"] == "2026-10-25"


def test_dal_puo_solo_andare_indietro():
    """Succede ricostruendo dalla cronologia una versione più vecchia."""
    registro = {}
    indirizzi.aggiungi(registro, [scheda("serie-a", "Inter", "Milan", "2026-11-01")], "2026-10-20")
    indirizzi.aggiungi(registro, [scheda("serie-a", "Inter", "Milan", "2026-11-01")], "2026-10-10")
    indirizzi.aggiungi(registro, [scheda("serie-a", "Inter", "Milan", "2026-11-01")], "2026-10-30")
    assert registro["/calcio/serie-a/inter-milan/"]["dal"] == "2026-10-10"


def test_il_file_ha_un_indirizzo_per_riga(tmp_path):
    f = tmp_path / "indirizzi.json"
    registro = {}
    indirizzi.aggiungi(registro, [scheda("ligue-1", "Paris SG", "Lyon", "2026-11-08"),
                                  scheda("jupiler", "Charleroi", "Mechelen", "2026-11-08")],
                       "2026-11-08")
    indirizzi.salva(registro, f)
    grezzo = f.read_bytes()
    assert b"\r\n" not in grezzo              # anche quando lo scrive Windows
    righe = grezzo.decode("utf-8").splitlines()
    assert righe[0] == "{" and righe[-1] == "}"
    assert righe[1].startswith('"/calcio/jupiler/charleroi-mechelen/": {')
    assert righe[2].startswith('"/calcio/ligue-1/paris-sg-lyon/": {')
    assert indirizzi.carica(f) == registro


def test_un_registro_che_manca_e_vuoto(tmp_path):
    assert indirizzi.carica(tmp_path / "non-ce.json") == {}


def test_un_registro_rotto_non_torna_vuoto(tmp_path):
    """Tornando vuoto verrebbe riscritto con le sole pagine di oggi."""
    f = tmp_path / "indirizzi.json"
    f.write_text('{"/calcio/serie-a/inter-milan/": {', encoding="utf-8")
    with pytest.raises(ValueError):
        indirizzi.carica(f)
    f.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        indirizzi.carica(f)


# --- i rinvii --------------------------------------------------------------------

def test_le_regole_si_leggono_come_le_legge_cloudflare():
    testo = """
# un commento
/calcio/a/x-y/ /calcio/a/x-z/ 301

   /calcio/a/b-c/    /calcio/a/b-d/
/calcio/a/x-y/ /calcio/a/altro/ 301
"""
    assert indirizzi.leggi_rinvii(testo) == {
        "/calcio/a/x-y/": "/calcio/a/x-z/",       # vale la prima delle due
        "/calcio/a/b-c/": "/calcio/a/b-d/",
    }


# --- il confronto ------------------------------------------------------------------

OGGI = [scheda("jupiler", "Charleroi", "Mechelen", "2026-11-08"),
        scheda("jupiler", "Gent", "Genk", "2026-11-08")]


def registro_con(*schede):
    registro = {}
    indirizzi.aggiungi(registro, list(schede), "2026-11-01")
    return registro


def test_una_pagina_che_esiste_non_e_persa():
    assert indirizzi.persi(registro_con(*OGGI), OGGI, {}) == []


def test_una_pagina_sparita_senza_rinvio_e_persa():
    vecchia = scheda("jupiler", "Charleroi", "KV Mechelen", "2026-11-08")
    fuori = indirizzi.persi(registro_con(vecchia, *OGGI), OGGI, {})
    assert [p.via for p in fuori] == ["/calcio/jupiler/charleroi-kv-mechelen/"]


def test_un_rinvio_verso_una_pagina_viva_basta():
    vecchia = scheda("jupiler", "Charleroi", "KV Mechelen", "2026-11-08")
    regole = {"/calcio/jupiler/charleroi-kv-mechelen/": "/calcio/jupiler/charleroi-mechelen/"}
    assert indirizzi.persi(registro_con(vecchia, *OGGI), OGGI, regole) == []


def test_un_rinvio_verso_una_pagina_morta_non_basta():
    vecchia = scheda("jupiler", "Charleroi", "KV Mechelen", "2026-11-08")
    regole = {"/calcio/jupiler/charleroi-kv-mechelen/": "/calcio/jupiler/charleroi-malines/"}
    fuori = indirizzi.persi(registro_con(vecchia, *OGGI), OGGI, regole)
    assert len(fuori) == 1
    assert fuori[0].rinvio_a == "/calcio/jupiler/charleroi-malines/"
    assert fuori[0].proposta is None


def test_i_rinvii_si_seguono_in_catena():
    a = scheda("jupiler", "Charleroi", "KV Mechelen", "2026-11-08")
    b = scheda("jupiler", "Charleroi", "Malines", "2026-11-08")
    regole = {"/calcio/jupiler/charleroi-kv-mechelen/": "/calcio/jupiler/charleroi-malines/",
              "/calcio/jupiler/charleroi-malines/": "/calcio/jupiler/charleroi-mechelen/"}
    assert indirizzi.persi(registro_con(a, b, *OGGI), OGGI, regole) == []


def test_un_giro_chiuso_di_rinvii_e_perso():
    a = scheda("jupiler", "Charleroi", "KV Mechelen", "2026-11-08")
    regole = {"/calcio/jupiler/charleroi-kv-mechelen/": "/calcio/jupiler/charleroi-kv-mechelen/"}
    assert len(indirizzi.persi(registro_con(a, *OGGI), OGGI, regole)) == 1


def test_un_rinvio_verso_una_pagina_che_non_e_una_partita_basta():
    """La pagina del campionato non nasce da schede.json: da qui non si verifica."""
    a = scheda("jupiler", "Charleroi", "KV Mechelen", "2026-11-08")
    regole = {"/calcio/jupiler/charleroi-kv-mechelen/": "/calcio/jupiler/"}
    assert indirizzi.persi(registro_con(a, *OGGI), OGGI, regole) == []


def test_un_rinvio_con_l_indirizzo_completo_si_segue():
    a = scheda("jupiler", "Charleroi", "KV Mechelen", "2026-11-08")
    regole = {"/calcio/jupiler/charleroi-kv-mechelen/":
              "https://quotavera.it/calcio/jupiler/charleroi-malines/"}
    fuori = indirizzi.persi(registro_con(a, *OGGI), OGGI, regole)
    assert fuori[0].rinvio_a == "/calcio/jupiler/charleroi-malines/"


def test_la_barra_finale_conta():
    """Non si dà per scontato che Cloudflare la aggiunga: meglio un falso allarme."""
    a = scheda("jupiler", "Charleroi", "KV Mechelen", "2026-11-08")
    regole = {"/calcio/jupiler/charleroi-kv-mechelen": "/calcio/jupiler/charleroi-mechelen/"}
    assert len(indirizzi.persi(registro_con(a, *OGGI), OGGI, regole)) == 1


def test_una_regola_con_l_asterisco_copre_la_sezione():
    a = scheda("jupiler", "Charleroi", "KV Mechelen", "2026-11-08")
    regole = {"/calcio/jupiler/charleroi-kv-*": "/calcio/jupiler/"}
    assert indirizzi.persi(registro_con(a, *OGGI), OGGI, regole) == []


# --- la proposta di rinvio -----------------------------------------------------------

def proposta(vecchia, oggi):
    fuori = indirizzi.persi(registro_con(vecchia, *oggi), oggi, {})
    assert len(fuori) == 1
    return fuori[0].proposta


def test_il_caso_mechelen():
    """Il caso vero di novembre: la proposta è il rinvio che è stato scritto a mano."""
    vecchia = scheda("jupiler", "KV Mechelen", "Anderlecht", "2026-09-11")
    oggi = [scheda("jupiler", "Mechelen", "Anderlecht", "2026-09-11"),
            scheda("jupiler", "Charleroi", "Genk", "2026-09-11"),
            scheda("jupiler", "Mechelen", "Genk", "2026-10-31")]
    assert proposta(vecchia, oggi) == "/calcio/jupiler/mechelen-anderlecht/"


def test_il_caso_sheffield_e_oxford():
    oggi = [scheda("championship", "Preston", "Sheffield United", "2026-11-03"),
            scheda("championship", "Sheffield Weds", "Hull", "2026-11-03")]
    vecchia = scheda("championship", "Preston", "Sheffield Utd", "2026-11-03")
    assert proposta(vecchia, oggi) == "/calcio/championship/preston-sheffield-united/"

    oggi = [scheda("league-one", "Oxford", "Reading", "2026-11-04")]
    vecchia = scheda("league-one", "Oxford Utd", "Reading", "2026-11-04")
    assert proposta(vecchia, oggi) == "/calcio/league-one/oxford-reading/"


def test_con_una_data_diversa_non_si_propone_niente():
    vecchia = scheda("jupiler", "KV Mechelen", "Anderlecht", "2026-09-11")
    oggi = [scheda("jupiler", "Mechelen", "Anderlecht", "2026-09-12")]
    assert proposta(vecchia, oggi) is None


def test_in_un_altro_campionato_non_si_propone_niente():
    vecchia = scheda("jupiler", "KV Mechelen", "Anderlecht", "2026-09-11")
    oggi = [scheda("eredivisie", "Mechelen", "Anderlecht", "2026-09-11")]
    assert proposta(vecchia, oggi) is None


def test_un_nome_che_somiglia_a_due_squadre_non_si_abbina():
    """Le due Bristol: senza univocità il rinvio potrebbe finire sulla partita sbagliata."""
    vecchia = scheda("championship", "Bristol", "Reading", "2026-11-07")
    oggi = [scheda("championship", "Bristol City", "Reading", "2026-11-07"),
            scheda("championship", "Bristol Rovers", "Hull", "2026-11-07")]
    assert proposta(vecchia, oggi) is None


def test_un_nome_sconosciuto_non_si_abbina():
    vecchia = scheda("jupiler", "Malines", "Anderlecht", "2026-09-11")
    oggi = [scheda("jupiler", "Mechelen", "Anderlecht", "2026-09-11")]
    assert proposta(vecchia, oggi) is None


def test_il_racconto_ha_le_righe_da_copiare():
    vecchia = scheda("jupiler", "KV Mechelen", "Anderlecht", "2026-09-11")
    sola = scheda("jupiler", "Malines", "Genk", "2026-09-12")
    oggi = [scheda("jupiler", "Mechelen", "Anderlecht", "2026-09-11")]
    righe = indirizzi.racconta(indirizzi.persi(registro_con(vecchia, sola, *oggi), oggi, {}))
    assert righe[0] == "2 indirizzi di partita già pubblicati oggi danno 404:"
    assert any("da guardare a mano" in r and "malines-genk" in r for r in righe)
    assert righe[-1] == ("    /calcio/jupiler/kv-mechelen-anderlecht/ "
                         "/calcio/jupiler/mechelen-anderlecht/ 301")


def test_un_racconto_lungo_si_accorcia():
    vecchie = [scheda("serie-a", f"Squadra{i}", "Como", "2026-11-01") for i in range(30)]
    righe = indirizzi.racconta(indirizzi.persi(registro_con(*vecchie), [], {}), quanti=5)
    assert righe[0].startswith("30 indirizzi")
    assert righe[-1] == "    … e altri 25"


def test_niente_da_raccontare():
    assert indirizzi.racconta([]) == []


# --- la sentinella ----------------------------------------------------------------------

def test_la_sentinella_dice_il_guaio_con_la_riga_da_copiare(tmp_path):
    controlla = modulo("controlla")
    f, r = tmp_path / "indirizzi.json", tmp_path / "_redirects"
    vecchia = scheda("jupiler", "KV Mechelen", "Anderlecht", "2026-09-11")
    oggi = [scheda("jupiler", "Mechelen", "Anderlecht", "2026-09-11")]
    indirizzi.salva(registro_con(vecchia, *oggi), f)
    r.write_text("# niente ancora\n", encoding="utf-8")

    guai = controlla.controlla_indirizzi(oggi, f, r)
    assert len(guai) == 1
    assert ("/calcio/jupiler/kv-mechelen-anderlecht/ "
            "/calcio/jupiler/mechelen-anderlecht/ 301") in guai[0]

    # Scritto il rinvio, il guaio sparisce.
    r.write_text("/calcio/jupiler/kv-mechelen-anderlecht/ "
                 "/calcio/jupiler/mechelen-anderlecht/ 301\n", encoding="utf-8")
    assert controlla.controlla_indirizzi(oggi, f, r) == []


def test_la_sentinella_si_accorge_di_un_registro_fermo(tmp_path):
    """Se genera_sito non lo aggiorna più, le pagine di oggi non ci sono."""
    controlla = modulo("controlla")
    f, r = tmp_path / "indirizzi.json", tmp_path / "_redirects"
    indirizzi.salva(registro_con(OGGI[0]), f)
    guai = controlla.controlla_indirizzi(OGGI, f, r)
    assert len(guai) == 1 and "non lo sta aggiornando" in guai[0]


def test_la_sentinella_si_accorge_di_un_registro_rotto(tmp_path):
    controlla = modulo("controlla")
    f = tmp_path / "indirizzi.json"
    f.write_text("{rotto", encoding="utf-8")
    guai = controlla.controlla_indirizzi(OGGI, f, tmp_path / "_redirects")
    assert len(guai) == 1 and "non si legge" in guai[0]


# --- la ricostruzione dalla cronologia ---------------------------------------------------

def test_dalla_cronologia_si_prende_l_ultima_versione_di_ogni_giorno():
    ricostruisci = modulo("ricostruisci_indirizzi")
    # Come arriva da git log: dalla più nuova alla più vecchia.
    elenco = [("c4", "2026-10-03"), ("c3", "2026-10-02"), ("c2", "2026-10-02"),
              ("c1", "2026-10-01")]
    assert ricostruisci.una_al_giorno(elenco) == [
        ("c1", "2026-10-01"), ("c3", "2026-10-02"), ("c4", "2026-10-03")]
