"""I numeri di un campionato messi accanto a quelli degli altri ventuno.

E' il materiale degli articoli con i dati: quanti gol si segnano, quanto conta
giocare in casa, quanto spesso finisce zero a zero. Domande che la gente si fa
e a cui in italiano nessuno risponde mettendo in fila ventidue campionati.

Due scelte, tutte e due contro la tentazione del numero piu' fresco.

**Si contano stagioni intere.** Sulle ultime venti partite di ogni squadra un
campionato pesa circa 170 partite, e su 170 partite le classifiche ballano: il
fattore campo della Serie A, misurato cosi', la dava ultima su ventidue, mentre
sui gol grezzi della stessa finestra era penultima. Un titolo costruito su un
campione del genere e' fortunato, non vero. Tre stagioni sono un migliaio di
partite per campionato, e li' l'ordine smette di dipendere dal caso.

**La stagione in corso sta a parte.** Si mostra, perche' e' quella che il
lettore sta guardando, ma non entra nella classifica: a ottobre sono poche
giornate, e mescolarle alle stagioni intere vorrebbe dire dar loro lo stesso
peso di un campionato concluso.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

# Sotto questa soglia una stagione non entra nel conto. Un campionato di cui la
# fonte ha pubblicato solo un pezzo di stagione farebbe classifica con un
# campione troppo piccolo, e in testa o in fondo ci finirebbe per caso.
MINIMO_PER_STAGIONE = 100

# Le fasce degli articoli su angoli e tiri: "piu' angoli vuol dire piu' gol?".
# Larghe abbastanza da avere migliaia di partite ciascuna; i limiti sono
# inclusi, l'ultima fascia e' aperta.
FASCE_ANGOLI = ((0, 7), (8, 10), (11, 13), (14, None))
FASCE_IN_PORTA = ((0, 5), (6, 8), (9, 11), (12, None))


# --- quali partite hanno quale dato -------------------------------------------
#
# Il lettore di football-data mette 0 dove una colonna manca, e uno zero finto
# dentro una media e' un numero falso che nessuno vede. Qui si decide, partita
# per partita, se un dato c'e' davvero. Verificato sui CSV grezzi il 12
# novembre 2026: nelle tre stagioni intere primo tempo, tiri, angoli, falli e
# cartellini ci sono al 100% in ventuno campionati; la National League ha primo
# tempo e cartellini ma non tiri, angoli e falli.

def _solo_espn(p) -> bool:
    """Le partite che football-data non ha ancora: arrivano da ESPN, che non
    pubblica il punteggio del primo tempo (vedi `engine/dati/unione.py`)."""
    return p.incontro.id.startswith("espn-")


def _ha_intervallo(p) -> bool:
    if _solo_espn(p):
        return False
    pc, po = p.stat.gol_primo_tempo
    # Un primo tempo con piu' gol della partita intera e' un errore della fonte.
    return pc <= p.incontro.punti_casa and po <= p.incontro.punti_ospite


def _ha_cartellini(p) -> bool:
    # Per le partite di football-data i cartellini ci sono anche dove mancano
    # i tiri (National League); per quelle di ESPN solo se il tabellino e'
    # completo.
    return p.stat.completa or not _solo_espn(p)


def _ha_campo(p) -> bool:
    """Tiri, tiri in porta, angoli e falli: `completa` vuol dire che ci sono."""
    return p.stat.completa


def _quote_esiti(gruppo: list[str]) -> dict | None:
    """Come finisce, per chi era avanti all'intervallo: vince, pareggia, perde."""
    k = len(gruppo)
    if not k:
        return None
    return {
        "partite": k,
        "vince": round(gruppo.count("vince") / k, 4),
        "pari": round(gruppo.count("pari") / k, 4),
        "perde": round(gruppo.count("perde") / k, 4),
    }


