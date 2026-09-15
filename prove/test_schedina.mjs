/**
 * Prove del simulatore di schedina.
 *
 * Il banco di prova sono le probabilita' note del Lotto, che sono pubbliche e
 * non opinabili: estratto una su 18, ambo secco una su 400,5, terno secco una
 * su 11.748, quaterna una su 511.038, cinquina una su 43.949.268. Se il modulo
 * riproduce quelle, la ripartizione della posta e tutto il resto stanno in piedi.
 *
 *     node prove/test_schedina.mjs
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  simula, probabilitaPresi, combinazioni, GiocataNonValida, NUMERI_PER_SORTE,
} from '../docs/schedina.js';

const QUI = dirname(fileURLToPath(import.meta.url));
const quote = JSON.parse(readFileSync(join(QUI, '..', 'archivio', 'quote.json'), 'utf8'));

let ok = 0, fail = 0;
const check = (nome, cond, dettaglio = '') => {
  if (cond) { ok++; console.log(`  OK   ${nome}`); }
  else { fail++; console.log(`  FAIL ${nome}  ${dettaglio}`); }
};
const vicino = (a, b, t = 1e-9) => Math.abs(a - b) <= t * Math.max(1, Math.abs(b));
const gioca = (o) => simula({ quote, ...o });

console.log("PROBABILITA' NOTE (sorte secca, una ruota)");
for (const [k, unaSu] of [[1, 18], [2, 400.5], [3, 11748], [4, 511038], [5, 43949268]]) {
  const p = probabilitaPresi(k, k);
  check(`${k} numer${k === 1 ? 'o' : 'i'}: una su ${unaSu}`,
        vicino(1 / p, unaSu, 1e-6), `ottenuto una su ${(1 / p).toFixed(2)}`);
}
check('C(90,5) = 43.949.268', combinazioni(90, 5) === 43949268, String(combinazioni(90, 5)));
check('C(5,2) = 10', combinazioni(5, 2) === 10);

console.log('\nLA DISTRIBUZIONE E\' COMPLETA');
for (const giocati of [1, 5, 10]) {
  let t = 0;
  for (let m = 0; m <= 5; m++) t += probabilitaPresi(giocati, m);
  check(`${giocati} numeri giocati: le probabilita' sommano a 1`, vicino(t, 1, 1e-12), String(t));
}

console.log('\nAMBO SECCO, 1 EURO, UNA RUOTA');
let r = gioca({ numeri: [37, 39], ruote: ['NA'], sorti: ['ambo'], importo: 1 });
let sc = r.righe[0].scenari[0];
check('una sola combinazione', r.righe[0].combinazioni === 1);
check('vincita lorda 250', vicino(sc.lordo, 250));
check('vincita netta 230 (ritenuta 8%)', vicino(sc.netto, 250 * (1 - quote.ritenuta)),
      String(sc.netto));
check('probabilita\' una su 400,5', vicino(1 / sc.probabilita, 400.5, 1e-6));
check('ritorno atteso 0,574 per euro',
      vicino(r.ritornoAttesoPerEuro, 250 / 400.5 * (1 - quote.ritenuta), 1e-3),
      String(r.ritornoAttesoPerEuro));

console.log('\nLA POSTA SI RIPARTISCE');
r = gioca({ numeri: [1, 2, 3, 4, 5], ruote: ['BA', 'NA'], sorti: ['ambo', 'terno'], importo: 10 });
const ambo = r.righe.find(x => x.sorte === 'ambo');
const terno = r.righe.find(x => x.sorte === 'terno');
check('2 ruote x 2 sorti: 2,50 per ruota e sorte', vicino(ambo.postaPerRuota, 2.5));
check('5 numeri per ambo sono 10 combinazioni', ambo.combinazioni === 10);
check('quindi 0,25 per ambo', vicino(ambo.postaPerCombinazione, 0.25));
check('con 3 numeri usciti si vincono 3 ambi',
      ambo.scenari.find(s => s.presi === 3).combinazioniVincenti === 3);
check('con 5 numeri usciti si vincono 10 ambi',
      ambo.scenari.find(s => s.presi === 5).combinazioniVincenti === 10);
check('e un solo terno con 3 usciti',
      terno.scenari.find(s => s.presi === 3).combinazioniVincenti === 1);

console.log("\nIL RITORNO ATTESO NON DIPENDE DA QUANTI NUMERI NE' DA QUANTE RUOTE");
const attesoAmbo = 250 / 400.5 * (1 - quote.ritenuta);
for (const [numeri, ruote, importo] of [
  [[7, 21], ['MI'], 1],
  [[7, 21, 55], ['MI'], 3],
  [[1, 2, 3, 4, 5, 6], ['BA', 'CA', 'FI'], 50],
  [[1, 2, 3, 4, 5, 6, 7, 8, 9, 10], ['TUTTE'], 20],
]) {
  const x = gioca({ numeri, ruote, sorti: ['ambo'], importo });
  check(`${numeri.length} numeri su ${x.ruote.length} ruote: 0,574 per euro`,
        vicino(x.ritornoAttesoPerEuro, attesoAmbo, 1e-3), String(x.ritornoAttesoPerEuro));
}

console.log("\nPIU' RUOTE: PIU' PROBABILE VINCERE, STESSO VALORE");
const una = gioca({ numeri: [7, 21], ruote: ['MI'], sorti: ['ambo'], importo: 10 });
const dieci = gioca({ numeri: [7, 21], ruote: ['TUTTE'], sorti: ['ambo'], importo: 10 });
check('la probabilita\' di vincere qualcosa cresce',
      dieci.qualcosaAlmenoUnaRuota > una.qualcosaAlmenoUnaRuota * 9);
check('ma il ritorno atteso resta lo stesso',
      vicino(dieci.ritornoAtteso, una.ritornoAtteso, 1e-9),
      `${una.ritornoAtteso} vs ${dieci.ritornoAtteso}`);
check('e la vincita si divide per dieci',
      vicino(dieci.righe[0].scenari[0].netto * 10, una.righe[0].scenari[0].netto, 1e-9));

console.log('\nLE SORTI LUNGHE PAGANO PEGGIO (e va detto)');
const ritorni = {};
for (const sorte of Object.keys(NUMERI_PER_SORTE)) {
  const k = NUMERI_PER_SORTE[sorte];
  const numeri = Array.from({ length: k }, (_, i) => i + 1);
  ritorni[sorte] = gioca({ numeri, ruote: ['RM'], sorti: [sorte], importo: 1 }).ritornoAttesoPerEuro;
}
check('estratto e ambo sono quasi identici (~0,574)',
      vicino(ritorni.estratto, ritorni.ambo, 5e-3), JSON.stringify(ritorni));
check('il terno rende meno dell\'ambo', ritorni.terno < ritorni.ambo);
check('la quaterna meno del terno', ritorni.quaterna < ritorni.terno);
check('la cinquina e\' la peggiore', ritorni.cinquina < ritorni.quaterna);
check('nessuna sorte restituisce piu\' di quanto costa',
      Object.values(ritorni).every(v => v < 1), JSON.stringify(ritorni));

console.log('\nGIOCATE IMPOSSIBILI: RIFIUTATE CON UNA SPIEGAZIONE');
const casi = [
  ['numero fuori scala', { numeri: [91], ruote: ['NA'], sorti: ['estratto'], importo: 1 }, '90'],
  ['numero ripetuto', { numeri: [7, 7], ruote: ['NA'], sorti: ['ambo'], importo: 1 }, 'due volte'],
  ['undici numeri', { numeri: [1,2,3,4,5,6,7,8,9,10,11], ruote: ['NA'], sorti: ['ambo'], importo: 1 }, 'massimo'],
  ['nessun numero', { numeri: [], ruote: ['NA'], sorti: ['ambo'], importo: 1 }, 'almeno un numero'],
  ['terno con due numeri', { numeri: [7, 21], ruote: ['NA'], sorti: ['terno'], importo: 1 }, 'almeno 3'],
  ['ruota inesistente', { numeri: [7, 21], ruote: ['XX'], sorti: ['ambo'], importo: 1 }, 'sconosciute'],
  ['nessuna ruota', { numeri: [7, 21], ruote: [], sorti: ['ambo'], importo: 1 }, 'almeno una ruota'],
  ['sorte inventata', { numeri: [7, 21], ruote: ['NA'], sorti: ['sestina'], importo: 1 }, 'sconosciute'],
  ['importo zero', { numeri: [7, 21], ruote: ['NA'], sorti: ['ambo'], importo: 0 }, 'maggiore di zero'],
  ['importo non numerico', { numeri: [7, 21], ruote: ['NA'], sorti: ['ambo'], importo: 'tanto' }, 'non è un numero'],
];
for (const [nome, argomenti, atteso] of casi) {
  try {
    gioca(argomenti);
    check(nome, false, 'accettata invece di essere rifiutata');
  } catch (e) {
    check(`${nome}: ${e.message}`,
          e instanceof GiocataNonValida && e.message.toLowerCase().includes(atteso.toLowerCase()),
          e.message);
  }
}

console.log('\nTUTTE = le dieci ruote classiche');
r = gioca({ numeri: [7, 21], ruote: ['tutte'], sorti: ['ambo'], importo: 10 });
check('dieci ruote', r.ruote.length === 10, r.ruote.join(' '));
check('la Nazionale non c\'e\'', !r.ruote.includes('RN'), r.ruote.join(' '));

console.log(`\n${'='.repeat(60)}\nRISULTATO: ${ok} OK, ${fail} FAIL`);
process.exit(fail ? 1 : 0);
