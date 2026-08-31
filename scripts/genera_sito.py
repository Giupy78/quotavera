"""Dal motore al sito, su dati veri.

Scarica lo storico e il calendario da football-data.co.uk, stima un modello per
campionato, calcola le statistiche di squadra e scrive i JSON che Astro legge
in fase di build.

Il motore calcola, questo script serializza, il sito disegna: nessuna logica di
modello qui dentro, altrimenti finirebbe per esistere in due posti.

    python scripts/genera_sito.py
"""

from __future__ import annotations

from collections import defaultdict
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from engine.classifica import calcola as calcola_classifica
from engine.classifica import giornate, posizioni_attese
from engine.core.market import margine, probabilita_implicite
from engine.core.types import Fixture
from engine.dati.catalogo import CAMPIONATI, PER_SLUG
from engine.dati.football_data import calendario, carica, stagioni
from engine.dati import espn, openfootball
from engine.dati.unione import fondi
from engine.sports.football.model import ModelloCalcio
from engine.statistiche import calcola, conversione_media, precedenti

USCITA = RADICE / "sito" / "src" / "dati"

# Quante stagioni di storia per stimare. Sui dati veri le squadre cambiano, e
# la storia lontana e' rumore: tre stagioni con il decadimento predefinito sono
# il compromesso fra avere abbastanza partite e non pesare rose che non
# esistono piu'.
STORIA = stagioni(2023, 2027)

# Il confine fra una stagione e l'altra. I campionati europei girano da agosto
# a maggio: tutto cio' che e' stato giocato dopo il 1 luglio appartiene alla
# stagione in corso.
INIZIO_STAGIONE = date(2026, 7, 1)
INIZIO_STAGIONE_PRECEDENTE = date(2025, 7, 1)
NOME_STAGIONE = "2026/27"
NOME_STAGIONE_PRECEDENTE = "2025/26"

# Quante partite servono perche' una statistica di squadra significhi qualcosa.
#
# A fine agosto la stagione nuova ha una giornata giocata: una classifica su una
# partita e' comunque la classifica — e' quello che la parola vuol dire — ma
# statistiche costruite su una partita sola non sono statistiche. Per quelle si
# usa una finestra mobile che attraversa il cambio di stagione, ed e' anche il
# modo giusto di misurare una squadra: la sosta estiva non azzera come gioca.
FINESTRA = 20

# Quante partite indietro puo' guardare chi legge. Sono quattro scelte e non un
# cursore libero perche' il sito e' statico: ogni finestra e' calcolata qui e
# scritta nella pagina, e il lettore le scambia senza che parta una richiesta.
# Cinque per la forma del momento, quaranta per il fondo stagione; venti resta
# il valore predefinito, che e' il compromesso fra rumore e attualita'.
FINESTRE = (5, 10, 20, 40)


def arrotonda(v: float, d: int = 4) -> float:
    return round(float(v), d)


def oggi_utc() -> date:
    """La data di oggi in UTC — la stessa che vede la macchina di GitHub."""
    return datetime.now(timezone.utc).date()


