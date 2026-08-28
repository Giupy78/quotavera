import type { APIRoute } from "astro";

/* robots.txt generato in build, non un file statico, perché deve restare
   coerente con lo stato del sito: se un giorno lo si richiude agli indici, non
   ha senso che il file continui a invitare i motori a entrare. */

const indicizzabile = import.meta.env.PUBLIC_NOINDEX !== "1";

/* I crawler che raccolgono testo per addestrare modelli.
 *
 * Due note che valgono più della lista:
 *
 * 1. `Google-Extended` e `Applebot-Extended` bloccano SOLO l'uso per
 *    l'addestramento. Non toccano `Googlebot` né `Applebot`, quindi il
 *    posizionamento nella ricerca resta intatto. Bloccare `Googlebot` invece
 *    farebbe sparire il sito da Google: sono due cose diverse e vengono
 *    confuse spesso.
 *
 * 2. `OAI-SearchBot` e `PerplexityBot` servono a *citare* il sito nelle
 *    risposte, non ad addestrare. Sono lasciati liberi apposta: per un sito
 *    che deve farsi trovare, essere citato è traffico, non un furto.
 */
const ADDESTRAMENTO = [
  "GPTBot",              // OpenAI, addestramento
  "ClaudeBot",           // Anthropic
  "anthropic-ai",
  "Claude-Web",
  "Google-Extended",     // Gemini: NON influisce sulla ricerca Google
  "Applebot-Extended",   // Apple Intelligence: NON influisce su Siri/Spotlight
  "CCBot",               // Common Crawl, la base di mezzo settore
  "Bytespider",          // ByteDance
  "meta-externalagent",  // Meta
  "FacebookBot",
  "Amazonbot",
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
    "",
    "# --- Raccolta per addestrare modelli linguistici: non consentita ---",
    "",
  ];

  for (const bot of ADDESTRAMENTO) {
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
