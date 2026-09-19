/**
 * App Lotto — la pagina.
 *
 * Tutto quello che si vede, tranne il simulatore di schedina, arriva gia'
 * calcolato da dati/*.json: e' il motore Python che li riscrive ogni sera e
 * GitHub che li pubblica. Qui non c'e' nessuna logica di Lotto - se un giorno
 * un numero non torna, la risposta sta in motore/, non in questo file.
 */
import { simula, combinazioni, GiocataNonValida, NUMERI_PER_SORTE }
  from './schedina.js';
import {
  componi, convergenze, riepilogo, etichettaGiocata, perRuota, SOGLIA_RESA,
  numeriInComune, previsioneUnica, primoGiornoUtile, proiettaConcorsi,
} from './consiglio.js';
import {
  leggiStorico, leggiPrevisioni, previsioniDi, estrazione, quadro,
  concorsoVicino, verifica, usciteDi,
} from './storico.js';
import { trasformazioni, gruppi, insieme } from './derivati.js';
import {
  righe as righeElenco, filtra as filtraElenco, conteggio, pagina, presenti,
  csv, ESITI, giorni as giorniElenco, giornoVicino, usciti as usciteRuota,
} from './elenco.js';

const NOMI_RUOTE = {
  BA: 'Bari', CA: 'Cagliari', FI: 'Firenze', GE: 'Genova', MI: 'Milano',
  NA: 'Napoli', PA: 'Palermo', RM: 'Roma', TO: 'Torino', VE: 'Venezia',
};
const SORTI = Object.entries(NUMERI_PER_SORTE);
const MAX_NUMERI = 10;

const giocata = { numeri: new Set(), ruote: new Set(['NA']), sorti: new Set(['ambo']), importo: 5 };
let quote = null, suggerite = [], attesaSimula = null;
// I nomi per esteso dei sei metodi arrivano da dati/stato.json: stanno in un
// posto solo, motore/pubblica.py, e non vanno ricopiati qui.
let NOMI_METODI = {};

/* ------------------------------------------------------------- formattazione */
const euro = n => n.toLocaleString('it-IT', {
  style: 'currency', currency: 'EUR',
  minimumFractionDigits: Math.abs(n) < 100 ? 2 : 0,
  maximumFractionDigits: Math.abs(n) < 100 ? 2 : 0,
});
const numero = n => n.toLocaleString('it-IT');
const dataIt = s => new Date(s + 'T00:00:00')
  .toLocaleDateString('it-IT', { day: 'numeric', month: 'long', year: 'numeric' });
const dataBreve = s => new Date(s + 'T00:00:00')
  .toLocaleDateString('it-IT', { weekday: 'short', day: 'numeric', month: 'short' });
// Nella scheda Previsioni si guardano concorsi di trent'anni fa: senza l'anno
// "sab 1 lug" sembra la settimana scorsa, ed e' il 2017.
const dataConAnno = s => new Date(s + 'T00:00:00')
  .toLocaleDateString('it-IT', { day: 'numeric', month: 'short', year: 'numeric' });
// sotto il migliaio il decimale conta: l'ambo secco e' 1 su 400,5, e
// arrotondarlo a 400 e' mezzo punto di errore su quattrocento
const unaSu = p => p ? `1 su ${(1 / p).toLocaleString('it-IT',
  { maximumFractionDigits: 1 / p < 1000 ? 1 : 0 })}` : '—';
// in italiano il separatore decimale e' la virgola: "67,7%", non "67.7%"
const percento = (v, dec = 1) => (v * 100).toLocaleString('it-IT',
  { minimumFractionDigits: dec, maximumFractionDigits: dec }) + '%';
const percentuale = p => p >= 0.01
  ? ` (${(p * 100).toLocaleString('it-IT', { maximumFractionDigits: 1 })}%)` : '';
const giorniDa = iso => Math.round(
  (new Date(iso + 'T00:00:00') - new Date(new Date().toDateString())) / 864e5);

async function prendi(nome) {
  // la marca temporale evita che il browser mostri i dati di ieri presi dalla
  // cache: il file cambia ogni sera ma l'indirizzo resta lo stesso
  const r = await fetch(`dati/${nome}?v=${Date.now()}`);
  if (!r.ok) throw new Error(`dati/${nome} → ${r.status}`);
  return r.json();
}

/* ------------------------------------------------------------- intestazione */
function mostraStato(s) {
  NOMI_METODI = s.metodi ?? {};
  const giorni = -giorniDa(s.ultima_estrazione);
  document.getElementById('stato').innerHTML =
    `${numero(s.concorsi)} concorsi in archivio · ultimo del ${dataIt(s.ultima_estrazione)}`
    + (giorni > 4 ? ` <span class="allarme">(${giorni} giorni fa: archivio arretrato)</span>` : '')
    + ` · ${numero(s.previsioni)} previsioni`;

  const quando = new Date(s.aggiornato_il);
  const ore = Math.round((Date.now() - quando) / 36e5);
  document.getElementById('aggiornamento').innerHTML =
    `Dati aggiornati ${quando.toLocaleString('it-IT',
      { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}`
    + (ore > 30 ? ` <span class="allarme">(${Math.round(ore / 24)} giorni fa)</span>` : '');

  document.getElementById('sorgente').textContent =
    `Archivio dal ${dataIt(s.prima_estrazione)}. Numeri in ordine di estrazione `
    + `(quota di quadri già crescenti ${percento(s.quota_crescenti, 2)}, `
    + `attesa dal caso 0,83%): i metodi che filtrano per posizione sono applicabili.`;
}

/* ------------------------------------------------------------- in corso */
function schedaPrevisione(p) {
  return `
    <article class="carta">
      <div class="riga">
        <div>
          <div class="meta">${dataIt(p.giorno)} · ${p.ruote.map(r => NOMI_RUOTE[r] ?? r).join(' · ')}${
            p.anche_tutte ? ' · anche a Tutte' : ''}${p.nota ? ' · ' + p.nota : ''}</div>
        </div>
        <div class="colpi"><b>${p.colpi_residui}</b> colpi su ${p.colpi}</div>
      </div>
      ${p.sorti.map(s => `
        <div class="sorte">
          <span class="tipo">${s.tipo}</span>
          ${s.numeri.map(n => `<span class="n">${n}</span>`).join('')}
        </div>`).join('')}
      ${p.avviso ? `<div class="avviso">${p.avviso}</div>` : ''}
    </article>`;
}

