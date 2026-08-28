"""Dal motore al sito: scrive i JSON che Astro legge in fase di build.

E' la cerniera fra le due meta' del progetto, ed e' volutamente stupida: il
motore calcola, questo script serializza, il sito disegna. Nessuna logica di
modello qui dentro, altrimenti finirebbe per esistere in due posti.

In produzione lo chiamera' il cron notturno, con i dati veri al posto della
simulazione. La forma dei file non cambia.

    python scripts/genera_sito.py
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
sys.path.insert(0, str(RADICE / "scripts"))

from campionati import CAMPIONATI, Campionato, forze_simulate
from engine.core.market import kelly, probabilita_implicite, valore_atteso
from engine.core.metrics import (
    brier,
    calibrazione,
    curva_profitto,
    curva_rendimento,
    errore_calibrazione,
    rendimento,
    ribasso_massimo,
)
from engine.core.types import Fixture, Incontro
from engine.sports.basketball.model import ModelloBasket
from engine.sports.football.model import ModelloCalcio, esiti_1x2, matrice_da_lambde
from engine.sports.tennis.model import ModelloTennis

USCITA = RADICE / "sito" / "src" / "dati"

STAGIONI_STORIA = 6      # su cui il modello si stima
STAGIONI_PROVA = 2       # tenute da parte per misurare come e' andata
Z_SHIN = 0.0225
RUMORE_BANCO = 0.03

# La soglia oltre cui uno scarto vale la pena di essere segnalato.
#
# Va tarata sull'errore dello *scarto*, non su quello che sembra tanto. Il
# modello sbaglia ogni probabilita' di 5-6 punti; il banco ne sbaglia meno.
# L'errore della differenza fra i due e' quindi di circa 6 punti, e due errori
# standard fanno 12. Sotto quella soglia "valore" e' solo il rumore del modello
# con un altro nome — il trucco per cui certi siti trovano un'occasione in ogni
# partita del turno.
SOGLIA_SCARTO = 0.12
SOGLIA_VALORE = 0.10

BOOKMAKER = ["Bet365", "Pinnacle", "William Hill", "Unibet", "Betfair", "888sport"]

# Gli orari veri di un turno, non un contatore di ore.
FASCE = [(0, 12, 30), (0, 15, 0), (0, 18, 0), (0, 20, 45),
         (1, 15, 0), (1, 17, 0), (1, 18, 30), (1, 20, 45), (2, 20, 45)]


# ------------------------------------------------------------------ simulazione


def simula(c: Campionato, n_stagioni: int, inizio: date, seme: int) -> list[Incontro]:
    """Genera stagioni dal mondo del campionato: forze note, due Poisson pure."""
    rng = np.random.default_rng(seme)
    forze = forze_simulate(c)
    # Il livello dei gol si calibra sul valore dichiarato del campionato.
    base = np.log(c.gol_partita / 2.0)
    fuori: list[Incontro] = []
    k = 0
    for s in range(n_stagioni):
        coppie = [
            (nc, ac, dc, no, ao, do)
            for nc, ac, dc in forze
            for no, ao, do in forze
            if nc != no
        ]
        rng.shuffle(coppie)
        for casa, att_c, dif_c, ospite, att_o, dif_o in coppie:
            lh = float(np.exp(base + att_c - dif_o + c.vantaggio_casa))
            la = float(np.exp(base + att_o - dif_c))
            k += 1
            fuori.append(
                Incontro(
                    id=f"{c.slug}-{k}",
                    data=inizio + timedelta(days=s * 330 + (k % 300)),
                    casa=casa,
                    ospite=ospite,
                    punti_casa=int(rng.poisson(lh)),
                    punti_ospite=int(rng.poisson(la)),
                    campionato=c.nome,
                )
            )
    return sorted(fuori, key=lambda i: i.data)


def quote_simulate(vere: list[float], margine: float, rng) -> list[float]:
    """Bookmaker che conosce quasi la verita' e applica il margine alla Shin.

    Il margine e' applicato **secondo Shin**, non dividendo tutto per la stessa
    costante: se il banco lo applicasse in modo uniforme e noi lo togliessimo
    con Shin, il mercato uscirebbe distorto per costruzione e il modello
    sembrerebbe batterlo quando starebbe solo battendo il nostro errore di
    conversione.
    """
    p = np.exp(np.log(np.array(vere)) + rng.normal(0.0, RUMORE_BANCO, len(vere)))
    p = p / p.sum()
    # z e' tarato perche' l'overround esca circa il doppio: e' la relazione
    # approssimata sul punto fisso.
    z = margine / 2.0
    somma = 1.0 + margine
    q = p
    for _ in range(80):
        a = 2.0 * (1.0 - z) * p + z
        q = np.sqrt(somma * (a * a - z * z) / (4.0 * (1.0 - z)))
        nuova = float(q.sum())
        if abs(nuova - somma) < 1e-13:
            break
        somma = nuova
    return [round(float(1.0 / x), 2) for x in q]


def probabilita_vere(c: Campionato, casa: str, ospite: str) -> tuple[list[float], float, float]:
    forze = {n: (a, d) for n, a, d in forze_simulate(c)}
    base = np.log(c.gol_partita / 2.0)
    att_c, dif_c = forze[casa]
    att_o, dif_o = forze[ospite]
    lh = float(np.exp(base + att_c - dif_o + c.vantaggio_casa))
    la = float(np.exp(base + att_o - dif_c))
    return list(esiti_1x2(matrice_da_lambde(lh, la, 0.0)).values()), lh, la


# ---------------------------------------------------------------------- giornata


def valuta(p_mod: list[float], quote: list[float], p_mkt: list[float], k: int) -> list[dict]:
    esiti = []
    for i, et in enumerate(("1", "X", "2")):
        ev = valore_atteso(p_mod[i], quote[i])
        scarto = p_mod[i] - p_mkt[i]
        esiti.append({
            "esito": et,
            "p_modello": round(p_mod[i], 4),
            "p_mercato": round(p_mkt[i], 4),
            "quota": quote[i],
            "quota_equa": round(1.0 / p_mod[i], 2),
            "valore_atteso": round(ev, 4),
            "scarto": round(scarto, 4),
            "kelly": round(kelly(p_mod[i], quote[i]), 4),
            "bookmaker": BOOKMAKER[(k + i) % len(BOOKMAKER)],
            "valore": ev >= SOGLIA_VALORE and scarto >= SOGLIA_SCARTO,
        })
    return esiti


def costruisci_giornata(c: Campionato, modello: ModelloCalcio, rng, giorno: date):
    """La giornata del campionato, piu' un dettaglio per ogni partita."""
    squadre = [n for n, _, _ in forze_simulate(c)]
    # Accoppiamenti stabili: 1-ultima, 2-penultima, e cosi' via a scendere.
    meta = len(squadre) // 2
    accoppiamenti = [(squadre[i], squadre[-(i + 1)]) for i in range(meta)]

    righe, dettagli = [], []
    for k, (casa, ospite) in enumerate(accoppiamenti):
        giorni, ora, minuti = FASCE[k % len(FASCE)]
        fid = f"{casa}-{ospite}".lower().replace(" ", "-").replace("'", "")
        f = Fixture(
            id=fid,
            data=datetime(giorno.year, giorno.month, giorno.day, ora, minuti,
                          tzinfo=timezone.utc) + timedelta(days=giorni),
            casa=casa, ospite=ospite, campionato=c.nome,
        )
        pred = modello.predict(f)
        p_mod = [pred.probabilita("1x2", e) for e in ("1", "X", "2")]

        vere, _, _ = probabilita_vere(c, casa, ospite)
        quote = quote_simulate(vere, c.margine_banco, rng)
        p_mkt = list(probabilita_implicite(quote, metodo="shin"))

        esiti = valuta(p_mod, quote, p_mkt, k)
        sopra = [e for e in esiti if e["valore"]]
        occasione = max(sopra, key=lambda e: e["valore_atteso"]) if sopra else None
        divergenza = max(esiti, key=lambda e: e["scarto"])

        righe.append({
            "id": fid, "casa": casa, "ospite": ospite,
            "ora": f.data.strftime("%d/%m %H:%M"),
            "margine_banco": round(sum(1 / q for q in quote) - 1, 4),
            "esiti": esiti, "occasione": occasione, "divergenza": divergenza,
        })

        m = pred.dettaglio["matrice"]
        dettagli.append({
            "id": fid, "campionato": c.slug, "casa": casa, "ospite": ospite,
            "ora": f.data.strftime("%d/%m/%Y %H:%M"),
            "gol_attesi_casa": round(pred.dettaglio["gol_attesi_casa"], 3),
            "gol_attesi_ospite": round(pred.dettaglio["gol_attesi_ospite"], 3),
            "rho": round(pred.dettaglio["rho"], 4),
            "matrice": [[round(v, 6) for v in riga[:6]] for riga in m[:6]],
            "risultati_probabili": [
                {"risultato": r["risultato"], "p": round(r["p"], 4)}
                for r in pred.dettaglio["risultati_probabili"]
            ],
            "mercati": {
                nome: {k2: round(v, 4) for k2, v in em.items()}
                for nome, em in pred.mercati.items()
            },
            "esiti": esiti,
        })
    return righe, dettagli


