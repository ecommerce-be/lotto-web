/**
 * Prove della ricerca delle ripetizioni.
 *
 * Qui si difendono tre cose:
 *
 *   - il file dello storico viene letto senza perdere ne' spostare niente, e
 *     una riga storta fa rumore invece di passare inosservata (un archivio
 *     letto male darebbe risposte plausibili e sbagliate, che e' il peggio);
 *   - la ricerca guarda solo in avanti, trova tutto quello che c'e' e non
 *     inventa niente: i conteggi sono quelli veri anche quando l'elenco
 *     mostrato e' tagliato;
 *   - il numero di ripetizioni attese per puro caso e' esatto, perche' e'
 *     l'unica cosa che rende leggibile il numero di quelle trovate.
 *
 *     node prove/test_ripetizioni.mjs
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  leggiStorico, estrazione, quadro, concorsoVicino, probRipetizione,
  attesi, cerca, confronto, StoricoNonValido, RUOTE,
} from '../docs/ripetizioni.js';

const QUI = dirname(fileURLToPath(import.meta.url));

let ok = 0, fail = 0;
const check = (nome, cond, dettaglio = '') => {
  if (cond) { ok++; console.log(`  OK   ${nome}`); }
  else { fail++; console.log(`  FAIL ${nome}  ${dettaglio}`); }
};
const vicino = (a, b, t = 1e-9) => Math.abs(a - b) <= t * Math.max(1, Math.abs(b));

// Un archivio finto, scritto nello stesso formato di quello vero.
const riga = (giorno, quadro) => giorno.replaceAll('-', '')
  + RUOTE.map(r => (quadro[r]
    ? quadro[r].map(n => String(n).padStart(2, '0')).join('')
    : '-'.repeat(10))).join('');
const archivio = (righe) => '# finto\n' + righe.join('\n') + '\n';

const FINTO = leggiStorico(archivio([
  // il concorso di partenza
  riga('2000-01-04', { NA: [7, 23, 41, 55, 62], BA: [1, 2, 3, 4, 5] }),
  // prima della partenza, con tre numeri in comune: non deve contare
  riga('1999-12-30', { NA: [7, 23, 41, 11, 12], BA: [6, 7, 8, 9, 10] }),
  // un terno su Napoli
  riga('2001-03-06', { NA: [7, 23, 41, 80, 81], BA: [11, 12, 13, 14, 15] }),
  // un ambo su Napoli
  riga('2002-05-07', { NA: [7, 23, 88, 89, 90], BA: [16, 17, 18, 19, 20] }),
  // un solo numero in comune: non e' una ripetizione
  riga('2003-06-10', { NA: [7, 70, 71, 72, 73], BA: [21, 22, 23, 24, 25] }),
  // una quaterna, ma su Bari: si vede solo cercando su tutte le ruote
  riga('2004-07-13', { NA: [30, 31, 32, 33, 34], BA: [7, 23, 41, 55, 90] }),
  // Napoli non estrae, Bari si'
  riga('2005-08-16', { BA: [7, 23, 41, 55, 62] }),
].sort()));

console.log('LEGGERE LO STORICO');
check('trova tutti i concorsi', FINTO.giorni.length === 7, String(FINTO.giorni.length));
check('le date sono in ordine e con i trattini',
  FINTO.giorni[0] === '1999-12-30' && FINTO.giorni.at(-1) === '2005-08-16',
  FINTO.giorni.join(' '));
check('i numeri restano nell\'ordine di estrazione, non riordinati',
  estrazione(FINTO, '2004-07-13', 'BA').join(',') === '7,23,41,55,90');
check('una ruota che non ha estratto e\' assente, non e\' zeri',
  estrazione(FINTO, '2005-08-16', 'NA') === null);
check('il quadro del giorno elenca solo le ruote che hanno estratto',
  Object.keys(quadro(FINTO, '2005-08-16')).join(',') === 'BA');
check('un giorno che non c\'e\' non da\' un quadro finto',
  quadro(FINTO, '1980-01-01') === null);
check('le righe di commento non diventano concorsi',
  !FINTO.giorni.includes(undefined));

let esplosa = false;
try { leggiStorico('# finto\n20000104123\n'); } catch (e) { esplosa = e instanceof StoricoNonValido; }
check('una riga della lunghezza sbagliata ferma tutto', esplosa);
let vuota = false;
try { leggiStorico('# solo commenti\n'); } catch (e) { vuota = e instanceof StoricoNonValido; }
check('uno storico senza concorsi non si legge in silenzio', vuota);

console.log('\nSCEGLIERE UNA DATA QUALUNQUE');
check('se il giorno e\' di concorso resta quello',
  concorsoVicino(FINTO, '2001-03-06') === '2001-03-06');
check('altrimenti prende il concorso piu\' vicino',
  concorsoVicino(FINTO, '2001-03-08') === '2001-03-06',
  concorsoVicino(FINTO, '2001-03-08'));
check('e guarda anche in avanti, se e\' piu\' vicino',
  concorsoVicino(FINTO, '2002-05-05') === '2002-05-07',
  concorsoVicino(FINTO, '2002-05-05'));
check('prima del primo concorso propone il primo',
  concorsoVicino(FINTO, '1900-01-01') === '1999-12-30');
check('dopo l\'ultimo propone l\'ultimo',
  concorsoVicino(FINTO, '2030-01-01') === '2005-08-16');

console.log('\nCERCARE LE RIPETIZIONI');
const r = cerca(FINTO, { giorno: '2000-01-04', ruota: 'NA' });
check('l\'estrazione di partenza e\' quella giusta',
  r.origine.numeri.join(',') === '7,23,41,55,62');
check('guarda solo i concorsi successivi', r.concorsi === 5, String(r.concorsi));
check('il terno del 2001 c\'e\'', r.conteggio[3] === 1, JSON.stringify(r.conteggio));
check('e l\'ambo del 2002 pure', r.conteggio[2] === 1);
check('un numero solo in comune non e\' una ripetizione',
  !r.trovati.some(t => t.giorno === '2003-06-10'));
check('cio\' che e\' successo PRIMA non entra nel conto',
  !r.trovati.some(t => t.giorno === '1999-12-30'), JSON.stringify(r.trovati));
check('la quaterna su Bari non si vede cercando su Napoli',
  r.conteggio[4] === 0);
check('in testa c\'e\' il ritrovamento piu\' grosso',
  r.trovati[0].quanti === 3 && r.trovati[0].giorno === '2001-03-06');
check('e dice quali numeri sono tornati',
  r.trovati[0].numeri.join(',') === '7,23,41');
check('il totale e\' la somma delle misure',
  r.conteggio.almeno2 === r.conteggio[2] + r.conteggio[3] + r.conteggio[4] + r.conteggio[5]);
check('senza taglio non c\'e\' niente di troncato', r.troncato === false);

const tutte = cerca(FINTO, { giorno: '2000-01-04', ruota: 'NA', tutteLeRuote: true });
check('allargando a tutte le ruote la quaterna di Bari salta fuori',
  tutte.conteggio[4] === 1, JSON.stringify(tutte.conteggio));
check('e anche la ripetizione del giorno in cui Napoli non estrae',
  tutte.trovati.some(t => t.giorno === '2005-08-16' && t.ruota === 'BA' && t.quanti === 5));
check('dieci ruote vogliono dieci volte gli attesi',
  vicino(tutte.attesi.almeno2, r.attesi.almeno2 * 10));
check('i concorsi guardati sono gli stessi', tutte.concorsi === r.concorsi);

const soloTerni = cerca(FINTO, { giorno: '2000-01-04', ruota: 'NA', minimo: 3 });
check('chiedendo almeno tre, gli ambi spariscono',
  soloTerni.trovati.every(t => t.quanti >= 3) && soloTerni.trovati.length === 1);

const tagliata = cerca(FINTO, { giorno: '2000-01-04', ruota: 'NA', quante: 1 });
check('l\'elenco si puo\' tagliare', tagliata.trovati.length === 1);
check('ma i conteggi restano quelli veri',
  tagliata.conteggio.almeno2 === r.conteggio.almeno2 && tagliata.troncato === true);
check('e il taglio tiene il ritrovamento piu\' grosso',
  tagliata.trovati[0].quanti === 3);

check('una ruota che quel giorno non ha estratto non si puo\' cercare',
  cerca(FINTO, { giorno: '2005-08-16', ruota: 'NA' }) === null);
check('ne\' un giorno che non esiste',
  cerca(FINTO, { giorno: '1980-01-01', ruota: 'NA' }) === null);
check('dall\'ultimo concorso non c\'e\' futuro da guardare',
  cerca(FINTO, { giorno: '2005-08-16', ruota: 'BA' }).concorsi === 0);

console.log('\nQUANTE SE NE ASPETTAVANO');
check('le sei probabilita\' fanno uno',
  vicino([0, 1, 2, 3, 4, 5].reduce((s, q) => s + probRipetizione(q), 0), 1, 1e-12));
check('due numeri in comune: 2,25 volte su cento',
  vicino(probRipetizione(2), 987700 / 43949268, 1e-12), String(probRipetizione(2)));
check('la cinquina identica: una su 43.949.268',
  vicino(probRipetizione(5), 1 / 43949268, 1e-12));
check('un terno vale piu\' o meno un ambo diviso ventotto',
  probRipetizione(2) / probRipetizione(3) > 27 && probRipetizione(2) / probRipetizione(3) < 29);
check('gli attesi crescono con i concorsi guardati',
  vicino(attesi(2000).almeno2, attesi(1000).almeno2 * 2));
check('su mille concorsi ci si aspettano una ventina di ambi',
  attesi(1000).almeno2 > 20 && attesi(1000).almeno2 < 25,
  String(attesi(1000).almeno2));

check('sotto i cinque attesi non si dichiara nessuno scarto',
  confronto(3, 1).scarto === null);
check('a meta\' degli attesi si dice che e\' meno del previsto',
  confronto(20, 50).parola === 'meno del previsto');
check('al doppio si dice che e\' piu\' del previsto',
  confronto(100, 50).parola.startsWith('pi'));
check('vicino agli attesi si dice che e\' andata come doveva',
  confronto(48, 50).parola === 'quanto ci si aspettava dal caso');

console.log('\nSULL\'ARCHIVIO VERO');
const VERO = leggiStorico(readFileSync(join(QUI, '..', 'docs', 'dati', 'storico.txt'), 'utf8'));
check('l\'archivio pubblicato si legge', VERO.giorni.length > 7000, String(VERO.giorni.length));
check('parte dal 1939', VERO.giorni[0].startsWith('1939'), VERO.giorni[0]);
check('le date sono in ordine crescente',
  VERO.giorni.every((g, i) => i === 0 || g > VERO.giorni[i - 1]));
check('tutti i numeri stanno fra 1 e 90 (lo zero vuol dire ruota assente)',
  VERO.numeri.every(n => n >= 0 && n <= 90));
check('nessuna ruota ha numeri ripetuti nella stessa estrazione',
  VERO.giorni.every((g) => Object.values(quadro(VERO, g))
    .every(c => new Set(c).size === 5)));

const mezzo = VERO.giorni[Math.floor(VERO.giorni.length / 2)];
const ruotaViva = Object.keys(quadro(VERO, mezzo))[0];
const reale = cerca(VERO, { giorno: mezzo, ruota: ruotaViva });
check('una ricerca vera non perde per strada nessuna ripetizione',
  reale.conteggio.almeno2 >= reale.trovati.length);
check('e i trovati assomigliano agli attesi (e\' cosi\' che deve andare)',
  reale.conteggio.almeno2 > reale.attesi.almeno2 * 0.6
  && reale.conteggio.almeno2 < reale.attesi.almeno2 * 1.6,
  `${reale.conteggio.almeno2} trovati, ${reale.attesi.almeno2.toFixed(1)} attesi`);
check('cercare su tutte e dieci le ruote resta immediato',
  (() => { const t = Date.now();
    cerca(VERO, { giorno: VERO.giorni[100], ruota: ruotaViva, tutteLeRuote: true });
    return Date.now() - t < 1500; })());

console.log(`\n${'='.repeat(60)}\nRISULTATO: ${ok} OK, ${fail} FAIL`);
process.exit(fail ? 1 : 0);
