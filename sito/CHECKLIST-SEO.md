# Checklist SEO — Quota Vera

Le pagine di Quota Vera le genera il cron, non una persona: la SEO qui si fa
sul codice e sui dati, non rileggendo i testi.

---

## Quello che il sito fa già da solo

- `title` e `meta description` su ogni pagina
- URL canonico
- `sitemap.xml` con **`lastmod` reale** (vedi `src/lib/lastmod.ts`): le pagine
  partita prendono il timestamp del cron, le pagine di spiegazione restano
  senza data perché non cambiano
- `robots.txt` aperto agli assistenti AI e chiuso agli scraper puri
  (vedi `src/pages/robots.txt.ts`)

## Quello che manca, in ordine di importanza

- [ ] **`og:image`** — oggi non c'è. Quando qualcuno incolla un link di Quota
      Vera su WhatsApp o Telegram, l'anteprima esce senza immagine. Per un
      sito di pronostici, che si condivide prima della partita nelle chat fra
      amici, è la lacuna che costa di più: un'anteprima muta viene cliccata
      molto meno. È anche la più facile da chiudere, perché l'immagine si può
      generare dai dati della partita.
- [ ] **Dati strutturati JSON-LD** — assenti. Per le pagine partita il tipo
      `SportsEvent` dice a Google squadre, data e competizione in modo
      esplicito, invece di farglieli indovinare.
- [ ] **Feed RSS** — assente. Meno urgente degli altri due, ma per il blog
      quotidiano è il modo più semplice di farsi seguire senza social.

## Da controllare quando tocchi il codice

- [ ] **Ogni pagina ha un solo `<h1>`.**
- [ ] **Le pagine partita restano indicizzabili anche dopo la partita**, oppure
      spariscono con un 301: quello che non va bene è lasciarle vive e vuote.
- [ ] **Il `lastmod` resta onesto.** Se aggiungi pagine nuove, aggiungile anche
      a `mappaLastmod()`, o resteranno senza data. Meglio senza data che con
      una data falsa: vedi il commento in testa al file.

## Una volta sola, per dominio

- [x] **Google Search Console** — `sitemap-index.xml` inviato.
- [ ] **Bing Webmaster Tools** — importa le proprietà da Search Console, non
      serve rifare la verifica.
- [ ] **Cloudflare Web Analytics** — prendi il token dal pannello Cloudflare e
      impostalo come `PUBLIC_CF_BEACON_TOKEN` fra le variabili del progetto.
      Vedi `src/components/Analitiche.astro`. Non attivare *anche*
      l'inserimento automatico dal pannello: conterebbe ogni visita due volte.

## Le tre cose che contano davvero

1. **Avere numeri che altrove non ci sono.** Il track record pubblico e la
   calibrazione sono l'unica cosa che un sito di pronostici può offrire e che i
   cento cloni non hanno.
2. **Pubblicare con regolarità.** Il cron lo fa già: il tuo lavoro è accorgerti
   se un giorno si ferma in silenzio.
3. **Farsi citare da altri.** I link in entrata restano il segnale più forte, e
   non si comprano.
