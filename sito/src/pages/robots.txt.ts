import type { APIRoute } from "astro";

/* robots.txt generato in build, non un file statico, perché deve restare
   coerente con lo stato del sito: se un giorno lo si richiude agli indici, non
   ha senso che il file continui a invitare i motori a entrare. */

const indicizzabile = import.meta.env.PUBLIC_NOINDEX !== "1";

/* Gli assistenti AI sono lasciati entrare apposta.
 *
 * Il criterio è uno solo: il crawler restituisce qualcosa? Chi indicizza per
 * citare il sito nelle risposte porta lettori, ed è lo stesso motivo per cui
 * lasciamo entrare Google. Chi aspira testo e non rimanda nessuno indietro
 * resta fuori: è la lista qui sotto.
 *
 * Due note che valgono più della lista:
 *
 * 1. `Google-Extended` e `Applebot-Extended` riguardano SOLO l'uso per
 *    l'addestramento e per le risposte generate. Non toccano `Googlebot` né
 *    `Applebot`, quindi il posizionamento nella ricerca non c'entra in nessuno
 *    dei due sensi: aprirli non aiuta il ranking, chiuderli non lo danneggia.
 *    Bloccare `Googlebot` invece farebbe sparire il sito da Google: sono cose
 *    diverse e vengono confuse spesso.
 *
 * 2. `OAI-SearchBot` e `PerplexityBot` non sono mai stati bloccati: servono a
 *    citare, non ad addestrare. `ClaudeBot` e `GPTBot` invece lo erano, e
 *    alimentano anche gli indici da cui quegli assistenti pescano le fonti.
 *    Per un sito di pronostici, dove la domanda arriva sempre più spesso a un
 *    assistente invece che a un motore, restare fuori da quegli indici costa
 *    più di quanto protegga.
 */
const SCRAPING = [
  "CCBot",               // Common Crawl: archivio, non manda lettori
  "Bytespider",          // ByteDance
  "cohere-ai",
  "Diffbot",
  "Omgilibot",
  "omgili",
  "img2dataset",
  "Timpibot",
  "Kangaroo Bot",
  "PanguBot",
  "Webzio-Extended",
  "AI2Bot",
  "Scrapy",
];

export const GET: APIRoute = ({ site }) => {
  const righe: string[] = [
    "# Quota Vera - statistiche sportive",
    "#",
    "# I dati di questo sito vengono da football-data.co.uk e sono pubblici.",
    "# Le elaborazioni, i testi e il codice sono nostri.",
    "#",
    "# Gli assistenti AI possono leggere e citare il sito: se portano lettori,",
    "# sono benvenuti come qualsiasi altro motore di ricerca.",
    "",
    "# --- Raccolta massiva senza ritorno: non consentita ---",
    "",
  ];

  for (const bot of SCRAPING) {
    righe.push(`User-agent: ${bot}`, "Disallow: /", "");
  }

  righe.push(
    "# --- Tutti gli altri ---",
    "",
    "User-agent: *",
    indicizzabile ? "Allow: /" : "Disallow: /",
    ""
  );

  if (indicizzabile && site) {
    righe.push(`Sitemap: ${new URL("sitemap-index.xml", site).href}`, "");
  } else if (!indicizzabile) {
    righe.push(
      "# Il sito e' temporaneamente chiuso agli indici (PUBLIC_NOINDEX=1).",
      ""
    );
  }

  return new Response(righe.join("\n"), {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
};
