# App Lotto

Un sito che applica sei metodi storici del Lotto alle estrazioni ufficiali, dice
quali previsioni sono ancora in gioco, e — soprattutto — dice quanto costano e
quanto rendono davvero.

Non c'è nessun server. Il sito è una pagina statica su GitHub Pages; ogni sera
un'azione di GitHub scarica l'estrazione, ricalcola tutto e riscrive i file che
la pagina legge. Si apre da qualunque telefono, non ha bisogno di manutenzione,
e continua a funzionare anche a computer spento.

**Il sito:** `https://<tuo-utente>.github.io/<nome-repo>/`

## La cosa da sapere prima di tutto il resto

Nessuno di questi metodi prevede l'estrazione. Il backtest su vent'anni di
archivio reale — 23.853 rilevamenti — dice che ogni euro giocato ne restituisce
in media **meno di settanta centesimi**, con i singoli metodi fra il 62% e il
74%. Non è un difetto di questo o quel metodo: è il margine del banco, ed è lo
stesso qualunque numero si giochi. I metodi scelgono *quali* numeri giocare, non
*quanto paga* il gioco.

Questa app esiste per rendere quel fatto visibile invece di nasconderlo. La
scheda **Bilancio** mostra speso, incassato e saldo reali; la scheda
**Schedina** mette la probabilità accanto a ogni vincita possibile, perché
"potresti vincere 575 €" da solo è pubblicità, mentre "575 €, una volta su
400,5" è un'informazione.

## Com'è fatto

```
motore/          Python, solo libreria standard. Nessuna dipendenza.
  lotto.py         i sei metodi. Puro: dizionari in ingresso, previsioni in uscita
  archivio.py      l'archivio delle estrazioni, letto da CSV
  fonte.py         scarica dal sito ufficiale (calendario + quadri estrattivi)
  rilevamento.py   esegue i metodi su un concorso
  valutazione.py   porta avanti le sorti aperte e registra gli esiti
  economia.py      speso, incassato, saldo, con le quote ufficiali
  pubblica.py      scrive i JSON che legge la pagina
  aggiorna.py      il ciclo completo: unico punto d'ingresso

archivio/        lo stato, versionato insieme al codice
  estrazioni.csv     76.000 estrazioni dal 1939, in ordine di estrazione
  previsioni.jsonl   ogni previsione rilevata, con le sue sorti e i suoi esiti
  quote.json         quote ufficiali e ritenuta: una sola fonte per tutti
  backtest.json      il riferimento ventennale, calcolato una volta

docs/            il sito (è la cartella che GitHub Pages pubblica)
  index.html  stile.css  app.js
  schedina.js      il simulatore: poste, vincite, probabilità
  consiglio.js     che cosa giocare stasera con un certo budget
  dati/*.json      generati dal motore, non si scrivono a mano

prove/           test_motore.py  test_pipeline.py
                 test_schedina.mjs  test_consiglio.mjs
fascicoli/       le scansioni dei fascicoli originali — NON versionate
```

### Perché lo stato sta in file di testo

Un database sarebbe stato il posto naturale, e per un po' c'è stato
(PostgreSQL, FastAPI, Docker: si ritrova nella storia di git). Ma per un'app che
serve una persona sola e viene aggiornata una volta al giorno, un database è
soprattutto una cosa che deve restare accesa. Un CSV e un JSONL versionati
accanto al codice hanno tre proprietà che qui contano di più: si leggono senza
installare niente, ogni modifica compare in un diff leggibile, e la cronologia
di git diventa gratis la cronologia dei dati.

Perché JSONL e non un unico JSON: con un array solo, ogni aggiornamento
riscriverebbe l'intero file e il diff sarebbe illeggibile. Una riga per
previsione fa comparire nel diff esattamente ciò che è cambiato — la previsione
nuova, o la sorte passata da aperta a vinta. Chiavi ordinate e righe ordinate,
così due esecuzioni sugli stessi dati producono lo stesso file byte per byte e
git non registra modifiche fantasma.