def intervallo(partite: list) -> dict | None:
    """Il primo tempo e quello che succede dopo: chi e' avanti al riposo quante
    volte vince, quante volte si fa rimontare, e quanti gol arrivano nella
    ripresa. Solo le partite di cui si conosce il punteggio dell'intervallo."""
    h = [p for p in partite if _ha_intervallo(p)]
    n = len(h)
    if not n:
        return None
    avanti: list[tuple[int, bool, str]] = []    # (scarto, casa avanti?, come finisce)
    dopo_pari: list[int] = []                    # 0 casa, 1 pari, 2 ospite
    gol_pt = gol = 0
    for p in h:
        pc, po = p.stat.gol_primo_tempo
        fc, fo = p.incontro.punti_casa, p.incontro.punti_ospite
        gol_pt += pc + po
        gol += fc + fo
        if pc == po:
            dopo_pari.append(0 if fc > fo else (1 if fc == fo else 2))
            continue
        casa_avanti = pc > po
        fine = "pari" if fc == fo else ("vince" if (fc > fo) == casa_avanti else "perde")
        avanti.append((abs(pc - po), casa_avanti, fine))

    ribaltate = [a for a in avanti if a[2] == "perde"]
    return {
        "partite": n,
        "gol_primo": round(gol_pt / n, 3),
        "gol_secondo": round((gol - gol_pt) / n, 3),
        "quota_secondo": round((gol - gol_pt) / gol, 4) if gol else None,
        "avanti": round(len(avanti) / n, 4),
        "chi_avanti": _quote_esiti([a[2] for a in avanti]),
        "di_uno": _quote_esiti([a[2] for a in avanti if a[0] == 1]),
        "di_due": _quote_esiti([a[2] for a in avanti if a[0] >= 2]),
        "casa_avanti": _quote_esiti([a[2] for a in avanti if a[1]]),
        "ospite_avanti": _quote_esiti([a[2] for a in avanti if not a[1]]),
        "pari_intervallo": round(len(dopo_pari) / n, 4),
        "dopo_il_pari": {
            "partite": len(dopo_pari),
            "casa": round(dopo_pari.count(0) / len(dopo_pari), 4),
            "pari": round(dopo_pari.count(1) / len(dopo_pari), 4),
            "ospite": round(dopo_pari.count(2) / len(dopo_pari), 4),
        } if dopo_pari else None,
        # Le rimonte sono contate su tutte le partite, non solo su quelle con
        # qualcuno avanti: "una partita su N viene ribaltata" e' la frase che
        # si legge senza fare conti.
        "rimonte": round(len(ribaltate) / n, 4),
        "rimonte_casa": round(sum(1 for a in ribaltate if not a[1]) / n, 4),
        "rimonte_ospite": round(sum(1 for a in ribaltate if a[1]) / n, 4),
    }


def disciplina(partite: list) -> dict | None:
    """Cartellini e falli. I falli solo dove ci sono: la National League ha i
    cartellini ma non i falli, e "falli per giallo" si calcola sulle sole
    partite che li hanno entrambi."""
    c = [p for p in partite if _ha_cartellini(p)]
    n = len(c)
    if not n:
        return None
    gc = sum(p.stat.gialli[0] for p in c)
    go = sum(p.stat.gialli[1] for p in c)
    rc = sum(p.stat.rossi[0] for p in c)
    ro = sum(p.stat.rossi[1] for p in c)
    if gc + go == 0:
        # Nessun giallo in un intero gruppo di partite non e' un campionato
        # di gentiluomini: e' una colonna che manca.
        return None
    f = [p for p in c if _ha_campo(p)]
    falli = sum(sum(p.stat.falli) for p in f)
    gialli_f = sum(sum(p.stat.gialli) for p in f)
    return {
        "partite": n,
        "cartellini": round((gc + go + rc + ro) / n, 3),
        "gialli": round((gc + go) / n, 3),
        "gialli_casa": round(gc / n, 3),
        "gialli_ospite": round(go / n, 3),
        "rossi": round((rc + ro) / n, 4),
        "rossi_casa": round(rc / n, 4),
        "rossi_ospite": round(ro / n, 4),
        "partite_falli": len(f),
        "falli": round(falli / len(f), 3) if f and falli else None,
        "falli_per_giallo": round(falli / gialli_f, 2) if f and falli and gialli_f else None,
    }


