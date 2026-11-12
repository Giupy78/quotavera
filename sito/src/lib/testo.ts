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

/** L'articolo davanti a un numero gia' scritto: "l'11%", "l'8,5%", "l'1%",
 *  ma "il 18%" e "il 12%". I numeri degli articoli cambiano ogni notte, e
 *  "il 11%" e' un errore che compare da solo il giorno in cui il dato cambia. */
export const ilNumero = (testo: string) =>
  /^(8|11(?![\d])|1(?![\d]))/.test(testo) ? "l'" : 'il ';

/** "il 73%", "l'11%": percentuale con il suo articolo. */
export const ilp = (v: number, decimali = 0) => {
  const s = pct(v, decimali);
  return `${ilNumero(s)}${s}`;
};

/** Lo stesso, a inizio frase: "Il 41%", "L'8%". */
export const Ilp = (v: number, decimali = 0) => {
  const s = ilp(v, decimali);
  return s.charAt(0).toUpperCase() + s.slice(1);
};

/* Tre nomi che a un lettore italiano non dicono il paese, e che nelle frasi
   non hanno la bandiera accanto come nelle tabelle. */
const QUALIFICA: Record<string, string> = {
  'Super League': 'Super League greca',
  Premiership: 'Premiership scozzese',
  'Pro League': 'Pro League belga',
};
/** "Super League" -> "Super League greca", dentro una frase. */
export const chiaro = (nome: string) => QUALIFICA[nome] ?? nome;

/** L'articolo davanti a un punteggio: "l'1-1", "lo 0-0", "il 2-1", "l'8-0". */
export const ilRisultato = (s: string) =>
  s.startsWith('0') ? 'lo ' : /^(1|8|11)-/.test(s) ? "l'" : 'il ';

/** "della Bundesliga", "dell'Eredivisie", "di LaLiga". */
export const della = (nome: string) =>
  haGiaArticolo(nome) ? 'di ' : vocale(nome) ? "dell'" : 'della ';