### Le tre proprietà che i test difendono

- **Determinismo** — gli stessi dati producono le stesse previsioni, con le
  stesse chiavi. Ogni previsione è identificata da un'impronta di metodo,
  giorno, ruote e numeri: senza, ricostruire lo storico creerebbe doppioni e il
  bilancio conterebbe due volte le stesse giocate.
- **Idempotenza** — rilanciare l'aggiornamento non conta due volte lo stesso
  colpo. È ciò che permette al processo serale di essere ripetuto senza paura,
  ed è il motivo per cui il recupero del mattino dopo è sicuro.
- **Stabilità su file** — due esecuzioni sugli stessi dati scrivono file
  identici, altrimenti ogni sera ci sarebbe un commit anche quando non è
  successo niente.

### Il controllo che non va tolto

L'archivio viene misurato a ogni avvio: quale **quota di quadri ha i cinque
numeri già in ordine crescente**. Se i numeri fossero in ordine di estrazione ci
si aspetta 1 su 120, cioè lo 0,83%; una quota molto più alta è la firma di un
archivio riordinato per valore. Succede spesso, negli archivi in circolazione, e
sarebbe un disastro silenzioso: quattro metodi su sei filtrano per *posizione di
estrazione*, e su un archivio riordinato continuerebbero a girare misurando
qualcos'altro senza che nulla lo segnali. Sull'archivio attuale: 0,83% esatto.

## I sei metodi

Vengono da fascicoli pubblicati fra gli anni Ottanta e Duemila. Le scansioni
originali restano fuori dal repository: qui c'è solo la descrizione algoritmica
di cosa ciascuno cerca.

| Metodo | Cosa cerca | Colpi |
|---|---|---|
| Lotto Facile — Il Metodo Vincente | coppie in posizione isotopa su due ruote | 9 |
| Lotto Facile 4 — Ciclo-Pondometria | somme e complementi fra due ruote, per posizione | 14 |
| Lotto Facile 5 — Rita Calone | numeri con ritardo alto assenti dai sei concorsi recenti | 12 |
| Fulmine — Osvaldo Manara | figure e cadenze ripetute su ruote contigue | 12 |
| Un Solo Ambo Secco | una configurazione verticale molto rara: scatta pochissime volte l'anno | 9 |
| Ambo Secco Caotico — Antonio Longo | un numero ripetuto su due ruote più il suo complemento a 90 su una terza | 2 |

Le selettività sono molto diverse — il primo scatta più di mille volte l'anno,
"Un Solo Ambo Secco" una manciata — e per questo la scheda **In corso** non
ordina per data ma **per rarità del metodo**, con accanto scritto quanto spesso
capita. Ordinare per data significherebbe seppellire il metodo raro sotto quello
prolifico, dando l'impressione che valgano uguale.

## Le cinque schede

**Schedina** — che cosa giocare al prossimo concorso. In cima il concorso in
arrivo con quanto manca; si scrive quanto si vuole spendere e la pagina compone
una giocata concreta, con costo, probabilità di vincere qualcosa e ritorno
atteso.

*Perché non consiglia dei numeri, e non è una reticenza.* In un'app di scommesse
sportive il consiglio ha senso perché le quote si muovono e possono sbagliare:
si cerca lo scarto fra il prezzo del bookmaker e il rischio vero. Nel Lotto non
esiste niente del genere — le quote sono fissate per legge, la probabilità è la
stessa per qualunque combinazione, e **a parità di sorte il ritorno atteso di
ogni giocata possibile è identico**. Una pagina che ordinasse i numeri dal
"migliore" al "peggiore" inventerebbe una classifica che non esiste.

Quello che invece si ottimizza davvero:

1. **quale sorte** — ambo e ambata rendono 57 centesimi per euro, il terno 35,
   la quaterna 22. È dimostrabile, e le righe che rendono meno sono attenuate e
   dichiarano quanto rendono;
