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

from collections import defaultdict
from datetime import date

# Sotto questa soglia una stagione non entra nel conto. Un campionato di cui la
# fonte ha pubblicato solo un pezzo di stagione farebbe classifica con un
# campione troppo piccolo, e in testa o in fondo ci finirebbe per caso.
MINIMO_PER_STAGIONE = 100


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
    }


def per_campionato(per_lega: list[tuple], stagione_in_corso: int) -> dict:
    """Un blocco per campionato, ordinati dal piu' prolifico al meno.

    `per_lega` e' una lista di (catalogo, partite), la stessa che usano le
    chicche trasversali. `stagione_in_corso` e' l'anno d'inizio della stagione
    che si sta giocando: tutto quello che viene prima ed e' abbastanza grande
    conta come stagione intera.
    """
    righe = []
    for c, partite in per_lega:
        divise: dict[int, list] = defaultdict(list)
        for p in partite:
            divise[inizio_stagione(p.incontro.data)].append(p)

        intere = sorted(a for a, ps in divise.items()
                        if a < stagione_in_corso and len(ps) >= MINIMO_PER_STAGIONE)
        if not intere:
            continue
        insieme = [p for a in intere for p in divise[a]]
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
        })

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
    }