def numeri_ruolo(r) -> dict:
    return {
        "partite": r.partite,
        "gol_fatti": arrotonda(r.gol_fatti_partita, 2),
        "gol_subiti": arrotonda(r.gol_subiti_partita, 2),
        "tiri": arrotonda(r.tiri_partita, 1),
        "in_porta": arrotonda(r.in_porta_partita, 1),
        "in_porta_subiti": arrotonda(r.in_porta_subiti_partita, 1),
        "tiri_subiti": arrotonda(r.tiri_subiti_partita, 1),
        "corner": arrotonda(r.corner_partita, 1),
        "corner_subiti": arrotonda(r.corner_subiti_partita, 1),
        "falli": arrotonda(r.falli_partita, 1),
        "cartellini": arrotonda(r.cartellini_partita, 1),
        "gialli": r.gialli,
        "rossi": r.rossi,
        "precisione_tiri": arrotonda(r.precisione_tiri, 3),
        "over_25": arrotonda(r.quota_over_25, 3),
        "gol_gol": arrotonda(r.quota_gol_gol, 3),
        "clean_sheet": arrotonda(r.quota_clean_sheet, 3),
        "a_secco": arrotonda(r.quota_a_secco, 3),
        # Dal tabellino ESPN. `con_avanzate` a zero significa che per questa
        # squadra non ne abbiamo ancora: il sito deve saperlo per non stampare
        # zeri che sembrano misure.
        "con_avanzate": r.con_avanzate,
        "possesso": arrotonda(r.possesso_medio, 1),
        "passaggi": arrotonda(r.passaggi_partita, 0),
        "precisione_passaggi": arrotonda(r.precisione_passaggi, 3),
        "precisione_cross": arrotonda(r.precisione_cross, 3),
        "precisione_lanci": arrotonda(r.precisione_lanci, 3),
        "contrasti": arrotonda(r.contrasti_partita, 1),
        "intercetti": arrotonda(r.intercetti_partita, 1),
        "respinte": arrotonda(r.respinte_partita, 1),
        "parate": arrotonda(r.parate_partita, 1),
        "fuorigioco": arrotonda(r.fuorigioco_partita, 1),
        "tiri_respinti": arrotonda(r.tiri_respinti_partita, 1),
    }


def incrocio(casa, ospite) -> list[dict] | None:
    """Attacco di chi gioca in casa contro difesa di chi gioca fuori.

    E' il confronto che serve davvero e che quasi nessuno fa. Mostrare i tiri
    dell'Inter accanto ai tiri del Como non dice niente: giocano contro
    avversari diversi. Mettere i tiri che l'Inter *fa in casa* accanto ai tiri
    che il Como *concede fuori* e' un incrocio, e risponde alla domanda vera —
    quanto e' probabile che questa partita produca tiri.

    Ogni riga tiene i due ruoli separati: la media complessiva di una squadra
    nasconde la differenza fra come gioca in casa e come gioca in trasferta,
    che in molti campionati e' il fattore piu' grande di tutti.
    """
    if not casa or not ospite:
        return None
    c, o = casa["casa"], ospite["trasferta"]
    righe = [
        ("Gol", c["gol_fatti"], o["gol_subiti"], 2),
        ("Tiri", c["tiri"], o["tiri_subiti"], 1),
        ("Tiri in porta", c["in_porta"], o["in_porta_subiti"], 1),
        ("Calci d'angolo", c["corner"], o["corner_subiti"], 1),
    ]
    fuori = [{"voce": v, "attacco": a, "difesa": d,
              "media": arrotonda((a + d) / 2, dec)}
             for v, a, d, dec in righe]
    # Le avanzate solo se ci sono da tutte e due le parti: mezza riga vuota
    # confonde piu' di una riga assente.
    # Con una partita sola "media possesso" e' una parola grossa: e' quel
    # singolo dato, e nell'incrocio i due valori sommerebbero a cento perche'
    # vengono dalla stessa partita. Sotto tre, meglio non dirlo.
    if c.get("con_avanzate", 0) >= 3 and o.get("con_avanzate", 0) >= 3:
        fuori.append({"voce": "Possesso", "attacco": c["possesso"],
                      "difesa": o["possesso"], "media": None})
    return fuori


def numeri_squadra(s, conv: float) -> dict:
    return {
        "squadra": s.squadra,
        "partite": s.partite,
        "gol_fatti": arrotonda(s.gol_fatti_partita, 2),
        "gol_subiti": arrotonda(s.gol_subiti_partita, 2),
        "gol_totali": s.gol_totali,
        "in_porta_totali": s.in_porta_totali,
        "attesi_dai_tiri": arrotonda(s.in_porta_totali * conv, 1),
        "scarto_conversione": arrotonda(s.scarto_dalla_conversione(conv), 1),
        "vantaggio_casa": arrotonda(s.vantaggio_casa, 2),
        "casa": numeri_ruolo(s.casa),
        "trasferta": numeri_ruolo(s.trasferta),
    }


