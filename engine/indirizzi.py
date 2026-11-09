"""Il registro degli indirizzi di partita pubblicati.

Una pagina di partita, una volta pubblicata, non deve sparire: Google l'ha
vista, e un indirizzo che diventa 404 è una pagina persa. È successo tre volte,
sempre per una squadra scritta in due modi — "Sheffield Utd" e "Sheffield
United", "Oxford Utd" e "Oxford", "KV Mechelen" e "Mechelen". Quando il nome
viene uniformato l'indirizzo cambia, e quello vecchio muore senza che niente lo
dica: l'ultima volta l'hanno scoperto due 404 su Google, tre giorni dopo.

L'archivio dei pronostici non basta come elenco. È fatto per un'altra cosa, e
il 6 novembre è stato ripulito a mano proprio dei doppioni — che erano indirizzi
pubblicati, e con quella pulizia sono morti. Questo registro invece contiene
solo l'elenco, e **cresce soltanto**: ogni giro aggiunge gli indirizzi nuovi e
non ne toglie mai uno.

La regola che controlla è una: ogni indirizzo del registro porta ancora a
qualcosa. O la sua pagina esiste, o c'è un rinvio in `sito/public/_redirects`
che arriva a una pagina che esiste. Se no, lo si dice: `genera_sito.py` con una
riga, `controlla.py` con un guaio che fa partire la mail.

Quando la pagina giusta è ovvia — stesso campionato, stessa data, e i nomi che
`abbina` riconosce come la stessa squadra — si propone anche la riga da
aggiungere ai rinvii. Proporla e basta: la scrive una persona. Un rinvio
sbagliato manda Google sulla partita sbagliata, e quello non lo nota nessuno.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from engine.dati.espn import abbina

RADICE = Path(__file__).resolve().parents[1]
REGISTRO = RADICE / "dati" / "indirizzi.json"
RINVII = RADICE / "sito" / "public" / "_redirects"

# Gli host che sono questo sito: un rinvio scritto con l'indirizzo completo
# verso uno di questi va seguito come se fosse un percorso.
NOSTRI_HOST = {"quotavera.it", "www.quotavera.it"}

# Quanti salti di rinvio seguire prima di arrendersi. Una catena più lunga è
# quasi certamente un giro chiuso.
SALTI = 10


def indirizzo(campionato: str, id_partita: str) -> str:
    """Il percorso della pagina di una partita, come lo vede Google."""
    return f"/calcio/{campionato}/{id_partita}/"


def _campionato(via: str) -> str | None:
    """Il campionato, se `via` ha la forma della pagina di una partita.

    Le pagine squadra (`/calcio/x/squadra/y/`) e quelle di campionato
    (`/calcio/x/`) hanno un numero diverso di pezzi e restano fuori.
    """
    pezzi = via.split("/")
    if (len(pezzi) == 5 and pezzi[0] == "" and pezzi[1] == "calcio"
            and pezzi[2] and pezzi[3] and pezzi[4] == ""):
        return pezzi[2]
    return None


def pagine(partite: list[dict]) -> dict[str, dict]:
    """Gli indirizzi delle schede di oggi, con quello che serve a riconoscerle."""
    return {
        indirizzo(p["campionato"], p["id"]):
            {"casa": p["casa"], "ospite": p["ospite"], "data": p["data"]}
        for p in partite
    }


# --- il registro ------------------------------------------------------------

def carica(percorso: Path = REGISTRO) -> dict[str, dict]:
    """Il registro su disco. Vuoto se il file non c'è ancora.

    Un file che c'è ma non si legge **solleva**, e non torna vuoto: chi lo
    ricevesse vuoto lo riscriverebbe con le sole pagine di oggi, e la memoria
    di tutto il resto andrebbe persa proprio nel modo che il registro deve
    impedire.
    """
    if not percorso.exists():
        return {}
    dati = json.loads(percorso.read_text(encoding="utf-8"))
    if not isinstance(dati, dict):
        raise ValueError(f"{percorso.name}: mi aspettavo un oggetto JSON")
    return dati


def salva(registro: dict[str, dict], percorso: Path = REGISTRO) -> None:
    """Un indirizzo per riga, in ordine: il commit di ogni notte resta leggibile.

    Si scrive su un file a parte e poi si sostituisce, così un'interruzione a
    metà non lascia un registro troncato. E sempre con `\\n`, anche su Windows,
    perché il file viene scritto da due sistemi diversi.
    """
    righe = [
        f"{json.dumps(via, ensure_ascii=False)}: "
        f"{json.dumps(registro[via], ensure_ascii=False, sort_keys=True)}"
        for via in sorted(registro)
    ]
    testo = "{\n" + ",\n".join(righe) + "\n}\n" if righe else "{}\n"
    percorso.parent.mkdir(parents=True, exist_ok=True)
    provvisorio = percorso.with_name(percorso.name + ".tmp")
    with provvisorio.open("w", encoding="utf-8", newline="\n") as f:
        f.write(testo)
    provvisorio.replace(percorso)


def aggiungi(registro: dict[str, dict], partite: list[dict], oggi: str) -> int:
    """Mette nel registro gli indirizzi di `partite`. Restituisce quanti nuovi.

    Non toglie mai niente. Di un indirizzo già noto aggiorna squadre e data,
    perché una partita può essere spostata di giorno: per riconoscere più
    avanti la pagina che l'ha sostituita serve l'ultima data pubblicata, non
    la prima. `dal` dice da quando l'indirizzo è pubblicato, e può solo
    andare indietro — succede ricostruendo il registro dalla cronologia.
    """
    nuovi = 0
    for via, voce in pagine(partite).items():
        vecchia = registro.get(via)
        if vecchia is None:
            registro[via] = {**voce, "dal": oggi}
            nuovi += 1
        else:
            vecchia.update(voce)
            vecchia["dal"] = min(vecchia.get("dal") or oggi, oggi)
    return nuovi


# --- i rinvii -----------------------------------------------------------------

def leggi_rinvii(testo: str) -> dict[str, str]:
    """Le regole di `_redirects`, dall'origine alla destinazione.

    Le origini si prendono come sono scritte, senza aggiungere né togliere la
    barra finale: se una regola non combacia carattere per carattere con
    l'indirizzo, non si dà per scontato che Cloudflare la applichi. Fra un
    falso allarme e un 404 dato per coperto, meglio il falso allarme.

    Con due regole per la stessa origine vale la prima, come per Cloudflare.
    """
    regole: dict[str, str] = {}
    for riga in testo.splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#"):
            continue
        pezzi = riga.split()
        if len(pezzi) >= 2:
            regole.setdefault(pezzi[0], pezzi[1])
    return regole


def carica_rinvii(percorso: Path = RINVII) -> dict[str, str]:
    if not percorso.exists():
        return {}
    return leggi_rinvii(percorso.read_text(encoding="utf-8"))


def _percorso(destinazione: str) -> str:
    """Un indirizzo completo verso questo sito diventa un percorso."""
    parti = urlsplit(destinazione)
    if parti.scheme and parti.netloc.lower() in NOSTRI_HOST:
        return parti.path or "/"
    return destinazione


def _regola(via: str, regole: dict[str, str]) -> str | None:
    """Dove manda la regola che si applica a `via`, se ce n'è una."""
    if via in regole:
        return regole[via]
    # Le regole con l'asterisco: oggi non ce ne sono, ma il formato le ammette
    # e un rinvio di un'intera sezione deve contare come rinvio.
    for origine, destinazione in regole.items():
        if origine.endswith("*") and via.startswith(origine[:-1]):
            return destinazione.replace(":splat", via[len(origine) - 1:])
    return None


