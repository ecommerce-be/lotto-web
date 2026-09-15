/**
 * App Lotto — la pagina.
 *
 * Tutto quello che si vede, tranne il simulatore di schedina, arriva gia'
 * calcolato da dati/*.json: e' il motore Python che li riscrive ogni sera e
 * GitHub che li pubblica. Qui non c'e' nessuna logica di Lotto - se un giorno
 * un numero non torna, la risposta sta in motore/, non in questo file.
 */
import { simula, GiocataNonValida, NUMERI_PER_SORTE } from './schedina.js';
import { componi, convergenze, riepilogo, etichettaGiocata, SOGLIA_RESA }
  from './consiglio.js';

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
function mostraStato(s, calendario) {
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
    + (ore > 30 ? ` <span class="allarme">(${Math.round(ore / 24)} giorni fa)</span>` : '')
    + (calendario?.date?.length
      ? ` · prossima estrazione ${dataBreve(calendario.date[0])} alle ${calendario.ora}` : '');

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

function mostraConcorso() {
  const box = document.getElementById('concorso');
  if (!calendario?.date?.length) {
    box.innerHTML = `<div class="quando">Non riesco a leggere il calendario delle estrazioni.</div>`;
    return;
  }
  const g = giorniDa(calendario.date[0]);
  const quando = g <= 0 ? 'Stasera' : g === 1 ? 'Domani' : `Fra ${g} giorni`;
  const giorno = new Date(calendario.date[0] + 'T00:00:00')
    .toLocaleDateString('it-IT', { weekday: 'long', day: 'numeric', month: 'long' });
  box.innerHTML = `
    <div>
      <div class="quando">${quando} si gioca</div>
      <div class="meta">${giorno} alle ${calendario.ora}${
        calendario.stimato ? ' · data proiettata dal calendario recente' : ''}</div>
    </div>`;
}

function mostraConsiglio() {
  const fuoriBox = document.getElementById('consiglio');
  const budget = Number(document.getElementById('budget').value);
  if (!quote || !inCorso.length) {
    fuoriBox.innerHTML = `<p class="vuoto">Nessuna previsione in gioco per il prossimo concorso.</p>`;
    return;
  }
  if (!(budget > 0)) {
    fuoriBox.innerHTML = `<p class="vuoto">Scrivi quanto vuoi spendere.</p>`;
    return;
  }

  const { dentro, fuori, speso, mancano } = componi(inCorso, budget, quote);
  if (!dentro.length) {
    fuoriBox.innerHTML = `<div class="carta"><p class="errore">Con ${euro(budget)} non si
      copre nemmeno una giocata: la piu' piccola in gioco ne costa
      ${euro(Math.min(...fuori.map(g => g.costo)))}, perché va giocata su
      ${Math.min(...fuori.map(g => g.ruote.length))} ruote.</p></div>`;
    document.getElementById('nota-budget').textContent = '';
    return;
  }

  const { attesa, qualcosa: pQualcosa, per_euro } = riepilogo(dentro);
  const resaMigliore = Math.max(...dentro.map(g => g.resa));
  const conv = convergenze(dentro);

  const gruppi = new Map();
  for (const g of dentro) {
    const m = g.previsione.metodo;
    if (!gruppi.has(m)) gruppi.set(m, []);
    gruppi.get(m).push(g);
  }

  const riga = g => `
    <div class="linea${g.resa < resaMigliore - SOGLIA_RESA ? ' scarsa' : ''}">
      <span class="sorte-nome">${etichettaGiocata(g)}</span>
      ${g.numeri.map(n => `<span class="n">${n}</span>`).join('')}
      ${g.resa >= resaMigliore - SOGLIA_RESA
        ? '<span class="consigliata">consigliata</span>'
        : `<span class="resa">rende ${Math.round(g.resa * 100)} cent. per euro</span>`}
      <span class="dove">${g.ruote.map(r => NOMI_RUOTE[r] ?? r).join(' · ')}${
        g.colpi_residui === 1 ? ' · <b>ultimo colpo</b>' : ''}</span>
      <span class="costo">${euro(g.costo)}</span>
    </div>`;

  fuoriBox.innerHTML = `
    <div class="carta">
      <div class="somme">
        <div><span class="valore">${euro(speso)}</span>
          <span class="didascalia">${dentro.length} giocate su
            ${gruppi.size} metod${gruppi.size === 1 ? 'o' : 'i'}</span></div>
        <div><span class="valore">${unaSu(pQualcosa)}</span>
          <span class="didascalia">circa, di vincere qualcosa${percentuale(pQualcosa)}</span></div>
        <div><span class="valore neg">${euro(attesa)}</span>
          <span class="didascalia">ritorno atteso: ${Math.round(attesa / speso * 100)}
            centesimi per ogni euro</span></div>
      </div>
    </div>

    ${[...gruppi.values()].map(g => {
      const p = g[0].previsione;
      const resa = resePerMetodo[p.metodo];
      return `
      <div class="carta gruppo-stasera">
        <h3>${p.nome_metodo}
          <span class="rarita">scatta ${p.per_anno} volte l'anno</span>
          ${resa != null ? `<span class="rarita">finora ${percento(resa, 0)} di ritorno</span>` : ''}
        </h3>
        ${g.map(riga).join('')}
      </div>`;
    }).join('')}

    ${conv.length ? `<div class="carta">
      <div class="convergenze"><b>Numeri su cui più previsioni convergono:</b>
        ${conv.slice(0, 8).map(c => `<span class="n">${c.numero}</span>`).join('')}</div>
      <p class="resa" style="margin:8px 0 0">Non aumenta di un millesimo la
        probabilità che escano: significa solo che coprendoli si soddisfano più
        previsioni con meno giocate distinte.</p>
    </div>` : ''}

    ${fuori.length ? `<p class="fuori">Restano fuori ${fuori.length} giocate:
      servirebbero altri ${euro(mancano)} per coprirle tutte.</p>` : ''}

    <p class="avvertenza">Le giocate sono in ordine di rarità del metodo: prima
      quelle che capitano poche volte l'anno, perché sono la ragione per cui i
      metodi sono sei e non uno. A parità di metodo viene prima ciò che scade
      prima, e prima la sorte che rende di più — così, se il budget taglia,
      taglia i terni e non gli ambi.<br><br>
      <b>Sui numeri non c'è nessun consiglio da dare, e non è una reticenza.</b>
      Nel Lotto le quote sono fissate per legge e la probabilità è la stessa per
      qualunque combinazione: il ritorno atteso di questa giocata sarebbe
      identico con novanta numeri scelti a caso. Le uniche scelte che cambiano
      qualcosa sono quante ne giochi, su quante ruote, e per quale sorte — ed è
      su quelle che questa pagina lavora.</p>`;

  document.getElementById('nota-budget').textContent =
    `coprire tutto costerebbe ${euro(speso + mancano)}`;
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
function mostraProssima(p) {
  const box = document.getElementById('prossima');
  if (!p.date?.length) {
    box.innerHTML = `<div class="quando">Non riesco a leggere il calendario delle estrazioni.</div>`;
    return;
  }
  const [prima, ...poi] = p.date;
  const g = giorniDa(prima);
  const fra = g <= 0 ? 'stasera' : g === 1 ? 'domani' : `fra ${g} giorni`;
  const giorno = new Date(prima + 'T00:00:00')
    .toLocaleDateString('it-IT', { weekday: 'long', day: 'numeric', month: 'long' });
  box.innerHTML = `
    <div>
      <div class="quando">Prossima estrazione <span class="fra">${fra}</span></div>
      <div class="meta">${giorno} alle ${p.ora}${
        p.stimato ? ' · proiettata dal calendario recente, una festa può spostarla' : ''}</div>
    </div>
    ${poi.length ? `<div class="poi">poi ${poi.map(dataBreve).join(' · ')}</div>` : ''}`;
}

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
for (const b of document.querySelectorAll('[data-vista]')) {
  b.onclick = () => {
    for (const x of document.querySelectorAll('[data-vista]'))
      x.setAttribute('aria-selected', String(x === b));
    for (const v of ['stasera', 'corso', 'bilancio', 'schedina', 'estrazioni'])
      document.getElementById(v).hidden = b.dataset.vista !== v;
  };
}

document.getElementById('budget').oninput = mostraConsiglio;
costruisciSchedina();

(async () => {
  try {
    const [stato, corso, bil, cal, ultime, q] = await Promise.all([
      prendi('stato.json'), prendi('in-corso.json'), prendi('bilancio.json'),
      prendi('calendario.json'), prendi('ultime-estrazioni.json'), prendi('quote.json'),
    ]);
    quote = q;
    inCorso = corso;
    calendario = cal;
    resePerMetodo = Object.fromEntries(bil.per_metodo.map(r => [r.metodo, r.ritorno]));
    mostraStato(stato, cal);
    mostraInCorso(corso);
    mostraBilancio(bil);
    mostraEstrazioni(ultime);
    mostraProssima(cal);
    mostraConcorso();
    mostraConsiglio();
    preparaSuggerimenti(corso);
    disegnaScelte();
  } catch (e) {
    document.getElementById('stato').textContent =
      `Non riesco a leggere i dati: ${e.message}. `
      + `Se hai aperto il file direttamente dal disco, serve un piccolo server web `
      + `(vedi il README): il browser non lascia leggere file locali a una pagina.`;
  }
})();
