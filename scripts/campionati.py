"""I campionati coperti, con i parametri che li rendono diversi fra loro.

Non e' una lista di etichette: ogni campionato ha un mondo statistico suo, e
sono proprio le differenze a costituire il contenuto del sito. La Bundesliga
segna un gol in piu' dell'Eredivisie di vent'anni fa; il vantaggio del campo in
Grecia e' il doppio che in Inghilterra; il banco sui campionati minori si tiene
il doppio del margine. Un sito che copre solo la Serie A non puo' dire niente
di tutto questo — uno internazionale si'.

I valori qui sotto sono ordini di grandezza plausibili, usati per generare il
mondo simulato. **Vanno sostituiti dalle stime sui dati veri** appena il
lettore dei risultati e' collegato: a quel punto questi numeri diventano un
output del modello, non un input.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Campionato:
    slug: str
    nome: str
    paese: str
    bandiera: str
    squadre: list[str]
    # Reti attese medie a partita: separa la Bundesliga dalla Ligue 1.
    gol_partita: float
    # Vantaggio del campo, in scala log. Varia molto piu' di quanto si creda.
    vantaggio_casa: float
    # Margine che il banco si tiene sull'1X2. Sui campionati minori e' doppio.
    margine_banco: float
    # Quanto sono diverse le squadre fra loro: un campionato con due corazzate
    # e sedici comparse ha dispersione alta ed e' molto piu' prevedibile.
    dispersione: float
    livello: int = 1
    note: str = ""

    @property
    def n_squadre(self) -> int:
        return len(self.squadre)


CAMPIONATI: list[Campionato] = [
    Campionato(
        slug="serie-a",
        nome="Serie A",
        paese="Italia",
        bandiera="🇮🇹",
        squadre=[
            "Inter", "Napoli", "Atalanta", "Juventus", "Milan", "Roma",
            "Lazio", "Bologna", "Fiorentina", "Torino", "Udinese", "Genoa",
            "Empoli", "Lecce", "Cagliari", "Verona", "Parma", "Como",
        ],
        gol_partita=2.72,
        vantaggio_casa=0.26,
        margine_banco=0.045,
        dispersione=0.30,
        note="Campionato tattico e con poche reti: i pareggi pesano più che altrove.",
    ),
    Campionato(
        slug="premier-league",
        nome="Premier League",
        paese="Inghilterra",
        bandiera="🏴󠁧󠁢󠁥󠁮󠁧󠁿",
        squadre=[
            "Manchester City", "Arsenal", "Liverpool", "Chelsea", "Tottenham",
            "Aston Villa", "Newcastle", "Manchester United", "Brighton",
            "West Ham", "Crystal Palace", "Fulham", "Brentford", "Everton",
            "Nottingham Forest", "Wolves", "Bournemouth", "Leeds",
        ],
        gol_partita=2.85,
        # Il campionato dove il fattore campo conta di meno fra i grandi.
        vantaggio_casa=0.19,
        # Mercato liquidissimo: il banco può permettersi il margine più basso.
        margine_banco=0.038,
        dispersione=0.34,
        note="Il mercato più liquido del mondo: margini bassi e quote quasi sempre corrette.",
    ),
    Campionato(
        slug="laliga",
        nome="LaLiga",
        paese="Spagna",
        bandiera="🇪🇸",
        squadre=[
            "Real Madrid", "Barcellona", "Atletico Madrid", "Athletic Bilbao",
            "Real Sociedad", "Villarreal", "Betis", "Siviglia", "Valencia",
            "Girona", "Osasuna", "Celta Vigo", "Rayo Vallecano", "Getafe",
            "Maiorca", "Alaves", "Espanyol", "Leganes",
        ],
        gol_partita=2.55,
        vantaggio_casa=0.28,
        margine_banco=0.044,
        dispersione=0.38,
        note="Due corazzate e un campionato dietro: dispersione alta, esiti più prevedibili.",
    ),
    Campionato(
        slug="bundesliga",
        nome="Bundesliga",
        paese="Germania",
        bandiera="🇩🇪",
        squadre=[
            "Bayern Monaco", "Bayer Leverkusen", "Stoccarda", "Lipsia",
            "Borussia Dortmund", "Eintracht Francoforte", "Friburgo",
            "Hoffenheim", "Werder Brema", "Augusta", "Wolfsburg", "Mainz",
            "Borussia M'gladbach", "Union Berlino", "St. Pauli", "Heidenheim",
        ],
        gol_partita=3.18,
        vantaggio_casa=0.22,
        margine_banco=0.042,
        dispersione=0.36,
        note="Il campionato con più reti fra i grandi: gli over valgono molto più che in Italia.",
    ),
    Campionato(
        slug="ligue-1",
        nome="Ligue 1",
        paese="Francia",
        bandiera="🇫🇷",
        squadre=[
            "Paris Saint-Germain", "Monaco", "Marsiglia", "Lilla", "Nizza",
            "Lione", "Lens", "Rennes", "Strasburgo", "Brest", "Tolosa",
            "Nantes", "Reims", "Auxerre", "Angers", "Le Havre",
        ],
        gol_partita=2.68,
        vantaggio_casa=0.25,
        margine_banco=0.047,
        dispersione=0.40,
        note="Una squadra fuori scala e il resto compresso: le quote sul PSG sono quasi mai valore.",
    ),
    Campionato(
        slug="eredivisie",
        nome="Eredivisie",
        paese="Paesi Bassi",
        bandiera="🇳🇱",
        squadre=[
            "PSV", "Feyenoord", "Ajax", "AZ Alkmaar", "Twente", "Utrecht",
            "Go Ahead Eagles", "Sparta Rotterdam", "NEC", "Heerenveen",
            "Groningen", "Fortuna Sittard", "Zwolle", "Waalwijk",
            "Willem II", "Almere City",
        ],
        gol_partita=3.35,
        vantaggio_casa=0.30,
        # Mercato più sottile: il banco si tiene di più.
        margine_banco=0.058,
        dispersione=0.46,
        note="Tanti gol e mercato sottile: è qui che un modello ha più spazio, e più margine da battere.",
    ),
    Campionato(
        slug="primeira-liga",
        nome="Primeira Liga",
        paese="Portogallo",
        bandiera="🇵🇹",
        squadre=[
            "Sporting", "Benfica", "Porto", "Braga", "Vitoria Guimaraes",
            "Moreirense", "Famalicao", "Santa Clara", "Estoril", "Casa Pia",
            "Arouca", "Gil Vicente", "Nacional", "Farense",
        ],
        gol_partita=2.60,
        vantaggio_casa=0.32,
        margine_banco=0.062,
        dispersione=0.52,
        note="Tre squadre che vincono quasi sempre e un margine del banco alto: poco spazio in alto, molto in basso.",
    ),
    Campionato(
        slug="superlig",
        nome="Süper Lig",
        paese="Turchia",
        bandiera="🇹🇷",
        squadre=[
            "Galatasaray", "Fenerbahçe", "Beşiktaş", "Trabzonspor",
            "Başakşehir", "Adana Demirspor", "Kasımpaşa", "Antalyaspor",
            "Alanyaspor", "Konyaspor", "Sivasspor", "Rizespor",
            "Gaziantep", "Hatayspor",
        ],
        gol_partita=3.05,
        # Il fattore campo più alto della lista, e non è un caso isolato.
        vantaggio_casa=0.38,
        margine_banco=0.068,
        dispersione=0.44,
        note="Il fattore campo più forte fra i campionati coperti, e il margine più alto: due ragioni per guardarci.",
    ),
]

PER_SLUG: dict[str, Campionato] = {c.slug: c for c in CAMPIONATI}


def forze_simulate(c: Campionato) -> list[tuple[str, float, float]]:
    """Assegna attacco e difesa alle squadre in modo deterministico.

    Le squadre sono elencate dalla più forte alla più debole, e le forze
    scendono linearmente con la dispersione del campionato. L'attacco medio è
    zero per costruzione: è lo stesso vincolo che usa il modello.
    """
    n = c.n_squadre
    fuori = []
    for i, squadra in enumerate(c.squadre):
        # Da +1 (la prima) a -1 (l'ultima).
        posizione = 1.0 - 2.0 * i / max(n - 1, 1)
        attacco = posizione * c.dispersione
        # La difesa segue la forza ma non perfettamente: alcune squadre sono
        # sbilanciate, ed è proprio lì che il modello guadagna qualcosa.
        difesa = posizione * c.dispersione * 0.85 + (0.06 if i % 3 == 0 else -0.03)
        fuori.append((squadra, attacco, difesa))
    media_att = sum(a for _, a, _ in fuori) / n
    return [(s, a - media_att, d) for s, a, d in fuori]
