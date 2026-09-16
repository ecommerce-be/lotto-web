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
import { leggiStorico, quadro, concorsoVicino, cerca, confronto }
  from './ripetizioni.js';

const NOMI_RUOTE = {
  BA: 'Bari', CA: 'Cagliari', FI: 'Firenze', GE: 'Genova', MI: 'Milano',
  NA: 'Napoli', PA: 'Palermo', RM: 'Roma', TO: 'Torino', VE: 'Venezia',
};
const SORTI = Object.entries(NUMERI_PER_SORTE);
const MAX_NUMERI = 10;

const giocata = { numeri: new Set(), ruote: new Set(['NA']), sorti: new Set(['ambo']), importo: 5 };
let quote = null, suggerite = [], attesaSimula = null;

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

/* ------------------------------------------------- si e' mai ripetuta? */
/* L'archivio intero pesa trecentosessanta chilobyte compressi: si scarica solo
 * quando si apre questa scheda, e una volta sola. Chi guarda la Schedina e
 * basta non lo prende mai. */
let storico = null, inArrivo = null;

const NOMI_MISURA = { 2: 'ambi', 3: 'terni', 4: 'quaterne', 5: 'cinquine' };
const NOME_MISURA = { 2: 'un ambo', 3: 'un terno', 4: 'una quaterna', 5: 'la cinquina' };

async function prendiStorico() {
  if (storico) return storico;
  if (!inArrivo) inArrivo = fetch(`dati/storico.txt?v=${Date.now()}`)
    .then(r => {
      if (!r.ok) throw new Error(`dati/storico.txt → ${r.status}`);
      return r.text();
    })
    .then(t => { storico = leggiStorico(t); return storico; })
    .catch(e => { inArrivo = null; throw e; });
  return inArrivo;
}

function costruisciRicerca() {
  document.getElementById('cerca').onclick = eseguiRicerca;
  document.getElementById('data-ricerca').onchange = aggiornaRuoteDelGiorno;
  document.getElementById('ruota-ricerca').onchange = aggiornaRuoteDelGiorno;
  document.getElementById('cerca').disabled = true;
}

