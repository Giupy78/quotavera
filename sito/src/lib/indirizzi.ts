/**
 * L'indirizzo di una squadra.
 *
 * Non è quello di una partita, e la differenza è voluta. Le partite usano
 * `id_partita` del generatore, che schiaccia gli spazi: "Man City" diventa
 * "mancity". Quella forma non si tocca più — quegli indirizzi sono indicizzati
 * da mesi, e riscriverli sarebbe esattamente il 404 che abbiamo appena chiuso.
 *
 * Qui invece partiamo da zero e lo spazio diventa un trattino, perché
 * "man-city" è anche la forma con cui la ricerca viene scritta. Gli accenti si
 * sciolgono nella lettera base: "Düsseldorf" → "dusseldorf", che è come la
 * cerca chi non ha la dieresi sulla tastiera.
 *
 * Verificato su tutte e 398 le squadre dei ventidue campionati: nessuna
 * collisione fra squadre dello stesso campionato, e nessuna con l'indirizzo di
 * una partita.
 */
export function lumacaSquadra(nome: string): string {
  return nome
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/['.]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}
