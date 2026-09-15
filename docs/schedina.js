/**
 * Simulazione di una giocata: quanto si punta, quanto si puo' vincere, e con
 * quale probabilita'.
 *
 * Sta nel browser perche' e' l'unica parte dell'app che deve rispondere mentre
 * l'utente clicca: tutto il resto e' precalcolato e arriva come JSON. E' anche
 * l'unica aritmetica duplicata fra Python e JavaScript, e per questo le quote
 * non sono scritte qui: arrivano da dati/quote.json, lo stesso file che legge
 * il motore Python. Una fonte sola, altrimenti il conto del passato e quello
 * del futuro finiscono per raccontare due storie diverse.
 *
 * Le regole del gioco, che sono la parte che si sbaglia piu' facilmente:
 *
 *  - la posta si RIPARTISCE fra le ruote e fra le sorti scelte. Dieci euro su
 *    due ruote per ambo e terno sono 2,50 € per ruota e per sorte, non dieci;
 *  - si ripartisce UNA SECONDA VOLTA sulle combinazioni: cinque numeri giocati
 *    per ambo sono dieci ambi, quindi 25 centesimi l'uno. E' il motivo per cui
 *    allargare la giocata non moltiplica la vincita come sembra;
 *  - se escono piu' numeri del minimo vincono TUTTE le combinazioni contenute:
 *    con cinque numeri giocati per ambo e tre usciti si vincono tre ambi;
 *  - ogni ruota e' un'estrazione a se'. Giocare su piu' ruote aumenta la
 *    probabilita' che almeno una vinca, ma divide la posta: il valore atteso
 *    non cambia di un centesimo.
 */

export const NUMERI_PER_SORTE = {
  estratto: 1, ambo: 2, terno: 3, quaterna: 4, cinquina: 5,
};
export const RUOTE = ['BA', 'CA', 'FI', 'GE', 'MI', 'NA', 'PA', 'RM', 'TO', 'VE'];
export const ESTRATTI_PER_RUOTA = 5;
export const TOTALE_NUMERI = 90;
export const MAX_NUMERI_GIOCABILI = 10;

export class GiocataNonValida extends Error {}

/** Coefficiente binomiale. Moltiplicando e dividendo a ogni passo si resta
 *  sempre su interi esatti: C(90,5) e' 43.949.268, ben dentro i numeri sicuri
 *  del JavaScript, ma 90! non lo sarebbe. */
export function combinazioni(n, k) {
  if (k < 0 || k > n) return 0;
  k = Math.min(k, n - k);
  let r = 1;
  for (let i = 1; i <= k; i++) r = (r * (n - k + i)) / i;
  return Math.round(r);
}

/** Probabilita' che su una ruota escano esattamente `presi` dei numeri giocati.
 *  E' l'ipergeometrica: cinque numeri estratti da novanta, senza reimmissione. */
export function probabilitaPresi(giocati, presi) {
  if (presi > giocati || presi > ESTRATTI_PER_RUOTA) return 0;
  return combinazioni(giocati, presi)
       * combinazioni(TOTALE_NUMERI - giocati, ESTRATTI_PER_RUOTA - presi)
       / combinazioni(TOTALE_NUMERI, ESTRATTI_PER_RUOTA);
}

function normalizzaNumeri(numeri) {
  const puliti = [...(numeri ?? [])].map(Number);
  if (!puliti.length) throw new GiocataNonValida('Serve almeno un numero.');
  if (puliti.some(n => !Number.isInteger(n)))
    throw new GiocataNonValida('I numeri devono essere interi.');
  const fuori = puliti.filter(n => n < 1 || n > TOTALE_NUMERI);
  if (fuori.length)
    throw new GiocataNonValida(
      `Il Lotto arriva a 90: ${[...new Set(fuori)].sort((a, b) => a - b).join(', ')} `
      + `non è un numero giocabile.`);
  if (new Set(puliti).size !== puliti.length)
    throw new GiocataNonValida('Lo stesso numero compare due volte: '
      + 'in una giocata ogni numero vale una volta sola.');
  if (puliti.length > MAX_NUMERI_GIOCABILI)
    throw new GiocataNonValida(
      `Massimo ${MAX_NUMERI_GIOCABILI} numeri per giocata (ne hai scelti ${puliti.length}).`);
  return puliti.sort((a, b) => a - b);
}

