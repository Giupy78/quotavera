/**
 * Scrivere numeri e nomi di campionati dentro una frase italiana.
 *
 * Servono agli articoli con i dati, dove ogni frase che contiene un numero lo
 * prende dai dati e quindi deve reggere qualunque campionato finisca in testa:
 * "la Bundesliga", "l'Eredivisie", "LaLiga" (che l'articolo ce l'ha gia' nel
 * nome). La stessa regola, in Python, e' `con_articolo` in `engine/chicche.py`.
 */

/** 2.534 -> "2,53". La virgola, perche' lo legge un lettore italiano. */
export const num = (v: number, decimali = 2) =>
  v.toLocaleString('it-IT', {
    minimumFractionDigits: decimali,
    maximumFractionDigits: decimali,
  });

/** 0.4123 -> "41%". */
export const pct = (v: number, decimali = 0) => `${num(v * 100, decimali)}%`;

const vocale = (nome: string) => /^[aeiouAEIOU]/.test(nome);
const haGiaArticolo = (nome: string) => nome.startsWith('La');

/** L'articolo davanti al nome: "la ", "l'", oppure niente per LaLiga. */
export const art = (nome: string) =>
  haGiaArticolo(nome) ? '' : vocale(nome) ? "l'" : 'la ';

/** "nella Bundesliga", "nell'Eredivisie", "in LaLiga". */
export const nella = (nome: string) =>
  haGiaArticolo(nome) ? 'in ' : vocale(nome) ? "nell'" : 'nella ';

/** "della Bundesliga", "dell'Eredivisie", "di LaLiga". */
export const della = (nome: string) =>
  haGiaArticolo(nome) ? 'di ' : vocale(nome) ? "dell'" : 'della ';