def campo(partite: list) -> dict | None:
    """Tiri, tiri in porta e calci d'angolo, solo dove ci sono."""
    s = [p for p in partite if _ha_campo(p)]
    n = len(s)
    if not n:
        return None
    tiri = sum(sum(p.stat.tiri) for p in s)
    porta = sum(sum(p.stat.in_porta) for p in s)
    gol = sum(p.incontro.punti_casa + p.incontro.punti_ospite for p in s)
    if not tiri or not porta:
        return None
    return {
        "partite": n,
        "tiri": round(tiri / n, 3),
        "tiri_casa": round(sum(p.stat.tiri[0] for p in s) / n, 3),
        "tiri_ospite": round(sum(p.stat.tiri[1] for p in s) / n, 3),
        "in_porta": round(porta / n, 3),
        "corner": round(sum(sum(p.stat.corner) for p in s) / n, 3),
        "corner_casa": round(sum(p.stat.corner[0] for p in s) / n, 3),
        "corner_ospite": round(sum(p.stat.corner[1] for p in s) / n, 3),
        "precisione": round(porta / tiri, 4),
        "gol_per_tiro_in_porta": round(gol / porta, 4),
        "tiri_per_gol": round(tiri / gol, 2) if gol else None,
    }


def risultati(partite: list) -> dict[str, int]:
    """Quante volte ogni punteggio, dal piu' frequente. Casa prima: "1-0" e'
    la vittoria di chi gioca in casa, "0-1" quella dell'ospite."""
    conti = Counter(f"{p.incontro.punti_casa}-{p.incontro.punti_ospite}" for p in partite)
    return dict(sorted(conti.items(), key=lambda kv: (-kv[1], kv[0])))


def fasce(partite: list, misura, limiti) -> list[dict]:
    """I gol a partita dentro fasce di un'altra misura (angoli, tiri in porta).
    E' il modo di chiedere ai dati "piu' X vuol dire piu' gol?" senza un
    coefficiente di correlazione, che nessuno sa leggere."""
    s = [p for p in partite if _ha_campo(p)]
    fuori = []
    for da, a in limiti:
        dentro = [p for p in s if misura(p) >= da and (a is None or misura(p) <= a)]
        if not dentro:
            continue
        gol = sum(p.incontro.punti_casa + p.incontro.punti_ospite for p in dentro)
        fuori.append({"da": da, "a": a, "partite": len(dentro),
                      "quota": round(len(dentro) / len(s), 4),
                      "gol": round(gol / len(dentro), 3)})
    return fuori


def inizio_stagione(giorno: date) -> int:
    """L'anno in cui comincia la stagione di una partita. Luglio fa da confine:
    nessuno dei ventidue campionati gioca a luglio, quindi non c'e' ambiguita'."""
    return giorno.year if giorno.month >= 7 else giorno.year - 1


def etichetta(anno: int) -> str:
    """2025 -> '2025/26', come si scrive una stagione."""
    return f"{anno}/{(anno + 1) % 100:02d}"