function mostraInCorso(lista) {
  const c = document.getElementById('corso');
  if (!lista.length) {
    c.innerHTML = `<p class="vuoto">Nessuna previsione ancora in gioco.<br>
      Le nuove compaiono la sera stessa dell'estrazione.</p>`;
    return;
  }
  // Raggruppate per metodo, e i gruppi nell'ordine in cui arrivano dal server:
  // dal metodo che scatta piu' di rado a quello che scatta piu' spesso. Un
  // elenco piatto di sessanta schede, tutte uguali, e' illeggibile - e nasconde
  // proprio la previsione rara, che e' quella per cui vale la pena guardare.
  const gruppi = new Map();
  for (const p of lista) {
    if (!gruppi.has(p.metodo)) gruppi.set(p.metodo, []);
    gruppi.get(p.metodo).push(p);
  }
  const SOGLIA_APERTO = 5;     // oltre questo numero il gruppo parte chiuso
  c.innerHTML = [...gruppi.values()].map(g => {
    const p = g[0];
    return `
      <details class="gruppo"${g.length <= SOGLIA_APERTO ? ' open' : ''}>
        <summary>
          <span class="metodo">${p.nome_metodo}</span>
          ${p.per_anno ? `<span class="rarita">scatta ${p.per_anno} volte l'anno</span>` : ''}
          <span class="conta">${g.length} in corso</span>
        </summary>
        ${g.map(schedaPrevisione).join('')}
      </details>`;
  }).join('')
    + `<p class="avvertenza">I gruppi sono ordinati dal metodo che scatta più di
       rado a quello che scatta più spesso, non per data: un metodo che produce
       mille rilevamenti l'anno e uno che ne produce ottanta non meritano lo
       stesso spazio solo perché sono usciti lo stesso giorno. I gruppi più
       affollati partono chiusi — si aprono con un clic.</p>`;
}

/* ------------------------------------------------------------- stasera
   Il consiglio per il concorso in arrivo. Il ragionamento (quali giocate, in
   che ordine, quanto costano, quanto rendono) sta in consiglio.js, che non
   tocca la pagina e si puo' provare con Node. Qui resta solo il disegno. */
let inCorso = [], calendario = null, resePerMetodo = {};

const SCELTE_BUDGET = [5, 10, 20, 50];

/** "a, b e c" — come lo scriverebbe una persona, non "a, b, c". */
const elenco = v => v.length < 2 ? (v[0] ?? '')
  : `${v.slice(0, -1).join(', ')} e ${v[v.length - 1]}`;

/** Quanto manca al concorso, detto come lo direbbe una persona. */
function attesa(giornoIso, ora) {
  const [h, m] = (ora ?? '20:00').split(':').map(Number);
  const quando = new Date(giornoIso + 'T00:00:00');
  quando.setHours(h, m, 0, 0);
  const minuti = Math.round((quando - Date.now()) / 60000);
  if (minuti <= 0) return 'è in corso';
  if (minuti < 60) return `è fra ${minuti} minut${minuti === 1 ? 'o' : 'i'}`;
  const ore = Math.round(minuti / 60);
  if (ore < 20) return `è fra ${ore} or${ore === 1 ? 'a' : 'e'}`;
  const giorni = giorniDa(giornoIso);
  return giorni === 1 ? 'è domani' : `è fra ${giorni} giorni`;
}

function mostraConcorso() {
  const box = document.getElementById('concorso');
  if (!calendario?.date?.length) {
    box.innerHTML = `<p class="quando">Non riesco a leggere il calendario
      delle estrazioni.</p>`;
    return;
  }
  const [prima, ...poi] = calendario.date;
  const giorno = new Date(prima + 'T00:00:00')
    .toLocaleDateString('it-IT', { weekday: 'long', day: 'numeric', month: 'long' });
  box.innerHTML = `
    <p class="quando">Il prossimo concorso <em>${attesa(prima, calendario.ora)}</em>.</p>
    <p class="data">${giorno}, alle ${calendario.ora}${
      calendario.stimato ? ' — data proiettata dal calendario recente' : ''}</p>
    ${poi.length ? `<p class="poi">Poi si gioca ${elenco(poi.map(d =>
      new Date(d + 'T00:00:00').toLocaleDateString('it-IT',
        { weekday: 'long', day: 'numeric', month: 'long' })))}.</p>` : ''}`;
}

/** La riga di una giocata. `conMetodo` decide che cosa scrivere sotto i numeri:
 *  nella vista per metodo serve sapere le ruote, in quella per ruota il metodo. */
function rigaGiocata(g, resaMigliore, conRuote = true) {
  const magra = g.resa < resaMigliore - SOGLIA_RESA;
  return `
    <div class="giocata${magra ? ' magra' : ''}">
      <span class="tipo-giocata">${etichettaGiocata(g)}</span>
      <span class="numeri">${g.numeri.map(n => `<span class="n">${n}</span>`).join('')}</span>
      <span class="sotto">
        <span class="dove">${conRuote
          ? 'su ' + elenco(g.ruote.map(r => NOMI_RUOTE[r] ?? r))
          : (g.altre?.length
              ? 'prevista anche su ' + elenco(g.altre.map(r => NOMI_RUOTE[r] ?? r))
              : 'solo su questa ruota')}</span>
        ${g.colpi_residui === 1 ? '<span class="ultimo">ultimo colpo</span>' : ''}
        ${magra ? `<span class="rende-meno">rende ${Math.round(g.resa * 100)}
          centesimi per euro</span>` : ''}
      </span>
      <span class="costo">${euro(g.costo)}</span>
    </div>`;
}

function raggruppaPerMetodo(giocate) {
  const gruppi = new Map();
  for (const g of giocate) {
    if (!gruppi.has(g.previsione.metodo)) gruppi.set(g.previsione.metodo, []);
    gruppi.get(g.previsione.metodo).push(g);
  }
  return gruppi;
}

/* ---------------------------------------------------- le ruote del concorso */
let ruotaScelta = null;

function mostraRuote() {
  const sezione = document.getElementById('ruote-giorno');
  if (!quote || !inCorso.length) { sezione.hidden = true; return; }
  sezione.hidden = false;

  const mappa = perRuota(inCorso, quote);
  if (!mappa.has(ruotaScelta)) {
    // si parte dalla ruota con piu' giocate: una sezione che si apre vuota
    // costringe a un clic per capire se c'e' qualcosa
    ruotaScelta = [...mappa.entries()]
      .sort((a, b) => b[1].length - a[1].length)[0]?.[0] ?? null;
  }

  document.getElementById('scelta-ruota').innerHTML =
    Object.entries(NOMI_RUOTE).map(([sigla, nome]) => {
      const n = mappa.get(sigla)?.length ?? 0;
      return `<button type="button" data-r="${sigla}" ${n ? '' : 'disabled'}
        aria-pressed="${sigla === ruotaScelta}">${nome}
        ${n ? `<span class="quante">${n}</span>` : ''}</button>`;
    }).join('');

  const giocate = mappa.get(ruotaScelta) ?? [];
  const fuori = document.getElementById('giocate-ruota');
  if (!giocate.length) {
    fuori.innerHTML = `<p class="scelta-ruota-vuota">Su questa ruota non c'è
      niente in gioco per il prossimo concorso.</p>`;
    return;
  }

  const { speso, attesa: resa, qualcosa, per_euro } = riepilogo(giocate);
  const resaMigliore = Math.max(...giocate.map(g => g.resa));
  fuori.innerHTML = `
    <div class="riepilogo" style="margin-top:16px">
      <div><span class="cifra">${euro(speso)}</span>
        <span class="glossa">${giocate.length} giocate su
          ${NOMI_RUOTE[ruotaScelta]}, un euro l'una</span></div>
      <div><span class="cifra">${qualcosa >= 0.01 ? percento(qualcosa, 0) : unaSu(qualcosa)}</span>
        <span class="glossa">la probabilità di vincere qualcosa giocandole
          tutte: circa ${unaSu(qualcosa)} volte</span></div>
      <div><span class="cifra perde">${euro(resa)}</span>
        <span class="glossa">quanto torna indietro in media:
          ${Math.round(per_euro * 100)} centesimi per ogni euro</span></div>
    </div>
    ${[...raggruppaPerMetodo(giocate).values()].map(gruppo => {
      const p = gruppo[0].previsione;
      return `
      <details class="gruppo"${gruppo.length <= 6 ? ' open' : ''}>
        <summary>
          <span class="metodo">${p.nome_metodo}</span>
          <span class="rarita">scatta ${p.per_anno} volte l'anno</span>
          <span class="conta">${gruppo.length} giocat${gruppo.length === 1 ? 'a' : 'e'}
            · ${euro(gruppo.length)}</span>
        </summary>
        ${gruppo.map(g => rigaGiocata(g, resaMigliore, false)).join('')}
      </details>`;
    }).join('')}`;
}

function costruisciRuote() {
  document.getElementById('scelta-ruota').onclick = e => {
    const b = e.target.closest('button[data-r]');
    if (!b || b.disabled) return;
    ruotaScelta = b.dataset.r;
    mostraRuote();
  };
}

function costruisciBudget() {
  const box = document.getElementById('scelte-budget');
  box.innerHTML = SCELTE_BUDGET.map(v =>
    `<button type="button" data-v="${v}" aria-pressed="false">${v} €</button>`).join('');
  box.onclick = e => {
    const b = e.target.closest('button[data-v]');
    if (!b) return;
    document.getElementById('budget').value = b.dataset.v;
    mostraConsiglio();
  };
  document.getElementById('budget').oninput = mostraConsiglio;
}

function mostraConsiglio() {
  const fuoriBox = document.getElementById('consiglio');
  const budget = Number(document.getElementById('budget').value);
  for (const b of document.querySelectorAll('#scelte-budget button'))
    b.setAttribute('aria-pressed', String(Number(b.dataset.v) === budget));

  if (!quote || !inCorso.length) {
    fuoriBox.innerHTML = `<p class="vuoto">Nessuna previsione in gioco per il
      prossimo concorso. Le nuove compaiono la sera stessa dell'estrazione.</p>`;
    return;
  }
  if (!(budget > 0)) {
    fuoriBox.innerHTML = `<p class="vuoto">Scrivi quanto vuoi spendere.</p>`;
    return;
  }

  const { dentro, fuori, speso, mancano } = componi(inCorso, budget, quote);
  document.getElementById('nota-budget').textContent =
    `Coprire tutte le previsioni in gioco costerebbe ${euro(speso + mancano)}.`;

  if (!dentro.length) {
    const minimo = Math.min(...fuori.map(g => g.costo));
    fuoriBox.innerHTML = `<p class="vuoto">Con ${euro(budget)} non entra nessuna
      giocata: la più economica ne costa ${euro(minimo)}, perché va giocata su
      ${minimo} ruote.</p>`;
    return;
  }

  const { attesa: resa, qualcosa, per_euro } = riepilogo(dentro);
  const resaMigliore = Math.max(...dentro.map(g => g.resa));
  const conv = convergenze(dentro);

  const gruppi = raggruppaPerMetodo(dentro);

  // Niente bollino "consigliata" su venticinque righe su trenta: sarebbe rumore.
  // Si segnala l'eccezione, cioe' le poche righe che rendono meno delle altre.
  const riga = g => rigaGiocata(g, resaMigliore);

  fuoriBox.innerHTML = `
    <div class="riepilogo">
      <div><span class="cifra">${euro(speso)}</span>
        <span class="glossa">${dentro.length} giocate, da
          ${gruppi.size} metod${gruppi.size === 1 ? 'o' : 'i'}</span></div>
      <div><span class="cifra">${qualcosa >= 0.01 ? percento(qualcosa, 0) : unaSu(qualcosa)}</span>
        <span class="glossa">la probabilità di vincere qualcosa: circa
          ${unaSu(qualcosa)} giocate come questa</span></div>
      <div><span class="cifra perde">${euro(resa)}</span>
        <span class="glossa">quanto torna indietro in media:
          ${Math.round(per_euro * 100)} centesimi per ogni euro</span></div>
    </div>

    ${[...gruppi.values()].map(g => {
      const p = g[0].previsione;
      const resaStorica = resePerMetodo[p.metodo];
      return `
      <section class="metodo-blocco">
        <h3>${p.nome_metodo}</h3>
        <p class="quanto">Scatta ${p.per_anno} volte l'anno${
          resaStorica != null
            ? `, e finora ha restituito ${percento(resaStorica, 0)} di quanto è costato`
            : ''}.</p>
        ${g.map(riga).join('')}
      </section>`;
    }).join('')}

    ${conv.length ? `<div class="convergenze">
      <span class="testo">Numeri chiesti da più previsioni:</span>
      ${conv.slice(0, 10).map(c => `<span class="n">${c.numero}</span>`).join('')}
    </div>
    <p class="fuori">Non li rende più probabili: significa che coprendoli si
      soddisfano più previsioni con meno giocate distinte.</p>` : ''}

    ${fuori.length ? `<p class="fuori">Restano fuori ${fuori.length} giocate,
      per altri ${euro(mancano)}. Le trovi tutte nella scheda
      <b>In corso</b>.</p>` : ''}

    <p class="avvertenza">Le giocate sono in ordine di rarità del metodo: prima
      quelle che capitano poche volte l'anno, perché sono la ragione per cui i
      metodi sono sei e non uno. A parità di metodo viene prima ciò che scade
      prima, e prima la sorte che rende di più — così, se il budget taglia,
      taglia i terni e non gli ambi.<br><br>
      <b>Sui numeri non c'è nessun consiglio da dare, e non è una reticenza.</b>
      Nel Lotto le quote sono fissate per legge e la probabilità è la stessa per
      qualunque combinazione: il ritorno atteso di questa giocata sarebbe
      identico con numeri scelti a caso. Le uniche scelte che cambiano qualcosa
      sono quante ne giochi, su quante ruote, e per quale sorte — ed è su quelle
      che questa pagina lavora.</p>`;
}

