"""Generatori di stagioni finte, per verificare che i modelli ritrovino la verita'.

E' la prova piu' importante che si possa fare su un modello statistico: si
inventano dei parametri veri, si simula un campionato che li rispetti, si da'
in pasto al modello solo i risultati, e si controlla che riesca a risalire ai
parametri di partenza. Se non ci riesce sui dati finti, sui dati veri non ha
speranza.
"""

from datetime import date, timedelta

import numpy as np
import pytest

from engine.core.types import Incontro


SQUADRE_CALCIO = [
    # nome, attacco (log), difesa (log)
    ("Inter", 0.42, 0.38),
    ("Napoli", 0.34, 0.42),
    ("Atalanta", 0.36, 0.10),
    ("Juventus", 0.12, 0.30),
    ("Milan", 0.24, 0.02),
    ("Roma", 0.06, 0.14),
    ("Lazio", 0.00, 0.06),
    ("Bologna", -0.08, 0.10),
    ("Fiorentina", -0.04, -0.10),
    ("Torino", -0.26, 0.04),
    ("Udinese", -0.30, -0.06),
    ("Genoa", -0.42, -0.18),
    ("Empoli", -0.44, -0.22),
    ("Lecce", -0.50, -0.30),
]
VANTAGGIO_CASA_VERO = 0.26


@pytest.fixture(scope="session")
def stagione_calcio() -> list[Incontro]:
    """Tre stagioni simulate da parametri noti e costanti, con due Poisson pure.

    Tre e non una: con 182 partite il vantaggio del campo resta incerto di
    circa 0,15 in scala log, e un test che ci passasse sopra proverebbe solo
    che il generatore e' stato fortunato. Tre stagioni sono anche cio' che si
    dara' in pasto al modello in produzione.
    """
    rng = np.random.default_rng(20260827)
    inizio = date(2023, 8, 20)
    incontri: list[Incontro] = []
    n = 0
    for stagione in range(3):
        for casa, att_c, dif_c in SQUADRE_CALCIO:
            for ospite, att_o, dif_o in SQUADRE_CALCIO:
                if casa == ospite:
                    continue
                lh = float(np.exp(att_c - dif_o + VANTAGGIO_CASA_VERO))
                la = float(np.exp(att_o - dif_c))
                n += 1
                incontri.append(
                    Incontro(
                        id=f"c{n}",
                        data=inizio + timedelta(days=stagione * 365 + (n % 182) * 2),
                        casa=casa,
                        ospite=ospite,
                        punti_casa=int(rng.poisson(lh)),
                        punti_ospite=int(rng.poisson(la)),
                        campionato="Serie A",
                    )
                )
    return incontri


@pytest.fixture(scope="session")
def calcio_con_svolta() -> list[Incontro]:
    """Due stagioni in cui il Lecce, a meta' strada, diventa una corazzata.

    Serve a verificare che il peso nel tempo faccia il suo mestiere: un modello
    senza decadimento continuerebbe a dare il Lecce per ultimo per mesi.
    """
    rng = np.random.default_rng(999)
    inizio = date(2024, 8, 20)
    incontri: list[Incontro] = []
    n = 0
    for meta in range(2):
        for casa, att_c, dif_c in SQUADRE_CALCIO:
            for ospite, att_o, dif_o in SQUADRE_CALCIO:
                if casa == ospite:
                    continue
                # Nella seconda meta' il Lecce passa da ultimo a fortissimo.
                if meta == 1 and casa == "Lecce":
                    att_c, dif_c = 0.55, 0.45
                if meta == 1 and ospite == "Lecce":
                    att_o, dif_o = 0.55, 0.45
                lh = float(np.exp(att_c - dif_o + VANTAGGIO_CASA_VERO))
                la = float(np.exp(att_o - dif_c))
                n += 1
                incontri.append(
                    Incontro(
                        id=f"s{n}",
                        data=inizio + timedelta(days=n * 2),
                        casa=casa,
                        ospite=ospite,
                        punti_casa=int(rng.poisson(lh)),
                        punti_ospite=int(rng.poisson(la)),
                        campionato="Serie A",
                    )
                )
    return incontri


SQUADRE_BASKET = [
    # nome, forza (punti sopra la media), ritmo (punti sul totale)
    ("Milano", 7.5, 3.0),
    ("Bologna", 6.0, 1.0),
    ("Trento", 1.5, 4.0),
    ("Venezia", 1.0, -1.0),
    ("Brescia", 0.5, 2.5),
    ("Trieste", -1.0, 5.0),
    ("Reggio", -2.0, -2.0),
    ("Napoli", -3.5, 0.0),
    ("Cremona", -4.5, -3.5),
    ("Pistoia", -5.5, -3.0),
]
VANTAGGIO_CASA_BASKET = 3.2
TOTALE_BASE_VERO = 160.0
SIGMA_MARGINE_VERO = 11.5


@pytest.fixture(scope="session")
def stagione_basket() -> list[Incontro]:
    """Quattro doppi gironi: nel basket il rumore per partita e' molto piu' alto.

    Con sigma 11,5 punti a partita e differenze fra squadre di qualche punto,
    servono 360 partite perche' le forze siano ricostruibili sul serio.
    """
    rng = np.random.default_rng(4242)
    inizio = date(2025, 10, 5)
    incontri: list[Incontro] = []
    n = 0
    for _ in range(4):
        for casa, forza_c, ritmo_c in SQUADRE_BASKET:
            for ospite, forza_o, ritmo_o in SQUADRE_BASKET:
                if casa == ospite:
                    continue
                mu = forza_c - forza_o + VANTAGGIO_CASA_BASKET
                totale = TOTALE_BASE_VERO + ritmo_c + ritmo_o
                margine = rng.normal(mu, SIGMA_MARGINE_VERO)
                punti_totali = rng.normal(totale, 12.0)
                n += 1
                incontri.append(
                    Incontro(
                        id=f"b{n}",
                        data=inizio + timedelta(days=n // 5),
                        casa=casa,
                        ospite=ospite,
                        punti_casa=int(round((punti_totali + margine) / 2)),
                        punti_ospite=int(round((punti_totali - margine) / 2)),
                        campionato="LBA",
                    )
                )
    return incontri


@pytest.fixture(scope="session")
def storico_tennis() -> list[Incontro]:
    """Match simulati da forze note: il piu' forte vince piu' spesso."""
    rng = np.random.default_rng(77)
    forze = {f"G{i:02d}": 1500 + (20 - i) * 45 for i in range(20)}
    nomi = list(forze)
    inizio = date(2025, 1, 6)
    incontri: list[Incontro] = []
    for n in range(3000):
        a, b = rng.choice(len(nomi), size=2, replace=False)
        na, nb = nomi[a], nomi[b]
        p_a = 1.0 / (1.0 + 10.0 ** ((forze[nb] - forze[na]) / 400.0))
        vince_a = rng.random() < p_a
        incontri.append(
            Incontro(
                id=f"t{n}",
                data=inizio + timedelta(days=n // 12),
                casa=na,
                ospite=nb,
                punti_casa=2 if vince_a else 0,
                punti_ospite=0 if vince_a else 2,
                campionato="cemento",
            )
        )
    return incontri
