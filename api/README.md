# App Lotto — API

Prima tranche: **dominio, schema dati, import dell'archivio**, più il ciclo completo
rilevamento → valutazione → consultazione. FastAPI + SQLAlchemy 2 + PostgreSQL.

## Struttura

```
api/
  app/
    config.py              configurazione da .env
    db.py                  engine, sessione, verifica dello schema
    models.py              Estrazione, Previsione, Sorte, Esito
    main.py                API
    pianificatore.py       l'aggiornamento serale, dentro l'applicazione
    engine/core.py         il motore dei sei metodi (puro, non conosce il DB)
    services/
      importer.py          import CSV + validazione
      rilevatore.py        esegue gli scanner su un concorso e persiste
      valutatore.py        rivaluta le sorti aperte, registra gli esiti
      economia.py          spesa, incasso e saldo con le quote ufficiali
      consultazione.py     letture per l'interfaccia (colpi residui)
      aggiornatore.py      scarica i concorsi nuovi dalla fonte ufficiale
      ciclo.py             scarica + rileva + valuta, in un posto solo
      calendario.py        quand'e' la prossima estrazione
      schedina.py          simulazione di una giocata: poste, vincite, probabilita'
    web/index.html         interfaccia (pagina unica, nessun build step)
  scripts/carica_archivio.py
  scripts/aggiorna.py
  test_schedina.py       probabilita' note del Lotto, poste, casi limite
  test_pianificatore.py  orario, lucchetto, segnalibro
  prova_interfaccia.py   serve la pagina con dati finti, senza database
  migrazioni/            script Alembic
  alembic.ini
  docker-compose.yml
```

### Perché il modello è fatto così

