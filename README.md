# Quota Vera — motore di pronostici sportivi

Stato al **27 agosto 2026**. Questo file tiene decisioni, stato e prossimi
passi, come il README di CondoManager. **Va aggiornato quando cambia una
decisione**, non quando cambia un'idea: quello che non è scritto qui, la
sessione dopo non esiste.

---

## 1. Cosa stiamo facendo, e cosa no

Un sito che pubblica probabilità calcolate da un modello statistico, il
confronto con le quote del mercato, e — soprattutto — **lo storico di quanto
il modello ci prende, perdite comprese**.

Non è un sito di pronostici nel senso corrente del termine. La differenza sta
in una riga sola:

> Ogni previsione viene congelata con la quota vista in quel momento, prima
> della partita, e non si tocca più.

È l'unica cosa che, fra sei mesi, distingue un track record da un racconto.
Di siti che dicono «oggi giochiamo questa» ce ne sono migliaia; di siti che
pubblicano la propria curva di calibrazione, nessuno.

### Decisioni prese il 27 agosto 2026

| Domanda | Decisione |
|---|---|
| A chi si vende | **A nessuno, per ora.** Progetto personale e vetrina tecnica. La monetizzazione si decide fra sei mesi, con i numeri in mano |
| Quali sport | **Calcio, basket e tennis.** Multi-sport dall'architettura, non come aggiunta successiva |
| Priorità | Alta: viene prima di CondoManager |
| Nome | *Quota Vera* è provvisorio. Il dominio non è registrato |

### Il nodo legale, da riprendere prima di monetizzare

Il decreto dignità vieta la pubblicità di giochi con vincita in denaro.
Finché il sito è gratuito, senza link a bookmaker e senza banner, il problema
non si pone. **Si ripone il giorno in cui si incassa qualcosa**, e le tre vie
praticabili (abbonamento analitico, mercato estero in inglese, vendita dati
B2B) cambiano il sito, non solo il listino. Prima del primo euro: mezz'ora con
un avvocato che si occupi di gioco e pubblicità.

---

## 2. Com'è fatto

Un nucleo che non sa nulla di sport, e uno sport per cartella. Tutti i modelli
espongono `fit(incontri)` e `predict(fixture)`, e restituiscono lo stesso
oggetto `Prediction`: una mappa `mercato -> {esito: probabilità}`. Il sito non
deve sapere di che sport sta parlando.

```
engine/
  core/         tipi, mercato (quote <-> probabilità), metriche
  sports/
    football/   Dixon-Coles: due Poisson corrette sui punteggi bassi
    basketball/ margine e totale come due normali, ridge sulle forze
    tennis/     Elo per superficie, poi ricorsione dal punto al match
scripts/
  dimostrazione.py   il giro completo su dati simulati
tests/               57 test, inclusa la riprova sui parametri noti
```

Il test che vale più di tutti gli altri è la **riprova sui parametri noti**: si
inventano delle forze vere, si simula un campionato che le rispetti, si dà al
modello solo i risultati, e si controlla che riesca a risalire ai parametri di
partenza. Se un modello non ci riesce sui dati finti, sui dati veri non ha
speranza — e questo è vero per tutti e tre gli sport.

### Perché tre modelli diversi e non uno

Non è pigrizia architetturale: i tre sport hanno strutture statistiche
incompatibili.

- **Calcio**: pochi gol, quindi il risultato esatto conta e la distribuzione
  va tenuta intera. Da una sola matrice escono 1X2, over/under e gol/gol, e
  restano coerenti fra loro per costruzione.
- **Basket**: cento possessi per parte, quindi il margine è normale e la
  matrice non serve a nessuno. Servono invece due modelli separati — forza e
  ritmo — perché rispondono a domande diverse e hanno rumore diverso.
- **Tennis**: il punteggio non è lineare, si può vincere meno punti e vincere
  il match. Bisogna scendere al singolo punto e risalire per ricorsione.

Quello che condividono è tutto il resto: togliere il margine dalle quote,
misurare il valore, dimensionare la puntata, giudicare la calibrazione.

### Le scelte che vale la pena conoscere

**Il margine si toglie con Shin, non dividendo per la somma.** Il margine non
è distribuito uniformemente: sugli esiti improbabili è molto più alto. Toglierlo
male è il modo più comune di convincersi di avere un vantaggio che non c'è.

**Kelly è frazionario e con un tetto.** Kelly pieno è ottimo solo se le
probabilità sono giuste; le nostre sono stimate. Un quarto di Kelly, massimo
il 5% del bankroll.

**Il closing line value conta più del rendimento.** È l'unica misura di
bravura che non dipende da come è finita la partita.

**Le soglie di valore sono tarate sull'errore del modello.** Con tre stagioni
di soli gol l'incertezza su ogni probabilità è di 3-4 punti: chiedere uno
scarto di 3 punti significa giocare il proprio rumore. È il motivo per cui una
soglia bassa fa «trovare valore» nel 90% delle partite — l'errore che rende
inutili quasi tutti i siti del genere.

---

## 3. Come si usa

```bash
.venv\Scripts\python.exe -m pytest -q
```

```bash
.venv\Scripts\python.exe scripts\dimostrazione.py
```

