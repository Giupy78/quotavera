# Mettere online Quota Vera

Stato: **il repository è pronto e committato in locale.** Quello che resta
richiede i tuoi account, e nessuno può farlo al posto tuo.

---

## Chi aggiorna il sito ogni notte

**Non io.** Questa è la cosa da chiarire subito, perché cambia come è fatto
tutto il resto.

Io esisto dentro una sessione: quando la chiudi non c'è nessun processo mio che
resta acceso ad aspettare le due di notte. Un aggiornamento che dipendesse
da me sarebbe un aggiornamento che non avviene.

Ad aggiornarlo è **GitHub Actions**, con il lavoro già scritto in
`.github/workflows/aggiorna.yml`. È anche la soluzione giusta nel merito, non
un ripiego: rigenerare i dati è una catena deterministica — scarica, stima,
scrivi, compila — e una catena deterministica va eseguita da un cron, non da un
modello linguistico che potrebbe interpretarla diversamente ogni notte. È
gratis sui repository pubblici, lascia un log di ogni esecuzione, e se una
notte fallisce te lo scrive per email.

### Cosa fa, ogni notte alle 04:00 italiane

1. controlla che a Roma siano davvero le 4 (Actions ragiona solo in UTC, e
   l'ora legale sposta tutto di un'ora: per questo parte alle 02:00 e alle
   03:00 UTC e si ferma da solo quando non è l'ora giusta)
2. fa girare i 57 test del motore — **se il motore è rotto, si ferma qui**:
   meglio un sito fermo a ieri che un sito aggiornato con numeri sbagliati
3. rigenera i JSON con `scripts/genera_sito.py`
4. compila il sito, per non mandare in produzione un commit che rompe il deploy
5. committa i dati nuovi e fa push

Il punto 5 non è pulizia: **è l'archivio**. Ogni notte resta agli atti, in un
commit non più modificabile, cosa sapeva il modello e quali quote vedeva. È
l'unica cosa che fra sei mesi permetterà di dimostrare un track record invece
che raccontarlo — e per questo `sito/src/dati/` non è in `.gitignore`.

### Due cose da sapere sulle pianificazioni di GitHub

- **Non sono puntuali.** Un lavoro pianificato parte quando c'è capacità:
  ritardi di 5-15 minuti sono normali, e nelle ore di punta può essere di più.
  Alle 4 di notte non è un problema, ma non aspettarti il secondo esatto.
- **Si disattivano da sole** dopo 60 giorni senza attività sul repository.
  Siccome il lavoro stesso fa un commit ogni notte, il repository resta attivo
  e il problema non si pone — ma se un giorno smettessi di generare dati, dopo
  due mesi il cron si spegne in silenzio.

---

## I passaggi che devi fare tu

### 1. Crea il repository su GitHub

Vuoto, senza README (ce l'abbiamo già). Poi, da questa cartella:

```bash
git remote add origin https://github.com/TUO-UTENTE/quotavera.git
```

```bash
git push -u origin main
```

**Pubblico o privato?** Consiglio **pubblico**, e non per risparmiare: il
posizionamento del sito è la trasparenza, e un motore che chiunque può leggere
e rifare è l'argomento più forte che abbiamo. Actions è gratis illimitato sui
repository pubblici, a consumo su quelli privati.

### 2. Collega Cloudflare Pages

Nel pannello Cloudflare, **Workers & Pages → Create → Pages → Connect to Git**,
scegli il repository. Poi imposta:

| Campo | Valore |
|---|---|
| Framework preset | Astro |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Root directory | `sito` |

È lo stesso meccanismo del sito di Isabella Caputo: Pages ricompila da solo a
ogni push, quindi il commit notturno di Actions fa partire il deploy senza che
serva nessun token Cloudflare da nessuna parte. Una cosa in meno da custodire.

### 3. Lascialo non indicizzato, per ora

**Non fare niente**: è già così. Finché i dati sono simulati il sito manda
`noindex, nofollow` ai motori di ricerca.

Il giorno in cui ci saranno i dati veri, si apre aggiungendo una variabile
d'ambiente in Cloudflare Pages — `PUBLIC_INDICIZZA` = `1` — e rilanciando il
deploy. Nessuna modifica al codice.

Se lo vuoi proprio chiuso anche a chi ha il link, in Cloudflare **Zero Trust →
Access** puoi mettere il progetto dietro a un accesso con email. Gratis fino a
50 utenti.

### 4. Il dominio

`quotavera.it` **non è registrato**, e il nome resta provvisorio. Finché non
decidi, Pages ti dà un indirizzo `nome-progetto.pages.dev` che funziona
benissimo. Prima di comprare un dominio conviene aver deciso se il nome resta
questo — è una spesa piccola ma è anche l'unica di tutto il progetto.

---

## Cosa manca prima di aprire al pubblico

Nell'ordine, e il primo vale più degli altri tre messi insieme.

1. **I dati veri.** Oggi le partite sono inventate su squadre reali. È la
   ragione per cui il sito nasce non indicizzato, ed è il prossimo lavoro:
   collegare `football-data.org` e far diventare `campionati.py` un output del
   modello invece che un input.
2. **Le quote vere.** Servono per il valore e, soprattutto, per la quota di
   chiusura — l'unica misura di bravura che non dipende dagli esiti.
3. **Una pagina che spieghi cosa è questo sito**, in prima persona, con la
   frase che dice che non si vendono pronostici.
4. **Rileggere il punto AGCOM** con i contenuti definitivi davanti: la
   comparazione di quote è esclusa dal divieto, ma il perimetro va verificato
   sul sito vero, non su questo.
