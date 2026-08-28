"""Dal motore al sito, su dati veri.

Scarica lo storico e il calendario da football-data.co.uk, stima un modello per
campionato, calcola le statistiche di squadra e scrive i JSON che Astro legge
in fase di build.

Il motore calcola, questo script serializza, il sito disegna: nessuna logica di
modello qui dentro, altrimenti finirebbe per esistere in due posti.

    python scripts/genera_sito.py
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from engine.classifica import calcola as calcola_classifica
from engine.classifica import posizioni_attese, ultimi_risultati
from engine.core.market import margine, probabilita_implicite
from engine.core.types import Fixture
from engine.dati.catalogo import CAMPIONATI, PER_SLUG
from engine.dati.football_data import calendario, carica, stagioni
from engine.sports.football.model import ModelloCalcio
from engine.statistiche import calcola, conversione_media, precedenti

USCITA = RADICE / "sito" / "src" / "dati"

# Quante stagioni di storia per stimare. Sui dati veri le squadre cambiano, e
# la storia lontana e' rumore: tre stagioni con il decadimento predefinito sono
# il compromesso fra avere abbastanza partite e non pesare rose che non
# esistono piu'.
STORIA = stagioni(2023, 2026)
STAGIONE = "2526"


def arrotonda(v: float, d: int = 4) -> float:
    return round(float(v), d)


def numeri_ruolo(r) -> dict:
    return {
        "partite": r.partite,
        "gol_fatti": arrotonda(r.gol_fatti_partita, 2),
        "gol_subiti": arrotonda(r.gol_subiti_partita, 2),
        "tiri": arrotonda(r.tiri_partita, 1),
        "in_porta": arrotonda(r.in_porta_partita, 1),
        "in_porta_subiti": arrotonda(r.in_porta_subiti_partita, 1),
        "corner": arrotonda(r.corner_partita, 1),
        "cartellini": arrotonda(r.cartellini_partita, 1),
        "over_25": arrotonda(r.quota_over_25, 3),
        "gol_gol": arrotonda(r.quota_gol_gol, 3),
        "clean_sheet": arrotonda(r.quota_clean_sheet, 3),
        "a_secco": arrotonda(r.quota_a_secco, 3),
    }


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
    """Tutto quello che serve al sito per un campionato."""
    if len(storico) < 100:
        return None

    modello = ModelloCalcio().fit([p.incontro for p in storico])
    conv = conversione_media(stagione) if stagione else 0.31
    stat = calcola(stagione)
    forma = calcola(stagione, ultime=6)

    partite_lega = [p for p in cal if p.campionato == c.slug]
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
            "precedenti": [
                {"data": x.incontro.data.isoformat(), "casa": x.incontro.casa,
                 "ospite": x.incontro.ospite, "gol_casa": x.incontro.punti_casa,
                 "gol_ospite": x.incontro.punti_ospite}
                for x in precedenti(storico, p.casa, p.ospite, quante=6)
            ],
        })

    squadre = sorted((numeri_squadra(s, conv) for s in stat.values()),
                     key=lambda s: s["scarto_conversione"], reverse=True)

    tabella = calcola_classifica(stagione, conv)
    attese = posizioni_attese(tabella)
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

    risultati = [
        {
            "data": p.incontro.data.isoformat(),
            "casa": p.incontro.casa,
            "ospite": p.incontro.ospite,
            "gol_casa": p.incontro.punti_casa,
            "gol_ospite": p.incontro.punti_ospite,
            "in_porta_casa": p.stat.in_porta[0] if p.stat.completa else None,
            "in_porta_ospite": p.stat.in_porta[1] if p.stat.completa else None,
        }
        for p in ultimi_risultati(stagione, quanti=20)
    ]

    return {
        "slug": c.slug, "nome": c.nome, "paese": c.paese, "bandiera": c.bandiera,
        "livello": c.livello, "principale": c.principale,
        "partite_storico": len(storico),
        "partite_stagione": len(stagione),
        "conversione": arrotonda(conv, 4),
        "vantaggio_casa": arrotonda(modello.vantaggio_casa, 4),
        "squadre": squadre,
        "calendario": righe,
        "schede": schede,
        "classifica": classifica,
        "risultati": risultati,
        "sorprese": sorprese(stagione, c),
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
    for c in CAMPIONATI:
        storico = carica(c.slug, STORIA)
        stagione = [p for p in storico if p.incontro.data >= date(2025, 7, 1)]
        dati = elabora(c, storico, stagione, cal)
        if not dati:
            print(f"  {c.etichetta:34s} dati insufficienti, salto")
            continue
        leghe.append(dati)
        print(f"  {c.etichetta:34s} {len(storico):5d} storico ·"
              f" {len(dati['squadre']):2d} squadre ·"
              f" {len(dati['calendario']):2d} in programma ·"
              f" campo {dati['vantaggio_casa']:+.3f}")

    print()
    indice = [{k: v for k, v in l.items()
               if k not in ("squadre", "calendario", "schede", "sorprese",
                            "classifica", "risultati")}
              for l in leghe]
    scrivi("campionati.json", {"generato_il": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "fonte": "football-data.co.uk",
                               "campionati": indice})
    scrivi("calendario.json", {"campionati": {l["slug"]: l["calendario"] for l in leghe}})
    scrivi("squadre.json", {"campionati": {l["slug"]: l["squadre"] for l in leghe}})
    scrivi("classifiche.json", {"campionati": {l["slug"]: l["classifica"] for l in leghe}})
    scrivi("risultati.json", {"campionati": {l["slug"]: l["risultati"] for l in leghe}})
    scrivi("schede.json", {"partite": [s for l in leghe for s in l["schede"]]})
    scrivi("articolo.json", articolo(leghe))

    print("\nFatto: dati veri, nessuna simulazione.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
