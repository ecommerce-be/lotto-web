# Backtest dei metodi su 20 anni di estrazioni reali

**Archivio**: `lotto-archivio-completo-1939-oggi.csv` (Ratio 90 / Overlab Italia)
**Finestra**: 3.340 concorsi completi, dal 03/01/2006 al 20/06/2026, 10 ruote (Nazionale esclusa)
**Rilevamenti generati**: 23.853

## Validazione dell'archivio (fatta prima di tutto il resto)

| Controllo | Esito |
|---|---|
| Righe valide | 76.549, nessuna malformata |
| Numeri fuori 1-90 | 0 |
| Estrazioni con numeri ripetuti | 0 |
| Ruote | 10 classiche + Nazionale (dal 04/05/2005) |
| **Ordine degli estratti** | **ordine di estrazione** — solo 0,85% delle estrazioni ha i 5 numeri crescenti, contro lo 0,83% atteso dal caso. Le posizioni sono utilizzabili, i filtri isotopi funzionano |
| Concorsi per anno | 52 (1939-1940) → 156/157 (2011-2022) → 182/209 (2023-2025), coerente con la storia del gioco |
| Regolarità dell'urna | distanze fra coppie estratte: nessuna sovra-rappresentata, scarto massimo +1,9σ su 45 distanze |
| Autocorrelazione | **assente**: un numero uscito su una ruota riesce entro 14 concorsi nel 54,90% dei casi, contro il 55,03% di numeri scelti a caso. Sugli ambi: 3,47% contro 3,48% |

L'archivio è pulito e l'urna è regolare. Nessuna "memoria" fra estrazioni.

## Test di regressione del motore

Il motore riproduce **25 su 25** gli esempi pubblicati nei fascicoli: applicazione pratica e casi della
tabella statistica di Lotto Facile 4, le due dimostrazioni di Lotto Facile 1, i tre esempi del Fulmine,
l'esempio di Un Solo Ambo Secco, quattro rilevamenti di Lotto Facile 5 con ambate e ambi secchi.

Un'eccezione trovata strada facendo: **l'esempio RM-VE del 09/12/1998 che Manara pubblica come successo
viola la sua stessa controindicazione 3** (ambata 82, il cui vertibile 28 è presente nella formazione).
Il filtro è quindi un parametro del motore, non una regola fissa.

## Frequenza dei rilevamenti

| Metodo | Rilevamenti | All'anno |
|---|---:|---:|
| lottofacile1 | 16.528 | 787 |
| lottofacile5 | 3.403 | 162 |
| lottofacile4 | 2.178 | 104 |
| fulmine | 1.668 | 79 |
| unsoloambosecco | 76 | 4 |

Lotto Facile 1 scatta 2-3 volte per concorso: come "assistente quotidiano" produrrebbe troppe segnalazioni
per essere credibile. Un Solo Ambo Secco scatta 4 volte l'anno: è un evento, non un servizio.

## Esito: metodo contro caso

Confronto a parità assoluta di esposizione. La baseline gioca la **stessa identica forma di giocata**
(stessi ambi, stesse ruote, stessi colpi, stessa struttura di condivisione dei numeri) cambiando solo
*quali* numeri o *quando* si gioca.

### Sorte dell'ambo — placebo temporale (gli stessi numeri, giocati a partire da una data a caso)

| Metodo | n | al rilevamento | in data casuale | differenza | verdetto |
|---|---:|---:|---:|---:|---|
| lottofacile4 | 2.178 | 21,17% | 18,51% | +2,66 [+0,94 / +4,45] | scostamento |
| fulmine | 2.343 | 16,01% | 16,50% | −0,50 [−2,04 / +1,03] | nessun vantaggio |
| lottofacile1 | 16.528 | 6,40% | 6,81% | −0,42 [−0,78 / −0,03] | nessun vantaggio |
| lottofacile5 | 3.731 | 8,36% | 8,43% | −0,07 [−0,94 / +0,88] | nessun vantaggio |
| unsoloambosecco | 76 | 2,63% | 1,84% | +0,79 [−2,19 / +4,93] | nessun vantaggio |

Quattro metodi su cinque sono **indistinguibili dal caso**. Le percentuali alte che si leggono nei
fascicoli (97%, 112%, 601%) non misurano una capacità predittiva: misurano l'ampiezza del gioco.
Con 1 ambata + 3 ambi + una lunga a Tutte, su 2 ruote, per 14 colpi, vince spesso anche una giocata
a caso — ed è esattamente ciò che mostra la colonna "in data casuale".