2. **quanto spendere** — coprire tutte le previsioni vive costa centinaia di
   euro, e la pagina dice quanto;
3. **cosa tenere quando il budget non basta** — prima il **metodo più raro**,
   poi ciò che scade prima, poi la sorte che rende di più. Così il taglio
   colpisce i terni e non gli ambi, e non lascia fuori il metodo che scatta
   quattro volte l'anno per far posto a quello che ne fa mille.

In fondo compaiono i **numeri chiesti da più previsioni**: non li rende più
probabili, significa che coprendoli si soddisfano più previsioni con meno
giocate distinte.

Poi **Ruota per ruota**: le stesse previsioni raccolte per ruota invece che per
metodo, che è come si ragiona davanti al botteghino — non si gioca "il Fulmine",
si gioca "su Napoli". Accanto a ogni ruota quante giocate ha in gioco; scelta
una, il costo per giocarle tutte, la probabilità e il ritorno atteso, e sotto le
giocate raggruppate per metodo. Qui una previsione che prevede due ruote costa
**un euro invece di due**, perché la si porta su una ruota sola: il ritorno per
euro non cambia, la spesa sì.

Infine, chiuso, il **compositore manuale** — griglia dei novanta numeri, ruote,
sorti, importo — per dare un prezzo a una giocata qualunque.

Costo e ritorno atteso sono esatti (il valore atteso è additivo anche fra
giocate dipendenti); la probabilità di vincere qualcosa è approssimata, perché
le giocate insistono sullo stesso concorso e condividono numeri e ruote — per
questo la pagina scrive "circa".

**Previsioni** — i numeri in comune fra i metodi, che cosa i metodi avrebbero
detto su un concorso qualunque del passato, e l'elenco completo di tutto quello
che hanno giocato. Sono le tre cose descritte qui sotto.

**In corso** — tutte le previsioni ancora giocabili, raggruppate per metodo e
ordinate **per rarità**, non per data: ordinare per data seppellisce il metodo
che scatta ottanta volte l'anno sotto quello che ne fa mille.

**Bilancio** — speso, incassato, saldo e ritorno per metodo, col riferimento del
backtest ventennale e il flag sui campioni troppo piccoli.

**Estrazioni** — gli ultimi otto concorsi, tutte le ruote, in ordine di
estrazione.

### "I numeri in comune", in cima a Previsioni

Raccoglie i numeri chiesti **da più di un metodo** contemporaneamente e ne
compone una **previsione unica**: i cinque più richiesti, giocati per ambo sulla
ruota su cui quel gruppo è chiesto più spesso.

Va letta per quello che è. L'accordo fra metodi **non alza la probabilità**: il
Lotto non ha memoria, e un ambo resta 1 su 400,5 anche se sei metodi lo indicano
insieme. Serve a un'altra cosa — con dieci ambi si coprono molte previsioni vive
invece di giocarle una per una.

E c'è un limite che la fascia dichiara da sola, in fondo: **i sei metodi non sono
sei pareri indipendenti**. Le loro condizioni di ricerca si riducono a tre
scansioni (è nel documento `kb-metodi-lotto`), quindi due metodi che ne
condividono una concordano *per costruzione*, non perché si siano trovati
d'accordo. Per questo il conteggio è sui **metodi** e non sulle previsioni: due
previsioni dello stesso metodo non sono due pareri, e le prove in
`prove/test_consiglio.mjs` difendono proprio questa distinzione.

### "Che cosa avrebbero detto i metodi"

Si sceglie un concorso qualunque dal 1939 in poi e una ruota. La pagina mostra
tre cose, nell'ordine:

1. **i cinque numeri usciti** su quella ruota quel giorno;
2. **le previsioni che i sei metodi hanno rilevato**, quelle che toccano la
   ruota scelta per prime, ciascuna col suo verdetto: dentro i colpi che il
   fascicolo prescrive, su quale ruota e a che colpo è uscita, oppure scaduta
   senza esito — e in quel caso, a parte e dichiarata come fuori giocata, la
   prima volta che si sarebbe verificata dopo la scadenza;