Un solo concetto è un fatto oggettivo — l'**Estrazione**. Tutto il resto è
interpretazione: la **Previsione** è ciò che un metodo ha suggerito, la **Sorte** è
ogni singola giocata al suo interno (l'ambata, ciascun ambo, la terzina), l'**Esito**
è quando e dove una sorte si è verificata.

La separazione Sorte/Esito è ciò che permette di dire la verità all'utente. Con una
sola colonna "vinta" si potrebbe dire soltanto *se* una previsione ha vinto; con questa
struttura si può dire **quanto è costata, quanto ha reso, e cosa è ancora in corso** —
che è la differenza fra un'app onesta e un volantino.

`Sorte.colpi_valutati` rende la rivalutazione **idempotente**: si può rilanciare quante
volte si vuole senza contare due volte lo stesso colpo.

## Avvio

```powershell
cd C:\Dev\App_Lotto\api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env      # e adatta DATABASE_URL
```

### Il database

Su questa macchina c'e' gia' un PostgreSQL installato nativamente, in ascolto
sulla **5432**. Ci sono quindi due strade, e vanno tenute distinte.

**Con Docker** (consigliata: isolata, si butta e si rifa'). Il compose usa la
**5433** proprio per non collidere con il server nativo:

```powershell
docker compose up -d
docker compose logs -f db      # ctrl+C quando dice "database system is ready"
```

Il `.env.example` punta gia' alla 5433.

**Con il PostgreSQL nativo**, se preferisci non usare Docker: servono utente e
database, che non esistono ancora. Verra' chiesta la password dell'utente
`postgres` scelta all'installazione.

```powershell
Get-Service *postgres*
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -c "CREATE USER lotto WITH PASSWORD 'lotto' CREATEDB;"
& "C:\Program Files\PostgreSQL\16\bin\createdb.exe" -U postgres -O lotto lotto
```

In questo caso nel `.env` la porta torna **5432**.

### Migrazioni

Lo schema e' gestito da **Alembic**: l'applicazione non crea piu' le tabelle da
sola. Prima del primo avvio, e dopo ogni `git pull` che tocchi il modello:

```powershell
alembic upgrade head
```

L'URL del database non sta in `alembic.ini` ma viene letto dal `.env` tramite
`migrazioni/env.py`: una sola sorgente di verita', e nessuna password in un file
versionato.

Dopo aver modificato `app/models.py`:

```powershell
alembic revision --autogenerate -m "descrizione della modifica"
alembic upgrade head
```

Rileggi sempre lo script generato prima di applicarlo — l'autogenerate vede le
differenze, non le intenzioni, e su rinomine e cambi di tipo va corretto a mano.

Se lo schema non e' allineato, l'app non parte alla cieca: dice a che revisione
sta il database, a quale arrivano gli script, e cosa lanciare.

Carica l'archivio (~73.000 estrazioni, meno di un minuto):

```powershell
python scripts\carica_archivio.py
```

Genera le previsioni di un periodo e valutale:

```powershell
python scripts\carica_archivio.py --rileva-da 2026-01-01 --valuta
```

Avvia l'API:

```powershell
uvicorn app.main:app --reload
# documentazione interattiva su http://127.0.0.1:8000/docs
```

## Endpoint

| Metodo | Percorso | Cosa fa |
|---|---|---|
| POST | `/estrazioni/import` | carica il CSV, con validazione |
| POST | `/estrazioni/aggiorna` | scarica i concorsi nuovi, poi rileva e valuta |
| GET | `/estrazioni?giorno=` | quadro estrattivo di un concorso |
| GET | `/estrazioni/ultima` | ultima data presente in archivio |
| POST | `/previsioni/rileva?giorno=` | esegue i sei scanner e persiste |
| GET | `/previsioni` | elenco, filtrabile per giorno, metodo, solo aperte |
| POST | `/previsioni/valuta` | rivaluta le sorti aperte |
| GET | `/statistiche/metodi` | esiti reali per metodo |
| GET | `/previsioni/aperte` | cosa è ancora in gioco, con i colpi residui |
| GET | `/statistiche/economia` | speso, incassato, saldo e ritorno per metodo |
| GET | `/prossima-estrazione` | le prossime date di concorso |
| GET | `/schedina/sorti` | cosa si puo' giocare e quanto paga |
| POST | `/schedina/simula` | poste, vincite possibili e probabilità di una giocata |
| GET | `/servizio/aggiornamento` | stato dell'aggiornamento automatico |
| POST | `/servizio/aggiornamento/esegui` | lancia subito il ciclo, senza attendere l'ora |
| GET | `/salute` | stato del servizio |

## Interfaccia

Una pagina sola, servita da FastAPI su **`/app`** (la radice ci reindirizza).
Niente build, niente dipendenze da CDN: si apre e funziona, anche dal telefono
sulla rete locale.

```powershell
uvicorn app.main:app --reload --host 0.0.0.0   # ascolta su tutte le interfacce
```

Dal PC resta `http://127.0.0.1:8000`. Dal telefono sulla stessa rete, l'IP della
macchina (`Get-NetIPAddress -AddressFamily IPv4`).

**Dall'emulatore Android** `localhost` è l'emulatore stesso, non il PC che lo
ospita: l'host si raggiunge all'indirizzo speciale **`10.0.2.2`**.

```
http://10.0.2.2:8000
```

In alternativa, il port forwarding di adb — più pulito, perché dentro
l'emulatore l'indirizzo torna a essere `localhost` e funziona identico anche su
un telefono collegato via USB:

```powershell
adb reverse tcp:8000 tcp:8000
# poi nel browser dell'emulatore: http://localhost:8000
```

Tre viste: **In corso**, le previsioni ancora giocabili con i colpi che restano;
**Bilancio**, speso e incassato per metodo; **Schedina**, il simulatore. La seconda è quella che conta: è
dove una "quota vincente del 26,8%" si rivela per quello che è, un ritorno del
65%. Dove il campione è troppo piccolo perché il saldo significhi qualcosa, la
riga lo dice da sola.

## La scheda Schedina

Dice quand'è la prossima estrazione e simula una giocata: si scelgono i numeri
sulla griglia (o si parte da una previsione in corso), le ruote, le sorti e
l'importo, e si vede quanto si punta davvero su ogni combinazione, quanto si
incassa in ciascuno scenario, e con quale probabilità.

Il calcolo sta sul server (`app/services/schedina.py`) e non nella pagina,
perché quote e ritenuta devono avere una sola definizione — la stessa che usa
il bilancio. Le tre regole che si sbagliano più spesso, e che il modulo
implementa esplicitamente:

1. **la posta si ripartisce** fra le ruote e fra le sorti. Dieci euro su due
   ruote per ambo e terno sono 2,50 € per ruota e per sorte, non dieci;
2. **si ripartisce una seconda volta** sulle combinazioni: cinque numeri per
   ambo sono dieci ambi, quindi 25 centesimi l'uno. È il motivo per cui
   allargare la giocata non moltiplica la vincita come sembra;
3. **vincono tutte le combinazioni contenute**: con cinque numeri giocati per
   ambo e tre usciti si vincono tre ambi, non uno.

Accanto a ogni vincita c'è la sua probabilità, ed è il punto dell'intera
scheda. "Potresti vincere 575 €" da solo è pubblicità; "575 €, una volta su
400,5" è un'informazione. In fondo compare il **ritorno atteso**, che su ogni
giocata possibile è inferiore alla posta — dal 57% dell'ambo al 12% della
cinquina. È il margine del banco, e nessun metodo lo sposta: i metodi scelgono
quali numeri giocare, non quanto paga il gioco.

Una proprietà che vale la pena conoscere, e che i test verificano: il ritorno
atteso **non dipende** da quanti numeri si giocano né da quante ruote si
scelgono. Allargare la giocata aumenta la probabilità di vincere qualcosa e
riduce nella stessa misura l'importo di ciascuna vincita.

La prossima estrazione arriva dal calendario ufficiale, non dal giorno della
settimana: i giorni di concorso sono cambiati più volte e saltano per le feste.
Se la fonte non risponde la data viene dedotta dall'archivio ed è **dichiarata
come stima**, perché una data sbagliata data per certa è peggio di un "non lo so".

### Guardare l'interfaccia senza database

```powershell
.\.venv\Scripts\python.exe prova_interfaccia.py    # http://127.0.0.1:8100/app/
```

Serve la pagina vera con dati finti — tranne la simulazione della schedina, che
è quella autentica, perché è solo aritmetica e non tocca il database.

## Aggiornamento automatico

Lo storico si carica una volta dal CSV; da lì in poi i concorsi nuovi arrivano
dalla **fonte ufficiale** (`www.lotto-italia.it`), gli stessi endpoint che il
loro sito usa per la propria pagina "estratti per ruota":

```
POST /gdl/estrazioni-e-vincite/calendario-estrazioni-del-lotto.json
     {"mese": 9, "anno": 2026}   ->  [1, 3, 4, 5, 8, 10, 11]

POST /gdl/estrazioni-e-vincite/estrazioni-del-lotto.json
     {"data": "20260911"}        ->  {"esito": "OK", "estrazione": [...]}
```

La data va passata come **stringa AAAAMMGG**: con un timestamp numerico
l'endpoint risponde "Errore nel recupero dell'estrazione" senza spiegare perché.
L'aggiornatore legge prima il calendario del mese, così interroga solo i giorni
in cui un concorso c'è stato davvero, invece di tentare tutte le date.

Il ciclo completo — scarica, rileva, valuta — si può lanciare a mano:

```powershell
.\.venv\Scripts\python.exe scripts\aggiorna.py
```

ma normalmente non serve, perché **lo fa l'applicazione da sola**. All'avvio
recupera quello che manca, poi ogni sera alle 20:45 (l'estrazione è alle 20, si
lascia un margine) rifà il giro. Si governa dal `.env`:

```
AGGIORNAMENTO_AUTOMATICO=true
ORA_AGGIORNAMENTO=20:45
```

Lo stato si legge da `GET /servizio/aggiornamento` ed è scritto in cima
all'interfaccia: quando è andato l'ultimo giro, com'è finito, quand'è il
prossimo. Il pulsante **Aggiorna ora** fa partire il ciclo fuori orario.

### Perché non l'utilità di pianificazione di Windows

Perché sarebbe il posto giusto, e su questa macchina è chiuso. L'account con
cui si lavora (`39347`) non appartiene al gruppo Administrators, e il servizio
Utilità di pianificazione gli nega tutto:

```
Register-ScheduledTask : Accesso negato.       HRESULT 0x80070005
schtasks /query /tn "AppLotto-Aggiorna"        ERRORE: Accesso negato.
```

Nega anche la sola **lettura**, il che è la prova che non si tratta di un
parametro sbagliato — non `-User`, non `-RunLevel`, non `-Force` — ma di un
permesso che il profilo non ha. Da un profilo amministratore funzionerebbe;
visto che il progetto deve girare da entrambi, la pianificazione è stata
spostata dentro l'applicazione (`app/pianificatore.py`).

**Il compromesso, detto chiaramente:** l'aggiornamento avviene finché il server
è acceso. Una sera a server spento non viene aggiornata. Non è però una perdita
permanente: l'aggiornatore non scarica "l'estrazione di ieri" ma tutti i
concorsi mancanti fra l'ultimo in archivio e oggi, quindi il primo avvio
successivo recupera il buco da solo. Se un giorno il progetto finisse su una
macchina dove la pianificazione è disponibile, basta rimettere l'attività
esterna e portare `AGGIORNAMENTO_AUTOMATICO` a `false`.

Due dettagli del pianificatore che sembrano pignoleria e non lo sono. Il
risveglio è a fette di un minuto con l'orario ricalcolato ogni volta, invece di
un `sleep` lungo quanto l'attesa: su un portatile che va in sospensione l'attesa
lunga si congela e l'appuntamento salta. E l'ultimo tentativo viene annotato in
`logs\ultimo-tentativo.txt`, altrimenti ogni riavvio di `uvicorn --reload` —
cioè ogni salvataggio, durante lo sviluppo — lancerebbe un giro completo sulla
fonte ufficiale.

In ogni caso il registro è uno solo, `logs\aggiorna.log`, e ci scrivono tutti e
tre i punti d'ingresso: è lì che si va a vedere *perché* una notte è fallita.

**Non è un'API pubblica documentata**, quindi può cambiare senza preavviso. Per
questo il parser scarta in silenzio le voci malformate invece di fidarsi, e
`aggiorna()` annota i giorni falliti e prosegue anziché interrompersi. Se un
giorno smettesse di funzionare, l'archivio resta caricabile a mano dal CSV.

## Il controllo che non va tolto

L'importer misura la **quota di estrazioni con i cinque numeri già in ordine crescente**.
Se fossero in ordine di estrazione ci si aspetta 1/120 = 0,83%; una quota molto più alta
significa che l'archivio li ha riordinati per valore. In quel caso quattro metodi su sei
— tutti quelli che filtrano per isotopia — continuerebbero a girare **misurando
qualcos'altro, senza che nulla lo segnali**. Per questo il rapporto di import lo dice
esplicitamente e l'endpoint restituisce un avviso in cima alla risposta.

Sull'archivio Ratio 90 attuale: 0,85%. Ordine di estrazione, isotopia utilizzabile.

## Stato e prossimi passi

Fatto: dominio, persistenza, import validato, rilevamento, valutazione idempotente,
statistiche reali per metodo.

Fatto anche: bilancio economico (`/statistiche/economia`) con le quote ufficiali,
e migrazioni Alembic.

Fatto anche: interfaccia su `/app` e aggiornamento dalla fonte ufficiale.

Fatto anche: aggiornamento serale interno all'applicazione, con stato visibile
nell'interfaccia.

Da fare: priorità fra le previsioni (i metodi hanno selettività molto diverse —
Ambo Secco Caotico produce 483 rilevamenti l'anno, Un Solo Ambo Secco quattro);
autenticazione se l'app deve uscire da localhost.