/* ------------------------------------------------ i numeri in comune
   Vive fuori dalle schede, sopra il piede: e' una lettura trasversale di tutte
   le previsioni in gioco, non appartiene a nessuna delle quattro viste. */
function mostraComuni() {
  const sezione = document.getElementById('comuni');
  if (!quote || !inCorso.length) { sezione.hidden = true; return; }

  const comuni = numeriInComune(inCorso);
  if (!comuni.length) {
    sezione.hidden = false;
    document.getElementById('comuni-spiega').textContent =
      'In questo momento nessun numero è chiesto da più di un metodo: '
      + 'le previsioni in gioco non si sovrappongono.';
    document.getElementById('comuni-numeri').innerHTML = '';
    document.getElementById('comuni-giocata').innerHTML = '';
    return;
  }
  sezione.hidden = false;

  const quantiMetodi = new Set(inCorso.map(p => p.metodo)).size;
  document.getElementById('comuni-spiega').innerHTML =
    `Dei ${quantiMetodi} metodi che hanno qualcosa in gioco, questi numeri sono
     chiesti da più d'uno contemporaneamente. Non li rende più probabili — il
     Lotto non ha memoria — ma coprirli soddisfa molte previsioni con poche
     giocate.`;

  document.getElementById('comuni-numeri').innerHTML = `
    <div class="elenco">
      ${comuni.slice(0, 12).map(c => `
        <div class="voce">
          <div class="capo">
            <span class="cifra-numero">${c.numero}</span>
            <span class="quanti">${c.metodi} metodi</span>
          </div>
          <span class="dettaglio">${c.previsioni} prevision${
            c.previsioni === 1 ? 'e' : 'i'}, su ${elenco(c.ruote.slice(0, 3)
              .map(r => NOMI_RUOTE[r.ruota] ?? r.ruota))}</span>
        </div>`).join('')}
    </div>`;

  const unica = previsioneUnica(comuni);
  const fuori = document.getElementById('comuni-giocata');
  if (!unica) { fuori.innerHTML = ''; return; }

  let conti = null;
  try {
    conti = simula({
      numeri: unica.numeri, ruote: [unica.ruota], sorti: ['ambo'],
      importo: combinazioni(unica.numeri.length, 2), quote,
    });
  } catch { /* una giocata impossibile non deve far sparire la sezione */ }

  fuori.innerHTML = `
    <div class="giocata-unica">
      <h3>La previsione unica</h3>
      <p class="conti">I ${unica.numeri.length} numeri più richiesti, giocati per
        ambo su ${NOMI_RUOTE[unica.ruota] ?? unica.ruota} — la ruota su cui
        questo gruppo è chiesto più spesso.</p>
      <div class="numeri">${unica.numeri.map(n => `<span class="n">${n}</span>`).join('')}</div>
      ${conti ? `<p class="conti">Sono ${conti.righe[0].combinazioni} ambi. A un euro
        l'uno costano ${euro(conti.importo)}, e uno di essi esce
        ${unaSu(conti.qualcosaPerRuota)} volte${percentuale(conti.qualcosaPerRuota)}.
        Ne tornano indietro ${euro(conti.ritornoAtteso)} in media, come per
        qualunque altra giocata di ambo.</p>` : ''}
      <p class="conti">I sei metodi non sono sei pareri indipendenti: le loro
        condizioni di ricerca si riducono a tre, e due metodi che ne condividono
        una concordano anche per costruzione. Per questo qui si contano i
        <b>metodi</b> e non le previsioni — due previsioni dello stesso metodo
        non sono due pareri.</p>
    </div>`;
}

/* ------------------------------- che cosa avrebbero detto i metodi */
/* Un concorso del passato, e tre risposte:
 *   1. i cinque numeri usciti sulla ruota scelta;
 *   2. le previsioni che i sei metodi hanno rilevato quel giorno — non
 *      ricalcolate qui, ma lette dai file che motore/storia.py scrive con lo
 *      stesso motore che gira ogni sera: due implementazioni della stessa cosa
 *      divergono sempre, e il giorno in cui divergono nessuno se ne accorge;
 *   3. su quali ruote quei numeri sono poi usciti davvero.
 * L'archivio e il file dell'anno si scaricano solo aprendo questa scheda. */
let storico = null, inArrivo = null, indiceAnni = null;
const anniInMemoria = new Map();

async function prendiStorico() {
  if (storico) return storico;
  if (!inArrivo) inArrivo = fetch(`dati/storico.txt?v=${Date.now()}`)
    .then(r => { if (!r.ok) throw new Error(`storico.txt → ${r.status}`); return r.text(); })
    .then(t => { storico = leggiStorico(t); return storico; })
    .catch(e => { inArrivo = null; throw e; });
  return inArrivo;
}

async function prendiAnno(anno) {
  if (anniInMemoria.has(anno)) return anniInMemoria.get(anno);
  const p = fetch(`dati/previsioni/${anno}.txt?v=${Date.now()}`)
    .then(r => { if (!r.ok) throw new Error(`previsioni/${anno}.txt → ${r.status}`); return r.text(); })
    .then(leggiPrevisioni)
    .catch(e => { anniInMemoria.delete(anno); throw e; });
  anniInMemoria.set(anno, p);
  return p;
}

function costruisciRicerca() {
  document.getElementById('cerca').onclick = eseguiRicerca;
  document.getElementById('data-ricerca').onchange = aggiornaRuoteDelGiorno;
  document.getElementById('ruota-ricerca').onchange = aggiornaRuoteDelGiorno;
  document.getElementById('cerca').disabled = true;
}

function preparaRicerca() {
  const campo = document.getElementById('data-ricerca');
  const primo = storico.giorni[0], ultimo = storico.giorni.at(-1);
  campo.min = primo;
  campo.max = ultimo;
  const indietro = (anni) => {
    const d = new Date(ultimo + 'T00:00:00');
    d.setFullYear(d.getFullYear() - anni);
    return d.toISOString().slice(0, 10);
  };
  if (!campo.value) campo.value = concorsoVicino(storico, indietro(10));

  const scelte = [10, 20, 30, 40].filter(a => indietro(a) >= primo);
  document.getElementById('date-rapide').innerHTML =
    scelte.map(a => `<button type="button" data-anni="${a}">${a} anni fa</button>`).join('')
    + `<button type="button" data-giorno="${primo}">il primo concorso (${primo.slice(0, 4)})</button>`;
  for (const b of document.querySelectorAll('#date-rapide button')) {
    b.onclick = () => {
      campo.value = b.dataset.giorno ?? concorsoVicino(storico, indietro(Number(b.dataset.anni)));
      aggiornaRuoteDelGiorno();
    };
  }
  document.getElementById('cerca').disabled = false;
  aggiornaRuoteDelGiorno();
}

/** Mostra il concorso scelto e lascia scegliere solo fra le ruote che quel
 *  giorno hanno davvero estratto. */
function aggiornaRuoteDelGiorno() {
  if (!storico) return;
  const campo = document.getElementById('data-ricerca');
  const scelta = document.getElementById('ruota-ricerca');
  const nota = document.getElementById('nota-data');
  if (!campo.value) { nota.textContent = ''; return; }

  const giorno = concorsoVicino(storico, campo.value);
  const spostata = giorno !== campo.value;
  if (spostata) campo.value = giorno;

  const q = quadro(storico, giorno) ?? {};
  const disponibili = Object.keys(q);
  const prima = scelta.value;
  scelta.innerHTML = disponibili
    .map(r => `<option value="${r}">${NOMI_RUOTE[r]}</option>`).join('');
  scelta.value = disponibili.includes(prima) ? prima
    : (disponibili.includes('NA') ? 'NA' : disponibili[0] ?? '');

  const numeri = q[scelta.value];
  nota.innerHTML = (spostata
    ? `Quel giorno non c'era concorso: il più vicino è <b>${dataIt(giorno)}</b>. `
    : `<b>${dataIt(giorno)}</b>. `)
    + (numeri
      ? `Su ${NOMI_RUOTE[scelta.value]} uscirono ${numeri.join(' · ')}.`
      : 'Nessuna ruota ha estratto in questo giorno.');
  document.getElementById('cerca').disabled = !numeri;
}