# ------------------------------------------------------- verifica fuori campione


def verifica(c: Campionato, storia: list[Incontro], rng) -> dict:
    """Cammina in avanti su stagioni mai viste e misura come e' andata."""
    prova = simula(c, STAGIONI_PROVA, date(2025, 8, 20), seme=hash(c.slug) % 9999)
    conosciute = list(storia)
    m = ModelloCalcio(xi=0.0).fit(conosciute)
    da_ristimare = 0

    p_mod_t, p_mkt_t, esiti_v = [], [], []
    puntate, quote_g, vinte = [], [], []
    scarti, margini = [], []

    for partita in prova:
        if da_ristimare >= 20:
            m = ModelloCalcio(xi=0.0).fit(conosciute, riferimento=partita.data)
            da_ristimare = 0
        f = Fixture(partita.id, datetime.combine(partita.data, datetime.min.time()),
                    partita.casa, partita.ospite, c.nome)
        pred = m.predict(f)
        p_mod = [pred.probabilita("1x2", e) for e in ("1", "X", "2")]

        vere, _, _ = probabilita_vere(c, partita.casa, partita.ospite)
        quote = quote_simulate(vere, c.margine_banco, rng)
        p_mkt = list(probabilita_implicite(quote, metodo="shin"))
        margini.append(sum(1 / q for q in quote) - 1)

        esito = (0 if partita.punti_casa > partita.punti_ospite
                 else 1 if partita.punti_casa == partita.punti_ospite else 2)
        p_mod_t.append(p_mod)
        p_mkt_t.append(list(p_mkt))
        esiti_v.append(esito)
        scarti.append(max(a - b for a, b in zip(p_mod, p_mkt)))

        for k in range(3):
            if (valore_atteso(p_mod[k], quote[k]) >= SOGLIA_VALORE
                    and (p_mod[k] - p_mkt[k]) >= SOGLIA_SCARTO):
                puntate.append(1.0)
                quote_g.append(quote[k])
                vinte.append(esito == k)

        conosciute.append(partita)
        da_ristimare += 1

    dichiarate, avvenuti = [], []
    for p, vero in zip(p_mod_t, esiti_v):
        for k in range(3):
            dichiarate.append(p[k])
            avvenuti.append(k == vero)
    fasce = calibrazione(dichiarate, avvenuti, fasce=10)
    profitto, roi = rendimento(puntate, quote_g, vinte)
    cp = curva_profitto(puntate, quote_g, vinte)

    return {
        "partite": len(prova),
        "brier_modello": round(brier(p_mod_t, esiti_v), 4),
        "brier_mercato": round(brier(p_mkt_t, esiti_v), 4),
        "errore_calibrazione": round(errore_calibrazione(fasce), 4),
        "margine_medio": round(float(np.mean(margini)), 4),
        "scarto_medio": round(float(np.mean(scarti)), 4),
        "quota_sopra_soglia": round(len(puntate) / max(len(prova), 1), 4),
        "calibrazione": [
            {"centro": round(f.centro, 3), "dichiarata": round(f.dichiarata, 4),
             "osservata": round(f.osservata, 4), "casi": f.casi} for f in fasce
        ],
        "giocate": len(puntate),
        "vinte": int(sum(vinte)),
        "quota_media": round(sum(quote_g) / len(quote_g), 2) if quote_g else 0,
        "profitto": round(profitto, 2),
        "rendimento": round(roi, 4),
        "curva_profitto": [round(v, 3) for v in cp],
        "curva_rendimento": [round(v, 5) for v in curva_rendimento(puntate, quote_g, vinte)],
        "ribasso_massimo": round(ribasso_massimo(cp), 2),
    }


