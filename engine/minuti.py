"""In che minuto si segna: i gol della stagione in corso, minuto per minuto.

E' il materiale dell'articolo `/statistiche/minuti-dei-gol/`. A differenza
degli altri articoli con i dati non usa football-data, che il minuto dei gol
non lo pubblica: usa l'elenco dei gol dei tabellini ESPN, che c'e' solo per
la stagione in corso. Per questo l'articolo dice "in questa stagione" e non
"nelle ultime tre".

Due regole, tutte e due contro i numeri falsi.

**Un campionato entra solo se i suoi tabellini sono completi.** Se una partita
finita 2-1 non ha l'elenco dei gol, quei tre gol non hanno minuto, e contare
solo gli altri sposterebbe le quote verso le partite che ESPN racconta meglio.
Sotto il 95% di partite complete il campionato resta fuori, e la pagina lo
dice. A novembre 2026 restano fuori le due divisioni scozzesi minori, dove
ESPN non pubblica l'elenco.

**Del tipo di gol si usano solo rigori e autogol.** ESPN etichetta anche i
colpi di testa e le punizioni, ma non sempre: i gol di testa risultano il 5%,
dove nel calcio sono intorno al 15. Un'etichetta che manca una volta su tre non
fa una statistica.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date

# Sotto questa quota di partite con tabellino completo, il campionato non entra.
COMPLETEZZA_MINIMA = 0.95

_MINUTO = re.compile(r"^(\d+)'(?:\+(\d+)')?$")

# Le fasce dell'articolo: sei quarti d'ora e i due recuperi, a parte. Il
# recupero sta da solo perche' "al 45'+2'" non e' il 45': mettere i gol del
# recupero dentro l'ultimo quarto d'ora gonfierebbe quella fascia senza dirlo.
FASCE = (
    ("1'-15'", 1, 15, False),
    ("16'-30'", 16, 30, False),
    ("31'-45'", 31, 45, False),
    ("recupero 1° tempo", 45, 45, True),
    ("46'-60'", 46, 60, False),
    ("61'-75'", 61, 75, False),
    ("76'-90'", 76, 90, False),
    ("recupero 2° tempo", 90, 90, True),
)


def leggi_minuto(testo: str | None) -> tuple[int, int] | None:
    """"45'+2'" -> (45, 2); "67'" -> (67, 0); tutto il resto -> None."""
    m = _MINUTO.match((testo or "").strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2) or 0)


def fascia(base: int, recupero: int) -> int:
    """L'indice della fascia di un gol."""
    if recupero and base <= 45:
        return 3
    if recupero and base >= 90:
        return 7
    if base <= 45:
        return min(max(base - 1, 0) // 15, 2)
    return 4 + min((base - 46) // 15, 2)


def _completa(p: dict) -> bool:
    """La partita ha un elenco dei gol che torna con il punteggio, e ogni gol
    ha un minuto leggibile. Uno 0-0 senza elenco e' completo per definizione."""
    gol = p.get("gol") or []
    if len(gol) != p.get("gol_casa", 0) + p.get("gol_ospite", 0):
        return False
    return all(leggi_minuto(g.get("minuto")) for g in gol)


def _conta(partite: list[dict]) -> dict | None:
    n = len(partite)
    if not n:
        return None
    fasce = Counter()
    rigori = autogol = 0
    primi = []
    for p in partite:
        minuti = []
        for g in p.get("gol") or []:
            base, extra = leggi_minuto(g["minuto"])
            fasce[fascia(base, extra)] += 1
            tipo = (g.get("tipo") or "").lower()
            rigori += "penalty" in tipo
            autogol += "own" in tipo
            minuti.append(base + extra / 100)
        if minuti:
            primi.append(min(minuti))
    gol = sum(fasce.values())
    if not gol:
        return None
    q = lambda k: round(fasce[k] / gol, 4)
    return {
        "partite": n,
        "gol": gol,
        "gol_a_partita": round(gol / n, 3),
        "fasce": [{"etichetta": e, "gol": fasce[i], "quota": q(i), "recupero": r}
                  for i, (e, _, _, r) in enumerate(FASCE)],
        "primo_tempo": round(sum(fasce[i] for i in range(4)) / gol, 4),
        "secondo_tempo": round(sum(fasce[i] for i in range(4, 8)) / gol, 4),
        "recupero": round((fasce[3] + fasce[7]) / gol, 4),
        "finale": round((fasce[6] + fasce[7]) / gol, 4),       # dal 76' in poi
        "rigori": round(rigori / gol, 4),
        "autogol": round(autogol / gol, 4),
        "senza_gol": round(sum(1 for p in partite if not p.get("gol")) / n, 4),
        # Il minuto del primo gol, sulle sole partite che ne hanno uno.
        "primo_gol_medio": round(sum(int(x) for x in primi) / len(primi), 1) if primi else None,
        "primo_gol_entro_15": round(sum(1 for x in primi if x <= 15) / n, 4),
    }


def per_il_sito(schede: list[dict], dal: date, catalogo: list) -> dict:
    """Il file `minuti.json`. `schede` sono le partite del sito, `dal` l'inizio
    della stagione, `catalogo` i campionati (slug, nome, paese, bandiera)."""
    giocate = [p for p in schede if p.get("giocata") and p.get("data", "") >= dal.isoformat()]
    righe, escluse, buone = [], [], []
    for c in catalogo:
        qui = [p for p in giocate if p.get("campionato") == c.slug]
        if not qui:
            continue
        complete = [p for p in qui if _completa(p)]
        if len(complete) / len(qui) < COMPLETEZZA_MINIMA:
            escluse.append({"slug": c.slug, "nome": c.nome,
                            "completezza": round(len(complete) / len(qui), 4)})
            continue
        buone += complete
        dati = _conta(complete)
        if dati:
            righe.append({"slug": c.slug, "nome": c.nome, "paese": c.paese,
                          "bandiera": c.bandiera, **dati})
    righe.sort(key=lambda r: -r["finale"])
    return {
        "dal": dal.isoformat(),
        "tutti": _conta(buone),
        "campionati": righe,
        "esclusi": escluse,
    }