/** Prepara i campi appena l'archivio e' in memoria. */
function preparaRicerca() {
  const campo = document.getElementById('data-ricerca');
  const primo = storico.giorni[0], ultimo = storico.giorni.at(-1);
  campo.min = primo;
  campo.max = ultimo;
  if (!campo.value) {
    // Un punto di partenza che ha senso: dieci anni fa. Da li' in poi ci sono
    // abbastanza concorsi perche' il confronto con gli attesi voglia dire
    // qualcosa, e chi apre la pagina vede subito un risultato invece di un
    // modulo vuoto.
    const d = new Date(ultimo + 'T00:00:00');
    d.setFullYear(d.getFullYear() - 10);
    campo.value = concorsoVicino(storico, d.toISOString().slice(0, 10));
  }

  const anni = [10, 20, 30, 40].filter(a => {
    const d = new Date(ultimo + 'T00:00:00');
    d.setFullYear(d.getFullYear() - a);
    return d.toISOString().slice(0, 10) >= primo;
  });
  document.getElementById('date-rapide').innerHTML =
    anni.map(a => `<button type="button" data-anni="${a}">${a} anni fa</button>`).join('')
    + `<button type="button" data-giorno="${primo}">il primo concorso (${primo.slice(0, 4)})</button>`;
  for (const b of document.querySelectorAll('#date-rapide button')) {
    b.onclick = () => {
      if (b.dataset.giorno) campo.value = b.dataset.giorno;
      else {
        const d = new Date(ultimo + 'T00:00:00');
        d.setFullYear(d.getFullYear() - Number(b.dataset.anni));
        campo.value = concorsoVicino(storico, d.toISOString().slice(0, 10));
      }
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
  const tutteLeRuote = document.getElementById('tutte-ruote').checked;
  if (!giorno || !ruota) return;

  bottone.disabled = true;
  avviso.textContent = 'cerco…';
  // un respiro prima di lavorare, se no il browser non ridisegna e sembra
  // che il tasto non abbia fatto niente
  await new Promise(r => setTimeout(r, 0));
  try {
    const esito = cerca(storico, { giorno, ruota, tutteLeRuote });
    avviso.textContent = '';
    mostraRicerca(esito);
  } catch (e) {
    avviso.textContent = `La ricerca non è riuscita: ${e.message}`;
  } finally {
    bottone.disabled = false;
  }
}

function mostraRicerca(esito) {
  const fuori = document.getElementById('esito-ricerca');
  if (!esito) { fuori.innerHTML = '<p class="nota">Quel concorso non c\'è.</p>'; return; }
  if (!esito.concorsi) {
    fuori.innerHTML = `<p class="nota">Dopo il ${dataIt(esito.origine.giorno)} non
      c'è ancora nessun concorso da guardare: è l'ultimo dell'archivio.</p>`;
    return;
  }

  const o = esito.origine;
  const dove = esito.tutteLeRuote ? 'su tutte e dieci le ruote'
    : `su ${NOMI_RUOTE[o.ruota]}`;

  const righe = [5, 4, 3, 2].map((q) => {
    const trovati = esito.conteggio[q], att = esito.attesi[q];
    const c = confronto(trovati, att);
    return `
      <tr class="${trovati ? '' : 'spento'}">
        <td>${NOMI_MISURA[q]}<span class="quanti-num">${q} numeri insieme</span></td>
        <td class="num" data-et="trovate"><b>${numero(trovati)}</b></td>
        <td class="num" data-et="attese dal caso">${
          att < 0.1 && att > 0 ? att.toFixed(2).replace('.', ',')
          : att.toLocaleString('it-IT', { maximumFractionDigits: 1 })}</td>
        <td class="verso" data-et="com'è andata">${
          c.scarto === null ? '—' : c.parola}</td>
      </tr>`;
  }).join('');

  const grossi = esito.trovati.filter(t => t.quanti >= 3);
  const ambi = esito.trovati.filter(t => t.quanti === 2);
  const voce = t => `
    <li>
      <span class="quando">${dataIt(t.giorno)}</span>
      ${esito.tutteLeRuote ? `<span class="dove">${NOMI_RUOTE[t.ruota]}</span>` : ''}
      <span class="numeri">${t.numeri.map(n => `<b>${n}</b>`).join(' ')}</span>
    </li>`;

  fuori.innerHTML = `
    <div class="esito">
      <p class="partenza">Concorso del <b>${dataIt(o.giorno)}</b> su
        <b>${NOMI_RUOTE[o.ruota]}</b>:${o.numeri.map(n =>
          ` <span class="n">${n}</span>`).join('')}</p>
      <p class="conti">Da quel giorno a ${dataIt(esito.ultimo)} si è estratto
        <b>${numero(esito.concorsi)}</b> volte. Guardando ${dove}, ecco quante
        volte quei numeri sono tornati fuori insieme.</p>

      <table class="ripetizioni">
        <thead><tr>
          <th>quanti insieme</th><th class="num">trovate</th>
          <th class="num">attese dal caso</th><th></th>
        </tr></thead>
        <tbody>${righe}</tbody>
      </table>

      <p class="avvertenza">La colonna <b>attese dal caso</b> è il conto esatto
        di quante ripetizioni sarebbero venute fuori da ${numero(esito.concorsi)}
        estrazioni a caso. Serve a leggere l'altra colonna: da sola, «${numero(
          esito.conteggio[2])} ambi» sembra un segnale, ma accanto a
        ${esito.attesi[2].toLocaleString('it-IT', { maximumFractionDigits: 0 })}
        attesi dice solo che è andata come doveva andare. E comunque nulla di
        tutto ciò riguarda il prossimo concorso: le estrazioni non hanno memoria
        di quelle prima.</p>

      ${grossi.length ? `
        <h3>${grossi.length === 1 ? 'L\'unica ripetizione da tre numeri in su'
          : 'Le ripetizioni da tre numeri in su'}</h3>
        <ul class="ritrovamenti">${grossi.map(voce).join('')}</ul>`
        : `<p class="nota">Da quel giorno in poi non è mai tornato fuori
           ${NOME_MISURA[3]} di quei cinque numeri${esito.tutteLeRuote ? ''
           : `, almeno su ${NOMI_RUOTE[o.ruota]}`}.</p>`}

      ${ambi.length ? `
        <details class="elenco-ambi">
          <summary>${numero(esito.conteggio[2])} volte è tornato un ambo${
            esito.troncato ? ` (ne elenco ${numero(ambi.length)})` : ''}</summary>
          <ul class="ritrovamenti">${ambi.map(voce).join('')}</ul>
        </details>` : ''}
    </div>`;
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
    await prendiStorico();
    avviso.textContent = '';
    preparaRicerca();
  } catch (e) {
    avviso.textContent = `Non riesco a caricare lo storico: ${e.message}. `
      + 'La ricerca delle ripetizioni non è disponibile; il resto della pagina sì.';
  }
}

costruisciBudget();
costruisciRuote();
costruisciSchedina();
costruisciRicerca();

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
