/**
 * Prove del consiglio per il concorso in arrivo.
 *
 * Qui si difendono quattro cose, e ognuna corrisponde a una promessa che la
 * pagina fa all'utente:
 *
 *   - il budget non viene mai sforato;
 *   - l'ordine e' quello dichiarato: metodo piu' raro, poi cio' che scade
 *     prima, poi la sorte che rende di piu';
 *   - il ritorno atteso per euro dipende SOLO dalla sorte, non da quanti
 *     numeri si giocano ne' da quante ruote (e' la ragione per cui la pagina
 *     dice che sui numeri non c'e' consiglio da dare);
 *   - le etichette dicono la verita': quattro numeri giocati per ambo sono
 *     "quartina per ambo", non "ambo".
 *
 *     node prove/test_consiglio.mjs
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  componi, convergenze, giocate, riepilogo, resaSorte, probAlmeno,
  etichettaGiocata, perRuota, SOGLIA_RESA, primoGiornoUtile, proiettaConcorsi,
  numeriInComune, previsioneUnica,
} from '../docs/consiglio.js';
import { simula, combinazioni } from '../docs/schedina.js';

const QUI = dirname(fileURLToPath(import.meta.url));
const quote = JSON.parse(readFileSync(join(QUI, '..', 'archivio', 'quote.json'), 'utf8'));

let ok = 0, fail = 0;
const check = (nome, cond, dettaglio = '') => {
  if (cond) { ok++; console.log(`  OK   ${nome}`); }
  else { fail++; console.log(`  FAIL ${nome}  ${dettaglio}`); }
};
const vicino = (a, b, t = 1e-9) => Math.abs(a - b) <= t * Math.max(1, Math.abs(b));

const sorte = (tipo, numeri, residui = 5) =>
  ({ tipo, numeri, colpi_residui: residui, colpi_giocati: 0 });
const previsione = (o) => ({
  chiave: o.chiave ?? Math.random().toString(36).slice(2),
  metodo: o.metodo, nome_metodo: o.metodo, per_anno: o.per_anno,
  ruote: o.ruote ?? ['NA', 'MI'], colpi: 9, anche_tutte: false,
  nota: null, avviso: null, colpi_residui: 5, sorti: o.sorti,
});

const RARO = previsione({
  chiave: 'raro', metodo: 'unsoloambosecco', per_anno: 4, ruote: ['CA', 'GE'],
  sorti: [sorte('ambo', [65, 40])],
});
const COMUNE = previsione({
  chiave: 'comune', metodo: 'lottofacile1', per_anno: 1062, ruote: ['BA', 'NA'],
  sorti: [sorte('ambata', [66]), sorte('ambo', [66, 36])],
});
const MEDIO = previsione({
  chiave: 'medio', metodo: 'fulmine', per_anno: 89, ruote: ['MI', 'VE'],
  sorti: [sorte('quartina', [19, 39, 69, 89], 1), sorte('ambata', [89], 3)],
});

console.log('IL RITORNO DIPENDE SOLO DALLA SORTE');
check('ambo: 57 centesimi per euro',
  vicino(resaSorte('ambo', quote), 250 / 400.5 * 0.92, 1e-3),
  String(resaSorte('ambo', quote)));
check('ambata: praticamente identico all\'ambo',
  Math.abs(resaSorte('estratto', quote) - resaSorte('ambo', quote)) < SOGLIA_RESA);
check('terno: nettamente peggiore', resaSorte('terno', quote) < resaSorte('ambo', quote) - 0.1);
check('quaterna: peggio ancora', resaSorte('quaterna', quote) < resaSorte('terno', quote));

// e' il punto su cui la pagina insiste: nessuna scelta di numeri sposta il valore
const soloAmbi = componi([RARO], 1000, quote);
const tanti = componi([MEDIO], 1000, quote).dentro.filter(g => g.sorte === 'ambo');
check('un ambo secco e una quartina giocata per ambo rendono uguale per euro',
  vicino(soloAmbi.dentro[0].resa, tanti[0].resa, 1e-12));

console.log('\nPROBABILITA\': ALMENO k, NON ESATTAMENTE k');
check('ambo secco: una su 400,5', vicino(1 / probAlmeno(2, 2), 400.5, 1e-6));
check('ambata: una su 18', vicino(1 / probAlmeno(1, 1), 18, 1e-6));
check('quartina per ambo vince anche con 3 o 4 numeri presi',
  probAlmeno(4, 2) > probAlmeno(4, 4) * 100, String(probAlmeno(4, 2)));
check('e' + ' non supera mai 1', probAlmeno(10, 1) < 1 && probAlmeno(10, 1) > 0.25,
  String(probAlmeno(10, 1)));

console.log('\nL\'ORDINE E\' QUELLO DICHIARATO');
let g = giocate([COMUNE, RARO, MEDIO], quote);
check('prima il metodo piu\' raro', g[0].previsione.metodo === 'unsoloambosecco',
  g[0].previsione.metodo);
check('poi quello intermedio', g[1].previsione.metodo === 'fulmine', g[1].previsione.metodo);
check('per ultimo quello che scatta mille volte l\'anno',
  g[g.length - 1].previsione.metodo === 'lottofacile1');
const fulmine = g.filter(x => x.previsione.metodo === 'fulmine');
check('dentro un metodo, prima cio\' che scade prima',
  fulmine[0].colpi_residui <= fulmine[fulmine.length - 1].colpi_residui,
  fulmine.map(x => x.colpi_residui).join(','));
const quartine = fulmine.filter(x => x.numeri.length === 4);
check('a parita\' di tutto, l\'ambo prima del terno',
  quartine[0].sorte === 'ambo' && quartine[1].sorte === 'terno',
  quartine.map(x => x.sorte).join(','));
check('l\'ordine e\' stabile: due chiamate danno la stessa sequenza',
  JSON.stringify(giocate([COMUNE, RARO, MEDIO], quote).map(x => x.numeri))
  === JSON.stringify(g.map(x => x.numeri)));

console.log('\nIL BUDGET NON SI SFORA MAI');
for (const budget of [1, 2, 3, 5, 7, 10, 50, 1000]) {
  const c = componi([COMUNE, RARO, MEDIO], budget, quote);
  check(`budget ${budget} €: speso ${c.speso} €`, c.speso <= budget,
    `speso ${c.speso}`);
}
const stretto = componi([COMUNE, RARO, MEDIO], 1, quote);
check('con un euro non entra niente (ogni giocata sta su due ruote)',
  stretto.dentro.length === 0 && stretto.speso === 0);
const largo = componi([COMUNE, RARO, MEDIO], 1000, quote);
check('con budget capiente non resta fuori niente', largo.fuori.length === 0);
check('e "mancano" e\' zero', largo.mancano === 0);
const parziale = componi([COMUNE, RARO, MEDIO], 6, quote);
check('dentro + fuori = tutte le giocate possibili',
  parziale.dentro.length + parziale.fuori.length === largo.dentro.length);
check('"mancano" e\' il costo di quelle rimaste fuori',
  parziale.mancano === parziale.fuori.reduce((s, x) => s + x.costo, 0));
check('col budget stretto entra il metodo raro, non quello comune',
  parziale.dentro.every(x => x.previsione.metodo !== 'lottofacile1'),
  parziale.dentro.map(x => x.previsione.metodo).join(','));

console.log('\nRIEPILOGO');
const r = riepilogo(largo.dentro);
check('il costo torna', r.speso === largo.speso, `${r.speso} vs ${largo.speso}`);
check('la probabilita\' resta fra 0 e 1', r.qualcosa > 0 && r.qualcosa < 1,
  String(r.qualcosa));
check('il ritorno per euro sta fra il terno e l\'ambo',
  r.per_euro > resaSorte('terno', quote) && r.per_euro <= resaSorte('ambo', quote) + 1e-9,
  String(r.per_euro));
check('nessuna giocata restituisce piu\' di quanto costa', r.attesa < r.speso);
const vuoto = riepilogo([]);
check('su zero giocate non esplode', vuoto.speso === 0 && vuoto.per_euro === 0);

console.log('\nLE ETICHETTE DICONO LA VERITA\'');
check('due numeri per ambo: "ambo"',
  etichettaGiocata({ sorte: 'ambo', numeri: [1, 2] }) === 'ambo');
check('un numero: "ambata"',
  etichettaGiocata({ sorte: 'estratto', numeri: [1] }) === 'ambata');
check('tre numeri giocati per ambo: "terzina per ambo"',
  etichettaGiocata({ sorte: 'ambo', numeri: [1, 2, 3] }) === 'terzina per ambo');
check('quattro numeri per terno: "quartina per terno"',
  etichettaGiocata({ sorte: 'terno', numeri: [1, 2, 3, 4] }) === 'quartina per terno');

console.log('\nCONVERGENZE');
const a = previsione({ chiave: 'a', metodo: 'x', per_anno: 10, sorti: [sorte('ambo', [7, 21])] });
const b = previsione({ chiave: 'b', metodo: 'y', per_anno: 20, sorti: [sorte('ambo', [7, 55])] });
const c = previsione({ chiave: 'c', metodo: 'y', per_anno: 20, sorti: [sorte('ambo', [7, 55])] });
const conv = convergenze(componi([a, b], 1000, quote).dentro);
check('trova il numero condiviso da due previsioni',
  conv.length === 1 && conv[0].numero === 7 && conv[0].previsioni === 2,
  JSON.stringify(conv));
const solo = convergenze(componi([a], 1000, quote).dentro);
check('una previsione sola non converge con se stessa', solo.length === 0, JSON.stringify(solo));
const tre = convergenze(componi([a, b, c], 1000, quote).dentro);
check('con tre previsioni conta le previsioni, non le giocate',
  tre[0].numero === 7 && tre[0].previsioni === 3, JSON.stringify(tre));

console.log('\nRUOTA PER RUOTA');
const mappa = perRuota([COMUNE, RARO, MEDIO], quote);
check('compaiono solo le ruote che hanno qualcosa in gioco',
  [...mappa.keys()].sort().join(' ') === 'BA CA GE MI NA VE',
  [...mappa.keys()].sort().join(' '));
check('una ruota senza previsioni non c\'e\'', !mappa.has('RM'));
check('ogni giocata compare sotto tutte le sue ruote',
  mappa.get('CA').length === mappa.get('GE').length,
  `CA ${mappa.get('CA').length}, GE ${mappa.get('GE').length}`);
check('sulla singola ruota costa un euro',
  mappa.get('NA').every(g => g.costo === 1),
  mappa.get('NA').map(g => g.costo).join(','));
check('e la ruota e\' una sola', mappa.get('NA').every(g => g.ruote.length === 1));
check('"altre" dice dove la stessa giocata e\' prevista',
  mappa.get('CA')[0].altre.join('') === 'GE', mappa.get('CA')[0].altre.join(','));
check('l\'ordine dentro la ruota resta quello del consiglio: prima il raro',
  mappa.get('CA')[0].previsione.metodo === 'unsoloambosecco',
  mappa.get('CA')[0].previsione.metodo);
check('giocare una ruota sola costa la meta\' di giocarne due',
  riepilogo(mappa.get('CA')).speso * 2
  === riepilogo(componi([RARO], 1000, quote).dentro).speso,
  `${riepilogo(mappa.get('CA')).speso} contro ${riepilogo(componi([RARO], 1000, quote).dentro).speso}`);
check('ma il ritorno per euro non cambia: e\' sempre la stessa sorte',
  vicino(riepilogo(mappa.get('CA')).per_euro,
         riepilogo(componi([RARO], 1000, quote).dentro).per_euro, 1e-12));
check('senza previsioni la mappa e\' vuota', perRuota([], quote).size === 0);

console.log('\nCALENDARIO DI RISERVA');
// Il martedi', giovedi', venerdi' e sabato di due settimane: il ritmo vero del
// Lotto di oggi. La proiezione deve ritrovarlo senza che glielo si dica.
const ULTIMI = ['2026-09-01', '2026-09-03', '2026-09-04', '2026-09-05',
                '2026-09-08', '2026-09-10', '2026-09-11', '2026-09-12'];
let d = proiettaConcorsi(ULTIMI, { da: '2026-09-13' });   // domenica
check('da domenica il primo concorso e\' il martedi\'', d[0] === '2026-09-15', d.join(' '));
check('poi giovedi\' e venerdi\'', d[1] === '2026-09-17' && d[2] === '2026-09-18', d.join(' '));
check('mai di domenica o di lunedi\'',
  proiettaConcorsi(ULTIMI, { da: '2026-09-13', quante: 8 })
    .every(g => ![0, 1].includes(new Date(g + 'T00:00:00').getDay())),
  proiettaConcorsi(ULTIMI, { da: '2026-09-13', quante: 8 }).join(' '));
check('se il giorno stesso e\' di concorso, e\' il primo proposto',
  proiettaConcorsi(ULTIMI, { da: '2026-09-15' })[0] === '2026-09-15');
check('ne propone quante gliene chiedi',
  proiettaConcorsi(ULTIMI, { da: '2026-09-13', quante: 6 }).length === 6);
check('senza storia non inventa niente', proiettaConcorsi([], { da: '2026-09-13' }).length === 0);
check('un solo concorso isolato non fa un calendario',
  proiettaConcorsi(['2026-09-03'], { da: '2026-09-13' }).length === 0);

check('alle 18 il giorno utile e\' oggi',
  primoGiornoUtile(new Date(2026, 8, 15, 18, 0)) === '2026-09-15');
check('alle 20:30 e\' domani',
  primoGiornoUtile(new Date(2026, 8, 15, 20, 30)) === '2026-09-16');
check('alle 20 in punto e\' gia\' domani',
  primoGiornoUtile(new Date(2026, 8, 15, 20, 0)) === '2026-09-16');
check('a fine mese passa al mese dopo',
  primoGiornoUtile(new Date(2026, 8, 30, 21, 0)) === '2026-10-01');
check('la data non slitta per il fuso: resta quella locale',
  primoGiornoUtile(new Date(2026, 8, 15, 23, 59)) === '2026-09-16');

console.log('\nI NUMERI IN COMUNE');
// La sezione promette una cosa sola: questi numeri sono chiesti da piu' di un
// METODO. Non da piu' di una previsione: due previsioni dello stesso metodo
// nascono dalla stessa condizione di ricerca e concordano per costruzione, non
// perche' si siano trovate d'accordo. Le prove qui sotto difendono questa
// distinzione, che e' l'unica cosa onesta che la sezione possa dire.
const A = previsione({ chiave: 'a', metodo: 'fulmine', per_anno: 89,
  ruote: ['NA', 'MI'], sorti: [sorte('ambo', [7, 23])] });
const B = previsione({ chiave: 'b', metodo: 'lottofacile1', per_anno: 1062,
  ruote: ['NA'], sorti: [sorte('ambata', [23]), sorte('ambo', [23, 41])] });
const C = previsione({ chiave: 'c', metodo: 'lottofacile1', per_anno: 1062,
  ruote: ['NA'], sorti: [sorte('ambo', [23, 55])] });
const D = previsione({ chiave: 'd', metodo: 'ambosecco', per_anno: 12,
  ruote: ['BA'], sorti: [sorte('ambo', [41, 7])] });

const com = numeriInComune([A, B, C, D]);
const trova = (lista, n) => lista.find(v => v.numero === n);

check('un numero chiesto da un metodo solo non compare',
  trova(com, 55) === undefined, JSON.stringify(com.map(v => v.numero)));
check('il 23 e\' chiesto da due metodi', trova(com, 23)?.metodi === 2,
  String(trova(com, 23)?.metodi));
check('e da tre previsioni diverse', trova(com, 23)?.previsioni === 3,
  String(trova(com, 23)?.previsioni));
check('due previsioni dello stesso metodo non contano per due',
  trova(com, 23).nomi.length === 2 && new Set(trova(com, 23).nomi).size === 2,
  trova(com, 23).nomi.join(' '));
check('il 7 e il 41 pure ci sono, con due metodi ciascuno',
  trova(com, 7)?.metodi === 2 && trova(com, 41)?.metodi === 2);
check('in testa c\'e\' chi ha piu\' previsioni, a pari metodi',
  com[0].numero === 23, com.map(v => `${v.numero}:${v.previsioni}`).join(' '));
check('a pari tutto vince il numero piu\' piccolo',
  com[1].numero === 7 && com[2].numero === 41,
  com.map(v => v.numero).join(' '));
check('le ruote sono contate, non solo elencate',
  trova(com, 23).ruote[0].ruota === 'NA' && trova(com, 23).ruote[0].previsioni === 3,
  JSON.stringify(trova(com, 23).ruote));
check('chiedendo tre metodi d\'accordo non resta piu\' niente',
  numeriInComune([A, B, C, D], { minimoMetodi: 3 }).length === 0);
check('chiedendone uno solo torna ogni numero in gioco',
  numeriInComune([A, B, C, D], { minimoMetodi: 1 }).map(v => v.numero).sort((a, b) => a - b)
    .join(',') === '7,23,41,55');
check('senza previsioni non c\'e\' niente in comune', numeriInComune([]).length === 0);
check('una previsione sola non e\' un accordo', numeriInComune([A]).length === 0);

const unica = previsioneUnica(com);
check('la previsione unica prende i numeri in comune',
  unica.numeri.join(',') === '7,23,41', unica.numeri.join(','));
check('e li mette in ordine crescente',
  unica.numeri.every((n, i) => i === 0 || n > unica.numeri[i - 1]));
check('la ruota e\' quella dove il gruppo e\' chiesto piu\' spesso',
  unica.ruota === 'NA', unica.ruota);
check('dichiara da quali metodi viene',
  new Set(unica.metodi).size === unica.metodi.length && unica.metodi.length === 3,
  unica.metodi.join(' '));
check('non tiene piu\' numeri di quanti gliene chiedi',
  previsioneUnica(com, { quanti: 2 }).numeri.length === 2);
check('con un numero solo non c\'e\' previsione da fare',
  previsioneUnica(com, { quanti: 1 }) === null);
check('senza numeri in comune non inventa una giocata',
  previsioneUnica([]) === null);
// La sezione non si limita a mostrare i numeri: ne fa una giocata di ambo e ne
// stampa il costo. Se la schedina rifiutasse quei numeri, la pagina mostrerebbe
// una giocata che al banco nessuno accetterebbe.
const giocabile = (numeri) => {
  try {
    const c = simula({ numeri, ruote: [unica.ruota], sorti: ['ambo'],
                       importo: combinazioni(numeri.length, 2), quote });
    return c.righe[0].combinazioni === combinazioni(numeri.length, 2);
  } catch { return false; }
};
check('i numeri della previsione unica sono giocabili sul serio',
  giocabile(unica.numeri), unica.numeri.join(','));
check('e un euro per ambo vuol dire un euro per ambo',
  simula({ numeri: unica.numeri, ruote: [unica.ruota], sorti: ['ambo'],
           importo: combinazioni(unica.numeri.length, 2), quote }).importo
  === combinazioni(unica.numeri.length, 2));

console.log(`\n${'='.repeat(60)}\nRISULTATO: ${ok} OK, ${fail} FAIL`);
process.exit(fail ? 1 : 0);
