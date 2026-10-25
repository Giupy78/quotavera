/**
 * L'immagine che compare quando qualcuno incolla un link di Quota Vera su
 * WhatsApp, Telegram, Facebook o X.
 *
 * Si lancia a mano, non a ogni costruzione del sito:
 *
 *     node scripts/immagine-sociale.mjs
 *
 * e scrive `sito/public/sociale.png` più una per ogni campionato. Il PNG
 * finisce nel repository come qualunque altro file statico. Girare questo
 * script ogni notte non avrebbe senso — l'immagine non dipende dai risultati.
 *
 * **Perché un PNG e non un SVG.** I social non seguono un `og:image` in SVG:
 * alcuni lo ignorano, altri mostrano un riquadro vuoto. Serve un raster, e le
 * misure sono quelle che si aspettano tutti: 1200×630.
 *
 * **Perché Georgia e Arial.** Il disegno è un SVG passato a sharp, che lo
 * compone con i font installati sul sistema: i font di Google non li scarica.
 * Non è un ripiego inventato qui — sono gli stessi che i token del sito
 * dichiarano subito dopo Newsreader e Archivo, quindi l'immagine cade sulla
 * seconda scelta del sito invece che su una terza estranea.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const QUI = path.dirname(fileURLToPath(import.meta.url));
const RADICE = path.join(QUI, '..');
const USCITA = path.join(RADICE, 'sito', 'public');

/* `sharp` e' gia' installato come dipendenza di Astro: non ne aggiungiamo una
   per fare un'immagine. Si risolve da dentro `sito/`, come lo risolverebbe
   Node da li', invece di indovinare il percorso del file dentro il pacchetto. */
const richiedi = createRequire(path.join(RADICE, 'sito', 'package.json'));
const sharp = richiedi('sharp');

/* I colori sono quelli della barra in testa al sito — il fondo scuro — presi
   dai token di `global.css`. Un'anteprima social sta quasi sempre dentro una
   conversazione su fondo chiaro: il riquadro scuro si stacca. */
const C = {
  fondo: '#101619',
  inchiostro: '#edeee9',
  spento: '#8e9a9e',
  riga: '#263035',
  s1: '#4a90cc',
  s2: '#b5842a',
};

const esc = (s) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/**
 * Le barrette in basso: lo stesso motivo dei grafici delle pagine squadra.
 * Non rappresentano dati veri e non devono sembrarlo — nessuna etichetta,
 * nessun numero, nessun asse: è l'ornamento che dice "qui si misura", non un
 * grafico travestito.
 */
function barrette(x, y, larghezza) {
  const quote = [0.86, 0.54, 0.97, 0.38, 0.72, 0.46, 0.63];
  const passo = larghezza / quote.length;
  const largaBarra = 26;
  return quote
    .map((q, i) => {
      const h = Math.round(q * 78);
      /* Colore e opacita' uguali per tutte. Farli variare con l'altezza
         sarebbe codificare due volte la stessa cosa, e darebbe a un ornamento
         l'aria di un grafico che si puo' leggere. */
      const colore = i % 3 === 1 ? C.s2 : C.s1;
      return `<rect x="${Math.round(x + i * passo)}" y="${y - h}" width="${largaBarra}" height="${h}" rx="3" fill="${colore}" opacity="0.9"/>`;
    })
    .join('');
}

function disegna({ occhiello, titolo, sottotitolo }) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <rect width="1200" height="630" fill="${C.fondo}"/>
  <rect x="0" y="0" width="1200" height="6" fill="${C.s1}"/>

  <text x="80" y="118" font-family="Arial, Helvetica, sans-serif" font-size="34" font-weight="700" fill="${C.inchiostro}">Quota<tspan fill="${C.spento}" dx="9">Vera</tspan></text>

  <line x1="80" y1="156" x2="1120" y2="156" stroke="${C.riga}" stroke-width="1"/>

  ${occhiello ? `<text x="80" y="208" font-family="Arial, Helvetica, sans-serif" font-size="21" font-weight="600" letter-spacing="2.6" fill="${C.s1}">${esc(occhiello.toUpperCase())}</text>` : ''}

  <text x="80" y="${occhiello ? 300 : 272}" font-family="Georgia, 'Times New Roman', serif" font-size="62" fill="${C.inchiostro}">${esc(titolo)}</text>

  <text x="80" y="${occhiello ? 366 : 338}" font-family="Arial, Helvetica, sans-serif" font-size="27" fill="${C.spento}">${esc(sottotitolo)}</text>

  ${barrette(80, 520, 420)}

  <line x1="80" y1="556" x2="1120" y2="556" stroke="${C.riga}" stroke-width="1"/>
  <text x="80" y="594" font-family="Arial, Helvetica, sans-serif" font-size="22" fill="${C.spento}">quotavera.it</text>
  <text x="1120" y="594" text-anchor="end" font-family="Arial, Helvetica, sans-serif" font-size="22" fill="${C.spento}">Nessun consiglio di gioco</text>
</svg>`;
}

async function scrivi(nome, svg) {
  const dove = path.join(USCITA, nome);
  await sharp(Buffer.from(svg)).png({ compressionLevel: 9 }).toFile(dove);
  const kb = Math.round(fs.statSync(dove).size / 1024);
  console.log(`  ${nome.padEnd(34)} ${String(kb).padStart(4)} KB`);
}

const campionati = JSON.parse(
  fs.readFileSync(path.join(RADICE, 'sito', 'src', 'dati', 'campionati.json'), 'utf8'),
);

console.log('Immagini sociali:');

await scrivi(
  'sociale.png',
  disegna({
    occhiello: null,
    titolo: 'Statistiche di 22 campionati europei',
    sottotitolo: 'Gol, tiri, cartellini, possesso. In casa e in trasferta, aggiornati ogni notte.',
  }),
);

/* Una per campionato: chi condivide una partita di Serie A non si merita la
   stessa immagine di chi condivide la pagina dell'Eredivisie. Le pagine
   partita e le pagine squadra ricadono su quella del loro campionato, che è
   abbastanza pertinente senza doverne generare quattromila. */
for (const c of campionati.campionati) {
  await scrivi(
    `sociale-${c.slug}.png`,
    disegna({
      occhiello: c.nome,
      titolo: 'Statistiche, numeri e quote',
      sottotitolo: 'Classifica, forma, casa e trasferta. Aggiornate ogni notte.',
    }),
  );
}

console.log(`\nFatte ${campionati.campionati.length + 1} immagini in sito/public/.`);
