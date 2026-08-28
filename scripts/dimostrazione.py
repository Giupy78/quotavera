"""Il giro completo, su dati simulati: stima, previsione, confronto col banco, resa.

Questo script non serve a fare soldi. Serve a rispondere a una domanda sola:
*la catena regge?* Simula un campionato da parametri noti e un bookmaker che
sbaglia un po' e si prende il suo margine, poi fa camminare il modello in
avanti nel tempo — ristimando solo su quello che avrebbe potuto sapere — e
misura calibrazione, confronto col mercato e rendimento.

Il numero che conta non e' il rendimento finale: e' se il modello e' calibrato
e se batte il Brier del mercato. Il resto e' varianza.

    python scripts/dimostrazione.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.core.market import kelly, probabilita_implicite, valore_atteso
from engine.core.metrics import (
    brier,
    calibrazione,
    curva_profitto,
    errore_calibrazione,
    rendimento,
    ribasso_massimo,
)
from engine.core.types import Fixture, Incontro
from engine.sports.football.model import ModelloCalcio, esiti_1x2, matrice_da_lambde

# --------------------------------------------------------------------- il mondo

SQUADRE = [
    ("Inter", 0.42, 0.38), ("Napoli", 0.34, 0.42), ("Atalanta", 0.36, 0.10),
    ("Juventus", 0.12, 0.30), ("Milan", 0.24, 0.02), ("Roma", 0.06, 0.14),
    ("Lazio", 0.00, 0.06), ("Bologna", -0.08, 0.10), ("Fiorentina", -0.04, -0.10),
    ("Torino", -0.26, 0.04), ("Udinese", -0.30, -0.06), ("Genoa", -0.42, -0.18),
    ("Empoli", -0.44, -0.22), ("Lecce", -0.50, -0.30),
]
VANTAGGIO_CASA = 0.26
MARGINE_BANCO = 0.045
# Quanto il bookmaker sbaglia le probabilita', in scala log.
#
# E' il parametro piu' importante di tutta la simulazione, e va guardato in
# faccia: un bookmaker vero e' *molto* preciso. Mettendolo a 0.09 il modello
# stravince, trova valore nell'87% delle partite e rende il 33% — numeri che
# nella realta' non esistono e che significherebbero solo che ci si e'
# costruiti un avversario di cartone. A 0.03 il banco e' piu' preciso di quanto
# il nostro modello riesca a essere con tre stagioni di soli gol, ed e'
# esattamente la situazione vera.
RUMORE_BANCO = 0.03

# Quanto deve essere netto lo scarto perche' valga la pena giocare.
SOGLIA_SCARTO = 0.08     # punti di probabilita' sopra il mercato
SOGLIA_VALORE = 0.08     # rendimento atteso minimo


def simula_stagioni(n_stagioni: int, inizio: date, seme: int) -> list[Incontro]:
    rng = np.random.default_rng(seme)
    incontri: list[Incontro] = []
    k = 0
    for s in range(n_stagioni):
        coppie = [
            (c, ac, dc, o, ao, do)
            for c, ac, dc in SQUADRE
            for o, ao, do in SQUADRE
            if c != o
        ]
        rng.shuffle(coppie)
        for casa, att_c, dif_c, ospite, att_o, dif_o in coppie:
            lh = float(np.exp(att_c - dif_o + VANTAGGIO_CASA))
            la = float(np.exp(att_o - dif_c))
            k += 1
            incontri.append(
                Incontro(
                    id=f"m{k}",
                    data=inizio + timedelta(days=s * 300 + (k % 182) * 1),
                    casa=casa,
                    ospite=ospite,
                    punti_casa=int(rng.poisson(lh)),
                    punti_ospite=int(rng.poisson(la)),
                    campionato="Serie A",
                )
            )
    incontri.sort(key=lambda i: i.data)
    return incontri


# Frazione di scommesse informate nel modello di Shin. E' il parametro che
# genera il margine: sul punto fisso l'overround esce circa il doppio di z,
# quindi 0.0225 per un margine del 4,5% come quello di un 1X2 di Serie A.
Z_SHIN = 0.0225


def quote_del_banco(vere: list[float], rng: np.random.Generator) -> list[float]:
    """Un bookmaker che conosce quasi la verita' e ci mette sopra il margine.

    Il margine e' applicato **secondo il modello di Shin**, non dividendo tutto
    per la stessa costante. Non e' pignoleria: se il banco applicasse il margine
    in modo uniforme e noi lo togliessimo con Shin, il mercato uscirebbe distorto
    per costruzione e il modello sembrerebbe batterlo quando in realta' starebbe
    solo battendo il nostro errore di conversione. Applicare e togliere con la
    stessa legge e' l'unico confronto onesto.
    """
    logit = np.log(np.array(vere)) + rng.normal(0.0, RUMORE_BANCO, size=len(vere))
    p = np.exp(logit)
    p = p / p.sum()

    # Forma diretta di Shin: si cerca il punto fisso della somma delle
    # probabilita' implicite, che e' quello che l'inversione poi ritrovera'.
    z = Z_SHIN
    somma = 1.0 + MARGINE_BANCO
    q = p
    for _ in range(80):
        a = 2.0 * (1.0 - z) * p + z
        q = np.sqrt(somma * (a * a - z * z) / (4.0 * (1.0 - z)))
        nuova = float(q.sum())
        if abs(nuova - somma) < 1e-13:
            break
        somma = nuova
    return [float(1.0 / x) for x in q]


# ------------------------------------------------------------------ il backtest


def main() -> int:
    print("=" * 74)
    print("  QUOTA VERA — verifica della catena su dati simulati")
    print("=" * 74)

    storia = simula_stagioni(3, date(2022, 8, 20), seme=11)
    prova = simula_stagioni(1, date(2025, 8, 20), seme=707)
    print(f"\nstoria per la stima : {len(storia)} partite")
    print(f"stagione di prova   : {len(prova)} partite")

    rng = np.random.default_rng(2026)
    vere_att = {n: a for n, a, _ in SQUADRE}
    vere_dif = {n: d for n, _, d in SQUADRE}

    p_modello: list[list[float]] = []
    p_mercato: list[list[float]] = []
    esiti: list[int] = []
    margini: list[float] = []
    giocate: list[tuple[float, float, bool]] = []   # puntata, quota, vinta

    conosciute = list(storia)
    modello = ModelloCalcio().fit(conosciute)
    da_ristimare = 0

    for partita in prova:
        # Ristima ogni 14 partite: nella realta' e' il cron notturno.
        if da_ristimare >= 14:
            modello = ModelloCalcio().fit(conosciute, riferimento=partita.data)
            da_ristimare = 0

        f = Fixture(
            id=partita.id,
            data=partita.data,
            casa=partita.casa,
            ospite=partita.ospite,
            campionato=partita.campionato,
        )
        pred = modello.predict(f)
        p_mod = [pred.probabilita("1x2", e) for e in ("1", "X", "2")]

        # Il banco parte dalle probabilita' VERE, non dalle nostre: e' l'unico
        # modo di misurare se il modello sa qualcosa, invece di misurare se il
        # modello assomiglia a se stesso.
        lh = float(np.exp(vere_att[partita.casa] - vere_dif[partita.ospite] + VANTAGGIO_CASA))
        la = float(np.exp(vere_att[partita.ospite] - vere_dif[partita.casa]))
        vere = list(esiti_1x2(matrice_da_lambde(lh, la, 0.0)).values())
        quote = quote_del_banco(vere, rng)
        margini.append(sum(1.0 / q for q in quote) - 1.0)
        p_mkt = probabilita_implicite(quote, metodo="shin")

        esito = (
            0 if partita.punti_casa > partita.punti_ospite
            else 1 if partita.punti_casa == partita.punti_ospite
            else 2
        )
        p_modello.append(p_mod)
        p_mercato.append(list(p_mkt))
        esiti.append(esito)

        # La soglia e' la decisione piu' importante di tutte, e va tarata
        # sull'errore del *nostro* modello, non su quello che sembra tanto.
        # Con tre stagioni di soli gol l'incertezza su ogni probabilita' e' di
        # 3-4 punti: chiedere uno scarto di 3 punti vuol dire giocare il proprio
        # rumore, ed e' il motivo per cui una soglia bassa fa "trovare valore"
        # nel 90% delle partite. Otto punti sono due errori standard.
        for k in range(3):
            ev = valore_atteso(p_mod[k], quote[k])
            if ev >= SOGLIA_VALORE and (p_mod[k] - p_mkt[k]) >= SOGLIA_SCARTO:
                if kelly(p_mod[k], quote[k]) > 0:
                    giocate.append((1.0, quote[k], esito == k))

        conosciute.append(partita)
        da_ristimare += 1

    # ------------------------------------------------------------------ i conti

    b_mod = brier(p_modello, esiti)
    b_mkt = brier(p_mercato, esiti)
    print("\n--- il modello sa qualcosa? ---")
    print(f"  margine medio del banco: {sum(margini)/len(margini):.2%}")
    print(f"  Brier del modello : {b_mod:.4f}")
    print(f"  Brier del mercato : {b_mkt:.4f}   ({'meglio' if b_mod < b_mkt else 'peggio'} il modello)")
    print(f"  scarto            : {b_mkt - b_mod:+.4f}")

    dichiarate, avvenuti = [], []
    for p, vero in zip(p_modello, esiti):
        for k in range(3):
            dichiarate.append(p[k])
            avvenuti.append(k == vero)
    fasce = calibrazione(dichiarate, avvenuti, fasce=10)

    print("\n--- e' calibrato? ---")
    print("  fascia   dichiarato   osservato   casi")
    for fa in fasce:
        barra = "#" * int(fa.osservata * 30)
        print(
            f"   {fa.centro:>5.0%}   {fa.dichiarata:>9.1%}   {fa.osservata:>8.1%}"
            f"   {fa.casi:>4}  {barra}"
        )
    print(f"  errore di calibrazione: {errore_calibrazione(fasce):.4f}"
          "   (sotto 0.02 e' buono)")

    print("\n--- ci si guadagna? ---")
    if not giocate:
        print("  nessuna occasione trovata: il banco era troppo preciso.")
        return 0
    puntate = [g[0] for g in giocate]
    quote = [g[1] for g in giocate]
    vinte = [g[2] for g in giocate]
    profitto, roi = rendimento(puntate, quote, vinte)
    # Il ribasso si misura sul profitto in unita', non sul rendimento.
    ribasso = ribasso_massimo(curva_profitto(puntate, quote, vinte))
    print(f"  giocate trovate   : {len(giocate)} su {len(prova)} partite"
          f"  ({len(giocate)/len(prova):.0%})")
    print(f"  vinte             : {sum(vinte)} ({sum(vinte)/len(vinte):.1%})")
    print(f"  quota media       : {sum(quote)/len(quote):.2f}")
    print(f"  profitto          : {profitto:+.2f} unita'")
    print(f"  rendimento        : {roi:+.2%}")
    print(f"  peggior ribasso   : {ribasso:.2f} unita'")

    # L'errore standard del rendimento, per non farsi illusioni sul numero sopra.
    if len(giocate) > 1:
        varianza = np.var(
            [q - 1.0 if v else -1.0 for q, v in zip(quote, vinte)], ddof=1
        )
        errore = float(np.sqrt(varianza / len(giocate)))
        print(f"  errore standard   : ±{errore:.2%} "
              f"(intervallo {roi - 2*errore:+.1%} … {roi + 2*errore:+.1%})")

    print("\n" + "-" * 74)
    print("  Il rendimento di una stagione non dimostra niente: guarda l'intervallo")
    print("  qui sopra, e' largo decine di punti. Le righe che contano sono il Brier")
    print("  contro il mercato e la calibrazione — quelle si leggono subito, e sono")
    print("  anche le uniche due che un lettore puo' verificare da solo.")
    print()
    print("  E vale anche la pena dire cosa questo NON dimostra: qui i gol sono")
    print("  generati esattamente dal modello che poi li stima, quindi il modello")
    print("  gioca in casa. Il calcio vero non e' Dixon-Coles, e il banco vero e'")
    print("  piu' preciso di questo. Serve a verificare che la catena regga, non")
    print("  a promettere un rendimento.")
    print("-" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
