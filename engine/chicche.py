"""Le chicche statistiche: i numeri che nessuno va a cercare ma che si leggono volentieri.

Il criterio con cui sono scelte, perche' non e' ovvio.

Una chicca non e' una statistica qualunque messa in grande. Deve avere tre
proprieta', e se ne manca una non entra:

1. **E' vera e verificabile.** Ogni voce porta con se' il numero che la regge e
   il campione su cui e' calcolata. Niente "la squadra piu' in forma".
2. **Non si trova altrove senza lavoro.** "L'Inter ha vinto tre partite" e' sul
   televideo. "L'Inter e' la squadra che segna la quota piu' alta dei suoi gol
   nel primo tempo" richiede di aprire tre stagioni di tabellini.
3. **Sorprende, o spiega.** Deve far alzare un sopracciglio, oppure dare un
   perche' a qualcosa che si era notato senza spiegarselo.

Da qui discende la scelta delle fonti dentro il dato. Usiamo pezzi che stanno
nei file da sempre e che non abbiamo mai sfruttato: i **gol del primo tempo**,
che aprono il capitolo rimonte e squadre che si accendono tardi; e le **quote
di chiusura**, che permettono di dire quale risultato il mercato non si
aspettava davvero — non "a sorpresa" a occhio, ma con un prezzo attaccato.

Un avvertimento che vale per tutte. Sono descrizioni del passato, non
previsioni: una serie aperta di sei vittorie dice cosa e' successo, non cosa
succedera'. Le pagine che le mostrano devono dirlo, e lo dicono.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from engine.dati.football_data import PartitaStorica

# Quante partite servono perche' una percentuale voglia dire qualcosa. Sotto
# questa soglia una squadra "che segna il 70% dei gol nel primo tempo" ne ha
# segnati sette in tutto, e la chicca e' rumore vestito bene.
MINIMO = 25

# Quanto deve essere alta la quota perche' un risultato sia una sorpresa vera.
# 6.0 vuol dire che il mercato le dava meno di una probabilita' su sei.
QUOTA_SORPRESA = 6.0


@dataclass
class Chicca:
    """Un fatto, il numero che lo regge, e da dove salta fuori."""

    tipo: str
    titolo: str
    testo: str
    numero: str = ""
    campionato: str = ""
    bandiera: str = ""
    slug: str = ""
    squadre: list[str] = field(default_factory=list)
    # Su quante partite e' calcolata: senza, il lettore non puo' pesarla.
    campione: int = 0

    def come_dizionario(self) -> dict:
        return {
            "tipo": self.tipo, "titolo": self.titolo, "testo": self.testo,
            "numero": self.numero, "campionato": self.campionato,
            "bandiera": self.bandiera, "slug": self.slug,
            "squadre": self.squadre, "campione": self.campione,
        }


def _percento(parte: float, tutto: float) -> str:
    return f"{100 * parte / tutto:.0f}%" if tutto else "—"


# --- il primo tempo, e cosa succede dopo ---------------------------------

def rimonte(partite: list[PartitaStorica], c,
            attuali: set[str] | None = None) -> list[Chicca]:
    """Chi va sotto all'intervallo e la ribalta, e chi si fa raggiungere.

    E' il dato che il tabellino nasconde: il risultato finale non dice se una
    squadra ha dominato o se ha rimesso in piedi una partita persa. Sta nei
    file da sempre — la colonna dei gol del primo tempo — e non l'avevamo mai
    guardata.
    """
    sotto = defaultdict(int)          # volte che era sotto all'intervallo
    ribaltate = defaultdict(int)      # ... e ha finito vincendo
    avanti = defaultdict(int)
    buttate = defaultdict(int)        # era avanti e non ha vinto

    for p in partite:
        s = p.stat
        if not s.completa:
            continue
        pc, po = s.gol_primo_tempo
        fc, fo = p.incontro.punti_casa, p.incontro.punti_ospite
        i = p.incontro
        for squadra, mio_pt, suo_pt, mio_ft, suo_ft in (
            (i.casa, pc, po, fc, fo), (i.ospite, po, pc, fo, fc)
        ):
            if mio_pt < suo_pt:
                sotto[squadra] += 1
                if mio_ft > suo_ft:
                    ribaltate[squadra] += 1
            elif mio_pt > suo_pt:
                avanti[squadra] += 1
                if mio_ft <= suo_ft:
                    buttate[squadra] += 1

    # Solo chi gioca in questo campionato adesso: una chicca su una retrocessa
    # e' vera ma non interessa nessuno, e sporca il "piu' alta del campionato".
    def qui(nome: str) -> bool:
        return not attuali or nome in attuali

    fuori = []
    candidate = [(s, ribaltate[s], sotto[s]) for s in sotto
                 if sotto[s] >= 8 and qui(s)]
    if candidate:
        nome, quante, su = max(candidate, key=lambda x: (x[1] / x[2], x[1]))
        if quante >= 3:
            fuori.append(Chicca(
                tipo="rimonte",
                titolo=f"{nome} non molla all'intervallo",
                testo=(f"Sotto al riposo {su} volte, ha finito vincendo {quante}. "
                       f"E' la quota di rimonte piu' alta del campionato."),
                numero=_percento(quante, su),
                campionato=c.nome, bandiera=c.bandiera, slug=c.slug,
                squadre=[nome], campione=su,
            ))

    fragili = [(s, buttate[s], avanti[s]) for s in avanti
               if avanti[s] >= 8 and qui(s)]
    if fragili:
        nome, quante, su = max(fragili, key=lambda x: (x[1] / x[2], x[1]))
        if quante >= 3:
            fuori.append(Chicca(
                tipo="fragilita",
                titolo=f"{nome} non tiene il vantaggio",
                testo=(f"Avanti al riposo {su} volte, non ha vinto {quante} di "
                       f"quelle partite. Nessuno in campionato ne butta via tanti."),
                numero=_percento(quante, su),
                campionato=c.nome, bandiera=c.bandiera, slug=c.slug,
                squadre=[nome], campione=su,
            ))
    return fuori


def quando_segnano(partite: list[PartitaStorica], c,
                   attuali: set[str] | None = None) -> list[Chicca]:
    """Chi fa la partita nel primo tempo e chi si accende dopo."""
    pt = defaultdict(int)
    totali = defaultdict(int)
    for p in partite:
        s = p.stat
        if not s.completa:
            continue
        i = p.incontro
        pt[i.casa] += s.gol_primo_tempo[0]
        pt[i.ospite] += s.gol_primo_tempo[1]
        totali[i.casa] += i.punti_casa
        totali[i.ospite] += i.punti_ospite

    validi = [(s, pt[s], totali[s]) for s in totali
              if totali[s] >= 20 and (not attuali or s in attuali)]
    if not validi:
        return []

    fuori = []
    nome, primi, tutti = max(validi, key=lambda x: x[1] / x[2])
    if primi / tutti >= 0.55:
        fuori.append(Chicca(
            tipo="primo_tempo",
            titolo=f"{nome} decide presto",
            testo=(f"{primi} dei suoi {tutti} gol arrivano prima dell'intervallo. "
                   f"E' la squadra piu' sbilanciata sul primo tempo del campionato."),
            numero=_percento(primi, tutti),
            campionato=c.nome, bandiera=c.bandiera, slug=c.slug,
            squadre=[nome], campione=tutti,
        ))

    nome, primi, tutti = min(validi, key=lambda x: x[1] / x[2])
    if primi / tutti <= 0.33:
        fuori.append(Chicca(
            tipo="ripresa",
            titolo=f"{nome} vive di secondi tempi",
            testo=(f"Solo {primi} dei suoi {tutti} gol arrivano nel primo tempo: "
                   f"il resto dopo l'intervallo."),
            numero=_percento(tutti - primi, tutti),
            campionato=c.nome, bandiera=c.bandiera, slug=c.slug,
            squadre=[nome], campione=tutti,
        ))
    return fuori


# --- quello che il mercato non si aspettava -------------------------------

def sorprese_del_mercato(partite: list[PartitaStorica], c,
                         quante: int = 2) -> list[Chicca]:
    """I risultati che il mercato pagava di piu', a stagione conclusa.

    Non "a sorpresa" a occhio: con un prezzo attaccato. La quota di chiusura e'
    la migliore stima di probabilita' che esista, quindi un 8.50 che entra e'
    un fatto misurabile, non un'impressione.
    """
    fuori = []
    for p in partite:
        q = p.riferimento()
        if not q:
            continue
        quota = q[p.esito]
        if quota < QUOTA_SORPRESA:
            continue
        i = p.incontro
        if p.esito == 0:
            testo_esito = f"{i.casa} batteva {i.ospite}"
        elif p.esito == 2:
            testo_esito = f"{i.ospite} vinceva in casa di {i.casa}"
        else:
            testo_esito = f"{i.casa} e {i.ospite} pareggiavano"
        fuori.append((quota, Chicca(
            tipo="sorpresa_mercato",
            titolo=f"{i.casa} {i.punti_casa}-{i.punti_ospite} {i.ospite}",
            testo=(f"{i.data.strftime('%d/%m/%Y')}: che {testo_esito} era pagato "
                   f"{quota:.2f}, cioe' circa {_percento(1, quota)} di probabilita' "
                   f"secondo il mercato."),
            numero=f"{quota:.2f}",
            campionato=c.nome, bandiera=c.bandiera, slug=c.slug,
            squadre=[i.casa, i.ospite], campione=1,
        )))
    fuori.sort(key=lambda x: x[0], reverse=True)
    return [ch for _, ch in fuori[:quante]]


# --- le serie aperte ------------------------------------------------------

def serie_aperte(partite: list[PartitaStorica], c,
                 squadre_attuali: set[str] | None = None) -> list[Chicca]:
    """Quello che sta succedendo adesso e dura da un po'.

    Le serie sono la statistica piu' fraintesa che ci sia: non predicono
    niente, e vanno raccontate per quello che sono — un fatto sul passato che
    ha il pregio di essere vistoso. Qui si riportano solo se abbastanza lunghe
    da non essere casuali a occhio.
    """
    per_squadra: dict[str, list] = defaultdict(list)
    for p in sorted(partite, key=lambda x: x.incontro.data):
        per_squadra[p.incontro.casa].append((p, True))
        per_squadra[p.incontro.ospite].append((p, False))

    imbattute, senza_vittoria, senza_subire, senza_segnare = [], [], [], []
    for squadra, elenco in per_squadra.items():
        if squadre_attuali and squadra not in squadre_attuali:
            continue
        # Le serie si contano una per volta, all'indietro, fermandosi al primo
        # risultato che le interrompe.
        def conta(condizione, elenco=elenco) -> int:
            n = 0
            for p, in_casa in reversed(elenco):
                mio = p.incontro.punti_casa if in_casa else p.incontro.punti_ospite
                suo = p.incontro.punti_ospite if in_casa else p.incontro.punti_casa
                if not condizione(mio, suo):
                    break
                n += 1
            return n

        n_imb = conta(lambda m, s: m >= s)
        n_sv = conta(lambda m, s: m <= s)
        n_ns = conta(lambda m, s: s == 0)
        n_nseg = conta(lambda m, s: m == 0)
        imbattute.append((n_imb, squadra))
        senza_vittoria.append((n_sv, squadra))
        senza_subire.append((n_ns, squadra))
        senza_segnare.append((n_nseg, squadra))

    fuori = []
    for elenco, soglia, tipo, titolo, testo in (
        (imbattute, 6, "imbattuta", "{s} non perde da {n} partite",
         "Una serie aperta: dice cosa e' successo, non cosa succedera'."),
        (senza_vittoria, 6, "digiuno", "{s} non vince da {n} partite",
         "Il digiuno aperto piu' lungo del campionato."),
        (senza_subire, 4, "porta_chiusa", "{s} non subisce gol da {n} partite",
         "Quattro o piu' partite di fila con la porta inviolata capitano poco."),
        (senza_segnare, 3, "a_secco", "{s} non segna da {n} partite",
         "Tre partite senza gol di fila sono gia' un problema, non un caso."),
    ):
        if not elenco:
            continue
        n, squadra = max(elenco)
        if n >= soglia:
            fuori.append(Chicca(
                tipo=tipo,
                titolo=titolo.format(s=squadra, n=n),
                testo=testo,
                numero=str(n),
                campionato=c.nome, bandiera=c.bandiera, slug=c.slug,
                squadre=[squadra], campione=n,
            ))
    return fuori


# --- i confronti fra campionati -------------------------------------------

def confronti(per_lega: list[tuple]) -> list[Chicca]:
    """Le differenze fra campionati, che quasi nessuno mette in fila.

    `per_lega` e' una lista di (catalogo, partite). Qui non si guarda una
    squadra ma un intero torneo, ed e' il taglio che rende utile avere
    ventidue campionati invece di uno.
    """
    righe = []
    for c, partite in per_lega:
        complete = [p for p in partite if p.stat.completa]
        if len(complete) < MINIMO * 4:
            continue
        n = len(complete)
        gol = sum(p.incontro.punti_casa + p.incontro.punti_ospite for p in complete)
        casa = sum(1 for p in complete if p.esito == 0)
        pari = sum(1 for p in complete if p.esito == 1)
        cartellini = sum(sum(p.stat.gialli) + sum(p.stat.rossi) for p in complete)
        corner = sum(sum(p.stat.corner) for p in complete)
        pt = sum(sum(p.stat.gol_primo_tempo) for p in complete)
        righe.append({
            "c": c, "n": n, "gol": gol / n, "casa": casa / n, "pari": pari / n,
            "cartellini": cartellini / n, "corner": corner / n,
            "quota_pt": pt / gol if gol else 0,
        })
    if len(righe) < 3:
        return []

    def estremo(chiave, massimo, tipo, titolo, testo, formato):
        r = (max if massimo else min)(righe, key=lambda x: x[chiave])
        v = r[chiave]
        return Chicca(
            tipo=tipo,
            titolo=titolo.format(c=r["c"].nome),
            testo=testo.format(v=formato(v), c=r["c"].nome),
            numero=formato(v),
            campionato=r["c"].nome, bandiera=r["c"].bandiera, slug=r["c"].slug,
            campione=r["n"],
        )

    due = lambda v: f"{v:.2f}"
    pc = lambda v: f"{100 * v:.0f}%"
    uno = lambda v: f"{v:.1f}"

    return [
        estremo("gol", True, "gol_lega", "Il campionato dove si segna di piu' e' {c}",
                "{v} gol a partita, contando tutte le gare delle ultime stagioni.", due),
        estremo("gol", False, "gol_lega_meno", "E quello dove si segna di meno e' {c}",
                "{v} gol a partita: quasi uno in meno del campionato piu' prolifico.", due),
        estremo("casa", True, "campo", "Giocare in casa conta piu' che altrove in {c}",
                "La squadra di casa vince il {v} delle partite.", pc),
        estremo("pari", True, "pareggi", "In {c} si pareggia piu' che ovunque",
                "Un {v} delle partite finisce in parita'.", pc),
        estremo("cartellini", True, "cartellini", "L'arbitro estrae di piu' in {c}",
                "{v} cartellini a partita fra le due squadre.", uno),
        estremo("corner", True, "corner", "Il campionato dei calci d'angolo e' {c}",
                "{v} angoli a partita in totale.", uno),
    ]


def per_campionato(partite: list[PartitaStorica], c,
                   squadre_attuali: set[str] | None = None) -> list[Chicca]:
    """Tutte le chicche di un campionato, gia' pronte da pubblicare."""
    fuori: list[Chicca] = []
    fuori += serie_aperte(partite, c, squadre_attuali)
    fuori += rimonte(partite, c, squadre_attuali)
    fuori += quando_segnano(partite, c, squadre_attuali)
    fuori += sorprese_del_mercato(partite, c)
    return fuori