async function eseguiRicerca() {
  const avviso = document.getElementById('stato-ricerca');
  const bottone = document.getElementById('cerca');
  const giorno = document.getElementById('data-ricerca').value;
  const ruota = document.getElementById('ruota-ricerca').value;
  if (!giorno || !ruota) return;

  bottone.disabled = true;
  avviso.textContent = 'cerco…';
  try {
    const previsioni = await prendiAnno(giorno.slice(0, 4));
    avviso.textContent = '';
    mostraConcorsoPassato(giorno, ruota, previsioni);
  } catch (e) {
    avviso.textContent = `Non riesco a leggere le previsioni di quell'anno: ${e.message}`;
  } finally {
    bottone.disabled = false;
  }
}

const ESITO = {
  vinta: { parola: 'si è verificata', classe: 'pos' },
  scaduta: { parola: 'scaduta senza esito', classe: 'neg' },
  aperta: { parola: 'colpi non ancora finiti', classe: '' },
};

function rigaUscita(e) {
  return `<li class="${e.a_tutte ? 'a-tutte' : ''}">
    <span class="colpo">${e.colpo}° colpo</span>
    <span class="quando">${dataConAnno(e.giorno)}</span>
    <span class="dove">${NOMI_RUOTE[e.ruota] ?? e.ruota}</span>
    <span class="numeri">${e.usciti.map(n => `<b>${n}</b>`).join(' ')}</span>
    ${e.a_tutte ? '<span class="postilla">solo perché vale anche a Tutte</span>' : ''}
  </li>`;
}

function schedaPassata(p, ruotaScelta) {
  const nome = NOMI_METODI[p.metodo] ?? p.metodo;
  const sua = p.ruote.includes(ruotaScelta);
  return `
    <article class="carta passata ${sua ? 'sua' : ''}">
      <div class="riga">
        <div>
          <div class="metodo">${nome}</div>
          <div class="meta">${p.ruote.map(r => NOMI_RUOTE[r] ?? r).join(' · ')}${
            p.anche_tutte ? ' · anche a Tutte' : ''}${p.nota ? ' · ' + p.nota : ''}</div>
        </div>
        <div class="colpi">${p.colpi} colpi</div>
      </div>
      ${p.avviso ? `<div class="avviso">${p.avviso}</div>` : ''}
      ${p.sorti.map(s => `
        <div class="sorte-esito">
          <div class="capo">
            <span class="tipo">${s.tipo}</span>
            ${s.numeri.map(n => `<span class="n">${n}</span>`).join('')}
            <span class="come-finita ${ESITO[s.stato].classe}">${ESITO[s.stato].parola}</span>
          </div>
          ${s.esiti.length ? `<ul class="uscite">${s.esiti.map(rigaUscita).join('')}</ul>` : ''}
          ${!s.esiti.length && s.altrove.length ? `
            <details class="altrove">
              <summary>nessuna uscita sulle ruote di gioco, ma ${s.altrove.length}
                su altre ruote</summary>
              <ul class="uscite">${s.altrove.map(rigaUscita).join('')}</ul>
            </details>` : ''}
          ${s.oltre ? `<p class="oltre">Fuori giocata: sarebbe uscita il
            ${dataConAnno(s.oltre.giorno)} su ${NOMI_RUOTE[s.oltre.ruota]}
            (${s.oltre.usciti.join(' e ')}) — ${s.oltre.colpo - p.colpi} concorsi
            dopo la scadenza, quindi a giocata chiusa.</p>` : ''}
        </div>`).join('')}
    </article>`;
}