3. **i numeri derivati dai cinque** — complemento, diametrale, vertibile,
   terzina simmetrica, figura, cadenza — e su quali ruote sono usciti nei dodici
   concorsi successivi.

Il terzo blocco è separato dal secondo, e con un avviso, perché **non sono
previsioni**. I sei metodi non partono da cinque numeri: partono da una
condizione su tutto il concorso, e solo quando quella scatta dicono che cosa
giocare. Applicare le loro formule a cinque numeri qualunque produce sempre un
risultato, per costruzione: sono numeri derivati, e chiamarli previsione
sarebbe l'unica vera bugia che questo sito potrebbe raccontare.

Su nove date-ruota su dieci c'è almeno una previsione vera. Nell'altro caso la
pagina lo dice e spiega perché: i metodi cercano una configurazione, non dei
numeri, e quasi sempre quella configurazione non c'è.

### "L'elenco di tutto"

Ogni numero che i sei metodi hanno giocato, su ogni ruota, a ogni concorso, con
com'è andata — un milione e quattro di righe in tutto l'archivio, sedicimila
l'anno. Si entra da una **data**, e si vede quel concorso; oppure si sceglie un
**anno intero**, per sfogliarlo. Poi i filtri per ruota, metodo, sorte ed
esito, la tabella a pagine da cento righe e un bottone che salva in CSV
**esattamente le righe filtrate**, apribile in Excel (punto e virgola come
separatore e BOM davanti, che è quello che Excel in italiano si aspetta).

La riga è la terna **previsione · sorte · ruota**, non la previsione: filtrare
per Napoli deve dare davvero solo Napoli.

**La data non chiede l'anno prima.** I dati stanno in un file per anno — è un
dettaglio di come sono pubblicati, e per un po' è finito in faccia a chi usa il
sito: bisognava scegliere l'anno da una tendina *e poi* una data che l'anno lo
contiene già. Ora il campo Giorno funziona da subito: la data dice quale anno
caricare, la tendina si allinea da sola, e se quel giorno non si è estratto
scatta al concorso più vicino **e lo scrive**, invece di mostrare un elenco
vuoto senza spiegazione.

**L'esito per ruota ha tre stati e non due**, ed è la cosa meno ovvia della
sezione. Come da fascicoli la sorte si sospende quando si verifica su una ruota
di gioco, e da quel momento non si gioca più *nemmeno sulle altre ruote della
stessa previsione*. Così una riga su Cagliari può finire senza esito non perché
i numeri non siano usciti, ma perché la giocata si era già chiusa su Bari due
colpi prima. Chiamarla «scaduta» sarebbe falso e «uscita» pure: si chiama
**sospesa** e dice dove e quando. Gli stati sono quattro:

| stato | vuol dire |
|---|---|
| `uscita` | su **questa** ruota, entro i colpi. È la riga che ha pagato. |
| `sospesa` | la giocata si è chiusa su un'altra ruota prima che qui uscisse. |
| `scaduta` | i colpi sono finiti e non è uscita da nessuna parte. |
| `aperta` | i colpi non sono ancora finiti. |

Il conto di un anno intero è qualche centinaio di millisecondi, quindi si fa una
volta sola quando cambia l'anno; cambiare una tendina filtra quello che è già in
memoria ed è istantaneo. Gli esiti non si ricalcolano in `elenco.js`: li dà
`verifica()` di `storico.js`, che è la regola provata contro Python.

#### Perché le previsioni storiche non si ricalcolano nel browser

Erano tre le strade, e non si equivalgono:

- **rifare i sei metodi in JavaScript** significa avere due implementazioni
  della stessa cosa. Prima o poi divergono, e il giorno in cui divergono nessuno
  se ne accorge: la pagina direbbe una cosa e il Bilancio un'altra;
