import type { APIRoute } from "astro";
import { execSync } from "node:child_process";

/* Il commit da cui è stato compilato il sito che si sta guardando.

   Serve alla sentinella (`scripts/controlla.py`) per una domanda che nessun
   altro controllo faceva: quello che è online è davvero l'ultimo commit? Il 9
   novembre 2026 non lo era. Un push con nove rinvii nuovi non ha mai avuto la
   sua build su Cloudflare, e per mezz'ora quei nove indirizzi hanno continuato
   a rispondere 404 mentre il repository diceva che erano a posto.

   Il valore lo dà Cloudflare durante la build: `CF_PAGES_COMMIT_SHA` su Pages,
   `WORKERS_CI_COMMIT_SHA` se un giorno il sito passasse a Workers (vedi
   `wrangler.jsonc`). Altrove — in locale, o nella compilazione di prova del
   turno notturno — si chiede a git. Non è nella sitemap: è un file per noi,
   non per i lettori. */
function commit(): string {
  const daCloudflare =
    process.env.CF_PAGES_COMMIT_SHA || process.env.WORKERS_CI_COMMIT_SHA;
  if (daCloudflare) return daCloudflare.trim();
  try {
    return execSync("git rev-parse HEAD", {
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return "sconosciuto";
  }
}

export const GET: APIRoute = () =>
  new Response(`${commit()}\n`, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
