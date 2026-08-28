"""Il movimento della linea contiene informazione? La prova, su partite vere.

E' la domanda da cui dipende se vale la pena costruire il pezzo che segue il
prezzo in tempo reale. Se la quota di chiusura non e' migliore di quella di
apertura, allora il movimento e' rumore, seguirlo non serve a nessuno, e il
prodotto non esiste.

Il conto e' semplice e non lascia scampo: si prendono le due quote dello stesso
libro sulla stessa partita, si ripuliscono entrambe dal margine, e si guarda
quale delle due ha previsto meglio l'esito davvero avvenuto.

    python scripts/analisi_movimento.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from engine.core.market import probabilita_implicite
from engine.core.metrics import brier, calibrazione, errore_calibrazione, log_loss
from engine.dati.football_data import carica, stagioni

CAMPIONATI = ["serie-a", "premier-league", "laliga", "bundesliga",
              "ligue-1", "eredivisie", "primeira-liga", "superlig"]
NOMI = {"serie-a": "Serie A", "premier-league": "Premier League",
        "laliga": "LaLiga", "bundesliga": "Bundesliga", "ligue-1": "Ligue 1",
        "eredivisie": "Eredivisie", "primeira-liga": "Primeira Liga",
        "superlig": "Süper Lig"}
STAGIONI = stagioni(2021, 2026)
LIBRI = ("betfair", "pinnacle")


def main() -> int:
    print("=" * 76)
    print("  IL MERCATO IMPARA? apertura contro chiusura, su partite vere")
    print(f"  stagioni {STAGIONI[0]} … {STAGIONI[-1]}")
    print("=" * 76)

    tot_ap, tot_ch, tot_esiti = [], [], []
    per_campionato = []
    movimenti = []
    # Quante volte l'esito che si e' accorciato (prezzo sceso = piu' probabile
    # secondo il mercato) e' poi davvero successo, contro quante volte lo
    # prevedeva l'apertura.
    accorciati_vinti = 0
    accorciati_totali = 0
    p_apertura_sugli_accorciati = 0.0
    p_chiusura_sugli_accorciati = 0.0

    for slug in CAMPIONATI:
        partite = carica(slug, STAGIONI)
        ap, ch, esiti = [], [], []

        for p in partite:
            coppia = None
            for libro in LIBRI:
                coppia = p.coppia(libro)
                if coppia:
                    break
            if not coppia:
                continue
            quote_ap, quote_ch = coppia
            p_ap = probabilita_implicite(list(quote_ap), metodo="shin")
            p_ch = probabilita_implicite(list(quote_ch), metodo="shin")
            ap.append(p_ap)
            ch.append(p_ch)
            esiti.append(p.esito)

            spostamento = max(abs(a - c) for a, c in zip(p_ap, p_ch))
            movimenti.append(spostamento)

            # L'esito che si e' mosso di piu' verso l'alto.
            k = max(range(3), key=lambda i: p_ch[i] - p_ap[i])
            if p_ch[k] - p_ap[k] > 0.03:
                accorciati_totali += 1
                accorciati_vinti += 1 if p.esito == k else 0
                p_apertura_sugli_accorciati += p_ap[k]
                p_chiusura_sugli_accorciati += p_ch[k]

        if not ap:
            continue
        b_ap, b_ch = brier(ap, esiti), brier(ch, esiti)
        per_campionato.append((NOMI[slug], len(ap), b_ap, b_ch))
        tot_ap.extend(ap)
        tot_ch.extend(ch)
        tot_esiti.extend(esiti)

    print(f"\nPartite con apertura e chiusura dello stesso libro: {len(tot_ap):,}")

    b_ap, b_ch = brier(tot_ap, tot_esiti), brier(tot_ch, tot_esiti)
    l_ap, l_ch = log_loss(tot_ap, tot_esiti), log_loss(tot_ch, tot_esiti)

    print("\n" + "=" * 76)
    print("  1. QUALE DELLE DUE QUOTE PREVEDE MEGLIO")
    print("=" * 76)
    print(f"  Brier    apertura {b_ap:.5f}   chiusura {b_ch:.5f}   "
          f"scarto {b_ap - b_ch:+.5f}")
    print(f"  Log-loss apertura {l_ap:.5f}   chiusura {l_ch:.5f}   "
          f"scarto {l_ap - l_ch:+.5f}")
    print()
    if b_ch < b_ap:
        print("  La chiusura vince. Il movimento NON e' rumore: fra l'apertura e")
        print("  il fischio d'inizio il mercato impara qualcosa, e lo mette nel prezzo.")
    else:
        print("  L'apertura vince. Il movimento e' rumore, e seguirlo non serve.")

    print("\n" + "=" * 76)
    print("  2. QUANTO SI MUOVONO I PREZZI")
    print("=" * 76)
    movimenti.sort()
    n = len(movimenti)
    print(f"  spostamento mediano   {movimenti[n // 2]:.1%} di probabilita'")
    print(f"  un quarto delle volte oltre {movimenti[3 * n // 4]:.1%}")
    print(f"  un decimo delle volte oltre {movimenti[9 * n // 10]:.1%}")
    grossi = sum(1 for m in movimenti if m > 0.05)
    print(f"  movimenti sopra i 5 punti: {grossi:,} partite ({grossi / n:.0%})")

    print("\n" + "=" * 76)
    print("  3. QUANDO UN ESITO SI ACCORCIA, POI SUCCEDE?")
    print("=" * 76)
    if accorciati_totali:
        reale = accorciati_vinti / accorciati_totali
        attesa_ap = p_apertura_sugli_accorciati / accorciati_totali
        attesa_ch = p_chiusura_sugli_accorciati / accorciati_totali
        # Errore standard di una proporzione: senza, la differenza qui sotto
        # potrebbe essere solo il caso.
        errore = (reale * (1 - reale) / accorciati_totali) ** 0.5

        print(f"  casi in cui un esito guadagna oltre 3 punti: {accorciati_totali:,}")
        print(f"  l'apertura gli dava in media       {attesa_ap:.1%}")
        print(f"  la chiusura gli dava in media      {attesa_ch:.1%}")
        print(f"  si e' poi verificato               {reale:.1%}  (±{2 * errore:.1%})")
        print()
        print(f"  contro l'apertura  {reale - attesa_ap:+.1%}"
              f"   <- quanto il mercato ha imparato")
        print(f"  contro la chiusura {reale - attesa_ch:+.1%}"
              f"   <- deve essere ~0, altrimenti c'e' un errore")
        print()
        print("  La seconda riga e' il controllo che conta. Avendo scelto gli esiti")
        print("  *perche'* si erano accorciati, la frequenza osservata deve")
        print("  coincidere con la probabilita' di CHIUSURA, non con quella di")
        print("  apertura. Se coincide, il salto rispetto all'apertura e' esattamente")
        print("  l'informazione entrata nel prezzo — e non un effetto della selezione.")

    print("\n" + "=" * 76)
    print("  4. CAMPIONATO PER CAMPIONATO")
    print("=" * 76)
    print(f"  {'Campionato':16s} {'partite':>8s} {'apertura':>10s} {'chiusura':>10s} {'scarto':>9s}")
    for nome, quante, a, c in sorted(per_campionato, key=lambda r: r[2] - r[3], reverse=True):
        print(f"  {nome:16s} {quante:8,d} {a:10.5f} {c:10.5f} {a - c:+9.5f}")

    fasce_ch = calibrazione(
        [p[k] for p in tot_ch for k in range(3)],
        [k == v for p, v in zip(tot_ch, tot_esiti) for k in range(3)],
    )
    print(f"\n  Errore di calibrazione della chiusura: {errore_calibrazione(fasce_ch):.4f}")
    print("  (e' il metro contro cui il nostro modello dovra' misurarsi)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