def conta(partite: list) -> dict | None:
    """Le medie di un gruppo di partite. Tutte sono **totale diviso totale**:
    la media di una stagione e' la media delle sue partite, non delle medie
    delle sue giornate."""
    n = len(partite)
    if not n:
        return None
    casa = [p.incontro.punti_casa for p in partite]
    fuori = [p.incontro.punti_ospite for p in partite]

    def quota(condizione) -> float:
        return round(sum(1 for c, o in zip(casa, fuori) if condizione(c, o)) / n, 4)

    return {
        "partite": n,
        "gol": round((sum(casa) + sum(fuori)) / n, 3),
        "gol_casa": round(sum(casa) / n, 3),
        "gol_ospite": round(sum(fuori) / n, 3),
        "almeno_tre": quota(lambda c, o: c + o >= 3),
        "zero_a_zero": quota(lambda c, o: c == 0 and o == 0),
        "entrambe": quota(lambda c, o: c > 0 and o > 0),
        "vittorie_casa": quota(lambda c, o: c > o),
        "pareggi": quota(lambda c, o: c == o),
        "vittorie_ospite": quota(lambda c, o: c < o),
        # Il fattore campo: quante volte vince chi gioca in casa, meno quante
        # volte vince chi gioca fuori. Si poteva misurare in gol, e la
        # classifica viene quasi uguale; in vittorie si legge senza spiegazioni.
        "vantaggio": round((sum(1 for c, o in zip(casa, fuori) if c > o)
                            - sum(1 for c, o in zip(casa, fuori) if c < o)) / n, 4),
        # Le misure degli articoli su intervallo, cartellini, angoli e tiri.
        # Ognuna conta solo le partite che hanno quel dato, e dice su quante.
        "intervallo": intervallo(partite),
        "disciplina": disciplina(partite),
        "campo": campo(partite),
    }


def per_campionato(per_lega: list[tuple], stagione_in_corso: int) -> dict:
    """Un blocco per campionato, ordinati dal piu' prolifico al meno.

    `per_lega` e' una lista di (catalogo, partite), la stessa che usano le
    chicche trasversali. `stagione_in_corso` e' l'anno d'inizio della stagione
    che si sta giocando: tutto quello che viene prima ed e' abbastanza grande
    conta come stagione intera.
    """
    righe = []
    tutte: list = []
    for c, partite in per_lega:
        divise: dict[int, list] = defaultdict(list)
        for p in partite:
            divise[inizio_stagione(p.incontro.data)].append(p)

        intere = sorted(a for a, ps in divise.items()
                        if a < stagione_in_corso and len(ps) >= MINIMO_PER_STAGIONE)
        if not intere:
            continue
        insieme = [p for a in intere for p in divise[a]]
        tutte += insieme
        righe.append({
            "slug": c.slug,
            "nome": c.nome,
            "paese": c.paese,
            "bandiera": c.bandiera,
            "livello": c.livello,
            "stagioni": [etichetta(a) for a in intere],
            "totale": conta(insieme),
            "per_stagione": {etichetta(a): conta(divise[a]) for a in intere},
            "in_corso": conta(divise.get(stagione_in_corso, [])),
            "risultati": risultati(insieme),
        })

    # Due classifiche sugli stessi dati: l'ordine della lista e' quello dei gol,
    # la posizione per il fattore campo sta in un campo a parte.
    for i, r in enumerate(sorted(righe, key=lambda r: -r["totale"]["vantaggio"]), start=1):
        r["posizione_campo"] = i
    righe.sort(key=lambda r: -r["totale"]["gol"])
    for i, r in enumerate(righe, start=1):
        r["posizione_gol"] = i

    # Le stagioni che tutti i campionati hanno per intero: e' quello che la
    # pagina puo' dichiarare senza note a margine.
    comuni = sorted(set.intersection(*(set(r["stagioni"]) for r in righe))) if righe else []
    return {
        "stagioni_comuni": comuni,
        "stagione_in_corso": etichetta(stagione_in_corso),
        "campionati": righe,
        # Tutti i campionati insieme, stagioni intere: la frase d'apertura degli
        # articoli ("chi e' avanti all'intervallo vince il ...") parla del
        # calcio europeo, non di un campionato. E' calcolata sulle partite, non
        # come media delle medie: un campionato da 552 partite a stagione pesa
        # piu' di uno da 180, come deve.
        "tutti": conta(tutte) if tutte else None,
        "tutti_risultati": risultati(tutte),
        "angoli_e_gol": fasce(tutte, lambda p: sum(p.stat.corner), FASCE_ANGOLI),
        "porta_e_gol": fasce(tutte, lambda p: sum(p.stat.in_porta), FASCE_IN_PORTA),
    }