def elabora(c, storico, stagione, cal) -> dict | None:
    """Tutto quello che serve al sito per un campionato.

    `stagione` sono le partite della stagione in corso — poche, a inizio anno.
    Le statistiche non si calcolano su quelle ma su una finestra mobile delle
    ultime partite giocate da ogni squadra, che scavalca la sosta estiva.
    """
    if len(storico) < 100:
        return None

    modello = ModelloCalcio().fit([p.incontro for p in storico])
    # La conversione media serve un campione ampio: si prende dallo storico
    # recente, non dalla stagione in corso che potrebbe avere dieci partite.
    conv = conversione_media(storico[-500:]) if storico else 0.31
    stat = calcola(storico, ultime=FINESTRA)
    forma = calcola(storico, ultime=6)

    # Il calendario di football-data continua a elencare partite gia' giocate
    # finche' non le sposta nel file dei risultati, e quel passaggio puo'
    # tardare giorni. Il risultato, senza questo filtro, e' un sito che mostra
    # Milan-Venezia "in programma" e due sezioni piu' sotto ne pubblica il 2-0.
    #
    # Adesso che ESPN ci dice quali sono finite, si incrociano: se una partita
    # e' nello storico, dal calendario esce. La tolleranza sulla data serve
    # perche' le due fonti non concordano sempre sul giorno.
    giocate: dict[tuple[str, str], list] = {}
    for x in storico:
        giocate.setdefault((x.incontro.casa, x.incontro.ospite), []).append(x.incontro.data)

    def gia_giocata(p) -> bool:
        return any(abs((d - p.data).days) <= 3
                   for d in giocate.get((p.casa, p.ospite), ()))

    # E una regola che non dipende da nessuna fonte: una partita di ieri non e'
    # "in programma". Serve per i due campionati scozzesi minori, che ESPN non
    # copre — li' non sappiamo il risultato, ma sappiamo che si sono giocate, e
    # tenerle fra le prossime sarebbe sbagliato comunque.
    # Il margine di un giorno evita di far sparire le partite di stasera per
    # via del fuso: il lavoro notturno gira in UTC.
    ieri = oggi_utc() - timedelta(days=1)

    partite_lega = [p for p in cal
                    if p.campionato == c.slug and not gia_giocata(p) and p.data > ieri]
    tolte = sum(1 for p in cal if p.campionato == c.slug) - len(partite_lega)
    if tolte:
        print(f"  {c.etichetta:34s} {tolte} partite tolte dal calendario: gia' giocate")
    righe, schede = [], []

    for p in partite_lega:
        quote = p.riferimento()
        p_mkt = list(probabilita_implicite(list(quote), metodo="shin")) if quote else None

        p_mod = None
        if p.casa in modello.squadre and p.ospite in modello.squadre:
            f = Fixture(p.id, datetime.combine(p.data, datetime.min.time()),
                        p.casa, p.ospite, c.nome)
            pred = modello.predict(f)
            p_mod = [pred.probabilita("1x2", e) for e in ("1", "X", "2")]
            dettaglio = {
                "gol_attesi_casa": arrotonda(pred.dettaglio["gol_attesi_casa"], 2),
                "gol_attesi_ospite": arrotonda(pred.dettaglio["gol_attesi_ospite"], 2),
                "matrice": [[arrotonda(v, 5) for v in riga[:6]]
                            for riga in pred.dettaglio["matrice"][:6]],
                "risultati_probabili": [
                    {"risultato": r["risultato"], "p": arrotonda(r["p"], 4)}
                    for r in pred.dettaglio["risultati_probabili"]
                ],
                "mercati": {n: {k: arrotonda(v, 4) for k, v in m.items()}
                            for n, m in pred.mercati.items()},
            }
        else:
            dettaglio = None

        riga = {
            "id": p.id,
            "casa": p.casa,
            "ospite": p.ospite,
            "data": p.data.isoformat(),
            "ora": p.ora,
            "quote": {k: list(v) for k, v in p.quote.items()},
            "p_mercato": [arrotonda(x) for x in p_mkt] if p_mkt else None,
            "p_modello": [arrotonda(x) for x in p_mod] if p_mod else None,
            "margine": arrotonda(margine(list(quote)), 4) if quote else None,
            "margine_migliore": (arrotonda(margine(list(p.quote["massimo"])), 4)
                                 if "massimo" in p.quote else None),
        }
        righe.append(riga)

        sc = stat.get(p.casa)
        so = stat.get(p.ospite)
        schede.append({
            **riga,
            "campionato": c.slug,
            "dettaglio": dettaglio,
            "stat_casa": numeri_squadra(sc, conv) if sc else None,
            "stat_ospite": numeri_squadra(so, conv) if so else None,
            "forma_casa": numeri_squadra(forma[p.casa], conv) if p.casa in forma else None,
            "forma_ospite": numeri_squadra(forma[p.ospite], conv) if p.ospite in forma else None,
            "incrocio": incrocio(numeri_squadra(sc, conv) if sc else None,
                                 numeri_squadra(so, conv) if so else None),
            "precedenti": [
                {"data": x.incontro.data.isoformat(), "casa": x.incontro.casa,
                 "ospite": x.incontro.ospite, "gol_casa": x.incontro.punti_casa,
                 "gol_ospite": x.incontro.punti_ospite}
                for x in precedenti(storico, p.casa, p.ospite, quante=6)
            ],
        })

    # Chi milita nel campionato *adesso*: la finestra mobile guarda indietro tre
    # stagioni, quindi senza questo filtro comparirebbero le retrocesse. Sono
    # quelle che hanno giocato in questa stagione, piu' quelle che compaiono nel
    # calendario — le neopromosse che non hanno ancora esordito.
    attuali = {p.incontro.casa for p in stagione} | {p.incontro.ospite for p in stagione}
    for p in cal:
        if p.campionato == c.slug:
            attuali |= {p.casa, p.ospite}

    squadre = sorted(
        (numeri_squadra(s, conv) for nome, s in stat.items() if nome in attuali),
        key=lambda s: s["scarto_conversione"], reverse=True,
    )

    # Le stesse statistiche su piu' profondita', perche' la domanda "come sta
    # questa squadra" non ha una sola risposta giusta: cinque partite dicono il
    # momento e sono quasi tutto rumore, quaranta dicono il valore e non si
    # accorgono di un cambio di allenatore. Darle tutte e lasciare scegliere e'
    # piu' onesto che sceglierne una e presentarla come la verita'.
    finestre = {}
    for n_finestra in FINESTRE:
        st = calcola(storico, ultime=n_finestra)
        finestre[str(n_finestra)] = sorted(
            (numeri_squadra(x, conv) for nome, x in st.items() if nome in attuali),
            key=lambda s: s["scarto_conversione"], reverse=True,
        )

    # Quanto della finestra e' di questa stagione. A inizio anno la risposta e'
    # "quasi niente", e va detto: chi legge deve sapere che sta guardando in
    # buona parte il campionato scorso. Il numero si calcola, non si scrive a
    # mano — cosi' l'avviso sparisce da solo quando smette di essere vero.
    per_squadra = defaultdict(list)
    for p_st in sorted(storico, key=lambda x: x.incontro.data):
        per_squadra[p_st.incontro.casa].append(p_st)
        per_squadra[p_st.incontro.ospite].append(p_st)
    composizione = {}
    for n_finestra in FINESTRE:
        dentro = fuori_stagione = 0
        for nome in attuali:
            for p_st in per_squadra.get(nome, [])[-n_finestra:]:
                if p_st.incontro.data >= INIZIO_STAGIONE:
                    dentro += 1
                else:
                    fuori_stagione += 1
        totale = dentro + fuori_stagione
        composizione[str(n_finestra)] = {
            "di_questa_stagione": dentro,
            "di_prima": fuori_stagione,
            "quota_stagione": arrotonda(dentro / totale, 3) if totale else 0.0,
        }

    # La classifica invece e' della stagione in corso e basta: sommare i punti
    # dell'anno scorso a quelli di quest'anno non sarebbe una classifica.
    tabella = calcola_classifica(stagione, conv)
    attese = posizioni_attese(tabella)
    n_giornate = max((r.giocate for r in tabella), default=0)
    classifica = [
        {
            "posizione": n,
            "squadra": r.squadra,
            "giocate": r.giocate,
            "vinte": r.vinte,
            "pareggiate": r.pareggiate,
            "perse": r.perse,
            "fatti": r.fatti,
            "subiti": r.subiti,
            "differenza": r.differenza,
            "punti": r.punti,
            "punti_attesi": arrotonda(r.punti_attesi, 1),
            "scarto_punti": arrotonda(r.scarto_punti, 1),
            "posizione_attesa": attese[r.squadra],
            "salto": attese[r.squadra] - n,
        }
        for n, r in enumerate(tabella, start=1)
    ]

    # I risultati raggruppati per giornata, dalla piu' recente. Un elenco piatto
    # di partite non si legge: chi guarda vuole vedere il turno, come su
    # qualsiasi sito di risultati.
    #
    # Se la stagione e' appena cominciata si mostrano anche le ultime giornate
    # di quella precedente, altrimenti la sezione sarebbe quasi vuota.
    numeri = giornate(stagione)
    per_giornata: dict[int, list] = defaultdict(list)
    for p in stagione:
        per_giornata[numeri[p.incontro.id]].append(p)

    if len(per_giornata) < 3:
        # Solo la stagione precedente, non tutto lo storico: le giornate si
        # contano dentro una stagione, altrimenti il contatore arriva a 120.
        precedente = [
            p for p in storico
            if INIZIO_STAGIONE_PRECEDENTE <= p.incontro.data < INIZIO_STAGIONE
        ]
        numeri_prec = giornate(precedente)
        ultime = sorted({numeri_prec[p.incontro.id] for p in precedente})[-3:]
        for p in precedente:
            n = numeri_prec[p.incontro.id]
            if n in ultime:
                per_giornata[n - 1000].append(p)      # negative: stagione scorsa

    def riga_risultato(p):
        return {
            "data": p.incontro.data.isoformat(),
            "casa": p.incontro.casa,
            "ospite": p.incontro.ospite,
            "gol_casa": p.incontro.punti_casa,
            "gol_ospite": p.incontro.punti_ospite,
            "in_porta_casa": p.stat.in_porta[0] if p.stat.completa else None,
            "in_porta_ospite": p.stat.in_porta[1] if p.stat.completa else None,
        }

    risultati = [
        {
            "giornata": n if n > 0 else n + 1000,
            "stagione_scorsa": n < 0,
            "partite": sorted(
                (riga_risultato(p) for p in gruppo), key=lambda r: r["data"]
            ),
        }
        for n, gruppo in sorted(per_giornata.items(), reverse=True)
    ][:8]

    return {
        "slug": c.slug, "nome": c.nome, "paese": c.paese, "bandiera": c.bandiera,
        "livello": c.livello, "principale": c.principale,
        "partite_storico": len(storico),
        "partite_stagione": len(stagione),
        "stagione": NOME_STAGIONE,
        "stagione_precedente": NOME_STAGIONE_PRECEDENTE,
        "giornate_giocate": n_giornate,
        "finestra_statistiche": FINESTRA,
        "conversione": arrotonda(conv, 4),
        "vantaggio_casa": arrotonda(modello.vantaggio_casa, 4),
        "squadre": squadre,
        "finestre": finestre,
        "composizione_finestre": composizione,
        "calendario": righe,
        "schede": schede,
        "classifica": classifica,
        "risultati": risultati,
        "sorprese": sorprese(stagione, c),
        "stagione_completa": stagione_completa(c, set(stat) | attuali),
    }


