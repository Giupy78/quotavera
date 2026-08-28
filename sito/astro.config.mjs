// @ts-check
import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";

// Statico: ogni pagina e' HTML generato in build, nessun server a runtime.
// E' la scelta che rende il sito gratis da tenere su Cloudflare Pages e che
// permette di rigenerarlo dal cron notturno senza toccare infrastruttura.
export default defineConfig({
  site: "https://quotavera.it",
  output: "static",
  devToolbar: { enabled: false },
  integrations: [
    sitemap({
      // Le pagine partita cambiano a ogni aggiornamento del calendario, le
      // pagine di spiegazione quasi mai. Dirlo ai motori evita che sprechino
      // la scansione dove non serve.
      serialize(pagina) {
        if (pagina.url.includes("/calcio/") && pagina.url.split("/").length > 6) {
          return { ...pagina, changefreq: "daily", priority: 0.6 };
        }
        if (pagina.url.includes("/calcio/") || pagina.url.includes("/blog/")) {
          return { ...pagina, changefreq: "daily", priority: 0.8 };
        }
        return { ...pagina, changefreq: "weekly", priority: 0.7 };
      },
    }),
  ],
});
