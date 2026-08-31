# Quota Vera — statistiche sportive dai dati veri

Stato al **28 agosto 2026**. Questo file tiene decisioni, stato e prossimi
passi, come il README di CondoManager. **Va aggiornato quando cambia una
decisione**, non quando cambia un'idea: quello che non è scritto qui, la
sessione dopo non esiste.

---

## 1. Cosa stiamo facendo, e cosa no

Un sito che, ogni giorno, pubblica **le statistiche delle partite in programma
su 22 campionati europei** e lascia che sia il lettore a farsi un'idea.

Non diamo consigli di gioco, e non è prudenza: **il modello non batte il
mercato**, l'abbiamo misurato su migliaia di partite vere contro la quota di
chiusura, e pubblicarne i pronostici come vincenti vorrebbe dire vendere una
cosa che non abbiamo. Quello che abbiamo è un modello **calibrato** — quando
dice 45%, succede il 45% delle volte — e per descrivere una partita serve
esattamente quello.

Le tre cose che diamo e che nessuno dà insieme:

1. **Statistiche che significano qualcosa.** La forma misurata sui tiri in
   porta e non sui risultati; chi segna più di quanto crea; i numeri di casa e
   trasferta tenuti separati.
2. **Il confronto fra mercati.** Quanto si tiene il banco, campionato per
   campionato: impossibile da costruire guardando una lega sola.
3. **Il nostro track record pubblicato**, con la calibrazione e la sconfitta
   contro il mercato scritta a chiare lettere.

### Cosa abbiamo scartato, e perché

**Surebet e valuebet.** Misurate su 13.688 partite vere: le surebet esistono e
valgono fra lo 0 e il 3 per mille, e per raccoglierle servono venti conti gioco
che vengono limitati in settimane. Il valore richiede di battere il mercato, e
non lo battiamo.

**Il pronostico come prodotto.** Stessa ragione: sarebbe l'unica cosa che non
possiamo onestamente offrire.

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
  dati/         catalogo dei campionati, lettore di football-data.co.uk
  statistiche.py  numeri di squadra: forma sui tiri, segna-vs-crea
  sports/
    football/   Dixon-Coles: due Poisson corrette sui punteggi bassi
    basketball/ margine e totale come due normali, ridge sulle forze
    tennis/     Elo per superficie, poi ricorsione dal punto al match
scripts/
  genera_sito.py     scarica, stima, scrive i JSON del sito
  track_record.py    la verifica walk-forward contro la quota di chiusura
  analisi_mercato.py quanto si tiene il banco, su partite vere
  analisi_movimento.py  il mercato impara fra apertura e chiusura?
sito/                Astro statico, 227 pagine
tests/               87 test
```

Il test che vale più di tutti è la **riprova sui parametri noti**: si inventano
delle forze vere, si simula un campionato che le rispetti, si dà al modello solo
i risultati, e si controlla che risalga ai parametri di partenza. Se un modello
non ci riesce sui dati finti, sui dati veri non ha speranza — e vale per tutti e
tre gli sport.

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
.venv\Scripts\python.exe scripts\genera_sito.py
```

Scarica lo storico e il calendario, stima un modello per campionato, calcola le
statistiche e riscrive i JSON che il sito legge. È quello che gira ogni notte.

```bash
.venv\Scripts\python.exe scripts\track_record.py
```

La verifica onesta: cammina in avanti su nove stagioni, ristima il modello ogni
giornata **usando solo il passato**, e lo confronta con la quota di chiusura.
Ci mette una decina di minuti. Gira il lunedì, non ogni notte.

Ci sono anche `analisi_mercato.py` (quanto si tiene il banco, su 13.688 partite
vere) e `analisi_movimento.py` (se il mercato impara fra apertura e chiusura:
sì, e si misura).

---

## 4. Stato

| Pezzo | Stato |
|---|---|
| Nucleo: tipi, mercato, metriche | fatto, 23 test |
| Calcio: Dixon-Coles | fatto, 13 test |
| Basket, tennis | fatti, 21 test — in attesa di una fonte dati vera |
| Lettore football-data.co.uk | fatto, 15 test |
| Statistiche di squadra | fatto, 9 test |
| **Sito su dati veri, 22 campionati** | **fatto, 227 pagine** |
| **Track record contro la chiusura** | **fatto** |
| Pipeline notturna | scritta, mai girata davvero |
| Messa in linea | **manca solo questo** — vedi `DEPLOY.md` |

### Il sito

```bash
python scripts/genera_sito.py    # scarica, stima, scrive i JSON
npm --prefix sito run dev        # http://localhost:4321
```

Astro statico, senza JavaScript nel browser. Niente Tailwind: il sistema visivo
sta in `sito/src/styles/global.css` come token CSS.

**Ventidue divisioni in undici paesi** (`engine/dati/catalogo.py`), 227 pagine:
le partite del giorno, una pagina per campionato con calendario e statistiche,
la scheda di ogni partita, gli articoli, il confronto fra mercati, come si
leggono le quote, il modello, il track record.

`scripts/genera_sito.py` è la cerniera: il motore calcola, lo script serializza,
il sito disegna. È quello che il cron notturno chiama alle 04:00.

**Le coppe non ci sono.** football-data copre solo campionati nazionali:
Champions, Europa League e coppe nazionali richiedono una fonte a pagamento.
Scritto in `catalogo.py` e sulla pagina dei campionati perché non venga
riscoperto ogni volta.