# ------------------------------------------------------------- gli altri sport


def costruisci_basket() -> dict:
    from tests.conftest import SQUADRE_BASKET

    rng = np.random.default_rng(4242)
    incontri, n = [], 0
    for _ in range(4):
        for casa, fc, rc in SQUADRE_BASKET:
            for ospite, fo, ro in SQUADRE_BASKET:
                if casa == ospite:
                    continue
                mu = fc - fo + 3.2
                tot = 160.0 + rc + ro
                margine = rng.normal(mu, 11.5)
                punti = rng.normal(tot, 12.0)
                n += 1
                incontri.append(Incontro(
                    f"b{n}", date(2025, 10, 5) + timedelta(days=n // 5), casa, ospite,
                    int(round((punti + margine) / 2)), int(round((punti - margine) / 2)),
                    "LBA"))
    m = ModelloBasket().fit(incontri)
    partite = []
    for casa, ospite in [("Milano", "Trento"), ("Bologna", "Venezia"), ("Brescia", "Napoli")]:
        f = Fixture(f"{casa.lower()}-{ospite.lower()}",
                    datetime(2026, 8, 30, 18, 0, tzinfo=timezone.utc), casa, ospite, "LBA")
        p = m.predict(f)
        partite.append({
            "id": f.id, "casa": casa, "ospite": ospite,
            "p_casa": round(p.probabilita("ml", "casa"), 4),
            "margine_atteso": round(p.dettaglio["margine_atteso"], 1),
            "totale_atteso": round(p.dettaglio["totale_atteso"], 1),
            "punti_casa": round(p.dettaglio["punti_attesi_casa"], 1),
            "punti_ospite": round(p.dettaglio["punti_attesi_ospite"], 1),
        })
    return {"campionato": "LBA", "partite": partite,
            "forze": [{"squadra": f.squadra, "forza": round(f.forza, 2),
                       "ritmo": round(f.ritmo, 2)} for f in m.forze()]}


def costruisci_tennis() -> dict:
    rng = np.random.default_rng(77)
    forze = {f"G{i:02d}": 1500 + (20 - i) * 45 for i in range(20)}
    nomi = list(forze)
    incontri = []
    for n in range(3000):
        a, b = rng.choice(len(nomi), size=2, replace=False)
        na, nb = nomi[a], nomi[b]
        pa = 1.0 / (1.0 + 10.0 ** ((forze[nb] - forze[na]) / 400.0))
        vince = rng.random() < pa
        incontri.append(Incontro(f"t{n}", date(2025, 1, 6) + timedelta(days=n // 12),
                                 na, nb, 2 if vince else 0, 0 if vince else 2, "cemento"))
    m = ModelloTennis().fit(incontri)
    partite = []
    for a, b in [("G01", "G07"), ("G03", "G04"), ("G02", "G12")]:
        f = Fixture(f"{a}-{b}", datetime(2026, 8, 30, 17, 0, tzinfo=timezone.utc),
                    a, b, "cemento")
        p = m.predict(f, al_meglio_di=5)
        partite.append({
            "id": f.id, "casa": a, "ospite": b,
            "p_casa": round(p.probabilita("ml", "casa"), 4),
            "elo_casa": round(p.dettaglio["elo_casa"]),
            "elo_ospite": round(p.dettaglio["elo_ospite"]),
            "servizio_casa": round(p.dettaglio["servizio_casa"], 4),
            "servizio_ospite": round(p.dettaglio["servizio_ospite"], 4),
            "p_set": round(p.dettaglio["p_set_casa"], 4),
        })
    return {"superficie": "cemento", "partite": partite}


# ---------------------------------------------------------------------- scrittura


def scrivi(nome: str, dati) -> None:
    USCITA.mkdir(parents=True, exist_ok=True)
    percorso = USCITA / nome
    percorso.write_text(json.dumps(dati, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {percorso.relative_to(RADICE)}  ({percorso.stat().st_size:,} byte)")


def main() -> int:
    print("Genero i dati del sito dal motore…\n")

    indice, giornate, dettagli_tutti, forze_tutte, verifiche = [], {}, [], {}, {}

    for c in CAMPIONATI:
        rng = np.random.default_rng(abs(hash(c.slug)) % 100000)
        storia = simula(c, STAGIONI_STORIA, date(2018, 8, 20), seme=abs(hash(c.slug)) % 5000)
        # Senza decadimento: nel mondo simulato le forze sono costanti, e
        # pesare meno il passato butterebbe via informazione buona. Sui dati
        # veri questa scelta va rovesciata.
        modello = ModelloCalcio(xi=0.0).fit(storia)

        righe, dettagli = costruisci_giornata(c, modello, rng, date(2026, 8, 29))
        v = verifica(c, storia, rng)

        giornate[c.slug] = righe
        dettagli_tutti.extend(dettagli)
        forze_tutte[c.slug] = [
            {"squadra": f.squadra, "attacco": round(f.attacco, 4),
             "difesa": round(f.difesa, 4), "fatti": round(f.gol_attesi_fatti, 3),
             "subiti": round(f.gol_attesi_subiti, 3)}
            for f in modello.forze()
        ]
        verifiche[c.slug] = v

        indice.append({
            "slug": c.slug, "nome": c.nome, "paese": c.paese, "bandiera": c.bandiera,
            "squadre": c.n_squadre, "note": c.note,
            "partite_giornata": len(righe),
            "occasioni": sum(1 for r in righe if r["occasione"]),
            "gol_partita": c.gol_partita,
            "vantaggio_casa_stimato": round(modello.vantaggio_casa, 4),
            "vantaggio_casa_vero": c.vantaggio_casa,
            "margine_banco": v["margine_medio"],
            "brier_mercato": v["brier_mercato"],
            "brier_modello": v["brier_modello"],
            "scarto_medio": v["scarto_medio"],
            "quota_sopra_soglia": v["quota_sopra_soglia"],
            "partite_verificate": v["partite"],
        })
        print(f"  {c.bandiera} {c.nome:16s} {len(storia):5d} partite di storia · "
              f"campo {modello.vantaggio_casa:.3f} (vero {c.vantaggio_casa:.2f}) · "
              f"margine {v['margine_medio']:.1%} · occasioni {indice[-1]['occasioni']}/{len(righe)}")

    print()
    scrivi("campionati.json", {"simulato": True,
                              "generato_il": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                              "campionati": indice})
    scrivi("giornate.json", {"simulato": True, "giornate": giornate})
    scrivi("partite.json", {"simulato": True, "partite": dettagli_tutti})
    scrivi("forze.json", {"simulato": True, "campionati": forze_tutte})
    scrivi("verifiche.json", {"simulato": True, "campionati": verifiche})
    scrivi("basket.json", {"simulato": True, **costruisci_basket()})
    scrivi("tennis.json", {"simulato": True, **costruisci_tennis()})

    print("\nFatto. Il sito legge questi file in fase di build.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