def stagione_completa(c, nostre_squadre: set[str]) -> dict | None:
    """Il calendario dell'intera stagione, giornata per giornata.

    Viene da openfootball, che pubblica il calendario ufficiale con il numero
    di giornata scritto. football-data ne da' solo una settimana, quindi senza
    questa fonte il sito non potrebbe dire quando gioca una squadra fra un mese.

    I nomi delle due fonti non coincidono ("FC Internazionale Milano" contro
    "Inter") e vanno riconciliati, altrimenti il calendario non si collega ne'
    alle statistiche ne' alle schede partita.
    """
    partite, alias = openfootball.carica(c.slug)
    if not partite:
        return None

    # Dalla forma canonica al nome che usiamo noi ovunque nel sito.
    verso_nostro = {
        openfootball.normalizza(n, alias): n for n in nostre_squadre
    }

    def nostro(nome: str) -> str | None:
        return verso_nostro.get(openfootball.normalizza(nome, alias))

    per_giornata: dict[int, list] = defaultdict(list)
    non_risolte = 0
    for p in partite:
        casa, ospite = nostro(p.casa), nostro(p.ospite)
        if not casa or not ospite:
            non_risolte += 1
        per_giornata[p.giornata].append({
            "data": p.data.isoformat(),
            "ora": p.ora,
            # Il nome nostro quando lo conosciamo, quello di openfootball
            # altrimenti: meglio una riga con un nome diverso che una mancante.
            "casa": casa or p.casa,
            "ospite": ospite or p.ospite,
            "collegabile": bool(casa and ospite),
            "gol_casa": p.gol_casa,
            "gol_ospite": p.gol_ospite,
            "giocata": p.giocata,
        })

    giornate_ordinate = sorted(per_giornata)
    # La giornata "corrente" e' la prima che non sia interamente giocata.
    corrente = next(
        (n for n in giornate_ordinate
         if any(not x["giocata"] for x in per_giornata[n])),
        giornate_ordinate[-1] if giornate_ordinate else 1,
    )
    return {
        "giornate": [
            {"numero": n,
             "partite": sorted(per_giornata[n], key=lambda x: (x["data"], x["ora"]))}
            for n in giornate_ordinate
        ],
        "corrente": corrente,
        "totale": len(giornate_ordinate),
        "non_risolte": non_risolte,
    }