- **mandare al browser tutte le previsioni della storia** sono settantatremila
  righe, per leggerne dieci;
- **dividerle per anno** costa un file di ottanta chilobyte a domanda, e il
  calcolo resta quello vero, fatto dal motore Python.

Si è scelta la terza. `motore/storia.py` scrive `docs/dati/previsioni/AAAA.txt`,
una riga per previsione (`giorno|metodo|ruote|colpi|anche_tutte|sorti|nota|avviso`),
più un `indice.json` che dice quali anni esistono. Il conto completo sull'intero
archivio dura un paio di minuti — `python -m motore.aggiorna --tutti-gli-anni` —
mentre la sera si riscrive solo l'anno dell'ultimo concorso, che sono due secondi.

C'è però **una** regola che resta scritta due volte: il controllo delle uscite.
`motore/valutazione.py` la applica per il Bilancio, `docs/storico.js` la rifà per
questa pagina. Non si poteva evitare — gli esiti dipendono dalla ruota e dai
colpi scelti a schermo — quindi si è messo un guinzaglio: `prove/test_pipeline.py`
scrive in `prove/dati/esiti-riferimento.json` quello che ha calcolato Python su
trecento previsioni vere, e `prove/test_storico.mjs` pretende che JavaScript
produca gli stessi stati e gli stessi esiti, colpo per colpo e ruota per ruota.
Se un giorno le due si allontanano, la prova diventa rossa.

#### E l'archivio delle estrazioni

Stesso problema, stessa soluzione. Il CSV di partenza è di due mega e mezzo;
`motore/pubblica.py` lo riscrive in `docs/dati/storico.txt`, una riga per
concorso, data senza trattini e dieci ruote da cinque numeri a due cifre, `--`
dove una ruota non ha estratto. Sono 108 caratteri per riga invece di circa 350;
il file sta sotto il mega e, servito compresso come qualunque testo, arriva a
poco più di trecento chilobyte. Resta leggibile a occhio, che qui conta: un file
che nessuno può controllare è un file di cui bisogna fidarsi.

`docs/storico.js` lo tiene in un solo `Uint8Array` invece che in settemila
oggetti annidati, e la pagina lo scarica **solo alla prima apertura della scheda
Previsioni** — chi guarda la Schedina e basta non lo prende mai.

### La data del prossimo concorso

È **proiettata** dai giorni della settimana in cui si è estratto negli ultimi
mesi, e dichiarata come proiezione. Il motivo è una trappola che vale la pena
conoscere: l'endpoint `calendario-estrazioni-del-lotto` elenca i giorni in cui un
concorso **si è già tenuto**, non quelli programmati, quindi interrogato sul
futuro risponde con una lista vuota. In sviluppo sembrava funzionare, perché con
l'archivio fermo a giugno i giorni "già avvenuti" erano comunque nel futuro
rispetto all'ultimo concorso caricato; si è visto solo alla prima esecuzione con
i dati aggiornati. La fonte viene interrogata lo stesso, prima: se un giorno
pubblicasse il calendario in anticipo, quella risposta avrebbe la precedenza.

## Farlo girare

Serve solo Python 3.11+ (e Node, per le prove del simulatore). Nessun `pip
install`: il motore usa la sola libreria standard.

```powershell
# aggiornamento completo: scarica, rileva, valuta, riscrive il sito
python -m motore.aggiorna

# senza toccare la rete: rileva, valuta e ripubblica quello che c'è già
python -m motore.aggiorna --senza-rete

# ricostruire le previsioni da una certa data (non crea doppioni)
python -m motore.aggiorna --ricostruisci 2025-09-01

# riscrivere le previsioni storiche di TUTTI gli anni (un paio di minuti):
# serve solo se cambia un metodo, o la prima volta su un repository nuovo
python -m motore.aggiorna --tutti-gli-anni
```

