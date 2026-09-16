/**
 * Cercare le ripetizioni: si prende un concorso vecchio e si guarda, da li' in
 * poi, quante volte i suoi numeri sono tornati fuori insieme.
 *
 * Questo file non tocca la pagina: legge lo storico, cerca, e restituisce dei
 * numeri. Tutto quello che si vede a schermo lo costruisce app.js.
 *
 * TRE COSE CHE VANNO DETTE, perche' questa e' la sezione dove e' piu' facile
 * vedere quello che non c'e'.
 *
 *   1. Trovare che un ambo del 1985 e' ritornato quarantasette volte non dice
 *      niente su domani. Le estrazioni sono indipendenti: quei quarantasette
 *      ritorni sono gia' avvenuti e non ne promettono un quarantottesimo.
 *
 *   2. Per questo ogni ricerca dichiara anche quante ripetizioni ci si
 *      aspettava per puro caso (`attesi`). E' il numero che rende la risposta
 *      leggibile: "47 ambi trovati" da solo sembra tanto, "47 trovati contro 43
 *      attesi" dice la verita', cioe' che e' andata come doveva andare.
 *
 *   3. Il conto degli attesi e' esatto, non una stima: e' l'ipergeometrica di
 *      cinque numeri estratti da novanta, moltiplicata per i concorsi guardati.
 *      Le ruote sono indipendenti fra loro, quindi cercare su dieci ruote
 *      moltiplica per dieci sia i trovati sia gli attesi — il confronto regge.
 */
import { combinazioni } from './schedina.js';

export const RUOTE = ['BA', 'CA', 'FI', 'GE', 'MI', 'NA', 'PA', 'RM', 'TO', 'VE'];
const PER_CONCORSO = RUOTE.length * 5;

export class StoricoNonValido extends Error {}

/** Legge il file pubblicato da motore/pubblica.py.
 *
 *  Il risultato non e' un albero di oggetti ma un solo Uint8Array di
 *  trecentosessanta chilobyte: settemila oggetti con dentro altri diecimila
 *  array sono comodi da scrivere e pesanti da tenere aperti su un telefono,
 *  mentre qui la posizione di ogni numero e' un conto a mente e la memoria e'
 *  quella dei dati e basta. Uno zero vuol dire "quella ruota non ha estratto".
 */
export function leggiStorico(testo) {
  const righe = testo.split('\n')
    .filter(r => r && !r.startsWith('#'));
  if (!righe.length) throw new StoricoNonValido('Lo storico e\' vuoto.');

  const giorni = new Array(righe.length);
  const numeri = new Uint8Array(righe.length * PER_CONCORSO);

  righe.forEach((riga, i) => {
    if (riga.length !== 8 + PER_CONCORSO * 2)
      throw new StoricoNonValido(
        `Riga ${i + 1} lunga ${riga.length} caratteri invece di ${8 + PER_CONCORSO * 2}.`);
    giorni[i] = `${riga.slice(0, 4)}-${riga.slice(4, 6)}-${riga.slice(6, 8)}`;
    for (let k = 0; k < PER_CONCORSO; k++) {
      const pezzo = riga.substr(8 + k * 2, 2);
      numeri[i * PER_CONCORSO + k] = pezzo === '--' ? 0 : Number(pezzo);
    }
  });
  return { giorni, numeri, ruote: RUOTE };
}

/** I cinque numeri di una ruota in un dato giorno, o null se non ha estratto. */
export function estrazione(storico, giorno, ruota) {
  const i = storico.giorni.indexOf(giorno);
  const r = RUOTE.indexOf(ruota);
  if (i < 0 || r < 0) return null;
  const base = i * PER_CONCORSO + r * 5;
  const cinque = [...storico.numeri.subarray(base, base + 5)];
  return cinque.includes(0) ? null : cinque;
}

/** Il quadro completo di un giorno: ogni ruota con i suoi cinque numeri. */
export function quadro(storico, giorno) {
  const i = storico.giorni.indexOf(giorno);
  if (i < 0) return null;
  const fuori = {};
  RUOTE.forEach((ruota, r) => {
    const base = i * PER_CONCORSO + r * 5;
    const cinque = [...storico.numeri.subarray(base, base + 5)];
    if (!cinque.includes(0)) fuori[ruota] = cinque;
  });
  return fuori;
}

/** Il concorso piu' vicino a una data qualunque, guardando indietro e poi avanti.
 *  Serve perche' il calendario del Lotto salta i giorni: chi sceglie una
 *  domenica non deve trovarsi davanti a un "nessun concorso" e basta. */
