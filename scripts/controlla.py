"""La sentinella: guarda i dati pubblicati e dice se hanno senso.

Perche' esiste.
---------------
Il 20 settembre il sito pubblicava da tre settimane la classifica di Serie A
con **una partita giocata**. Nel frattempo: sedici turni notturni su sedici
riusciti, nessuna mail di errore, nessuna pagina rotta, il commit dei dati
ogni notte puntuale. Il processo *riusciva* — rigenerava semplicemente sempre
gli stessi numeri.

Nessuno dei controlli che avevamo poteva accorgersene, perche' guardavano tutti
**se il lavoro era andato a buon fine**, non **se il risultato aveva senso**.
Anche l'avviso in fondo al sito guarda quando abbiamo girato, non cosa abbiamo
prodotto: con un processo che gira due volte al giorno restava verde mentre i
dati invecchiavano di tre settimane.

Questo script fa l'unica domanda che li avrebbe scoperti: *quello che abbiamo
pubblicato somiglia a quello che e' successo in campo?*

Come va usato.
--------------
Gira **dopo** la pubblicazione, non prima. Un dato in ritardo non e' una buona
ragione per non pubblicare: il sito con i dati di ieri vale piu' di nessun
sito. Serve a far diventare rosso il turno — e quindi a far partire la mail —
lasciando che il sito esca comunque.

    python scripts/controlla.py

Esce con 1 se qualcosa non torna, con 0 se e' tutto a posto.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
DATI = RADICE / "sito" / "src" / "dati"
GREZZI = RADICE / "data" / "grezzi"
ESPN = RADICE / "dati" / "espn"
PRONOSTICI = RADICE / "dati" / "pronostici"

# Quanti giorni puo' restare una partita senza risultato prima di essere
# sospetta. Due bastano: football-data pubblica a turno concluso, ma ESPN entro
# pochi minuti dal fischio, e da quando ci sono tutt'e due il ritardo normale e'
# di poche ore.
GIORNI_TOLLERATI = 2

# Quante partite senza risultato tollerare in un campionato prima di dirlo.
# Una sola e' quasi sempre un rinvio vero — succede, e non e' un guasto nostro.
# Due o piu' nello stesso campionato vuol dire che manca un turno.
RINVII_PLAUSIBILI = 1

# Oltre questi giorni senza una partita nuova, una fonte e' ferma. Le soglie
# sono diverse perche' i due ritmi sono diversi: ESPN pubblica subito,
# football-data a turno concluso e con calma.
ESPN_FERMO = 5
FOOTBALL_DATA_FERMO = 12


def _carica(nome: str) -> dict:
    return json.loads((DATI / nome).read_text(encoding="utf-8"))


def _ultima_partita_nel_csv(percorso: Path) -> date | None:
    """L'ultima data presente in un CSV di football-data."""
    import csv

    try:
        with percorso.open(encoding="utf-8-sig", errors="replace", newline="") as f:
            date_trovate = []
            for riga in csv.DictReader(f):
                testo = (riga.get("Date") or "").strip()
                for formato in ("%d/%m/%Y", "%d/%m/%y"):
                    try:
                        date_trovate.append(datetime.strptime(testo, formato).date())
                        break
                    except ValueError:
                        continue
        return max(date_trovate, default=None)
    except OSError:
        return None


