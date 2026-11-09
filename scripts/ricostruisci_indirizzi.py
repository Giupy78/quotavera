"""Il registro degli indirizzi, ricostruito dalla cronologia git.

Serve per partire, e per rimetterlo in piedi se un giorno andasse perso: legge
una versione di `sito/src/dati/schede.json` al giorno — l'ultima di ciascun
giorno, in UTC — e mette nel registro ogni indirizzo di partita che vi compare,
più quelli della versione su disco. Il registro esistente non si svuota: si
aggiunge soltanto, come ogni notte.

    python scripts/ricostruisci_indirizzi.py                 # dal 1 ottobre 2026
    python scripts/ricostruisci_indirizzi.py --dal 2026-08-28
    python scripts/ricostruisci_indirizzi.py --tutte         # ogni versione, non una al giorno

Alla fine dice quali indirizzi pubblicati non portano più a niente, con le
stesse parole della sentinella.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from engine import indirizzi

SCHEDE = "sito/src/dati/schede.json"


def versioni(dal: str) -> list[tuple[str, str]]:
    """(commit, giorno UTC) di ogni versione di schede.json da `dal`, dalla più nuova."""
    uscita = subprocess.run(
        ["git", "log", f"--since={dal}", "--format=%H %cI", "--", SCHEDE],
        cwd=RADICE, capture_output=True, text=True, check=True,
    ).stdout
    fuori = []
    for riga in uscita.splitlines():
        commit, quando = riga.split()
        fuori.append((commit, _giorno_utc(quando)))
    return fuori


def _giorno_utc(quando: str) -> str:
    return datetime.fromisoformat(quando).astimezone(timezone.utc).date().isoformat()


def una_al_giorno(elenco: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """L'ultima versione di ogni giorno, dalla più vecchia alla più nuova.

    `elenco` arriva da `git log`, quindi dalla più nuova: la prima che si
    incontra per un giorno è l'ultima di quel giorno.
    """
    scelte: dict[str, str] = {}
    for commit, giorno in elenco:
        scelte.setdefault(giorno, commit)
    return [(scelte[g], g) for g in sorted(scelte)]


def partite_di(commit: str) -> list[dict]:
    testo = subprocess.run(
        ["git", "show", f"{commit}:{SCHEDE}"],
        cwd=RADICE, capture_output=True, check=True,
    ).stdout
    return json.loads(testo.decode("utf-8"))["partite"]


def main() -> int:
    argomenti = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    argomenti.add_argument("--dal", default="2026-10-01",
                           help="da che giorno leggere la cronologia (AAAA-MM-GG)")
    argomenti.add_argument("--tutte", action="store_true",
                           help="ogni versione invece di una al giorno")
    a = argomenti.parse_args()

    tutte = versioni(a.dal)
    # Sempre dalla più vecchia: così `dal` resta il giorno della prima comparsa.
    scelte = list(reversed(tutte)) if a.tutte else una_al_giorno(tutte)
    registro = indirizzi.carica()
    prima = len(registro)
    print(f"Registro attuale: {prima} indirizzi. Leggo {len(scelte)} versioni "
          f"di schede.json su {len(tutte)} dal {a.dal}.")

    for commit, giorno in scelte:
        nuovi = indirizzi.aggiungi(registro, partite_di(commit), giorno)
        if nuovi:
            print(f"  {giorno} {commit[:7]}  +{nuovi}")

    # E la versione su disco, che può essere più nuova dell'ultimo commit.
    su_disco = json.loads((RADICE / SCHEDE).read_text(encoding="utf-8"))["partite"]
    oggi = datetime.now(timezone.utc).date().isoformat()
    nuovi = indirizzi.aggiungi(registro, su_disco, oggi)
    if nuovi:
        print(f"  {oggi} su disco  +{nuovi}")

    indirizzi.salva(registro)
    print(f"\n{indirizzi.REGISTRO.relative_to(RADICE)}: {len(registro)} indirizzi "
          f"({len(registro) - prima} aggiunti), {len(su_disco)} pagine oggi.")

    fuori = indirizzi.persi(registro, su_disco, indirizzi.carica_rinvii())
    if not fuori:
        print("Nessun indirizzo perso: ognuno ha la sua pagina o un rinvio.")
        return 0
    print()
    for riga in indirizzi.racconta(fuori, quanti=len(fuori)):
        print(riga)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
