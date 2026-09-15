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
scheda **Bilancio** mostra speso, incassato e saldo reali. La scheda
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
  schedina.js      il simulatore, l'unica logica che vive nel browser
  dati/*.json      generati dal motore, non si scrivono a mano

prove/           test_motore.py  test_pipeline.py  test_schedina.mjs
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
```

Per guardare il sito in locale — aprendo `index.html` col doppio clic **non
funziona**, perché il browser non lascia leggere file locali a una pagina:

```powershell
python -m http.server 8000 --directory docs
# poi http://127.0.0.1:8000
```

Le prove:

```powershell
python prove/test_motore.py       # i metodi riproducono gli esempi dei fascicoli
python prove/test_pipeline.py     # determinismo, idempotenza, stabilità su file
node prove/test_schedina.mjs      # le probabilità note del Lotto
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
