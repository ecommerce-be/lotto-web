/**
 * Prove della lettura del passato.
 *
 * Tre cose:
 *
 *   - l'archivio e i file d'anno vengono letti senza perdere ne' spostare
 *     niente, e una riga storta fa rumore invece di passare inosservata (un
 *     archivio letto male darebbe risposte plausibili e sbagliate, che e' il
 *     peggio che possa capitare qui);
 *
 *   - il controllo delle uscite da' **esattamente** quello che da' Python. E'
 *     la prova piu' importante del file: la regola dei fascicoli e' scritta due
 *     volte, in motore/valutazione.py e in docs/storico.js, e due copie della
 *     stessa regola divergono sempre prima o poi. Il confronto gira su
 *     trecento previsioni vere, scritte da prove/test_pipeline.py;
 *
 *   - le formule dei metodi applicate a cinque numeri danno quello che dice il
 *     fascicolo, e restano quelle di motore/lotto.py.
 *
 *     node prove/test_storico.mjs
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  leggiStorico, leggiPrevisioni, previsioniDi, estrazione, quadro,
  concorsoVicino, verifica, usciteDi, StoricoNonValido, RUOTE,
} from '../docs/storico.js';
import {
  f90, complemento, diametrale, vertibile, figura, cadenza, terzinaDi,
  trasformazioni, gruppi, insieme,
} from '../docs/derivati.js';

const QUI = dirname(fileURLToPath(import.meta.url));
const DOCS = join(QUI, '..', 'docs');

let ok = 0, fail = 0;
const check = (nome, cond, dettaglio = '') => {
  if (cond) { ok++; console.log(`  OK   ${nome}`); }
  else { fail++; console.log(`  FAIL ${nome}  ${dettaglio}`); }
};

// Un archivio finto, scritto nello stesso formato di quello vero.
const riga = (giorno, q) => giorno.replaceAll('-', '')
  + RUOTE.map(r => (q[r]
    ? q[r].map(n => String(n).padStart(2, '0')).join('')
    : '-'.repeat(10))).join('');
const archivio = (righe) => '# finto\n' + righe.join('\n') + '\n';

const FINTO = leggiStorico(archivio([
  riga('2000-01-04', { NA: [7, 23, 41, 55, 62], BA: [1, 2, 3, 4, 5] }),
  riga('1999-12-30', { NA: [7, 23, 41, 11, 12], BA: [6, 7, 8, 9, 10] }),
  riga('2000-01-06', { NA: [7, 80, 81, 82, 83], BA: [23, 41, 13, 14, 15] }),
  riga('2000-01-08', { NA: [23, 41, 84, 85, 86], BA: [16, 17, 18, 19, 20] }),
  riga('2000-01-11', { NA: [7, 23, 41, 87, 88], BA: [21, 22, 24, 25, 26] }),
  riga('2000-01-13', { BA: [7, 23, 41, 55, 62] }),
].sort()));

console.log('LEGGERE L\'ARCHIVIO');
check('trova tutti i concorsi', FINTO.giorni.length === 6, String(FINTO.giorni.length));
check('le date sono in ordine e con i trattini',
  FINTO.giorni[0] === '1999-12-30' && FINTO.giorni.at(-1) === '2000-01-13');
check('i numeri restano nell\'ordine di estrazione, non riordinati',
  estrazione(FINTO, '2000-01-04', 'NA').join(',') === '7,23,41,55,62');
check('una ruota che non ha estratto e\' assente, non e\' zeri',
  estrazione(FINTO, '2000-01-13', 'NA') === null);
check('il quadro del giorno elenca solo le ruote che hanno estratto',
  Object.keys(quadro(FINTO, '2000-01-13')).join(',') === 'BA');
check('un giorno che non c\'e\' non da\' un quadro finto',
  quadro(FINTO, '1980-01-01') === null);

let esplosa = false;
try { leggiStorico('# finto\n20000104123\n'); } catch (e) { esplosa = e instanceof StoricoNonValido; }
check('una riga della lunghezza sbagliata ferma tutto', esplosa);
let vuota = false;
try { leggiStorico('# solo commenti\n'); } catch (e) { vuota = e instanceof StoricoNonValido; }
check('uno storico senza concorsi non si legge in silenzio', vuota);

console.log('\nSCEGLIERE UNA DATA QUALUNQUE');
check('se il giorno e\' di concorso resta quello',
  concorsoVicino(FINTO, '2000-01-06') === '2000-01-06');
check('altrimenti prende il concorso piu\' vicino',
  concorsoVicino(FINTO, '2000-01-07') === '2000-01-06',
  concorsoVicino(FINTO, '2000-01-07'));
check('e guarda anche in avanti, se e\' piu\' vicino',
  concorsoVicino(FINTO, '2000-01-10') === '2000-01-11');
check('prima del primo concorso propone il primo',
  concorsoVicino(FINTO, '1900-01-01') === '1999-12-30');
check('dopo l\'ultimo propone l\'ultimo',
  concorsoVicino(FINTO, '2030-01-01') === '2000-01-13');

console.log('\nCONTROLLARE LE USCITE');
const prev = {
  giorno: '2000-01-04', metodo: 'finto', ruote: ['NA'], colpi: 3,
  anche_tutte: false, nota: null, avviso: null,
  sorti: [
    { tipo: 'ambo', numeri: [23, 41] },     // esce su NA al 2o colpo
    { tipo: 'ambata', numeri: [7] },        // esce su NA al 1o colpo
    { tipo: 'ambo', numeri: [55, 62] },     // non esce mai su NA
  ],
};
const v = verifica(FINTO, prev);
const [ambo, ambata, mai] = v.sorti;
check('l\'ambata esce al primo colpo', ambata.stato === 'vinta'
  && ambata.esiti[0].colpo === 1 && ambata.esiti[0].ruota === 'NA',
  JSON.stringify(ambata.esiti));
check('l\'ambo esce al secondo colpo, non al primo', ambo.stato === 'vinta'
  && ambo.esiti[0].colpo === 2, JSON.stringify(ambo.esiti));
check('un numero solo non basta a fare un ambo',
  !ambo.esiti.some(e => e.usciti.length < 2));
check('cio\' che non esce entro i colpi e\' scaduto', mai.stato === 'scaduta');
check('ma si vede dov\'era finito nel frattempo, sulle altre ruote',
  ambo.altrove.some(a => a.ruota === 'BA' && a.colpo === 1),
  JSON.stringify(ambo.altrove));
check('le uscite sulle ruote non in gioco non fanno vincere',
  !ambo.esiti.some(e => e.ruota !== 'NA'));
check('la sorte si sospende quando si verifica: niente colpi dopo',
  ambata.esiti.every(e => e.colpo <= 1));

const tutte = verifica(FINTO, { ...prev, anche_tutte: true, colpi: 1 });
check('con "anche a Tutte" l\'uscita su un\'altra ruota e\' un esito',
  tutte.sorti[0].esiti.some(e => e.ruota === 'BA' && e.a_tutte === true),
  JSON.stringify(tutte.sorti[0].esiti));
check('ma la sorte non si sospende per un esito a Tutte',
  tutte.sorti[0].stato !== 'vinta', tutte.sorti[0].stato);

const corta = verifica(FINTO, { ...prev, colpi: 1 });
check('oltre i colpi si dice quando si sarebbe verificata',
  corta.sorti[0].oltre?.colpo === 2, JSON.stringify(corta.sorti[0].oltre));
check('e non si guarda oltre per una sorte gia\' vinta',
  corta.sorti[1].oltre === null);
check('una previsione di un giorno che non c\'e\' non si verifica',
  verifica(FINTO, { ...prev, giorno: '1980-01-01' }) === null);

const uscite = usciteDi(FINTO, [23, 41, 99], '2000-01-04', { concorsi: 3 });
check('le uscite dei numeri sciolti guardano tutte le ruote',
  uscite.find(u => u.numero === 23).ruote.join(',') === 'BA,NA',
  JSON.stringify(uscite.find(u => u.numero === 23)));
check('un numero che non esce mai resta con la lista vuota',
  uscite.find(u => u.numero === 99).uscite.length === 0);
check('in testa c\'e\' il numero uscito piu\' volte',
  uscite[0].uscite.length >= uscite.at(-1).uscite.length);

console.log('\nLE PREVISIONI GIA\' RILEVATE');
const ANNO = leggiPrevisioni([
  '# commento',
  '20000104|fulmine|NA,MI|12|1|ambata:34;ambo:34-12|nota qui|un avviso',
  '20000104|lottofacile1|BA,CA|5|0|ambo:7-9||',
  '20000106|fulmine|NA,MI|12|0|ambata:1||',
].join('\n') + '\n');
check('legge tutte le righe che non sono commenti', ANNO.length === 3,
  String(ANNO.length));
check('nota e avviso arrivano interi',
  ANNO[0].nota === 'nota qui' && ANNO[0].avviso === 'un avviso');
check('i campi vuoti diventano null', ANNO[1].nota === null && ANNO[1].avviso === null);
check('le sorti si ricompongono', ANNO[0].sorti[1].numeri.join(',') === '34,12');
check('"anche a Tutte" e\' un vero booleano',
  ANNO[0].anche_tutte === true && ANNO[1].anche_tutte === false);
let storta = false;
try { leggiPrevisioni('20000104|fulmine|NA\n'); } catch (e) { storta = e instanceof StoricoNonValido; }
check('una riga con i campi sbagliati ferma tutto', storta);

const delGiorno = previsioniDi(ANNO, '20000104'.replace(/(\d{4})(\d\d)(\d\d)/, '$1-$2-$3'), 'BA');
check('si filtra per giorno', delGiorno.length === 2);
check('e la ruota scelta viene prima',
  delGiorno[0].ruote.includes('BA'), JSON.stringify(delGiorno.map(p => p.ruote)));

console.log('\nLE DUE IMPLEMENTAZIONI DEVONO COINCIDERE');
const VERO = leggiStorico(readFileSync(join(DOCS, 'dati', 'storico.txt'), 'utf8'));
const riferimento = JSON.parse(
  readFileSync(join(QUI, 'dati', 'esiti-riferimento.json'), 'utf8'));
check('il riferimento di Python c\'e\'', riferimento.length > 100,
  String(riferimento.length));

let confrontate = 0, statiDiversi = [], esitiDiversi = [];
for (const r of riferimento) {
  const p = leggiPrevisioni(r.previsione + '\n')[0];
  const nostra = verifica(VERO, p);
  if (!nostra) continue;
  r.sorti.forEach((attesa, i) => {
    const mia = nostra.sorti[i];
    confrontate++;
    if (mia.stato !== attesa.stato)
      statiDiversi.push(`${p.giorno} ${p.metodo} ${attesa.tipo} ${attesa.numeri}: `
        + `Python ${attesa.stato}, JS ${mia.stato}`);
    const chiave = e => `${e.giorno}/${e.ruota}/${e.colpo}/${e.usciti.join('-')}`;
    const a = attesa.esiti.map(chiave).sort().join(' ');
    const b = mia.esiti.map(chiave).sort().join(' ');
    if (a !== b)
      esitiDiversi.push(`${p.giorno} ${p.metodo} ${attesa.numeri}:\n      Python ${a}\n      JS     ${b}`);
  });
}
check('si sono confrontate abbastanza sorti', confrontate > 500, String(confrontate));
check('lo stato di ogni sorte e\' lo stesso in Python e in JavaScript',
  statiDiversi.length === 0, '\n      ' + statiDiversi.slice(0, 3).join('\n      '));
check('e gli esiti sono gli stessi, colpo per colpo e ruota per ruota',
  esitiDiversi.length === 0, '\n      ' + esitiDiversi.slice(0, 2).join('\n      '));
const vinte = riferimento.flatMap(r => r.sorti).filter(s => s.stato === 'vinta').length;
check('e fra quelle confrontate ce ne sono parecchie vinte, se no non si proverebbe niente',
  vinte > 50, `${vinte} vinte`);

console.log('\nLE FORMULE DEI FASCICOLI');
check('fuori 90: il 90 resta 90, il 91 torna 1',
  f90(90) === 90 && f90(91) === 1 && f90(180) === 90);
check('complemento a 90', complemento(23) === 67 && complemento(45) === 45);
check('diametrale: piu\' quarantacinque', diametrale(1) === 46 && diametrale(46) === 1
  && diametrale(45) === 90);
check('il diametrale del diametrale e\' il numero di partenza',
  [...Array(90).keys()].every(i => diametrale(diametrale(i + 1)) === i + 1));
check('vertibile: 12 e 21', vertibile(12) === 21 && vertibile(21) === 12);
check('le decine tonde e le unita\' si scambiano',
  vertibile(7) === 70 && vertibile(70) === 7);
check('i sedici irregolari seguono la tavola del fascicolo',
  vertibile(11) === 19 && vertibile(19) === 11 && vertibile(88) === 89);
check('il vertibile del vertibile e\' il numero di partenza',
  [...Array(90).keys()].every(i => vertibile(vertibile(i + 1)) === i + 1));
check('figura: da 1 a 9', figura(1) === 1 && figura(9) === 9 && figura(10) === 1
  && figura(90) === 9);
check('cadenza: l\'ultima cifra', cadenza(7) === 7 && cadenza(70) === 0
  && cadenza(23) === 3);
check('la terzina simmetrica sono tre numeri a distanza trenta',
  terzinaDi(5).join(',') === '5,35,65' && terzinaDi(65).join(',') === '65,5,35');

const T = trasformazioni([7, 23, 41, 55, 62]);
check('una riga per numero', T.length === 5 && T[0].numero === 7);
check('ogni riga porta le quattro trasformazioni',
  T[0].complemento === 83 && T[0].diametrale === 52 && T[0].vertibile === 70
  && T[0].terzina.join(',') === '37,67');
const G = gruppi([7, 16, 25, 41, 62]);
check('i numeri della stessa figura finiscono nello stesso gruppo',
  G.figure[0].numeri.join(',') === '7,16,25', JSON.stringify(G.figure));
check('un numero da solo non fa gruppo',
  G.figure.every(g => g.numeri.length >= 2)
  && G.cadenze.every(g => g.numeri.length >= 2));
check('senza gruppi non si inventa niente',
  gruppi([1, 2, 3]).figure.length === 0);
const I = insieme([7, 23, 41, 55, 62]);
check('l\'insieme dei derivati non ripete i numeri di partenza',
  !I.some(n => [7, 23, 41, 55, 62].includes(n)));
check('ne\' se stesso', new Set(I).size === I.length);
check('ed e\' ordinato', I.every((n, i) => i === 0 || n > I[i - 1]));
check('tutti i derivati stanno fra 1 e 90', I.every(n => n >= 1 && n <= 90));

console.log(`\n${'='.repeat(60)}\nRISULTATO: ${ok} OK, ${fail} FAIL`);
process.exit(fail ? 1 : 0);