def segui(via: str, regole: dict[str, str]) -> str | None:
    """Dove arriva chi chiede `via`, seguendo i rinvii. None se non ce ne sono."""
    arrivo = None
    visti = {via}
    for _ in range(SALTI):
        dopo = _regola(via, regole)
        if dopo is None:
            break
        arrivo = via = _percorso(dopo)
        if via in visti:
            break                     # un giro chiuso: si ferma qui
        visti.add(via)
    return arrivo


# --- il confronto -------------------------------------------------------------

@dataclass(frozen=True)
class Perso:
    """Un indirizzo pubblicato che oggi non porta a niente."""

    via: str
    casa: str
    ospite: str
    data: str
    # Se c'è un rinvio ma finisce su una pagina partita che non esiste più.
    rinvio_a: str | None = None
    # La pagina che con ogni evidenza ha preso il suo posto, se è ovvia.
    proposta: str | None = None


def persi(registro: dict[str, dict], partite: list[dict],
          regole: dict[str, str]) -> list[Perso]:
    """Gli indirizzi del registro che non sono pagine e non hanno un rinvio buono.

    Un rinvio è buono se arriva a una pagina partita di oggi, oppure a una
    pagina che partita non è (quella del campionato, per esempio): quelle non
    nascono da `schede.json` e da qui non si possono verificare.
    """
    vive = pagine(partite)
    fuori = []
    for via in sorted(registro):
        if via in vive:
            continue
        arrivo = segui(via, regole)
        if arrivo is not None and (arrivo in vive or _campionato(arrivo) is None):
            continue
        voce = registro[via]
        fuori.append(Perso(
            via=via, casa=voce.get("casa", ""), ospite=voce.get("ospite", ""),
            data=voce.get("data", ""), rinvio_a=arrivo,
            proposta=None if arrivo else proponi(via, voce, vive),
        ))
    return fuori