function normalizzaRuote(ruote) {
  const scelte = [...(ruote ?? [])].map(r => String(r).toUpperCase());
  if (!scelte.length) throw new GiocataNonValida('Serve almeno una ruota.');
  if (scelte.includes('TUTTE')) return [...RUOTE];
  const ignote = scelte.filter(r => !RUOTE.includes(r));
  if (ignote.length)
    throw new GiocataNonValida(`Ruote sconosciute: ${[...new Set(ignote)].join(', ')}.`);
  return [...new Set(scelte)];
}

function normalizzaSorti(sorti, quantiNumeri) {
  const scelte = [...new Set((sorti ?? []).map(s => String(s).toLowerCase()))];
  if (!scelte.length)
    throw new GiocataNonValida('Serve almeno una sorte (estratto, ambo, terno…).');
  const ignote = scelte.filter(s => !(s in NUMERI_PER_SORTE));
  if (ignote.length)
    throw new GiocataNonValida(`Sorti sconosciute: ${ignote.join(', ')}. `
      + `Sono ammesse: ${Object.keys(NUMERI_PER_SORTE).join(', ')}.`);
  const troppo = scelte.find(s => NUMERI_PER_SORTE[s] > quantiNumeri);
  if (troppo)
    throw new GiocataNonValida(
      `Con ${quantiNumeri} numer${quantiNumeri === 1 ? 'o' : 'i'} non si può giocare `
      + `${troppo}: ne servono almeno ${NUMERI_PER_SORTE[troppo]}.`);
  return scelte.sort((a, b) => NUMERI_PER_SORTE[a] - NUMERI_PER_SORTE[b]);
}

/**
 * Il quadro completo di una giocata.
 *
 * `quote` è il contenuto di dati/quote.json: {moltiplicatori, ritenuta}.
 * Non arrotonda la posta al centesimo come farebbe una ricevitoria vera —
 * servirebbe a far tornare lo scontrino, non a capire la giocata.
 */
export function simula({ numeri, ruote, sorti, importo, quote }) {
  const n = normalizzaNumeri(numeri);
  const r = normalizzaRuote(ruote);
  const s = normalizzaSorti(sorti, n.length);
  const posta = Number(importo);
  if (!Number.isFinite(posta)) throw new GiocataNonValida("L'importo non è un numero.");
  if (posta <= 0) throw new GiocataNonValida("L'importo deve essere maggiore di zero.");
  if (!quote?.moltiplicatori) throw new GiocataNonValida('Quote non disponibili.');

  const ritenuta = quote.ritenuta ?? 0;
  const perSorteERuota = posta / (r.length * s.length);

  let attesoTotale = 0;
  const righe = s.map(nome => {
    const k = NUMERI_PER_SORTE[nome];
    const quota = quote.moltiplicatori[nome];
    const comb = combinazioni(n.length, k);
    const postaPerCombinazione = perSorteERuota / comb;

    let attesoPerRuota = 0, probVincente = 0;
    const scenari = [];
    for (let presi = k; presi <= Math.min(n.length, ESTRATTI_PER_RUOTA); presi++) {
      const vincenti = combinazioni(presi, k);
      const lordo = postaPerCombinazione * quota * vincenti;
      const netto = lordo * (1 - ritenuta);
      const p = probabilitaPresi(n.length, presi);
      attesoPerRuota += p * netto;
      probVincente += p;
      scenari.push({ presi, combinazioniVincenti: vincenti, lordo, netto, probabilita: p });
    }
    attesoTotale += attesoPerRuota * r.length;
    return {
      sorte: nome, numeriNecessari: k, combinazioni: comb,
      postaPerCombinazione, postaPerRuota: perSorteERuota,
      probabilitaPerRuota: probVincente,
      probabilitaAlmenoUnaRuota: 1 - (1 - probVincente) ** r.length,
      scenari,
    };
  });

  // per vincere qualcosa basta la sorte piu' corta: e' la piu' probabile e le
  // contiene tutte (se esce un terno e' uscito anche un ambo)
  const pMinima = righe[0].probabilitaPerRuota;
  return {
    numeri: n, ruote: r, sorti: s, importo: posta, righe,
    qualcosaPerRuota: pMinima,
    qualcosaAlmenoUnaRuota: 1 - (1 - pMinima) ** r.length,
    ritornoAtteso: attesoTotale,
    ritornoAttesoPerEuro: attesoTotale / posta,
  };
}