export function concorsoVicino(storico, giorno) {
  const { giorni } = storico;
  if (!giorni.length) return null;
  if (giorni.includes(giorno)) return giorno;
  let prima = null;
  for (const g of giorni) { if (g <= giorno) prima = g; else break; }
  const dopo = giorni.find(g => g > giorno) ?? null;
  if (!prima) return dopo;
  if (!dopo) return prima;
  const scarto = (a, b) =>
    Math.abs(Date.parse(a + 'T00:00:00') - Date.parse(b + 'T00:00:00'));
  return scarto(prima, giorno) <= scarto(dopo, giorno) ? prima : dopo;
}

/** Probabilita' che un concorso qualunque, su una ruota, ripeta esattamente
 *  `quanti` dei cinque numeri di partenza. Ipergeometrica, conti esatti. */
export function probRipetizione(quanti) {
  if (quanti < 0 || quanti > 5) return 0;
  return combinazioni(5, quanti) * combinazioni(85, 5 - quanti) / combinazioni(90, 5);
}

/** Quante ripetizioni ci si aspetta per puro caso, per ciascuna misura. */
export function attesi(concorsi, ruote = 1) {
  const fuori = {};
  for (let q = 2; q <= 5; q++) fuori[q] = concorsi * ruote * probRipetizione(q);
  fuori.almeno2 = fuori[2] + fuori[3] + fuori[4] + fuori[5];
  return fuori;
}

/**
 * La ricerca vera e propria.
 *
 * Si scorre lo storico dal giorno dopo quello scelto fino in fondo e, per ogni
 * ruota guardata, si contano i numeri in comune con l'estrazione di partenza.
 * Due o piu' fanno una ripetizione: due e' un ambo, tre un terno, e cosi' via.
 *
 * Tutte le ripetizioni vengono trovate; il taglio a `quante` riguarda solo
 * l'elenco che si porta indietro, e i conteggi restano quelli veri.
 */
export function cerca(storico, {
  giorno, ruota, tutteLeRuote = false, minimo = 2, quante = 400,
} = {}) {
  const partenza = estrazione(storico, giorno, ruota);
  if (!partenza) return null;

  const cercate = tutteLeRuote ? RUOTE : [ruota];
  const indici = cercate.map(r => RUOTE.indexOf(r));
  const inGioco = new Uint8Array(91);
  for (const n of partenza) inGioco[n] = 1;

  const da = storico.giorni.indexOf(giorno) + 1;
  const trovati = [];
  const conteggio = { 2: 0, 3: 0, 4: 0, 5: 0 };
  let concorsi = 0;

  for (let i = da; i < storico.giorni.length; i++) {
    concorsi++;
    for (let k = 0; k < indici.length; k++) {
      const base = i * PER_CONCORSO + indici[k] * 5;
      let comuni = 0, assente = false;
      const quali = [];
      for (let j = 0; j < 5; j++) {
        const n = storico.numeri[base + j];
        if (n === 0) { assente = true; break; }
        if (inGioco[n]) { comuni++; quali.push(n); }
      }
      if (assente || comuni < minimo) continue;
      conteggio[comuni]++;
      if (trovati.length < quante)
        trovati.push({
          giorno: storico.giorni[i], ruota: cercate[k],
          numeri: quali.sort((a, b) => a - b), quanti: comuni,
        });
    }
  }

  // Prima il ritrovamento piu' grosso, e a parita' il piu' recente: una
  // cinquina ripetuta non deve finire in fondo a quattrocento ambi.
  trovati.sort((a, b) => b.quanti - a.quanti || b.giorno.localeCompare(a.giorno)
    || a.ruota.localeCompare(b.ruota));

  const totale = conteggio[2] + conteggio[3] + conteggio[4] + conteggio[5];
  return {
    origine: { giorno, ruota, numeri: partenza },
    tutteLeRuote, concorsi, ruote: cercate.length,
    trovati, troncato: totale > trovati.length,
    conteggio: { ...conteggio, almeno2: totale },
    attesi: attesi(concorsi, cercate.length),
    ultimo: storico.giorni[storico.giorni.length - 1] ?? null,
  };
}

/** Le parole per dire com'e' andata rispetto al caso.
 *  Sotto i cinque casi attesi il confronto non regge e si dice: e' cosi' che si
 *  evita di far sembrare un miracolo un terno trovato dove se ne attendeva uno. */
export function confronto(trovati, attesi) {
  if (attesi < 5) return { scarto: null, parola: 'troppo pochi per dire qualcosa' };
  const scarto = trovati / attesi;
  if (scarto > 1.35) return { scarto, parola: 'piu' + '̀' + ' del previsto' };
  if (scarto < 0.65) return { scarto, parola: 'meno del previsto' };
  return { scarto, parola: 'quanto ci si aspettava dal caso' };
}
