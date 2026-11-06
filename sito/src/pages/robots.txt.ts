import type { APIRoute } from "astro";

/* robots.txt generato in build, non un file statico, perché deve restare
   coerente con lo stato del sito: se un giorno lo si richiude agli indici, non
   ha senso che il file continui a invitare i motori a entrare. */

const indicizzabile = import.meta.env.PUBLIC_NOINDEX !== "1";

/* Chi entra e chi no, e perche' questo file non e' tutta la storia.
 *
 * Il criterio e' uno solo: il crawler restituisce qualcosa? Chi legge per citare
 * il sito in una risposta porta lettori, ed e' lo stesso motivo per cui entra
 * Google. Chi raccoglie testo per addestrare un modello non rimanda nessuno.
 *
 * Questo file da solo non decide: Cloudflare aggiunge davanti al nostro il suo
 * robots.txt gestito, e in piu' blocca alcuni robot sulla rete. Verificato il 6
 * novembre 2026 sul sito vero:
 *
 *   - entrano (200): Googlebot, bingbot, OAI-SearchBot, ChatGPT-User,
 *     PerplexityBot, Claude-SearchBot, Claude-User;
 *   - restano fuori (403): GPTBot, ClaudeBot, che servono all'addestramento.
 *
 * E' esattamente il criterio qui sopra, quindi l'impostazione di Cloudflare e'
 * rimasta com'e'. Una versione precedente di questo commento diceva che GPTBot e
 * ClaudeBot erano lasciati entrare apposta: non era vero, e non serve, perche' le
 * citazioni dipendono dai robot di ricerca.
 *
 * Attenzione a una confusione frequente: `Google-Extended` e `Applebot-Extended`
 * riguardano solo addestramento e risposte generate, e non toccano `Googlebot` ne'
 * il posizionamento. Bloccare `Googlebot` farebbe sparire il sito da Google: sono
 * cose diverse.
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
