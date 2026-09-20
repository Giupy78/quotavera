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


def controlla() -> list[str]:
    """Tutti i guai trovati, in ordine di gravita'. Lista vuota = tutto bene."""
    guai: list[str] = []
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
            guai.append(f"{nomi[slug]}: ESPN fermo al {ultima}")

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
                guai.append(
                    f"{nomi[slug]}: football-data fermo al {ultima} "
                    f"({(oggi - ultima).days} giorni)"
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

    return guai


def main() -> int:
    guai = controlla()
    dati = _carica("campionati.json")
    print(f"Generato il {dati['generato_il']}, risultati fino al {dati['dati_fino_al']}.")
    if not guai:
        print("Tutto in ordine.")
        return 0
    print(f"\n{len(guai)} cose non tornano:\n")
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
