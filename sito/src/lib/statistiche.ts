/**
 * Ricomporre le statistiche di una squadra, e la media del suo campionato.
 *
 * I dati arrivano separati fra casa e trasferta, ed è giusto che sia così: il
 * vantaggio del campo è uno dei pochi effetti davvero grandi del calcio. Ma
 * per il totale vanno ricomposti **pesando per le partite**, non facendo la
 * media delle due medie: chi ha giocato sei partite in casa e quattro fuori
 * non sta a metà strada fra i due numeri.
 */

/** Le voci che abbiamo per ogni partita, senza eccezioni. */
export const CHIAVI = [
  'gol_fatti', 'gol_subiti', 'tiri', 'in_porta', 'tiri_subiti',
  'in_porta_subiti', 'corner', 'corner_subiti', 'falli', 'cartellini',
] as const;

/**
 * Le voci avanzate hanno un denominatore loro. Possesso, passaggi e contrasti
 * li abbiamo solo per le partite di cui ESPN pubblica il dettaglio, che sono
 * meno delle altre: dividerle per il totale delle partite le schiaccerebbe
 * verso il basso di una quantità che cambia da squadra a squadra.
 */
export const AVANZATE = [
  'possesso', 'passaggi', 'precisione_passaggi', 'contrasti',
  'intercetti', 'parate',
] as const;

/** Casa + trasferta in un solo blocco di medie a partita. */
export function unisci(r: any) {
  const c = r?.casa ?? {};
  const t = r?.trasferta ?? {};
  const n = (c.partite ?? 0) + (t.partite ?? 0);
  const na = (c.con_avanzate ?? 0) + (t.con_avanzate ?? 0);
  const out: any = { partite: n, con_avanzate: na };

  for (const k of CHIAVI) {
    out[k] = n
      ? ((c[k] ?? 0) * (c.partite ?? 0) + (t[k] ?? 0) * (t.partite ?? 0)) / n
      : null;
  }
  for (const k of AVANZATE) {
    out[k] = na
      ? ((c[k] ?? 0) * (c.con_avanzate ?? 0) + (t[k] ?? 0) * (t.con_avanzate ?? 0)) / na
      : null;
  }
  return out;
}

/**
 * La media del campionato: un totale diviso un totale, non la media delle
 * medie delle squadre. Le squadre non hanno tutte giocato lo stesso numero di
 * partite, e a inizio stagione la differenza si vede.
 */
export function mediaLega(righe: any[]) {
  const uniti = righe.map(unisci);
  const pesata = (k: string, peso: 'partite' | 'con_avanzate') => {
    let somma = 0;
    let pesi = 0;
    for (const u of uniti) {
      const v = u[k];
      const p = u[peso];
      if (v === null || !p) continue;
      somma += v * p;
      pesi += p;
    }
    return pesi ? somma / pesi : null;
  };

  const out: any = {};
  for (const k of CHIAVI) out[k] = pesata(k, 'partite');
  for (const k of AVANZATE) out[k] = pesata(k, 'con_avanzate');
  return out;
}