def sorprese(storico, c, quante: int = 40) -> list[dict]:
    """I risultati recenti che il gioco non spiega.

    Non e' cronaca: della partita sappiamo solo i numeri, e arrivano con un
    paio di giorni di ritardo. Ma il taglio che possiamo dare e' quello che
    nessuno da', perche' richiede di guardare i tiri invece del tabellino:
    **quella vittoria era meritata o e' stata varianza?**

    Chi vince tirando in porta molto meno dell'avversario ha vinto contro il
    gioco, e quel risultato tende a non ripetersi. Chi perde dominando ai tiri
    tende a raddrizzarla. Sono le due situazioni che il pubblico legge sempre
    al contrario, perche' la classifica registra solo il punteggio.
    """
    recenti = [p for p in storico if p.stat.completa][-quante:]
    fuori = []
    for p in recenti:
        i = p.incontro
        casa_p, ospite_p = p.stat.in_porta
        esito = p.esito
        if esito == 1:
            continue                       # un pareggio non sorprende nessuno
        vincitore_casa = esito == 0
        tiri_vincitore = casa_p if vincitore_casa else ospite_p
        tiri_perdente = ospite_p if vincitore_casa else casa_p
        scarto = tiri_perdente - tiri_vincitore
        if scarto < 3:
            continue                       # ha vinto chi ha creato di piu': normale

        fuori.append({
            "campionato": c.nome, "bandiera": c.bandiera, "slug": c.slug,
            "data": i.data.isoformat(),
            "casa": i.casa, "ospite": i.ospite,
            "gol_casa": i.punti_casa, "gol_ospite": i.punti_ospite,
            "in_porta_casa": casa_p, "in_porta_ospite": ospite_p,
            "vincitore": i.casa if vincitore_casa else i.ospite,
            "perdente": i.ospite if vincitore_casa else i.casa,
            "scarto_tiri": scarto,
        })
    fuori.sort(key=lambda x: (x["scarto_tiri"], x["data"]), reverse=True)
    return fuori[:3]


