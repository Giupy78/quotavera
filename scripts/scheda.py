"""La scheda statistica di una partita: il prodotto quotidiano, in prototipo.

Non dice cosa giocare. Mette in fila i numeri che servono a farsi un'idea, e
lascia l'idea al lettore. E' la differenza fra un sito di statistica e un sito
di pronostici, e passa tutta da come sono scritte le ultime tre righe.

    python scripts/scheda.py                    # Serie A, ultima stagione
    python scripts/scheda.py premier-league
"""

from __future__ import annotations

import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from engine.core.market import probabilita_implicite
from engine.dati.football_data import carica, stagioni
from engine.statistiche import calcola, conversione_media, precedenti


def barra(valore: float, massimo: float, larghezza: int = 22) -> str:
    if massimo <= 0:
        return ""
    return "█" * max(0, min(larghezza, round(valore / massimo * larghezza)))


def scheda(partite, storico, casa: str, ospite: str, conv: float) -> None:
    stat = calcola(partite)
    recente = calcola(partite, ultime=6)
    c, o = stat.get(casa), stat.get(ospite)
    if not c or not o:
        print(f"  Dati insufficienti per {casa} — {ospite}")
        return

    print("\n" + "=" * 74)
    print(f"  {casa.upper()} — {ospite.upper()}")
    print("=" * 74)

    print(f"\n  {'':22s} {casa[:16]:>16s}   {ospite[:16]:>16s}")
    print("  " + "-" * 60)
    righe = [
        ("Gol fatti a partita", c.casa.gol_fatti_partita, o.trasferta.gol_fatti_partita, "{:.2f}"),
        ("Gol subiti a partita", c.casa.gol_subiti_partita, o.trasferta.gol_subiti_partita, "{:.2f}"),
        ("Tiri a partita", c.casa.tiri_partita, o.trasferta.tiri_partita, "{:.1f}"),
        ("Tiri in porta", c.casa.in_porta_partita, o.trasferta.in_porta_partita, "{:.1f}"),
        ("Tiri in porta subiti", c.casa.in_porta_subiti_partita, o.trasferta.in_porta_subiti_partita, "{:.1f}"),
        ("Corner a partita", c.casa.corner_partita, o.trasferta.corner_partita, "{:.1f}"),
        ("Cartellini a partita", c.casa.cartellini_partita, o.trasferta.cartellini_partita, "{:.1f}"),
    ]
    for nome, a, b, f in righe:
        print(f"  {nome:22s} {f.format(a):>16s}   {f.format(b):>16s}")

    print(f"\n  {'(in casa / in trasferta)':22s}")
    print("  " + "-" * 60)
    percentuali = [
        ("Over 2,5", c.casa.quota_over_25, o.trasferta.quota_over_25),
        ("Gol / Gol", c.casa.quota_gol_gol, o.trasferta.quota_gol_gol),
        ("Porta inviolata", c.casa.quota_clean_sheet, o.trasferta.quota_clean_sheet),
        ("Rimasta a secco", c.casa.quota_a_secco, o.trasferta.quota_a_secco),
    ]
    for nome, a, b in percentuali:
        print(f"  {nome:22s} {a:>15.0%}   {b:>15.0%}")

    print("\n  SEGNA PIÙ O MENO DI QUANTO CREA?")
    print("  " + "-" * 60)
    for s in (c, o):
        scarto = s.scarto_dalla_conversione(conv)
        segno = "sopra" if scarto > 0 else "sotto"
        print(f"  {s.squadra:18s} {s.gol_totali:3d} gol contro"
              f" {s.in_porta_totali * conv:5.1f} attesi dai tiri"
              f"   {abs(scarto):4.1f} {segno}")
    print(f"  (conversione media del campionato: {conv:.1%} dei tiri in porta)")

    print("\n  FORMA — ultime 6, sui tiri in porta invece che sui risultati")
    print("  " + "-" * 60)
    for nome in (casa, ospite):
        r = recente.get(nome)
        if not r:
            continue
        tot = r.casa.in_porta + r.trasferta.in_porta
        sub = r.casa.in_porta_subiti + r.trasferta.in_porta_subiti
        n = r.casa.con_statistiche + r.trasferta.con_statistiche
        if n:
            print(f"  {nome:18s} crea {tot / n:4.1f}  concede {sub / n:4.1f}"
                  f"  {barra(tot / n, 8)}")

    scontri = precedenti(storico, casa, ospite, quante=6)
    if scontri:
        print("\n  PRECEDENTI")
        print("  " + "-" * 60)
        for p in scontri:
            i = p.incontro
            print(f"  {i.data:%d/%m/%Y}  {i.casa:18s} {i.punti_casa}-{i.punti_ospite}  {i.ospite}")


def spunti(partite, conv: float, quanti: int = 6) -> None:
    """Le statistiche che saltano all'occhio: il contenuto quotidiano."""
    stat = calcola(partite)
    print("\n" + "=" * 74)
    print("  GLI SPUNTI DELLA GIORNATA")
    print("=" * 74)

    scarti = sorted(
        (s for s in stat.values() if s.in_porta_totali > 50),
        key=lambda s: s.scarto_dalla_conversione(conv),
    )
    print("\n  Chi sta segnando MENO di quanto crea — di solito rientrano:")
    for s in scarti[:3]:
        print(f"    {s.squadra:18s} {s.scarto_dalla_conversione(conv):+5.1f} gol"
              f"   ({s.gol_totali} fatti, {s.in_porta_totali * conv:.1f} attesi)")
    print("\n  Chi sta segnando PIÙ di quanto crea — attenzione a inseguirli:")
    for s in reversed(scarti[-3:]):
        print(f"    {s.squadra:18s} {s.scarto_dalla_conversione(conv):+5.1f} gol"
              f"   ({s.gol_totali} fatti, {s.in_porta_totali * conv:.1f} attesi)")

    casalinghe = sorted(stat.values(), key=lambda s: s.vantaggio_casa, reverse=True)
    print("\n  Chi cambia di più fra casa e trasferta (gol a partita):")
    for s in casalinghe[:3]:
        print(f"    {s.squadra:18s} {s.casa.gol_fatti_partita:.2f} in casa"
              f"  contro {s.trasferta.gol_fatti_partita:.2f} fuori"
              f"   ({s.vantaggio_casa:+.2f})")

    over = sorted(stat.values(),
                  key=lambda s: (s.casa.over_25 + s.trasferta.over_25) / max(s.partite, 1),
                  reverse=True)
    print("\n  Le partite di chi finiscono più spesso sopra i 2,5 gol:")
    for s in over[:3]:
        q = (s.casa.over_25 + s.trasferta.over_25) / s.partite
        print(f"    {s.squadra:18s} {q:.0%} delle partite")


def main() -> int:
    slug = sys.argv[1] if len(sys.argv) > 1 else "serie-a"
    print(f"Carico {slug}…")
    storico = carica(slug, stagioni(2021, 2026))
    stagione = carica(slug, ["2526"])
    conv = conversione_media(stagione)

    con_stat = sum(1 for p in stagione if p.stat.completa)
    print(f"{len(stagione)} partite nell'ultima stagione, {con_stat} con statistiche complete")

    stat = calcola(stagione)
    forti = sorted(stat.values(), key=lambda s: s.gol_fatti_partita, reverse=True)
    scheda(stagione, storico, forti[0].squadra, forti[1].squadra, conv)
    spunti(stagione, conv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
