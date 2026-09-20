/**
 * `lastmod` per la sitemap: quando i dati di quella pagina sono cambiati.
 *
 * Qui la tentazione è forte: il sito si rigenera ogni notte dal cron, quindi
 * mettere la data di build su tutti gli URL sembrerebbe quasi sincero. Non lo
 * è per le pagine di spiegazione — `/modello/`, `/cosa-facciamo/`, `/quote/`
 * raccontano come funziona il modello e restano identiche per settimane. Se
 * dichiarassero di cambiare ogni mattina, Google smetterebbe di fidarsi del
 * `lastmod` di tutto il sito, comprese le pagine partita dove invece la data
 * serve davvero.
 *
 * Quindi: la data ce l'hanno le pagine che dipendono dai dati sportivi, e la
 * prendono dal timestamp che scrive il generatore. Le altre restano senza.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import campionati from '../dati/campionati.json';
import articoli from '../dati/articoli.json';
import trackRecord from '../dati/track-record.json';
import calendario from '../dati/calendario.json';

/** Quando il cron ha rigenerato i dati. È il nostro "ultimo aggiornamento". */
const GENERATO = (campionati as { generato_il?: string }).generato_il;
const ARTICOLI = (articoli as { data?: string }).data;
const TRACK = (trackRecord as { generato_il?: string }).generato_il;

const SLUG_CAMPIONATI = Object.keys(
  (calendario as { campionati?: Record<string, unknown> }).campionati ?? {},
);

/**
 * Le vie del blog non sono i campionati: `articoli.pezzi` contiene anche i
 * pezzi evergreen, che hanno uno slug tutto loro. Le rotte le genera quello,
 * quindi la mappa deve seguire lui.
 */
const SLUG_BLOG = ((articoli as { pezzi?: Array<{ slug?: string }> }).pezzi ?? [])
  .map((p) => p.slug)
  .filter((slug): slug is string => Boolean(slug));

/**
 * Gli articoli evergreen sono pagine markdown in src/pages/blog: non passano
 * dai dati del cron, hanno una data di scrittura nel frontmatter e quella
 * resta valida finché non li riscriviamo. Sono esattamente il caso in cui una
 * data di build mentirebbe.
 */
function articoliScritti(): Array<[string, string]> {
  const cartella = fileURLToPath(new URL('../pages/blog', import.meta.url));
  if (!fs.existsSync(cartella)) return [];

  return fs
    .readdirSync(cartella)
    .filter((nome) => nome.endsWith('.md'))
    .flatMap((nome) => {
      const testo = fs.readFileSync(path.join(cartella, nome), 'utf8');
      const data = testo.match(/^data:[ 	]*(\d{4}-\d{2}-\d{2})/m)?.[1];
      return data ? [[`/blog/${nome.slice(0, -3)}/`, data] as [string, string]] : [];
    });
}

/**
 * Mappa via -> data. Le vie hanno la barra finale, come le scrive Astro.
 * Le pagine assenti dalla mappa finiscono in sitemap senza `lastmod`, ed è
 * voluto: vedi il commento in testa al file.
 */
export function mappaLastmod(): Map<string, string> {
  const mappa = new Map<string, string>();
  const segna = (via: string, quando: string | undefined) => {
    if (quando) mappa.set(via, quando);
  };

  // La home mostra il pezzo del giorno e le partite in arrivo.
  segna('/', GENERATO);
  segna('/campionati/', GENERATO);
  segna('/mercati/', GENERATO);
  segna('/track-record/', TRACK);

  // Il blog esce con i dati del giorno.
  segna('/blog/', ARTICOLI);
  segna('/blog/giornata/', ARTICOLI);
  for (const slug of SLUG_BLOG) {
    segna(`/blog/${slug}/`, ARTICOLI);
  }

  // Pagine campionato e pagine partita: quote e probabilità si muovono ogni
  // notte, qui la data di generazione è la data vera.
  for (const slug of SLUG_CAMPIONATI) {
    segna(`/calcio/${slug}/`, GENERATO);
    const partite =
      ((calendario as { campionati: Record<string, Array<{ id?: string }>> }).campionati[slug] ?? []);
    for (const partita of partite) {
      if (partita.id) segna(`/calcio/${slug}/${partita.id}/`, GENERATO);
    }
  }

  for (const [via, quando] of articoliScritti()) {
    segna(via, quando);
  }

  return mappa;
}