def articolo(leghe: list[dict]) -> dict:
    """L'articolo del giorno, costruito dai numeri e non dalle opinioni.

    Non contiene consigli di gioco: contiene fatti misurati e il perche'
    meritano attenzione. E' la differenza fra una rubrica statistica e un sito
    di pronostici, e sta tutta nel modo in cui sono scritte queste righe.
    """
    tutte = [(l, s) for l in leghe for s in l["squadre"] if s["in_porta_totali"] > 40]
    sopra = sorted(tutte, key=lambda x: x[1]["scarto_conversione"], reverse=True)[:5]
    sotto = sorted(tutte, key=lambda x: x[1]["scarto_conversione"])[:5]

    partite = [(l, p) for l in leghe for p in l["calendario"]
               if p["margine"] is not None]
    care = sorted(partite, key=lambda x: x[1]["margine"], reverse=True)[:5]
    convenienti = sorted(partite, key=lambda x: x[1]["margine"])[:5]

    def voce(l, s):
        return {"campionato": l["nome"], "bandiera": l["bandiera"], **s}

    def voce_partita(l, p):
        return {"campionato": l["nome"], "bandiera": l["bandiera"], "slug": l["slug"],
                "id": p["id"], "casa": p["casa"], "ospite": p["ospite"],
                "data": p["data"], "ora": p["ora"], "margine": p["margine"]}

    tutte_sorprese = [s for l in leghe for s in l.get("sorprese", [])]
    tutte_sorprese.sort(key=lambda x: x["scarto_tiri"], reverse=True)

    return {
        "data": date.today().isoformat(),
        "partite_in_programma": sum(len(l["calendario"]) for l in leghe),
        "campionati": len(leghe),
        "sorprese": tutte_sorprese[:6],
        "segnano_piu_di_quanto_creano": [voce(l, s) for l, s in sopra],
        "segnano_meno_di_quanto_creano": [voce(l, s) for l, s in sotto],
        "partite_piu_care": [voce_partita(l, p) for l, p in care],
        "partite_meno_care": [voce_partita(l, p) for l, p in convenienti],
    }