La dimostrazione simula tre stagioni, ne tiene una da parte, fa camminare il
modello in avanti nel tempo ristimando solo su quello che avrebbe potuto
sapere, e stampa calibrazione, confronto col mercato e rendimento con il suo
intervallo di confidenza.

### Cosa dice, e cosa non dice

Sui dati simulati la catena regge: il modello ritrova i parametri da cui la
stagione è stata generata, è calibrato, e trova valore in circa il 20% delle
partite. **Ma i gol lì sono generati esattamente dal modello che poi li stima**:
il modello gioca in casa. Il calcio vero non è Dixon-Coles e il banco vero è più
preciso di quello simulato. Serve a verificare che la catena regga, non a
promettere un rendimento.

---

## 4. Stato

| Pezzo | Stato |
|---|---|
| Nucleo: tipi, mercato, metriche | fatto, 23 test |
| Calcio: Dixon-Coles | fatto, 13 test, riprova sui parametri noti superata |
| Basket: margine e totale | fatto, 8 test |
| Tennis: Elo e ricorsione | fatto, 13 test |
| Backtest walk-forward | fatto, su dati simulati |
| Sito (Astro, 12 pagine) | fatto, gira in locale su dati simulati |
| **Dati veri** | **da fare — è il prossimo passo** |
| Archivio dei pronostici congelati | da fare |
| Aggiornamento automatico | da fare |
| Messa in linea su Cloudflare | da fare |

### Il sito

```bash
python scripts/genera_sito.py    # il motore scrive i JSON
npm --prefix sito run dev        # http://localhost:4321
```

Astro statico, senza JavaScript nel browser: i grafici sono SVG generati in
build. Niente Tailwind — il sistema visivo sta in `sito/src/styles/global.css`
come token CSS, ed è lo stesso del mockup approvato.

**Otto campionati europei** (`scripts/campionati.py`), 80 pagine generate:
l'indice dei campionati, una **giornata** per campionato, il **dettaglio
partita**, il **confronto fra mercati**, **come si leggono le quote**, il
**track record**, **il modello**, più basket e tennis. La cerniera fra le due
metà è `scripts/genera_sito.py`: il motore calcola, lo script serializza, il
sito disegna. In produzione lo chiamerà il cron notturno con i dati veri, e la
forma dei file non cambia.

I parametri per campionato in `campionati.py` (reti a partita, fattore campo,
margine del banco, dispersione delle forze) sono oggi **input** della
simulazione. Sui dati veri diventano **output** del modello: è quella la
sostituzione da fare, non una riscrittura.

### Il posizionamento, deciso il 28 agosto 2026

Non «troviamo le occasioni che gli altri non trovano» — la verifica dice che il
modello non batte il mercato, e promettere il contrario sarebbe la cosa che
questo progetto esiste per non fare. Le tre cose che diamo e che nessuno dà
insieme: **spiegare i numeri** (`/quote/`), **confrontare i mercati fra
campionati** (`/mercati/` — impossibile da costruire guardando una lega sola), e
**pubblicare il nostro track record con la calibrazione**, giornate vuote
comprese.

### Cosa ha detto il primo giro completo (28 agosto 2026)

Su 910 partite fuori campione, con il banco simulato che parte dalle
probabilità vere più un 3% di rumore:

- **il modello non batte il mercato**: Brier 0,580 contro 0,578. Sono
  indistinguibili
- **è calibrato**: errore 0,017, sotto la soglia dei 0,02
- **zero giocate di valore**, perché alla pari col mercato non ce ne sono

Non è un difetto da correggere alzando il rumore del banco finché il modello
vince: è il risultato, e il sito è disegnato perché lo stato normale sia
«nessuna occasione». Le divergenze sotto soglia si mostrano lo stesso, in
grigio, così le giornate vuote non sembrano nascondere qualcosa.

---

## 5. Prossimi passi, in ordine

1. **Collegare i dati veri.** `football-data.org` ha un piano gratuito che
   copre Serie A e i maggiori campionati europei. Serve un lettore che porti i
   risultati nel tipo `Incontro`, e nient'altro.
2. **Rifare la dimostrazione su dati veri.** È il momento della verità: qui il
   modello smette di giocare in casa. Il risultato atteso è che *non* batta il
   mercato — e va scritto lo stesso.
3. **L'archivio dei pronostici.** Un file per giornata, con quota e ora, mai
   più modificato. Va fatto prima del sito, perché il sito senza storico non
   ha niente da dire.
4. **L'aggiornamento automatico.** GitHub Actions con un cron notturno che
   ristima e scrive JSON.
5. **Il sito.** Astro su Cloudflare, come il sito di Isabella Caputo. Pagine
   statiche, isole solo per i grafici. Il mockup grafico esiste già ed è il
   riferimento visivo.

---

## 6. Riferimenti

- Dixon & Coles, *Modelling Association Football Scores and Inefficiencies in
  the Football Betting Market*, Applied Statistics 46(2), 1997
- Shin, *Measuring the Incidence of Insider Trading in a Market for
  State-Contingent Claims*, Economic Journal 103, 1993
- Barnett & Clarke, *Combining player statistics to predict outcomes of tennis
  matches*, IMA Journal of Management Mathematics 16(2), 2005
