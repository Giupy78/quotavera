"""La sentinella guarda il sito vero: online c'è l'ultimo commit?

Il 9 novembre 2026 un push non ha mai avuto la sua build su Cloudflare, e per
mezz'ora nove rinvii che il repository dava per fatti rispondevano 404. Qui si
prova il confronto senza rete e senza aspettare davvero: il sito, git e
l'orologio sono finti.
"""

import importlib.util
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]

VECCHIO = "24c3edb" + "0" * 33
NOSTRO = "fb22260" + "0" * 33
PIU_NUOVO = "a1b2c3d" + "0" * 33


def sentinella():
    spec = importlib.util.spec_from_file_location("controlla", RADICE / "scripts" / "controlla.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Tempo:
    """Un orologio che va avanti solo quando la sentinella dorme."""

    def __init__(self):
        self.adesso = 0.0
        self.sonni = 0

    def orologio(self):
        return self.adesso

    def dormi(self, secondi):
        self.adesso += secondi
        self.sonni += 1


def in_sequenza(*valori):
    """Restituisce i valori uno dopo l'altro, poi ripete l'ultimo."""
    resto = list(valori)

    def prossimo():
        return resto.pop(0) if len(resto) > 1 else resto[0]
    return prossimo


def prova(sito, ultimo, attesa=600, ogni=20):
    t = Tempo()
    guai, avvisi = sentinella().controlla_pubblicazione(
        leggi=sito, ultimo=ultimo, attesa=attesa, ogni=ogni,
        dormi=t.dormi, orologio=t.orologio)
    return guai, avvisi, t


def test_se_online_c_e_l_ultimo_commit_va_tutto_bene_subito():
    guai, avvisi, t = prova(lambda: (NOSTRO, ""), lambda: NOSTRO)
    assert (guai, avvisi) == ([], [])
    assert t.sonni == 0


def test_aspetta_che_cloudflare_finisca_la_build():
    sito = in_sequenza((VECCHIO, ""), (VECCHIO, ""), (VECCHIO, ""), (NOSTRO, ""))
    guai, avvisi, t = prova(sito, lambda: NOSTRO)
    assert (guai, avvisi) == ([], [])
    assert t.sonni == 3


def test_un_sito_fermo_al_commit_vecchio_e_un_guaio():
    """Il caso del 9 novembre: la build non arriva mai."""
    guai, avvisi, t = prova(lambda: (VECCHIO, ""), lambda: NOSTRO, attesa=600, ogni=20)
    assert avvisi == []
    assert len(guai) == 1
    assert "24c3edb" in guai[0] and "fb22260" in guai[0]
    assert "dopo 10 minuti" in guai[0]
    assert t.adesso >= 600                    # ha aspettato tutto il margine, non di più
    assert t.adesso < 600 + 20


def test_un_commit_spinto_durante_l_attesa_si_aspetta_quello():
    """Se qualcuno spinge dopo di noi, l'ultimo diventa il suo: niente falso allarme."""
    ultimo = in_sequenza(NOSTRO, PIU_NUOVO)
    sito = in_sequenza((VECCHIO, ""), (NOSTRO, ""), (PIU_NUOVO, ""))
    guai, avvisi, _ = prova(sito, ultimo)
    assert (guai, avvisi) == ([], [])


def test_un_sito_che_non_si_legge_e_solo_un_avviso():
    """Può essere la rete o Cloudflare che ci tratta da robot: non deve gridare ogni notte."""
    guai, avvisi, t = prova(lambda: (None, "risposta 403"), lambda: NOSTRO)
    assert guai == []
    assert len(avvisi) == 1 and "risposta 403" in avvisi[0]
    assert t.sonni == 2                       # tre tentativi, non dieci minuti


def test_una_lettura_fallita_ogni_tanto_non_basta_a_rinunciare():
    sito = in_sequenza((None, "timeout"), (VECCHIO, ""), (NOSTRO, ""))
    guai, avvisi, _ = prova(sito, lambda: NOSTRO)
    assert (guai, avvisi) == ([], [])


def test_senza_sapere_l_ultimo_commit_non_si_controlla():
    guai, avvisi, _ = prova(lambda: (NOSTRO, ""), lambda: None)
    assert guai == []
    assert len(avvisi) == 1


def test_il_sito_dichiara_il_suo_commit():
    """La pagina esiste e prende il commit da Cloudflare, o da git in locale."""
    testo = (RADICE / "sito" / "src" / "pages" / "versione.txt.ts").read_text(encoding="utf-8")
    assert "CF_PAGES_COMMIT_SHA" in testo
    assert "git rev-parse HEAD" in testo
    assert sentinella().VERSIONE_PUBBLICATA.endswith("/versione.txt")