def controlla() -> tuple[list[str], list[str]]:
    """Restituisce (guai, avvisi).

    La distinzione e' costata cara per impararla. La prima versione trattava
    tutto allo stesso modo, e dal 25 settembre ha fatto fallire **trentatre'
    turni di fila** per una cosa che non toccava nessun lettore: football-data
    aveva smesso di pubblicare, ma ESPN copriva tutto e il sito era aggiornato
    al giorno prima.

    Trentatre' mail identiche equivalgono a nessuna mail. E infatti, nascosto
    dietro quel rumore, c'era un guasto vero che nessuno ha guardato per tre
    settimane: l'archivio dei pronostici non veniva committato, quindi ogni
    notte veniva scritto e buttato via.

    Da qui la regola: **si fallisce su cio' che il lettore vede**, e si avvisa
    su cio' che potrebbe diventare un problema. Una fonte ferma mentre l'altra
    copre e' un avviso. Tutt'e due ferme, o i risultati che non arrivano in
    pagina, sono un guaio.
    """
    guai: list[str] = []
    avvisi: list[str] = []
    oggi = date.today()

    campionati = _carica("campionati.json")
    nomi = {c["slug"]: c["nome"] for c in campionati["campionati"]}

    # --- 1. i risultati stanno dietro al calendario? ----------------------
    #
    # E' il controllo che avrebbe scoperto i due guasti di settembre: le partite
    # c'erano nel calendario di stagione, erano passate da settimane, e il
    # punteggio non arrivava mai.
    limite = (oggi - timedelta(days=GIORNI_TOLLERATI)).isoformat()
    stagione = _carica("stagione.json")["campionati"]
    in_ritardo: dict[str, list[str]] = defaultdict(list)
    for slug, dati in stagione.items():
        for giornata in dati["giornate"]:
            for p in giornata["partite"]:
                if p["data"] < limite and not p["giocata"]:
                    in_ritardo[slug].append(f"{p['data']} {p['casa']}-{p['ospite']}")
    for slug, elenco in sorted(in_ritardo.items()):
        if len(elenco) > RINVII_PLAUSIBILI:
            guai.append(
                f"{nomi.get(slug, slug)}: {len(elenco)} partite chiuse da oltre "
                f"{GIORNI_TOLLERATI} giorni senza risultato "
                f"(es. {elenco[0]})"
            )

    # --- 2. le fonti stanno producendo? -----------------------------------
    #
    # Una fonte ferma non e' di per se' un guaio: ne abbiamo due apposta. Lo
    # diventa quando si fermano tutte e due, perche' allora siamo ciechi.
    fonti_ferme: dict[str, list[str]] = {"espn": [], "football-data": []}
    for slug in nomi:
        archivio = ESPN / f"{slug}.json"
        if not archivio.exists():
            continue
        try:
            dati = json.loads(archivio.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            guai.append(f"{nomi[slug]}: l'archivio ESPN non si legge")
            continue
        ultima = max((v["data"] for v in dati.values()), default=None)
        if ultima and (oggi - date.fromisoformat(ultima)).days > ESPN_FERMO:
            fonti_ferme["espn"].append(nomi[slug])

    stagione_corrente = max(
        (p.name.rsplit("-", 1)[1][:4] for p in GREZZI.glob("*-*.csv")
         if p.stem.rsplit("-", 1)[-1].isdigit()),
        default=None,
    )
    if stagione_corrente:
        for slug in nomi:
            f = GREZZI / f"{slug}-{stagione_corrente}.csv"
            if not f.exists():
                continue
            ultima = _ultima_partita_nel_csv(f)
            if ultima and (oggi - ultima).days > FOOTBALL_DATA_FERMO:
                fonti_ferme["football-data"].append(
                    f"{nomi[slug]} (al {ultima})"
                )

    # Il verdetto sulle fonti: ferme tutte e due vuol dire che non arrivera'
    # piu' niente, e quello e' un guaio. Una sola, con l'altra che copre, e'
    # una cosa da sapere e basta.
    if fonti_ferme["espn"] and fonti_ferme["football-data"]:
        guai.append(
            f"ferme tutt'e due le fonti: ESPN su {len(fonti_ferme['espn'])} "
            f"campionati e football-data su {len(fonti_ferme['football-data'])}. "
            f"Da qui in poi non arriva piu' niente."
        )
    else:
        for fonte, elenco in fonti_ferme.items():
            if elenco:
                avvisi.append(
                    f"{fonte} fermo su {len(elenco)} campionati "
                    f"(es. {elenco[0]}) - l'altra fonte sta coprendo"
                )

    # --- i pronostici tornano a casa? -------------------------------------
    #
    # Questo controllo nasce dal guasto che il rumore aveva nascosto: l'archivio
    # dei pronostici veniva scritto ogni notte sulla macchina di GitHub e perso
    # subito dopo, perche' non era fra i file da committare. Il codice
    # funzionava, il file esisteva, semplicemente non tornava a casa.
    #
    # Il modo per accorgersene non e' guardare se il processo riesce, ma se le
    # partite in programma hanno davvero un pronostico messo da parte.
    in_programma = [
        (slug, q)
        for slug, elenco in _carica("calendario.json")["campionati"].items()
        for q in elenco
    ]
    if in_programma:
        coperte = 0
        for slug, q in in_programma:
            archivio = PRONOSTICI / f"{slug}.json"
            if not archivio.exists():
                continue
            try:
                dati_arch = json.loads(archivio.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if q["id"] in dati_arch:
                coperte += 1
        quota = coperte / len(in_programma)
        if quota < 0.5:
            guai.append(
                f"solo {coperte} partite in programma su {len(in_programma)} hanno "
                f"un pronostico archiviato: l'archivio non sta tornando a casa"
            )
        elif quota < 0.9:
            avvisi.append(
                f"{coperte} partite in programma su {len(in_programma)} hanno "
                f"un pronostico archiviato"
            )

    # --- 3. le classifiche tornano? ---------------------------------------
    #
    # Aritmetica pura: se non torna, si e' rotto qualcosa nella fusione delle
    # fonti — una partita contata due volte, o attribuita alla squadra
    # sbagliata. Sono errori che sulla pagina non si vedono.
    for slug, tabella in _carica("classifiche.json")["campionati"].items():
        for r in tabella:
            if r["punti"] != 3 * r["vinte"] + r["pareggiate"]:
                guai.append(f"{nomi.get(slug, slug)}: i punti di {r['squadra']} non tornano")
            if r["giocate"] != r["vinte"] + r["pareggiate"] + r["perse"]:
                guai.append(f"{nomi.get(slug, slug)}: le partite di {r['squadra']} non tornano")
        fatti = sum(r["fatti"] for r in tabella)
        subiti = sum(r["subiti"] for r in tabella)
        if fatti != subiti:
            guai.append(
                f"{nomi.get(slug, slug)}: {fatti} gol fatti contro {subiti} subiti "
                f"(devono pareggiare: ogni gol e' fatto da uno e subito dall'altro)"
            )

    # --- 4. c'e' ancora un sito dentro i dati? ----------------------------
    squadre = _carica("squadre.json")["campionati"]
    vuoti = [nomi.get(s, s) for s, v in squadre.items() if not v]
    if vuoti:
        guai.append(f"campionati senza statistiche: {', '.join(vuoti)}")

    # --- 5. il calendario guarda avanti? ----------------------------------
    passate = [
        f"{nomi.get(slug, slug)} {p['data']} {p['casa']}-{p['ospite']}"
        for slug, elenco in _carica("calendario.json")["campionati"].items()
        for p in elenco
        if p["data"] < oggi.isoformat()
    ]
    if passate:
        guai.append(
            f"{len(passate)} partite gia' giocate ancora fra quelle in programma "
            f"(es. {passate[0]})"
        )

    # --- 6. i dati sono di stanotte? --------------------------------------
    generato = datetime.fromisoformat(campionati["generato_il"])
    ore = (datetime.now(timezone.utc) - generato).total_seconds() / 3600
    if ore > 30:
        guai.append(f"i dati sono stati generati {ore:.0f} ore fa")

    return guai, avvisi


def main() -> int:
    guai, avvisi = controlla()
    dati = _carica("campionati.json")
    print(f"Generato il {dati['generato_il']}, risultati fino al {dati['dati_fino_al']}.")
    if avvisi:
        quante = "1 cosa" if len(avvisi) == 1 else f"{len(avvisi)} cose"
        print(f"\n{quante} da sapere (il turno resta verde):\n")
        for a in avvisi:
            print(f"  . {a}")

    if not guai:
        print("\nNiente di rotto." if avvisi else "Tutto in ordine.")
        return 0
    quanti = "1 cosa non torna" if len(guai) == 1 else f"{len(guai)} cose non tornano"
    print(f"\n{quanti}:\n")
    for g in guai:
        print(f"  - {g}")
    print(
        "\nIl sito e' pubblicato lo stesso: un dato in ritardo non e' una buona\n"
        "ragione per non pubblicare. Questo turno risulta fallito apposta, per\n"
        "far partire la mail."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