## Il caso Lotto Facile 4

L'unico scostamento sopravvive a tutti i controlli che gli ho fatto:

| Controllo | Risultato |
|---|---|
| Stabilità temporale | +2,9σ su 2006-2015, +1,7σ su 2016-2026 |
| Bootstrap a blocchi sui concorsi (non-indipendenza) | IC95 +0,94 / +4,40 punti, zero escluso |
| Permutazione delle date (200 permutazioni) | 0 permutazioni su 200 eguagliano il reale, p < 0,005 |
| Colpo per colpo | vantaggio distribuito su tutti i 14 colpi, nessun picco al 1° o 2° → esclusa la contaminazione |
| Controllo A: ambata casuale, stessa forma | −0,05 punti (zero, come deve essere) |
| Controllo B: ambata reale ruotata, struttura identica | +0,43 punti (zero) |
| **Archivio sintetico casuale, 3 semi** | **−0,83 / −0,14 / +0,33 punti (zero)** |

I controlli negativi funzionano, quindi il disegno del test è corretto; sull'archivio sintetico l'effetto
sparisce, quindi non è un artefatto del metodo. Lo scostamento è **nei dati reali**.

**Come va letto.** Non come "il metodo funziona": il meccanismo causale non esiste, i numeri futuri non
sanno cosa è uscito prima, e l'autocorrelazione dell'archivio è misurata a zero. Le spiegazioni residue
plausibili sono, in ordine: una peculiarità o un errore dell'archivio di terze parti; una fluttuazione
più rara del previsto; un bias che non ho individuato. **Il passo per chiudere la questione è ripetere
il test su un secondo archivio di provenienza diversa.** Finché non lo si fa, resta una curiosità aperta.

## Il dato che conta davvero: il bilancio

Quote ufficiali (moltiplicatore della posta su ruota singola): ambata 11,232 · ambo 250 · terno 4.500 ·
quaterna 120.000. Ritenuta erariale 8%. Regola: 1 € per sorte, per ruota, per colpo, sospendendo la sorte
sulla ruota dove si è vinto, come prescrivono i fascicoli stessi.

| Metodo | Previsioni | Speso | Incassato | Saldo | Ritorno |
|---|---:|---:|---:|---:|---:|
| lottofacile5 | 3.731 | 281.564 € | 207.974 € | −73.590 € | 73,9% |
| lottofacile1 | 16.528 | 756.535 € | 506.160 € | −250.375 € | 66,9% |
| lottofacile4 | 2.178 | 280.075 € | 192.593 € | −87.482 € | 68,8% |
| fulmine | 2.343 | 260.006 € | 160.946 € | −99.060 € | 61,9% |
| unsoloambosecco | 76 | 604 € | 460 € | −144 € | 76,2% |
| **TOTALE** | | **1.578.784 €** | **1.068.134 €** | **−510.650 €** | **67,7%** |

Venti anni di applicazione disciplinata di tutti i metodi: **mezzo milione di euro persi, 32 centesimi
su ogni euro**.

E soprattutto: **anche Lotto Facile 4, quello con lo scostamento, rende il 68,8%.** È il punto da tenere
fermo. Il margine del banco sull'ambo è circa il 38%; uno scostamento di 2,66 punti percentuali ne
recupera una frazione e lascia il gioco largamente in perdita. Nessuno scostamento di quell'ordine può
ribaltare quel margine — servirebbe un vantaggio dieci volte più grande.

## Cosa significa per l'app

L'assistente non può promettere di far vincere, perché nessuno dei metodi lo fa. Può però fare cose
che oggi nessuno fa bene, e che hanno valore reale per chi al Lotto gioca comunque:

1. **Applicare i metodi senza errori di calcolo**, sui sei fascicoli, su tutte le ruote, a ogni estrazione.
   È il lavoro che questi appassionati fanno a mano su carta quadrettata.
2. **Tenere il conto dei colpi** e dire quando una previsione è scaduta — la disciplina che fa la
   differenza fra un gioco controllato e una rincorsa.
3. **Mostrare gli esiti veri**, non le percentuali dei fascicoli: quanto è costata ogni previsione,
   quanto ha reso, il saldo dall'inizio.
4. **Dire la verità sulle probabilità**, con il backtest a supporto, invece di alimentare l'illusione.

Un'app che fa questo è utile e onesta. Un'app che promette il 97% è un volantino digitale con una
schermata più bella — e i volantini li abbiamo appena letti tutti.
