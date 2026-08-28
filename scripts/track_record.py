"""Il track record vero: il modello contro la quota di chiusura del mercato.

E' la verifica che decide se questo progetto ha una gamba su cui stare, e va
fatta in un modo solo: **camminando in avanti nel tempo**. Per ogni partita il
modello viene stimato usando esclusivamente le partite giocate prima, e poi
confrontato con la quota di chiusura — il prezzo che il mercato espone al
fischio d'inizio, quando tutte le informazioni sono arrivate.

Due errori rendono inutile un backtest, e qui sono evitati per costruzione:

  1. **guardare avanti.** Stimare su tutta la stagione e poi "prevedere" partite
     che erano nel campione e' il modo piu' comune di ottenere numeri splendidi
     e falsi. Qui la ristima usa solo il passato, sempre.
  2. **scegliersi l'avversario.** Misurarsi contro le quote di apertura, o
     contro la media di tutti i libri, e' darsi ragione da soli. Il confronto e'
     con la chiusura di Betfair o Pinnacle, che e' il metro piu' duro esistente.

    python scripts/track_record.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from engine.core.market import probabilita_implicite
from engine.core.metrics import brier, calibrazione, errore_calibrazione, log_loss
from engine.core.types import Fixture
from engine.dati.catalogo import CAMPIONATI
from engine.dati.football_data import carica, stagioni
from engine.sports.football.model import ModelloCalcio

USCITA = RADICE / "sito" / "src" / "dati"

STAGIONI = stagioni(2017, 2026)     # nove stagioni
MINIMO_STORIA = 300                  # partite prima di iniziare a misurare
OGNI = 40                            # ogni quante partite si ristima (~una giornata)


def valuta(campionato) -> dict | None:
    partite = carica(campionato.slug, STAGIONI)
    if len(partite) < MINIMO_STORIA + 200:
        return None

    p_modello, p_mercato, esiti, stagioni_di = [], [], [], []
    modello = None
    da_ristimare = OGNI

    for i, p in enumerate(partite):
        quote = p.riferimento()          # chiusura di Betfair, o Pinnacle
        misurabile = i >= MINIMO_STORIA and quote is not None

        if misurabile and da_ristimare >= OGNI:
            # Solo il passato: `partite[:i]` sono le gare gia' giocate.
            try:
                modello = ModelloCalcio().fit(
                    [x.incontro for x in partite[:i]], riferimento=p.incontro.data
                )
            except ValueError:
                modello = None
            da_ristimare = 0

        if misurabile and modello:
            casa, ospite = p.incontro.casa, p.incontro.ospite
            if casa in modello.squadre and ospite in modello.squadre:
                f = Fixture(p.incontro.id,
                            datetime.combine(p.incontro.data, datetime.min.time()),
                            casa, ospite, campionato.nome)
                pred = modello.predict(f)
                p_modello.append([pred.probabilita("1x2", e) for e in ("1", "X", "2")])
                p_mercato.append(list(probabilita_implicite(list(quote), metodo="shin")))
                esiti.append(p.esito)
                stagioni_di.append(p.incontro.data.year)
            da_ristimare += 1
        elif misurabile:
            da_ristimare += 1

    if len(p_modello) < 200:
        return None

    def fasce(prob):
        dichiarate = [x[k] for x in prob for k in range(3)]
        avvenuti = [k == v for x, v in zip(prob, esiti) for k in range(3)]
        return calibrazione(dichiarate, avvenuti, fasce=10)

    f_mod, f_mkt = fasce(p_modello), fasce(p_mercato)

    per_anno = defaultdict(lambda: {"n": 0, "mod": 0.0, "mkt": 0.0})
    for pm, pk, e, anno in zip(p_modello, p_mercato, esiti, stagioni_di):
        g = per_anno[anno]
        g["n"] += 1
        g["mod"] += sum((pm[k] - (1.0 if k == e else 0.0)) ** 2 for k in range(3))
        g["mkt"] += sum((pk[k] - (1.0 if k == e else 0.0)) ** 2 for k in range(3))

    return {
        "slug": campionato.slug, "nome": campionato.nome,
        "bandiera": campionato.bandiera, "paese": campionato.paese,
        "partite": len(p_modello),
        "brier_modello": round(brier(p_modello, esiti), 5),
        "brier_mercato": round(brier(p_mercato, esiti), 5),
        "logloss_modello": round(log_loss(p_modello, esiti), 5),
        "logloss_mercato": round(log_loss(p_mercato, esiti), 5),
        "ece_modello": round(errore_calibrazione(f_mod), 5),
        "ece_mercato": round(errore_calibrazione(f_mkt), 5),
        "calibrazione_modello": [
            {"centro": round(x.centro, 3), "dichiarata": round(x.dichiarata, 4),
             "osservata": round(x.osservata, 4), "casi": x.casi} for x in f_mod
        ],
        "calibrazione_mercato": [
            {"centro": round(x.centro, 3), "dichiarata": round(x.dichiarata, 4),
             "osservata": round(x.osservata, 4), "casi": x.casi} for x in f_mkt
        ],
        "per_anno": [
            {"anno": a, "partite": g["n"],
             "brier_modello": round(g["mod"] / g["n"], 5),
             "brier_mercato": round(g["mkt"] / g["n"], 5)}
            for a, g in sorted(per_anno.items()) if g["n"] >= 50
        ],
    }


def main() -> int:
    print("=" * 76)
    print("  TRACK RECORD — il modello contro la quota di chiusura")
    print("=" * 76)
    print(f"  stagioni {STAGIONI[0]}…{STAGIONI[-1]}, ristima ogni {OGNI} partite,"
          f" solo sul passato\n")

    risultati = []
    for c in CAMPIONATI:
        if not c.principale:
            continue
        print(f"  {c.etichetta:30s} ", end="", flush=True)
        r = valuta(c)
        if not r:
            print("dati insufficienti")
            continue
        risultati.append(r)
        segno = "meglio" if r["brier_modello"] < r["brier_mercato"] else "peggio"
        print(f"{r['partite']:5d} partite   modello {r['brier_modello']:.5f}"
              f"   mercato {r['brier_mercato']:.5f}   {segno}")

    if not risultati:
        print("\nNessun campionato misurabile.")
        return 1

    tot = sum(r["partite"] for r in risultati)
    pesata = lambda k: sum(r[k] * r["partite"] for r in risultati) / tot

    b_mod, b_mkt = pesata("brier_modello"), pesata("brier_mercato")
    l_mod, l_mkt = pesata("logloss_modello"), pesata("logloss_mercato")

    print("\n" + "=" * 76)
    print(f"  COMPLESSIVO — {tot:,} partite fuori campione")
    print("=" * 76)
    print(f"  Brier     modello {b_mod:.5f}   mercato {b_mkt:.5f}   "
          f"scarto {b_mod - b_mkt:+.5f}")
    print(f"  Log-loss  modello {l_mod:.5f}   mercato {l_mkt:.5f}   "
          f"scarto {l_mod - l_mkt:+.5f}")
    print(f"  Calibraz. modello {pesata('ece_modello'):.5f}   "
          f"mercato {pesata('ece_mercato'):.5f}")
    print()
    if b_mod < b_mkt:
        print("  Il modello batte la chiusura. Da verificare due volte prima di")
        print("  crederci: e' un risultato che quasi nessuno ottiene.")
    else:
        print("  Il mercato vince, come previsto. Il modello resta utile per")
        print("  descrivere una partita, non per batterne il prezzo.")

    riepilogo = {
        "generato_il": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "partite": tot,
        "stagioni": f"{STAGIONI[0]}–{STAGIONI[-1]}",
        "brier_modello": round(b_mod, 5),
        "brier_mercato": round(b_mkt, 5),
        "logloss_modello": round(l_mod, 5),
        "logloss_mercato": round(l_mkt, 5),
        "ece_modello": round(pesata("ece_modello"), 5),
        "ece_mercato": round(pesata("ece_mercato"), 5),
        "campionati": risultati,
    }
    USCITA.mkdir(parents=True, exist_ok=True)
    percorso = USCITA / "track-record.json"
    percorso.write_text(json.dumps(riepilogo, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"\n  scritto {percorso.relative_to(RADICE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
