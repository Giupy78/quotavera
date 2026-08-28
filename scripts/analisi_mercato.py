"""Cosa mostriamo a chi ci guarda: il conto, su partite vere.

Questo script non stima niente e non prevede niente. Prende le quote di
chiusura reali degli ultimi anni e risponde a tre domande che nessun sito pone
al lettore, e che si possono verificare senza fidarsi di noi:

  1. quanto si tiene il banco, davvero, su ogni giocata
  2. quanto varia il prezzo dello stesso identico esito da un libro all'altro
  3. quanto costa, in euro, prendere il prezzo medio invece del migliore

La terza e' la piu' importante, perche' e' una perdita certa e silenziosa che
riguarda chiunque giochi senza confrontare — cioe' quasi tutti.

    python scripts/analisi_mercato.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from engine.core.market import margine, probabilita_implicite
from engine.dati.football_data import CODICI, carica, stagioni

CAMPIONATI = ["serie-a", "premier-league", "laliga", "bundesliga",
              "ligue-1", "eredivisie", "primeira-liga", "superlig"]
NOMI = {"serie-a": "Serie A", "premier-league": "Premier League",
        "laliga": "LaLiga", "bundesliga": "Bundesliga", "ligue-1": "Ligue 1",
        "eredivisie": "Eredivisie", "primeira-liga": "Primeira Liga",
        "superlig": "Süper Lig"}
STAGIONI = stagioni(2021, 2026)      # dalla 2021/22 alla 2025/26


def media(valori: list[float]) -> float:
    return sum(valori) / len(valori) if valori else 0.0


def main() -> int:
    print("=" * 78)
    print("  QUOTE DI CHIUSURA VERE — football-data.co.uk")
    print(f"  stagioni {STAGIONI[0]} … {STAGIONI[-1]}")
    print("=" * 78)

    totali: dict[str, list[float]] = {}
    costo_totale: list[float] = []
    righe = []

    for slug in CAMPIONATI:
        partite = carica(slug, STAGIONI)
        if not partite:
            continue

        margini: dict[str, list[float]] = {}
        costo: list[float] = []
        dispersione: list[float] = []

        for p in partite:
            for libro, quote in p.quote.items():
                margini.setdefault(libro, []).append(margine(list(quote)))

            if "media" not in p.quote or "massimo" not in p.quote:
                continue
            avg, mx = p.quote["media"], p.quote["massimo"]
            # Quanto perde chi prende il prezzo medio invece del migliore.
            #
            # Si passa dal rendimento atteso, non sommando le differenze di
            # quota sui tre esiti: quella somma vale per chi gioca un euro su
            # *ognuno* dei tre, cioe' tre euro, e sovrastima di circa tre volte.
            #
            # Per uno scommettitore le cui probabilita' sono corrette, il
            # rendimento atteso su un libro con somma delle inverse S vale
            # esattamente 1/S per euro giocato. La differenza fra i due libri
            # e' quindi 1/S_migliore - 1/S_media, e non dipende da quale esito
            # sceglie: e' il costo del prezzo, non della previsione.
            s_avg = sum(1.0 / q for q in avg)
            s_max = sum(1.0 / q for q in mx)
            costo.append(1.0 / s_max - 1.0 / s_avg)
            dispersione.append(media([(m - a) / a for a, m in zip(avg, mx)]))

        righe.append({
            "nome": NOMI[slug],
            "partite": len(partite),
            "margini": {k: media(v) for k, v in margini.items()},
            "costo": media(costo),
            "dispersione": media(dispersione),
        })
        for k, v in margini.items():
            totali.setdefault(k, []).extend(v)
        costo_totale.extend(costo)

        print(f"\n{NOMI[slug]:16s} {len(partite):5d} partite")
        for libro in ("betfair", "pinnacle", "bet365", "media", "massimo"):
            if libro in margini:
                print(f"   margine {libro:9s} {media(margini[libro]):+7.2%}"
                      f"   ({len(margini[libro])} partite)")

    print("\n" + "=" * 78)
    print("  1. QUANTO SI TIENE IL BANCO — tutti i campionati insieme")
    print("=" * 78)
    for libro in ("betfair", "pinnacle", "bet365", "media", "massimo"):
        if libro in totali:
            etichetta = {
                "betfair": "Betfair Exchange (mercato vero)",
                "pinnacle": "Pinnacle (il banco piu' preciso)",
                "bet365": "Bet365 (banco al dettaglio)",
                "media": "media di tutti i libri",
                "massimo": "prendendo sempre il prezzo migliore",
            }[libro]
            print(f"  {etichetta:36s} {media(totali[libro]):+7.2%}")

    print("\n" + "=" * 78)
    print("  2. QUANTO COSTA NON CONFRONTARE")
    print("=" * 78)
    c = media(costo_totale)
    print(f"  Prendere la quota media invece della migliore costa {c:.2%}")
    print(f"  per euro giocato: su 100 euro sono {c * 100:.2f} euro,")
    print(f"  su 10.000 euro giocati in una stagione sono {c * 10000:.0f} euro.")
    print()
    print("  Non dipende da chi vince la partita: e' il prezzo, non l'esito.")
    print("  E' anche piu' di quanto il miglior modello del mondo potrebbe mai")
    print("  guadagnare, il che dice quale dei due problemi conviene risolvere.")

    print("\n" + "=" * 78)
    print("  3. CAMPIONATO PER CAMPIONATO")
    print("=" * 78)
    print(f"  {'Campionato':16s} {'partite':>8s} {'Pinnacle':>9s} {'Bet365':>8s}"
          f" {'migliore':>9s} {'costo medio':>12s}")
    for r in sorted(righe, key=lambda x: x["margini"].get("pinnacle", 9)):
        m = r["margini"]
        print(f"  {r['nome']:16s} {r['partite']:8d} {m.get('pinnacle', 0):+8.2%}"
              f" {m.get('bet365', 0):+7.2%} {m.get('massimo', 0):+8.2%}"
              f" {r['costo']:+11.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