def scrivi(nome: str, dati) -> None:
    USCITA.mkdir(parents=True, exist_ok=True)
    percorso = USCITA / nome
    percorso.write_text(json.dumps(dati, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {percorso.relative_to(RADICE)}  ({percorso.stat().st_size:,} byte)")


def main() -> int:
    print("Scarico il calendario…")
    cal = calendario()
    print(f"  {len(cal)} partite in programma\n")

    leghe = []
    oggi = date.today()
    for c in CAMPIONATI:
        storico = carica(c.slug, STORIA)

        # Il buco che ESPN riempie: football-data pubblica a turno concluso e
        # puo' arrivare con giorni di ritardo, cosi' il sito resta fermo mentre
        # il campionato va avanti. Qui si prendono da ESPN le partite gia'
        # giocate che football-data non ha ancora, e le statistiche avanzate
        # che non avra' mai.
        #
        # I nomi contro cui abbinare sono quelli della *stagione in corso* —
        # dalle partite gia' giocate e dal calendario. Usare tutto lo storico
        # metterebbe in gara squadre retrocesse anni fa, e una somiglianza di
        # troppo e' precisamente il modo in cui i gol finiscono nella squadra
        # sbagliata.
        in_corso = [p for p in storico if p.incontro.data >= INIZIO_STAGIONE]
        squadre_note = sorted(
            {p.incontro.casa for p in in_corso} | {p.incontro.ospite for p in in_corso}
            | {p.casa for p in cal if p.campionato == c.slug}
            | {p.ospite for p in cal if p.campionato == c.slug}
        )
        if squadre_note:
            recenti, _ = espn.aggiorna(c.slug, squadre_note, INIZIO_STAGIONE, oggi)
            storico, arricchite, aggiunte = fondi(storico, recenti, c.slug)
            if aggiunte or arricchite:
                print(f"  {c.etichetta:34s} ESPN: +{aggiunte} partite,"
                      f" {arricchite} arricchite")

        stagione = [p for p in storico if p.incontro.data >= INIZIO_STAGIONE]
        dati = elabora(c, storico, stagione, cal)
        if not dati:
            print(f"  {c.etichetta:34s} dati insufficienti, salto")
            continue
        leghe.append(dati)
        print(f"  {c.etichetta:34s} {len(storico):5d} storico ·"
              f" {dati['giornate_giocate']:2d} giornate {NOME_STAGIONE} ·"
              f" {len(dati['calendario']):2d} in programma ·"
              f" campo {dati['vantaggio_casa']:+.3f}")

    print()
    indice = [{k: v for k, v in l.items()
               if k not in ("squadre", "calendario", "schede", "sorprese",
                            "classifica", "risultati", "stagione_completa",
                            "finestre")}
              for l in leghe]
    # Due date diverse, e tenerle separate e' il punto.
    #
    # `generato_il` dice quando abbiamo guardato. `dati_fino_al` dice fin dove
    # arrivano i risultati che abbiamo trovato. Le fonti pubblicano a turno
    # concluso, un paio di volte a settimana: fra il venerdi' e la domenica si
    # gioca e non esce niente, e un sito che mostra solo "ultimo aggiornamento:
    # stanotte" sembra rotto proprio quando sta funzionando. Con tutt'e due si
    # legge la differenza fra "il nostro processo si e' inceppato" e "il turno
    # non e' ancora finito", che per chi guarda non e' la stessa cosa.
    giocate = [p["data"] for l in leghe for g in l["risultati"] for p in g["partite"]]
    scrivi("campionati.json", {"generato_il": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "dati_fino_al": max(giocate) if giocate else None,
                               "fonte": "football-data.co.uk",
                               "campionati": indice})
    scrivi("calendario.json", {"campionati": {l["slug"]: l["calendario"] for l in leghe}})
    scrivi("squadre.json", {"campionati": {l["slug"]: l["squadre"] for l in leghe}})
    scrivi("finestre.json", {
        "disponibili": list(FINESTRE),
        "predefinita": FINESTRA,
        "campionati": {l["slug"]: {"dati": l["finestre"],
                                   "composizione": l["composizione_finestre"]}
                       for l in leghe},
    })
    scrivi("classifiche.json", {"campionati": {l["slug"]: l["classifica"] for l in leghe}})
    scrivi("risultati.json", {"campionati": {l["slug"]: l["risultati"] for l in leghe}})
    scrivi("stagione.json", {"campionati": {
        l["slug"]: l["stagione_completa"] for l in leghe if l["stagione_completa"]
    }})
    scrivi("schede.json", {"partite": [s for l in leghe for s in l["schede"]]})
    scrivi("articolo.json", articolo(leghe))

    print("\nFatto: dati veri, nessuna simulazione.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