function mostraConcorsoPassato(giorno, ruota, previsioni) {
  const fuori = document.getElementById('esito-ricerca');
  const numeri = estrazione(storico, giorno, ruota);
  if (!numeri) { fuori.innerHTML = ''; return; }

  const delGiorno = previsioniDi(previsioni, giorno, ruota).map(p => verifica(storico, p));
  const sue = delGiorno.filter(p => p.ruote.includes(ruota));
  const altre = delGiorno.filter(p => !p.ruote.includes(ruota));
  const vinte = sue.reduce((n, p) => n + p.sorti.filter(s => s.stato === 'vinta').length, 0);
  const sorti = sue.reduce((n, p) => n + p.sorti.length, 0);

  // I numeri derivati: le formule dei metodi applicate comunque ai cinque
  // numeri. Vanno in un blocco a parte, e dichiarato, perche' non sono
  // previsioni: nessun fascicolo le prescrive senza la sua condizione.
  const derivati = insieme(numeri);
  const uscite = usciteDi(storico, derivati, giorno, { concorsi: 12 });
  const T = trasformazioni(numeri);
  const G = gruppi(numeri);

  fuori.innerHTML = `
    <div class="esito">
      <p class="partenza">Concorso del <b>${dataIt(giorno)}</b> su
        <b>${NOMI_RUOTE[ruota]}</b>:${numeri.map(n =>
          ` <span class="n">${n}</span>`).join('')}</p>

      <h3>Le previsioni di quel giorno</h3>
      ${sue.length ? `
        <p class="conti">I sei metodi hanno rilevato <b>${sue.length}</b>
          prevision${sue.length === 1 ? 'e' : 'i'} che
          ${sue.length === 1 ? 'tocca' : 'toccano'}
          ${NOMI_RUOTE[ruota]}, per un totale di ${sorti}
          sort${sorti === 1 ? 'e' : 'i'}: ${vinte === 0 ? 'nessuna si è verificata'
            : `${vinte} si ${vinte === 1 ? 'è' : 'sono'} verificat${vinte === 1 ? 'a' : 'e'}`}
          entro i colpi previsti.</p>
        ${sue.map(p => schedaPassata(p, ruota)).join('')}`
        : `<p class="nota">Quel giorno nessuna delle condizioni dei sei metodi è
           scattata su ${NOMI_RUOTE[ruota]}. Capita una volta su dieci: i metodi
           non cercano dei numeri, cercano una configurazione, e quasi sempre
           quella configurazione non c'è.</p>`}

      ${altre.length ? `
        <details class="altre-ruote">
          <summary>${altre.length} altre previsioni di quel giorno, su altre ruote</summary>
          ${altre.map(p => schedaPassata(p, ruota)).join('')}
        </details>` : ''}

      <h3>I numeri derivati dai cinque</h3>
      <p class="avvertenza"><b>Questi non sono previsioni.</b> I sei metodi non
        partono da cinque numeri: partono da una condizione su tutto il concorso
        — due ambi con la stessa somma, quattro numeri della stessa figura, un
        ambo diametrale — e solo quando quella scatta dicono che cosa giocare.
        Qui le loro formule sono applicate comunque ai numeri usciti, quindi
        viene sempre fuori qualcosa, per costruzione. Sono numeri derivati, ed è
        tutto quello che sono.</p>

      <div class="tabella-scroll">
        <table class="derivati">
          <thead><tr>
            <th>uscito</th><th>complemento</th><th>diametrale</th>
            <th>vertibile</th><th>terzina simmetrica</th><th>fig.</th><th>cad.</th>
          </tr></thead>
          <tbody>${T.map(r => `
            <tr>
              <td><b>${r.numero}</b></td>
              <td data-et="complemento">${r.complemento}</td>
              <td data-et="diametrale">${r.diametrale}</td>
              <td data-et="vertibile">${r.vertibile}</td>
              <td data-et="terzina">${r.terzina.join(' · ')}</td>
              <td data-et="figura">${r.figura}</td>
              <td data-et="cadenza">${r.cadenza}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>

      ${G.figure.length || G.cadenze.length ? `
        <p class="conti">${[
          ...G.figure.map(g => `di figura ${g.chiave}: ${g.numeri.join(', ')}`),
          ...G.cadenze.map(g => `di cadenza ${g.chiave}: ${g.numeri.join(', ')}`),
        ].join(' · ')}</p>` : ''}

      <h4>Dove sono usciti, nei dodici concorsi dopo</h4>
      <p class="conti">I ${derivati.length} numeri derivati, cercati su tutte e
        dieci le ruote nei dodici concorsi successivi al
        ${dataConAnno(giorno)}.</p>
      <ul class="derivati-uscite">
        ${uscite.map(u => `
          <li>
            <span class="cifra">${u.numero}</span>
            ${u.uscite.length ? `
              <span class="dove">${u.ruote.map(r => NOMI_RUOTE[r]).join(', ')}</span>
              <span class="quante">${u.uscite.length} volt${u.uscite.length === 1 ? 'a' : 'e'}
                · prima il ${dataConAnno(u.prima.giorno)} su ${NOMI_RUOTE[u.prima.ruota]}</span>`
              : '<span class="mai">mai uscito</span>'}
          </li>`).join('')}
      </ul>
      <p class="avvertenza">Un numero qualunque esce su una ruota qualunque circa
        una volta ogni diciotto concorsi: su dieci ruote e dodici concorsi ci si
        aspetta di trovarlo circa sei volte, e infatti si trova. Nessuno di questi
        conteggi dice niente sul concorso che verrà.</p>
    </div>`;
}

/* ------------------------------------------------- l'elenco di tutto */
/* Sedicimila righe l'anno, un milione e quattro in tutto l'archivio: non si
 * mostrano insieme, si filtrano e si sfogliano. Il conto degli esiti per un
 * anno intero e' qualche centinaio di millisecondi, quindi si fa una volta
 * sola quando cambia l'anno e poi si filtra su quello che e' gia' in memoria:
 * cambiare una tendina deve essere istantaneo. */
const NOMI_ESITO = {
  uscita: 'uscita', sospesa: 'sospesa', scaduta: 'scaduta senza esito',
  aperta: 'ancora in gioco',
};
const NOMI_TIPO = {
  ambata: 'ambata', ambo: 'ambo', terzina: 'terzina', quartina: 'quartina',
};
const PER_PAGINA = 100;

// Nella tabella il nome per esteso occupa mezza riga ("Ambo Secco Caotico —
// Antonio Longo"): qui basta la parte prima del trattino, che e' gia' unica
// fra i sei metodi.
const breve = m => (NOMI_METODI[m] ?? m).split(' — ')[0];

let elencoAnno = null, elencoRighe = [], elencoFiltrate = [], elencoPagina = 1;
let elencoGiorno = '', spostata = null, paginaCorrente = [];

const FILTRI = ['ruota-elenco', 'metodo-elenco', 'sorte-elenco', 'esito-elenco'];

function costruisciElenco() {
  document.getElementById('anno-elenco').onchange = cambiaAnnoElenco;
  for (const id of FILTRI)
    document.getElementById(id).onchange = () => { elencoPagina = 1; applicaFiltri(); };
  document.getElementById('scarica-elenco').onclick = scaricaElenco;
  document.getElementById('data-elenco').onchange = cambiaGiornoElenco;
  bloccaFiltri();
}

/** Il campo data: si sceglie il concorso preciso invece di cercarselo dentro
 *  sedicimila righe d'annata. Se la data cade in un altro anno si carica
 *  quell'anno da solo, e se quel giorno non c'era concorso scatta al piu'
 *  vicino e lo dice, invece di mostrare un elenco vuoto. */
async function cambiaGiornoElenco() {
  const campo = document.getElementById('data-elenco');
  const scelta = campo.value;
  // Se il campo ci ridice la data su cui ci eravamo gia' spostati, la
  // spiegazione dello spostamento non va cancellata: e' lo stesso concorso.
  if (scelta && scelta === elencoGiorno) return;
  spostata = null;
  if (!scelta) { elencoGiorno = ''; elencoPagina = 1; applicaFiltri(); return; }

  const anno = scelta.slice(0, 4);
  if (anno !== elencoAnno) {
    const tendina = document.getElementById('anno-elenco');
    if (![...tendina.options].some(o => o.value === anno)) {
      document.getElementById('stato-elenco').textContent =
        `Il ${anno} non è fra gli anni disponibili.`;
      return;
    }
    tendina.value = anno;
    await cambiaAnnoElenco({ tieniIlGiorno: true });
    if (elencoAnno !== anno) return;        // il caricamento e' fallito
  }
  const vicino = giornoVicino(elencoRighe, scelta);
  elencoGiorno = vicino ?? '';
  // se quel giorno non si e' estratto si scatta al concorso piu' vicino, ma
  // va detto: se no sembra che la data scelta sia stata ignorata
  spostata = Boolean(vicino) && vicino !== scelta ? scelta : null;
  if (vicino) campo.value = vicino;
  elencoPagina = 1;
  applicaFiltri();
}

/** Finche' non si sceglie un anno le tendine non hanno niente dentro, e una
 *  tendina vuota ma cliccabile sembra un programma rotto: meglio spenta e con
 *  scritto perche'. */
function bloccaFiltri(testo = 'scegli sopra') {
  for (const id of FILTRI) {
    const s = document.getElementById(id);
    s.innerHTML = `<option value="">${testo}</option>`;
    s.disabled = true;
  }
  // il campo data NON si spegne: e' la porta d'ingresso della sezione, e l'anno
  // lo porta gia' dentro. Chiedere l'anno prima di una data che contiene l'anno
  // sarebbe far pagare a chi legge un dettaglio nostro (i dati stanno in un
  // file per anno).
  document.getElementById('rapidi-elenco').innerHTML = '';
}

/** Riempie la tendina degli anni dall'indice pubblicato. */
function preparaElenco() {
  const scelta = document.getElementById('anno-elenco');
  const anni = Object.entries(indiceAnni?.anni ?? {})
    .filter(([, quante]) => quante > 0)
    .map(([a]) => a)
    .sort((a, b) => b.localeCompare(a));
  if (!anni.length) {
    document.getElementById('stato-elenco').textContent =
      'L\'indice degli anni non è disponibile.';
    return;
  }
  scelta.innerHTML = '<option value="">scegli un anno…</option>'
    + anni.map(a => `<option value="${a}">${a}</option>`).join('');
  const campo = document.getElementById('data-elenco');
  campo.min = storico.giorni[0];
  campo.max = storico.giorni.at(-1);
  campo.disabled = false;

  document.getElementById('stato-elenco').textContent =
    'Metti una data e vedi quel concorso, oppure scegli un anno intero: '
    + `ce ne sono ${anni.length}, dal ${anni.at(-1)} a oggi. `
    + 'Gli altri filtri si riempiono da soli.';
}

async function cambiaAnnoElenco({ tieniIlGiorno = false } = {}) {
  const anno = document.getElementById('anno-elenco').value;
  const avviso = document.getElementById('stato-elenco');
  if (!anno) return;
  if (!tieniIlGiorno) {
    // scegliere un anno vuol dire "fammi vedere l'anno": la data di prima
    // resterebbe appiccicata e mostrerebbe un solo concorso senza spiegazione
    elencoGiorno = '';
    spostata = null;
    document.getElementById('data-elenco').value = '';
  }
  avviso.textContent = `sto leggendo il ${anno}…`;
  svuotaElenco();
  bloccaFiltri('un momento…');
  try {
    const previsioni = await prendiAnno(anno);
    // un respiro prima del conto, se no il browser non ridisegna l'avviso
    await new Promise(r => setTimeout(r, 0));
    elencoAnno = anno;
    elencoRighe = righeElenco(storico, previsioni);
    riempiFiltri();
    preparaGiorni();
    elencoPagina = 1;
    applicaFiltri();
  } catch (e) {
    avviso.textContent = `Non riesco a leggere il ${anno}: ${e.message}`;
    bloccaFiltri();
  }
}

/** Limiti del campo data e i due tasti sotto: primo e ultimo concorso
 *  dell'anno, e il ritorno a tutto l'anno. */
function preparaGiorni() {
  const g = giorniElenco(elencoRighe);
  if (!g.length) { document.getElementById('rapidi-elenco').innerHTML = ''; return; }
  // i limiti restano quelli di tutto l'archivio: restringerli all'anno caricato
  // impedirebbe di saltare a un altro anno scrivendo la data, che e' il modo
  // piu' veloce di arrivarci
  document.getElementById('rapidi-elenco').innerHTML = `
    <button type="button" data-giorno="">tutto l'anno</button>
    <button type="button" data-giorno="${g[0]}">primo concorso (${dataConAnno(g[0])})</button>
    <button type="button" data-giorno="${g.at(-1)}">ultimo (${dataConAnno(g.at(-1))})</button>`;
  for (const b of document.querySelectorAll('#rapidi-elenco button')) {
    b.onclick = () => {
      campo.value = b.dataset.giorno;
      cambiaGiornoElenco();
    };
  }
}

function svuotaElenco() {
  elencoRighe = []; elencoFiltrate = [];
  document.getElementById('tabella-elenco').innerHTML = '';
  document.getElementById('riassunto-elenco').innerHTML = '';
  document.getElementById('usciti-elenco').innerHTML = '';
  document.getElementById('paginatore').innerHTML = '';
  document.getElementById('scarica-elenco').hidden = true;
}

/** Le tendine offrono solo le voci che daranno un risultato. */
function riempiFiltri() {
  const p = presenti(elencoRighe);
  const opzioni = (voci, nomi) => '<option value="">tutte</option>'
    + voci.map(v => `<option value="${v}">${nomi[v] ?? v}</option>`).join('');
  const tieni = (id, html) => {
    const s = document.getElementById(id);
    const prima = s.value;
    s.innerHTML = html;
    s.value = [...s.options].some(o => o.value === prima) ? prima : '';
  };
  tieni('ruota-elenco', opzioni(p.ruote, NOMI_RUOTE));
  tieni('metodo-elenco', opzioni(p.metodi, NOMI_METODI));
  tieni('sorte-elenco', opzioni(p.tipi, NOMI_TIPO));
  tieni('esito-elenco', '<option value="">tutte</option>'
    + ESITI.map(e => `<option value="${e}">${NOMI_ESITO[e]}</option>`).join(''));
  for (const id of FILTRI) document.getElementById(id).disabled = false;
}

function applicaFiltri() {
  elencoFiltrate = filtraElenco(elencoRighe, {
    giorno: elencoGiorno,
    ruota: document.getElementById('ruota-elenco').value,
    metodo: document.getElementById('metodo-elenco').value,
    tipo: document.getElementById('sorte-elenco').value,
    esito: document.getElementById('esito-elenco').value,
  });
  mostraElenco();
}

function mostraElenco() {
  const c = conteggio(elencoFiltrate);
  const avviso = document.getElementById('stato-elenco');
  const tabella = document.getElementById('tabella-elenco');
  const riassunto = document.getElementById('riassunto-elenco');

  if (!elencoFiltrate.length) {
    avviso.textContent = elencoRighe.length
      ? (elencoGiorno
        ? `Nessuna riga il ${dataIt(elencoGiorno)} con questi filtri.`
        : 'Nessuna riga con questi filtri.')
      : `Il ${elencoAnno} non ha previsioni.`;
    tabella.innerHTML = '';
    riassunto.innerHTML = '';
    document.getElementById('usciti-elenco').innerHTML = '';
    document.getElementById('paginatore').innerHTML = '';
    document.getElementById('scarica-elenco').hidden = true;
    return;
  }

  avviso.textContent = spostata
    ? `Il ${dataIt(spostata)} non c'era concorso: ti mostro il ${dataIt(elencoGiorno)}.`
    : '';
  // Le voci a zero non si scrivono: "0 sospese (0,0%)" e' rumore, e quando si
  // filtra per un solo esito resterebbero tre zeri su quattro.
  const quota = n => c.totale ? ` (${percento(n / c.totale, 1)})` : '';
  const voci = [
    [c.uscita, `${numero(c.uscita)} uscite${quota(c.uscita)}`],
    [c.sospesa, `${numero(c.sospesa)} sospese perché la giocata si era già chiusa
       su un'altra ruota${quota(c.sospesa)}`],
    [c.scaduta, `${numero(c.scaduta)} scadute senza esito${quota(c.scaduta)}`],
    [c.aperta, `${numero(c.aperta)} ancora in gioco${quota(c.aperta)}`],
  ].filter(([n]) => n > 0).map(([, testo]) => testo);
  const dove = elencoGiorno
    ? `nel concorso del <b>${dataIt(elencoGiorno)}</b>`
    : `nel ${elencoAnno}`;
  riassunto.innerHTML = `
    <p class="conti"><b>${numero(c.totale)}</b> righe ${dove}${
      elencoFiltrate.length < elencoRighe.length
        ? ` (su ${numero(elencoRighe.length)} dell'anno)` : ''}${
      voci.length > 1 ? ': ' + elenco(voci) : ''}.</p>`;

  mostraUsciti();

  const P = pagina(elencoFiltrate, elencoPagina, PER_PAGINA);
  elencoPagina = P.numero;
  paginaCorrente = P.righe;
  tabella.innerHTML = `
    <thead><tr>
      <th>giorno</th><th>metodo</th><th>ruota</th><th>sorte</th>
      <th>numeri</th><th>com'è andata</th>
    </tr></thead>
    <tbody>${P.righe.map((r, i) => `
      <tr class="esito-${r.esito}" id="riga-${i}">
        <td>${dataConAnno(r.giorno)}</td>
        <td data-et="metodo">${breve(r.metodo)}</td>
        <td data-et="ruota">${NOMI_RUOTE[r.ruota] ?? r.ruota}</td>
        <td data-et="sorte">${r.tipo}</td>
        <td data-et="numeri" class="numeri">${r.numeri.join(' · ')}</td>
        <td data-et="com'è andata"><span class="andata">${
          descriviEsito({ ...r, indice: i })}</span></td>
      </tr>
      <tr class="dettaglio-riga" id="dett-${i}" hidden><td colspan="6"></td></tr>`).join('')}
    </tbody>`;

  // "un numero solo, 2 volte" e' una risposta a meta': la domanda dopo e'
  // sempre "quale numero, e dov'e' finito l'altro". Si apre sotto la riga.
  for (const b of tabella.querySelectorAll('button.sfiorata')) {
    b.onclick = () => {
      const i = Number(b.dataset.riga);
      const fila = document.getElementById(`dett-${i}`);
      const aperto = !fila.hidden;
      if (!aperto && !fila.firstElementChild.innerHTML)
        fila.firstElementChild.innerHTML = dettaglioSfiorata(paginaCorrente[i]);
      fila.hidden = aperto;
      b.setAttribute('aria-expanded', String(!aperto));
    };
  }

  document.getElementById('paginatore').innerHTML = P.pagine > 1 ? `
    <button type="button" data-va="1" ${P.numero === 1 ? 'disabled' : ''}>inizio</button>
    <button type="button" data-va="${P.numero - 1}" ${P.numero === 1 ? 'disabled' : ''}>‹ indietro</button>
    <span class="dove">righe ${numero(P.da)}–${numero(P.a)} di ${numero(c.totale)}
      · pagina ${P.numero} di ${P.pagine}</span>
    <button type="button" data-va="${P.numero + 1}" ${P.numero === P.pagine ? 'disabled' : ''}>avanti ›</button>
    <button type="button" data-va="${P.pagine}" ${P.numero === P.pagine ? 'disabled' : ''}>fine</button>`
    : `<span class="dove">${numero(c.totale)} righe in tutto</span>`;
  for (const b of document.querySelectorAll('#paginatore button')) {
    b.onclick = () => {
      elencoPagina = Number(b.dataset.va);
      mostraElenco();
      document.getElementById('elenco').scrollIntoView({ block: 'start' });
    };
  }

  const scarica = document.getElementById('scarica-elenco');
  scarica.hidden = false;
  scarica.textContent = `Scarica queste ${numero(c.totale)} righe in Excel`;
}

/** Ruota per ruota: di tutto quello che i metodi avevano dato, che cosa e'
 *  uscito. La tabella lo dice gia' riga per riga, ma per rispondere bisogna
 *  leggerne settanta: qui la risposta sta in tre righe. */
function mostraUsciti() {
  const fuori = document.getElementById('usciti-elenco');
  const per = usciteRuota(elencoFiltrate);
  if (!per.length) {
    fuori.innerHTML = elencoFiltrate.length
      ? `<p class="niente-uscito">Di tutti i numeri che i metodi avevano dato,
         ${elencoGiorno ? 'in quel concorso' : 'in questo elenco'} non ne è uscito
         nessuno — nemmeno da solo.</p>`
      : '';
    return;
  }

  // Il gettone e' un bottone: si clicca e porta alla riga che lo spiega. Il
  // colpo sta staccato dal numero e grande abbastanza da leggersi - attaccato
  // e in corpo minuscolo sembrava una macchia sul numero.
  const gettone = (x, classe, ruota) => `
    <button type="button" class="gettone ${classe}" data-ruota="${ruota}"
            data-numero="${x.numero}" data-gruppo="${classe}"
            title="vai alla riga di questo numero">
      <span class="cifra">${x.numero}</span>
      <span class="al-colpo">${x.colpo}° colpo</span>
    </button>`;

  fuori.innerHTML = `
    <div class="usciti">
      <h3>Che cosa è uscito, ruota per ruota</h3>
      ${per.map(u => `
        <div class="riga-ruota">
          <span class="nome-ruota">${NOMI_RUOTE[u.ruota] ?? u.ruota}</span>
          <div class="gruppi">
            ${u.pagati.length ? `
              <div class="gruppo-usciti">
                <span class="che">${u.sorti} sort${u.sorti === 1 ? 'e' : 'i'}
                  uscit${u.sorti === 1 ? 'a' : 'e'}</span>
                ${u.pagati.map(x => gettone(x, 'pagato', u.ruota)).join('')}
              </div>` : ''}
            ${u.soli.length ? `
              <div class="gruppo-usciti">
                <span class="che">usciti da soli</span>
                ${u.soli.map(x => gettone(x, 'solo', u.ruota)).join('')}
              </div>` : ''}
          </div>
        </div>`).join('')}
      <p class="nota">Sotto ogni numero c'è il colpo in cui è uscito la prima
        volta. Quelli in verde hanno completato la loro sorte e avrebbero
        pagato; gli altri sono usciti davvero, ma da soli, e al botteghino non
        valgono niente. <b>Tocca un numero</b> per andare alla riga che lo
        spiega.</p>
    </div>`;

  for (const b of fuori.querySelectorAll('button.gettone'))
    b.onclick = () => vaiAllaRiga(b.dataset.ruota, Number(b.dataset.numero),
                                 b.dataset.gruppo);
}

/** Dal numero alla riga che lo spiega: cambia pagina se serve, ci scorre
 *  sopra e la illumina il tempo di farsi trovare. */
function vaiAllaRiga(ruota, num, gruppo) {
  const cerca = gruppo === 'pagato'
    ? r => r.ruota === ruota && r.esito === 'uscita' && r.usciti.includes(num)
    : r => r.ruota === ruota && r.sfiorata.some(a => a.usciti.includes(num));
  const i = elencoFiltrate.findIndex(cerca);
  if (i < 0) return;

  const suaPagina = Math.floor(i / PER_PAGINA) + 1;
  if (suaPagina !== elencoPagina) {
    elencoPagina = suaPagina;
    mostraElenco();
  }
  const fila = document.getElementById(`riga-${i % PER_PAGINA}`);
  if (!fila) return;
  fila.scrollIntoView({ block: 'center', behavior: 'smooth' });
  for (const x of document.querySelectorAll('tr.illuminata'))
    x.classList.remove('illuminata');
  fila.classList.add('illuminata');
}

function descriviEsito(r) {
  if (r.esito === 'uscita') {
    // i numeri usciti si ripetono solo se sono meno di quelli giocati: per un
    // ambo uscito intero riscriverli sarebbe dire due volte la stessa cosa
    const parziale = r.usciti.length < r.numeri.length;
    return `<span class="pos">uscita al ${r.colpo}° colpo</span>${
      parziale ? `<span class="quali">usciti ${r.usciti.join(' · ')}</span>` : ''}`;
  }
  if (r.esito === 'sospesa')
    return `<span class="tiepido">giocata chiusa al ${r.colpo}° colpo
      su ${NOMI_RUOTE[r.dove] ?? r.dove}</span>`;
  if (r.esito === 'aperta')
    return '<span class="tiepido">ancora in gioco</span>';
  return `<span class="spento">niente in ${r.colpi} colpi</span>${
    r.sfiorata.length ? `<button type="button" class="quali sfiorata"
      data-riga="${r.indice}" aria-expanded="false">un numero solo, ${
      r.sfiorata.length} volt${r.sfiorata.length === 1 ? 'a' : 'e'}</button>` : ''}`;
}

/** Il dettaglio di una riga sfiorata: quale numero e' uscito su questa ruota e
 *  quando, e dove sono finiti gli altri numeri della sorte nello stesso giro di
 *  colpi. E' la domanda che viene subito dopo "un numero solo": quale? */
function dettaglioSfiorata(r) {
  const mio = new Map();
  for (const a of r.sfiorata)
    for (const n of a.usciti) {
      if (!mio.has(n)) mio.set(n, []);
      mio.get(n).push(a);
    }

  const altrove = r.altrove.filter(a => a.ruota !== r.ruota);
  const perNumero = new Map();
  for (const a of altrove)
    for (const n of a.usciti) {
      if (!perNumero.has(n)) perNumero.set(n, new Map());
      const m = perNumero.get(n);
      if (!m.has(a.ruota)) m.set(a.ruota, []);
      m.get(a.ruota).push(a);
    }

  const dove = n => {
    const m = perNumero.get(n);
    if (!m) return '<span class="niente">su nessun\'altra ruota</span>';
    return [...m.entries()]
      .sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]))
      .map(([ruota, quali]) => `<span class="posto">${NOMI_RUOTE[ruota] ?? ruota}
        <em>${quali.map(q => `${q.colpo}°`).join(', ')}</em></span>`).join('');
  };

  const mancanti = r.numeri.filter(n => !mio.has(n));
  return `
    <div class="sfiorata-dentro">
      ${[...mio.entries()].sort((a, b) => a[0] - b[0]).map(([n, quando]) => `
        <div class="voce-numero">
          <span class="cifra">${n}</span>
          <span class="qui">uscito su ${NOMI_RUOTE[r.ruota] ?? r.ruota} al
            ${elenco(quando.map(q => `${q.colpo}° colpo`))}</span>
          <span class="fuori">${dove(n)}</span>
        </div>`).join('')}
      ${mancanti.map(n => `
        <div class="voce-numero assente">
          <span class="cifra">${n}</span>
          <span class="qui">mai su ${NOMI_RUOTE[r.ruota] ?? r.ruota} nei
            ${r.colpi} colpi</span>
          <span class="fuori">${dove(n)}</span>
        </div>`).join('')}
      <p class="nota">Perché la sorte paghi, i ${r.numeri.length === 1 ? 'suoi numeri'
        : 'due numeri'} devono uscire <b>insieme, nello stesso concorso e sulla
        stessa ruota</b>. Un numero per volta non vale niente — ed è la cosa che
        al Lotto fa più rabbia.</p>
    </div>`;
}

function scaricaElenco() {
  const testo = csv(elencoFiltrate, { nomiRuote: NOMI_RUOTE, nomiMetodi: NOMI_METODI });
  const pezzi = ['lotto', elencoGiorno || elencoAnno];
  for (const [id, nomi] of [['ruota-elenco', NOMI_RUOTE], ['metodo-elenco', NOMI_METODI],
                            ['sorte-elenco', NOMI_TIPO], ['esito-elenco', NOMI_ESITO]]) {
    const v = document.getElementById(id).value;
    if (v) pezzi.push((nomi[v] ?? v).toLowerCase().replaceAll(' ', '-'));
  }
  const url = URL.createObjectURL(new Blob([testo], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `${pezzi.join('-')}.csv`;
  a.click();
  // il browser tiene in vita il Blob finche' non si revoca: senza questo, ogni
  // scarico lascia un megabyte in memoria fino a che non si chiude la pagina
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* ------------------------------------------------------------- bilancio */
function mostraBilancio(b) {
  const segno = v => v >= 0 ? 'pos' : 'neg';
  const cella = r => `
    <tr>
      <td>${r.nome_metodo}
        ${r.campione_scarso ? '<span class="scarso">campione troppo piccolo per essere indicativo</span>' : ''}</td>
      <td data-et="Previsioni">${numero(r.previsioni)}</td>
      <td data-et="Speso">${euro(r.speso)}</td>
      <td data-et="Incassato">${euro(r.incassato)}</td>
      <td data-et="Saldo" class="${segno(r.saldo)}">${euro(r.saldo)}</td>
      <td data-et="Ritorno" class="${r.ritorno >= 1 ? 'pos' : 'neg'}">${
        r.ritorno == null ? '—' : percento(r.ritorno)}</td>
    </tr>`;
  const t = b.totale, rif = b.riferimento;
  document.getElementById('bilancio').innerHTML = `
    <div class="carta tabella-scroll">
      <table>
        <thead><tr><th>Metodo</th><th>Previsioni</th><th>Speso</th>
          <th>Incassato</th><th>Saldo</th><th>Ritorno</th></tr></thead>
        <tbody>${b.per_metodo.map(cella).join('')}</tbody>
        <tfoot><tr>
          <td>Totale</td>
          <td data-et="Previsioni">${numero(t.previsioni)}</td>
          <td data-et="Speso">${euro(t.speso)}</td>
          <td data-et="Incassato">${euro(t.incassato)}</td>
          <td data-et="Saldo" class="${segno(t.saldo)}">${euro(t.saldo)}</td>
          <td data-et="Ritorno" class="${t.ritorno >= 1 ? 'pos' : 'neg'}">${
            t.ritorno == null ? '—' : percento(t.ritorno)}</td>
        </tfoot>
      </table>
    </div>
    <p class="avvertenza">Un euro per sorte, per ruota, per colpo; la sorte si
      sospende quando si verifica. Vincite al netto della ritenuta dell'8%.
      <br><br>
      Dove è segnalato un campione insufficiente il saldo non significa nulla:
      le previsioni sono troppo poche e un solo terno ne ribalta il segno. Il
      riferimento vero è il backtest su ${rif.periodo}, ${numero(rif.rilevamenti)}
      rilevamenti: ogni metodo restituisce fra il ${percento(rif.ritorno_minimo, 0)}
      e il ${percento(rif.ritorno_massimo, 0)} di quanto costa, in media il
      ${percento(rif.ritorno_medio)}. È lì che tende qualunque riga di
      questa tabella, col tempo.</p>`;
}

/* ------------------------------------------------------------- estrazioni */
function mostraEstrazioni(lista) {
  document.getElementById('estrazioni').innerHTML = lista.map(e => `
    <article class="carta">
      <h2>${dataIt(e.giorno)}</h2>
      ${Object.entries(e.quadro).map(([r, numeri]) => `
        <div class="quadro">
          <span class="ruota">${NOMI_RUOTE[r] ?? r}</span>
          ${numeri.map(n => `<span class="n">${n}</span>`).join('')}
        </div>`).join('')}
    </article>`).join('')
    + `<p class="avvertenza">I numeri sono nell'ordine in cui sono stati estratti,
       non riordinati per valore: è quello che permette ai metodi basati sulla
       posizione di funzionare davvero.</p>`;
}

/* ------------------------------------------------------------- schedina */
function costruisciSchedina() {
  const griglia = document.getElementById('griglia');
  griglia.innerHTML = Array.from({ length: 90 }, (_, i) =>
    `<button type="button" data-n="${i + 1}" aria-pressed="false">${i + 1}</button>`).join('');
  griglia.onclick = e => {
    const b = e.target.closest('button[data-n]');
    if (!b) return;
    const n = Number(b.dataset.n);
    if (giocata.numeri.has(n)) giocata.numeri.delete(n);
    else if (giocata.numeri.size >= MAX_NUMERI) return;   // dieci e' il massimo giocabile
    else giocata.numeri.add(n);
    document.getElementById('da-previsione').value = '';
    disegnaScelte();
  };

  document.getElementById('ruote').innerHTML =
    Object.entries(NOMI_RUOTE).map(([s, nome]) =>
      `<button type="button" data-r="${s}" aria-pressed="false">${nome}</button>`).join('')
    + `<button type="button" data-r="TUTTE" aria-pressed="false">Tutte</button>`;
  document.getElementById('ruote').onclick = e => {
    const b = e.target.closest('button[data-r]');
    if (!b) return;
    const r = b.dataset.r;
    if (r === 'TUTTE') {
      giocata.ruote = new Set(giocata.ruote.size === 10 ? ['NA'] : Object.keys(NOMI_RUOTE));
    } else if (giocata.ruote.has(r)) {
      if (giocata.ruote.size > 1) giocata.ruote.delete(r);   // almeno una deve restare
    } else giocata.ruote.add(r);
    disegnaScelte();
  };

  document.getElementById('sorti').innerHTML = SORTI.map(([nome, k]) =>
    `<button type="button" data-s="${nome}" data-k="${k}" aria-pressed="false">${nome}</button>`).join('');
  document.getElementById('sorti').onclick = e => {
    const b = e.target.closest('button[data-s]');
    if (!b || b.disabled) return;
    const s = b.dataset.s;
    if (giocata.sorti.has(s)) { if (giocata.sorti.size > 1) giocata.sorti.delete(s); }
    else giocata.sorti.add(s);
    disegnaScelte();
  };

  document.getElementById('importo').oninput = e => {
    giocata.importo = Number(e.target.value);
    disegnaScelte();
  };

  document.getElementById('da-previsione').onchange = e => {
    const s = suggerite[Number(e.target.value)];
    if (!s) return;
    giocata.numeri = new Set(s.numeri);
    giocata.ruote = new Set(s.ruote);
    // le sorti compatibili: una terzina si gioca per ambo, non "per terzina"
    giocata.sorti = new Set(SORTI.filter(([, k]) => k >= 2 && k <= s.numeri.length).map(([n]) => n));
    if (!giocata.sorti.size) giocata.sorti = new Set(['estratto']);
    disegnaScelte();
  };
}

function disegnaScelte() {
  for (const b of document.querySelectorAll('#griglia button'))
    b.setAttribute('aria-pressed', String(giocata.numeri.has(Number(b.dataset.n))));
  for (const b of document.querySelectorAll('#ruote button'))
    b.setAttribute('aria-pressed', String(b.dataset.r === 'TUTTE'
      ? giocata.ruote.size === 10 : giocata.ruote.has(b.dataset.r)));

  // Una sorte scelta ma non ancora giocabile (il terno con due numeri) resta
  // scelta invece di essere cancellata: e' un'intenzione, e appena arriva il
  // terzo numero deve tornare attiva da sola. Cancellarla costringerebbe a
  // ricliccarla, e nel frattempo farebbe sparire in silenzio la scelta iniziale.
  const quanti = giocata.numeri.size;
  for (const b of document.querySelectorAll('#sorti button')) {
    const attiva = Number(b.dataset.k) <= quanti;
    b.disabled = !attiva;
    b.setAttribute('aria-pressed', String(attiva && giocata.sorti.has(b.dataset.s)));
  }

  document.getElementById('conta-numeri').textContent = quanti
    ? [...giocata.numeri].sort((a, b) => a - b).join(' · ') : 'nessuno scelto';
  document.getElementById('nota-sorti').textContent = quanti
    ? `con ${quanti} numer${quanti === 1 ? 'o' : 'i'}` : 'scegli prima i numeri';

  clearTimeout(attesaSimula);
  attesaSimula = setTimeout(calcola, 120);
}

function sortiGiocabili() {
  return [...giocata.sorti].filter(s => NUMERI_PER_SORTE[s] <= giocata.numeri.size);
}

function calcola() {
  const fuori = document.getElementById('risultato');
  if (!giocata.numeri.size || !sortiGiocabili().length || !(giocata.importo > 0)) {
    fuori.innerHTML = `<p class="vuoto">Scegli i numeri e l'importo: qui comparirà
      quanto puoi vincere, e con quale probabilità.</p>`;
    return;
  }
  let r;
  try {
    r = simula({
      numeri: [...giocata.numeri], ruote: [...giocata.ruote],
      sorti: sortiGiocabili(), importo: giocata.importo, quote,
    });
  } catch (e) {
    fuori.innerHTML = `<div class="carta"><p class="errore">${
      e instanceof GiocataNonValida ? e.message : 'Non riesco a calcolare: ' + e.message}</p></div>`;
    return;
  }
  mostraSimulazione(r);
}

function mostraSimulazione(r) {
  const righe = r.righe.flatMap(s => s.scenari.map((sc, i) => `
    <tr>
      <td>${i === 0 ? `<b>${s.sorte}</b> — ` : ''}escono ${sc.presi} dei tuoi ${r.numeri.length} numeri</td>
      <td data-et="Vincite">${sc.combinazioniVincenti}</td>
      <td data-et="Incassi" class="${sc.netto >= r.importo ? 'pos' : ''}">${euro(sc.netto)}</td>
      <td data-et="Probabilità su una ruota">${unaSu(sc.probabilita)}</td>
    </tr>`)).join('');

  const rip = r.righe.map(s =>
    `${s.sorte}: ${euro(s.postaPerRuota)} per ruota su ${s.combinazioni} combinazion${
      s.combinazioni === 1 ? 'e' : 'i'} = ${euro(s.postaPerCombinazione)} l'una`).join(' · ');

  document.getElementById('risultato').innerHTML = `
    <div class="carta tabella-scroll">
      <p class="ripartizione">${euro(r.importo)} su ${r.ruote.length} ruot${
        r.ruote.length === 1 ? 'a' : 'e'} (${r.ruote.join(' ')}) — ${rip}</p>
      <table>
        <thead><tr><th>Se esce</th><th>Vincite</th><th>Incassi</th>
          <th>Probabilità su una ruota</th></tr></thead>
        <tbody>${righe}</tbody>
      </table>
      <div class="verdetto">
        <div>
          <span class="valore">${unaSu(r.qualcosaAlmenoUnaRuota)}</span>
          <span class="didascalia">probabilità di vincere qualcosa, su almeno una
            delle ${r.ruote.length} ruote${percentuale(r.qualcosaAlmenoUnaRuota)}</span>
        </div>
        <div>
          <span class="valore ${r.ritornoAtteso >= r.importo ? 'pos' : 'neg'}">${euro(r.ritornoAtteso)}</span>
          <span class="didascalia">ritorno atteso su ${euro(r.importo)} giocati:
            ${(r.ritornoAttesoPerEuro * 100).toFixed(0)} centesimi per ogni euro</span>
        </div>
      </div>
    </div>
    <p class="avvertenza">La posta si ripartisce fra le ruote, fra le sorti scelte e
      fra le combinazioni di ciascuna sorte. Giocare su più ruote aumenta la
      probabilità che almeno una vinca, ma divide la posta: il ritorno atteso non
      cambia.<br><br>
      Il ritorno atteso è la media matematica, non una previsione su questa giocata:
      in una singola estrazione o si vince o non si vince. Dice che, ripetendo la
      giocata molte volte, tornano indietro circa
      ${(r.ritornoAttesoPerEuro * 100).toFixed(0)} centesimi per euro. È il margine
      del banco, ed è lo stesso per tutti i metodi: nessuna previsione lo cambia,
      perché agisce su quali numeri giocare, non su quanto paga il gioco.</p>`;
}

function preparaSuggerimenti(lista) {
  suggerite = [];
  for (const p of lista.slice(0, 25)) {
    for (const s of p.sorti) {
      if (!s.numeri.length) continue;
      suggerite.push({
        numeri: s.numeri, ruote: p.ruote,
        etichetta: `${p.nome_metodo} · ${s.tipo} ${s.numeri.join('-')} · ${p.ruote.join(' ')}`,
      });
    }
  }
  document.getElementById('da-previsione').innerHTML =
    `<option value="">parti da una previsione in corso…</option>`
    + suggerite.map((s, i) => `<option value="${i}">${s.etichetta}</option>`).join('');
}

/* ------------------------------------------------------------- avvio */
const VISTE = ['schedina', 'previsioni', 'corso', 'bilancio', 'estrazioni'];
for (const b of document.querySelectorAll('[data-vista]')) {
  b.onclick = () => {
    for (const x of document.querySelectorAll('[data-vista]'))
      x.setAttribute('aria-selected', String(x === b));
    for (const v of VISTE)
      document.getElementById(v).hidden = b.dataset.vista !== v;
    if (b.dataset.vista === 'previsioni') apriPrevisioni();
  };
}

/** L'archivio si scarica alla prima apertura della scheda, non prima. */
async function apriPrevisioni() {
  if (storico) return;
  const avviso = document.getElementById('stato-ricerca');
  avviso.textContent = 'sto caricando lo storico delle estrazioni…';
  try {
    const [, indice] = await Promise.all([
      prendiStorico(),
      fetch(`dati/previsioni/indice.json?v=${Date.now()}`).then(r => r.json()),
    ]);
    indiceAnni = indice;
    avviso.textContent = '';
    preparaRicerca();
    preparaElenco();
  } catch (e) {
    avviso.textContent = `Non riesco a caricare lo storico: ${e.message}. `
      + 'La ricerca delle ripetizioni non è disponibile; il resto della pagina sì.';
  }
}

costruisciBudget();
costruisciRuote();
costruisciSchedina();
costruisciRicerca();
costruisciElenco();

(async () => {
  try {
    const [stato, corso, bil, cal, ultime, q] = await Promise.all([
      prendi('stato.json'), prendi('in-corso.json'), prendi('bilancio.json'),
      prendi('calendario.json'), prendi('ultime-estrazioni.json'), prendi('quote.json'),
    ]);
    quote = q;
    inCorso = corso;
    // Se il calendario pubblicato e' vuoto - la pipeline non e' ancora girata,
    // o quella sera e' andata male - la pagina se lo ricava dagli ultimi
    // concorsi invece di alzare le mani.
    calendario = cal?.date?.length ? cal : {
      date: proiettaConcorsi(ultime.map(e => e.giorno), { da: primoGiornoUtile() }),
      stimato: true, ora: cal?.ora ?? '20:00',
      motivo: 'Date proiettate dagli ultimi concorsi.',
    };
    resePerMetodo = Object.fromEntries(bil.per_metodo.map(r => [r.metodo, r.ritorno]));
    mostraStato(stato);
    mostraInCorso(corso);
    mostraBilancio(bil);
    mostraEstrazioni(ultime);
    mostraConcorso();
    mostraConsiglio();
    mostraRuote();
    mostraComuni();
    preparaSuggerimenti(corso);
    disegnaScelte();
  } catch (e) {
    document.getElementById('stato').textContent =
      `Non riesco a leggere i dati: ${e.message}. `
      + `Se hai aperto il file direttamente dal disco, serve un piccolo server web `
      + `(vedi il README): il browser non lascia leggere file locali a una pagina.`;
  }
})();
