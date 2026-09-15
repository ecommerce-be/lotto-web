/**
 * Il consiglio per il concorso in arrivo: quali giocate fare con un certo budget.
 *
 * Una premessa, perché il resto si capisca. Nel Lotto **non esiste una giocata
 * migliore di un'altra quanto a numeri**: le quote sono fissate per legge e la
 * probabilità è la stessa per qualunque combinazione, quindi a parità di sorte
 * il ritorno atteso è identico. Non c'è nessun "valore" da scovare come nelle
 * scommesse sportive, dove le quote si muovono e possono sbagliare.
 *
 * Quello che invece si può ottimizzare davvero è tre cose, e sono le tre che
 * questo modulo mette in fila:
 *
 *   1. **quale sorte** — l'ambo e l'ambata rendono 57 centesimi per euro, il
 *      terno 35, la quaterna 22. È una raccomandazione dimostrabile, non
 *      un'opinione;
 *   2. **quanto spendere** — coprire tutte le previsioni vive costa centinaia
 *      di euro, e quasi nessuno lo fa;
 *   3. **cosa tenere quando il budget non basta** — che è una decisione vera.
 *      La priorità scelta è il metodo più raro per primo: avere sei metodi ha
 *      senso solo se quello che scatta quattro volte l'anno non viene sepolto
 *      da quello che ne fa mille.
 *
 * Sta in un file a parte, senza una riga che tocchi la pagina, così si può
 * provare con Node: è la parte dove un errore costerebbe soldi veri.
 */
import { NUMERI_PER_SORTE, probabilitaPresi } from './schedina.js';

export const NOMI_GIOCATA = {
  estratto: 'ambata', ambo: 'ambo', terno: 'terno', quaterna: 'quaterna',
};
const NOMI_GRUPPO = { 3: 'terzina', 4: 'quartina', 5: 'cinquina' };

/** Sotto un centesimo per euro due sorti rendono uguale: l'ambata fa 57,41 e
 *  l'ambo 57,43, e segnalare solo uno dei due come "consigliato" sarebbe falso. */
export const SOGLIA_RESA = 0.01;

/** Probabilità che una giocata vinca: **almeno** k numeri presi, non esattamente k.
 *  Con una quartina giocata per ambo vincono anche i casi da tre e da quattro. */
export function probAlmeno(giocati, k) {
  let p = 0;
  for (let m = k; m <= Math.min(giocati, 5); m++) p += probabilitaPresi(giocati, m);
  return p;
}

/** Il ritorno atteso di un euro giocato su una sorte. Dipende SOLO dalla sorte:
 *  non da quanti numeri si giocano né da quante ruote. */
export function resaSorte(sorte, quote) {
  const k = NUMERI_PER_SORTE[sorte];
  return quote.moltiplicatori[sorte] * probabilitaPresi(k, k) * (1 - quote.ritenuta);
}

/** Il nome della giocata come lo direbbe un giocatore. Una terzina non è una
 *  sorte: è tre numeri su cui si gioca ambo. Scrivere "AMBO" accanto a quattro
 *  numeri confonde e basta. */
export function etichettaGiocata(g) {
  const k = NUMERI_PER_SORTE[g.sorte];
  if (g.numeri.length === k) return NOMI_GIOCATA[g.sorte];
  const gruppo = NOMI_GRUPPO[g.numeri.length] ?? `${g.numeri.length} numeri`;
  return `${gruppo} per ${NOMI_GIOCATA[g.sorte]}`;
}

/** Le giocate elementari che una previsione mette sul tavolo. */
function giocateDa(p, quote) {
  const fuori = [];
  for (const s of p.sorti) {
    const sorti = s.numeri.length === 1 ? ['estratto']
      : s.numeri.length === 2 ? ['ambo']
        : ['ambo', 'terno'];          // terzine e quartine si giocano per ambo e terno
    for (const sorte of sorti) {
      fuori.push({
        previsione: p, sorte, numeri: s.numeri, ruote: p.ruote,
        colpi_residui: s.colpi_residui,
        costo: p.ruote.length,        // un euro per sorte e per ruota, come nei fascicoli
        resa: resaSorte(sorte, quote),
        probabilita: probAlmeno(s.numeri.length, NUMERI_PER_SORTE[sorte]),
      });
    }
  }
  return fuori;
}

/** Tutte le giocate in gioco, già nell'ordine in cui vanno proposte. */
export function giocate(previsioni, quote) {
  return previsioni.flatMap(p => giocateDa(p, quote)).sort((a, b) =>
    // dal metodo più raro
    (a.previsione.per_anno ?? 1e6) - (b.previsione.per_anno ?? 1e6)
    // a parità, prima ciò che scade prima
    || a.colpi_residui - b.colpi_residui
    // e prima la sorte che rende di più: se il budget taglia, taglia i terni
    || b.resa - a.resa
    // ordine stabile anche a parità di tutto
    || a.numeri.length - b.numeri.length
    || a.numeri[0] - b.numeri[0]);
}

/** Riempie il budget seguendo quell'ordine. */
export function componi(previsioni, budget, quote) {
  const tutte = giocate(previsioni, quote);
  const dentro = [], fuori = [];
  let speso = 0;
  for (const g of tutte) {
    if (speso + g.costo <= budget) { dentro.push(g); speso += g.costo; }
    else fuori.push(g);
  }
  return { dentro, fuori, speso, mancano: fuori.reduce((s, g) => s + g.costo, 0) };
}

/** Costo, ritorno atteso e probabilità di portare a casa qualcosa.
 *
 *  Costo e ritorno atteso sono **esatti**: il valore atteso è additivo anche
 *  quando le giocate non sono indipendenti. La probabilità no — le giocate
 *  insistono sullo stesso concorso e condividono numeri e ruote, quindi il
 *  prodotto qui sotto la tratta come se fossero indipendenti. Con probabilità
 *  così piccole lo scarto è trascurabile, ma resta un "circa", ed è scritto
 *  anche nella pagina.
 */
export function riepilogo(dentro) {
  let speso = 0, attesa = 0, nessuna = 1;
  for (const g of dentro) {
    speso += g.costo;
    attesa += g.costo * g.resa;
    nessuna *= (1 - g.probabilita) ** g.ruote.length;
  }
  return { speso, attesa, qualcosa: 1 - nessuna, per_euro: speso ? attesa / speso : 0 };
}

/** I numeri che compaiono in più di una previsione. Non alza la probabilità di
 *  nulla — riduce il numero di giocate distinte, che è un'altra cosa. */
export function convergenze(giocate) {
  const conta = new Map();
  for (const g of giocate)
    for (const n of g.numeri) {
      if (!conta.has(n)) conta.set(n, new Set());
      conta.get(n).add(g.previsione.chiave);
    }
  return [...conta.entries()]
    .filter(([, chiavi]) => chiavi.size > 1)
    .map(([numero, chiavi]) => ({ numero, previsioni: chiavi.size }))
    .sort((a, b) => b.previsioni - a.previsioni || a.numero - b.numero);
}