def proponi(via: str, voce: dict, vive: dict[str, dict]) -> str | None:
    """La pagina di oggi che ha preso il posto di `via`, se è ovvia.

    Ovvia vuol dire tre cose insieme: stesso campionato, stessa data, e
    ciascuna delle due squadre o è identica o è un nome che `abbina` riconosce
    come variante. I nomi si abbinano contro **tutte** le squadre del
    campionato e non contro la sola pagina candidata: è l'univocità su tutto
    l'elenco che impedisce a "Bristol City" di diventare "Bristol Rovers". Con
    più di un candidato, o nessuno, non si propone niente.
    """
    campionato = _campionato(via)
    if not campionato or not voce.get("data"):
        return None
    prefisso = f"/calcio/{campionato}/"
    stesse = {v: x for v, x in vive.items() if v.startswith(prefisso)}
    nomi = {x["casa"] for x in stesse.values()} | {x["ospite"] for x in stesse.values()}

    vecchi = [voce.get("casa", ""), voce.get("ospite", "")]
    diversi = [n for n in dict.fromkeys(vecchi) if n and n not in nomi]
    if not diversi:
        return None                   # stessi nomi: non è una questione di grafia
    fatti, _ = abbina(diversi, sorted(nomi - set(vecchi)))
    casa = vecchi[0] if vecchi[0] in nomi else fatti.get(vecchi[0])
    ospite = vecchi[1] if vecchi[1] in nomi else fatti.get(vecchi[1])
    if not casa or not ospite:
        return None

    candidati = [v for v, x in stesse.items()
                 if x["casa"] == casa and x["ospite"] == ospite
                 and x["data"] == voce["data"]]
    return candidati[0] if len(candidati) == 1 else None


def racconta(fuori: list[Perso], quanti: int = 20) -> list[str]:
    """Le righe con cui si dice cosa si è perso, e cosa fare.

    I rinvii proposti stanno insieme in fondo, già nel formato del file:
    controllati, si copiano così come sono.
    """
    if not fuori:
        return []
    n = len(fuori)
    righe = [
        "1 indirizzo di partita già pubblicato oggi dà 404:" if n == 1 else
        f"{n} indirizzi di partita già pubblicati oggi danno 404:"
    ]
    for p in fuori[:quanti]:
        chi = f"{p.casa}-{p.ospite} del {p.data}"
        if p.rinvio_a:
            righe.append(f"    {p.via}  ({chi}): il rinvio porta a {p.rinvio_a}, "
                         f"che non esiste più")
        elif p.proposta:
            righe.append(f"    {p.via}  ({chi}): la pagina giusta sembra {p.proposta}")
        else:
            righe.append(f"    {p.via}  ({chi}): nessuna pagina ovvia, "
                         f"da guardare a mano")
    if n > quanti:
        righe.append(f"    … e altri {n - quanti}")

    proposte = [p for p in fuori if p.proposta]
    if proposte:
        righe.append(
            "  Rinvii proposti (stesso campionato, stessa data, nome riconosciuto "
            "come variante). Da controllare e poi copiare in sito/public/_redirects:"
        )
        righe += [f"    {p.via} {p.proposta} 301" for p in proposte]
    return righe
