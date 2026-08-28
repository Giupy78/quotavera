// @ts-check
import { defineConfig } from "astro/config";

// Statico: ogni pagina e' HTML generato in build, nessun server a runtime.
// E' la scelta che rende il sito gratis da tenere su Cloudflare Pages e che
// permette di rigenerarlo dal cron notturno senza toccare infrastruttura.
export default defineConfig({
  site: "https://quotavera.it",
  output: "static",
  devToolbar: { enabled: false },
});