Per guardare il sito in locale — aprendo `index.html` col doppio clic **non
funziona**, perché il browser non lascia leggere file locali a una pagina:

```powershell
python -m http.server 8000 --directory docs
# poi http://127.0.0.1:8000
```

Le prove, tutte e cinque:

```powershell
python prove\test_motore.py
python prove\test_pipeline.py
node prove\test_schedina.mjs
node prove\test_consiglio.mjs
node prove\test_storico.mjs
```

`test_pipeline.py` riscrive `prove/dati/esiti-riferimento.json`, che
`test_storico.mjs` rilegge: se si lancia solo quello JavaScript dopo aver
cambiato il motore, va rilanciato prima quello Python.

Le prove:

```powershell
python prove/test_motore.py       # i metodi riproducono gli esempi dei fascicoli
python prove/test_pipeline.py     # determinismo, idempotenza, stabilità su file
node prove/test_schedina.mjs      # le probabilità note del Lotto
node prove/test_consiglio.mjs     # ordine, budget, etichette del consiglio
```

## L'aggiornamento serale

`.github/workflows/aggiorna.yml` gira due volte al giorno: alle 20:00 UTC —
sempre almeno un'ora dopo l'estrazione delle 20:00 italiane, in qualunque
stagione, senza doversi inventare conti sull'ora legale — e alle 6:00 UTC del
mattino dopo, come rete di sicurezza se la fonte era giù o se GitHub aveva
saltato l'esecuzione (le schedule sono *best effort* e possono slittare).

Se non è cambiato niente non committa e non costa nulla. Se la fonte non
risponde esce con codice 1 e il sito resta con i dati di ieri, invece di
restare senza dati.

Le estrazioni arrivano dagli stessi endpoint che `www.lotto-italia.it` usa per
la propria pagina:

```
POST /gdl/estrazioni-e-vincite/calendario-estrazioni-del-lotto.json
     {"mese": 9, "anno": 2026}   ->  [1, 3, 4, 5, 8, 10, 11]

POST /gdl/estrazioni-e-vincite/estrazioni-del-lotto.json
     {"data": "20260911"}        ->  {"esito": "OK", "estrazione": [...]}
```

La data va passata come **stringa AAAAMMGG**: con un timestamp numerico
l'endpoint risponde "Errore nel recupero dell'estrazione" senza spiegare perché,
e ci si perde un'ora. Non è un'API pubblica documentata, quindi può cambiare
senza preavviso: per questo il parser scarta in silenzio le voci malformate
invece di fidarsi, e i giorni falliti vengono annotati anziché interrompere il
lavoro a metà.

## Pubblicarlo

1. Crea un repository **pubblico** su GitHub (le azioni programmate sono gratis
   sui repository pubblici).
2. Dalla cartella del progetto:

   ```powershell
   git remote add origin https://github.com/<tuo-utente>/<nome-repo>.git
   git branch -M main
   git push -u origin main
   ```

3. Su GitHub: **Settings → Pages → Source: Deploy from a branch**, ramo `main`,
   cartella **`/docs`**. Dopo un minuto il sito è online.
4. **Settings → Actions → General → Workflow permissions**: scegli *Read and
   write permissions*, altrimenti l'aggiornamento serale non può committare.
5. La prima esecuzione si lancia a mano da **Actions → Aggiornamento serale →
   Run workflow**, per non aspettare sera.

Un'avvertenza su GitHub: le azioni programmate vengono disattivate in un
repository senza attività da 60 giorni. Qui il problema non si pone finché
l'aggiornamento committa qualcosa quasi ogni giorno — ma se un periodo lungo
passa senza estrazioni nuove, vale la pena dare un'occhiata alla scheda Actions.

## Cosa non c'è dentro

Le scansioni dei fascicoli originali sono materiale protetto da copyright e
restano fuori dal repository (`fascicoli/` è ignorato da git). Nel codice c'è
solo la descrizione algoritmica di cosa ciascun metodo cerca, che è ciò che
serve per farlo girare.