### I dati, e quanto costano

| Cosa | Da dove | Costo |
|---|---|---|
| Storico, quote di chiusura e di apertura | football-data.co.uk | gratis |
| Calendario e quote pre-partita | `fixtures.csv`, stessa fonte | gratis |
| Calendario completo di stagione | openfootball | gratis |
| **Risultati del giorno e tabellini** | **ESPN** | **gratis** |
| Coppe, quote in tempo reale | serve un'API | 20-30 €/mese |

Trent'anni di risultati, dieci di quote di chiusura, senza una chiave né un
account.

#### Perché è entrato ESPN (31 agosto 2026)

football-data pubblica i risultati **a turno concluso**, e le intestazioni HTTP
dei suoi file dicono quanto: il 31 agosto, di lunedì, i file di Serie A, Premier
e Ligue 1 erano fermi al 24 — una settimana, con un turno intero giocato in
mezzo. Il sito si rigenerava ogni notte e restava giustamente identico, il che
è il modo peggiore di funzionare: sembra rotto proprio mentre non lo è.

ESPN ha un endpoint pubblico senza chiave con i risultati entro pochi minuti dal
fischio. Copre **20 dei nostri 22 campionati** (mancano le due serie scozzesi
minori) e porta in regalo **27 statistiche per squadra** contro le 7 di
football-data: possesso, passaggi, cross, contrasti, intercetti, respinte,
parate.

Tre cose imparate, che non si indovinano:

- **Non si manda uno `User-Agent`.** Qualunque valore, anche quello di un
  browser, fa rispondere `403`. Con quello predefinito di urllib la stessa
  richiesta passa.
- **I nomi delle squadre vanno abbinati con cura.** ESPN dice «Wolverhampton
  Wanderers», football-data dice «Wolves». Togliendo gli orpelli societari si
  arriva al 99%, ma togliere «City» e «Rovers» renderebbe *Bristol City* e
  *Bristol Rovers* lo stesso nome: l'abbinamento accetta solo accoppiate
  **univoche da entrambi i lati**, e chi resta fuori viene saltato. Un
  abbinamento sbagliato non si vede — i gol finiscono nella squadra sbagliata e
  la classifica mente in silenzio.
- **`dati/espn/` sta nel repository.** È la memoria dei tabellini scaricati: la
  macchina di GitHub nasce e muore ogni notte, e senza archivio rifarebbe una
  richiesta per partita su tutta la stagione, ogni volta.

Incrociando le due fonti è saltato fuori un difetto che c'era da sempre:
`fixtures.csv` continua a elencare le partite già giocate finché non le sposta
nei risultati. Il 31 agosto **8 delle 10 partite di Serie A «in programma»
erano già finite**, e il sito ne pubblicava il risultato due sezioni più sotto.
Ora chi è nello storico esce dal calendario, e una partita con data passata non
è «in programma» comunque — regola che serve per i due campionati scozzesi che
ESPN non copre.

### Cosa ha detto la verifica sui dati veri (28 agosto 2026)

Il modello ristimato ogni giornata usando **solo il passato**, confrontato con
la quota di chiusura del Betfair Exchange (o Pinnacle dove manca), su nove
stagioni e undici campionati — **27.474 partite fuori campione**:

| | Modello | Mercato | Scarto |
|---|---|---|---|
| Brier | 0,58543 | **0,56802** | +0,01741 |
| Log-loss | 0,98594 | **0,95723** | +0,02871 |
| Errore di calibrazione | 0,01215 | 0,00993 | |

**Il mercato vince, in tutti e undici i campionati.** La regolarità del
distacco dice che non è rumore: è il risultato.

Non è un difetto da correggere. Battere la quota di chiusura è difficile per i
fondi che ci lavorano a tempo pieno; un modello sui soli gol non ci arriva. Il
modello resta però **calibrato** — errore 0,012, sotto la soglia dei 0,02 — e
per descrivere una partita serve esattamente quello. Sono due asticelle
diverse: per informare serve essere corretti, per guadagnare serve essere
*migliori*.

**È la ragione per cui il sito non dà consigli di gioco, ed è scritta sulla
pagina `/track-record/` perché chiunque possa verificarla invece di crederci.**

---

## 5. Prossimi passi, in ordine

1. **Metterlo online.** È l'unica cosa che manca e richiede i tuoi account:
   repository GitHub, Cloudflare Pages. Istruzioni in `DEPLOY.md`.
2. **Far girare la pipeline almeno una volta a mano** dalla scheda Actions
   («Run workflow»), che salta il controllo dell'orario apposta.
3. **Togliere il `noindex`** quando decidi di aprire: una variabile
   d'ambiente su Cloudflare, non una modifica al codice.
4. **Scrivere qualche approfondimento.** Il pezzo del giorno lo genera il
   programma; gli articoli che restano validi oltre la giornata no.
5. **Poi, se serve:** una fonte a pagamento per le coppe e le quote in diretta.
   Da valutare solo quando il resto è in piedi e si vede se interessa a qualcuno.

---

## 6. Riferimenti

- Dixon & Coles, *Modelling Association Football Scores and Inefficiencies in
  the Football Betting Market*, Applied Statistics 46(2), 1997
- Shin, *Measuring the Incidence of Insider Trading in a Market for
  State-Contingent Claims*, Economic Journal 103, 1993
- Barnett & Clarke, *Combining player statistics to predict outcomes of tennis
  matches*, IMA Journal of Management Mathematics 16(2), 2005
