/**
 * Le formule dei fascicoli, applicate a cinque numeri qualunque.
 *
 * ATTENZIONE, ED E' TUTTO IL SENSO DI QUESTO FILE: quello che c'e' qui dentro
 * NON sono previsioni. I sei metodi non partono da cinque numeri: partono da
 * una **condizione di ricerca** su tutto il concorso — due ambi che hanno la
 * stessa somma su due ruote, quattro numeri della stessa figura che si
 * accoppiano incrociando le ruote, un ambo diametrale su una ruota sola. Solo
 * quando quella condizione scatta il fascicolo dice che numeri giocare, per
 * quante volte e su quali ruote.
 *
 * Qui invece si prendono i cinque numeri usciti e ci si applicano comunque i
 * calcoli che i metodi usano — complemento, diametrale, terzina simmetrica,
 * vertibile, figura, cadenza. Viene sempre fuori qualcosa, per costruzione.
 * Sono numeri derivati, non giocate consigliate, e la pagina lo scrive accanto.
 *
 * Le formule sono le stesse di motore/lotto.py, riga per riga: se un giorno una
 * cambia di la', va cambiata anche qui. Sono sei righe di aritmetica e nessuna
 * condizione, l'unico posto del sito dove una copia costa meno di un ponte.
 */

/** Fuori 90: riporta n nell'intervallo 1..90. */
export const f90 = n => ((n % 90) === 0 ? 90 : ((n % 90) + 90) % 90);

export const complemento = n => 90 - n;
export const diametrale = n => f90(n + 45);
export const figura = n => ((n - 1) % 9) + 1;
export const cadenza = n => n % 10;

// I sedici vertibili irregolari della tavola dei novanta
// (LottoFacile_IlMetodoVincente.pdf, pag. 3): i numeri a cifre uguali non si
// possono girare, e il fascicolo assegna loro un compagno per convenzione.
const VERT_ECC = {
  11: 19, 19: 11, 22: 29, 29: 22, 33: 39, 39: 33, 44: 49, 49: 44,
  55: 59, 59: 55, 66: 69, 69: 66, 77: 79, 79: 77, 88: 89, 89: 88,
};

export function vertibile(n) {
  if (n in VERT_ECC) return VERT_ECC[n];
  if (n < 10) return n * 10;
  if (n % 10 === 0) return n / 10;
  return (n % 10) * 10 + Math.floor(n / 10);
}

/** I tre numeri a distanza 30 l'uno dall'altro: la terzina simmetrica di n. */
export const terzinaDi = n => [n, f90(n + 30), f90(n + 60)];

export const NOMI = {
  complemento: 'Complemento a 90',
  diametrale: 'Diametrale',
  vertibile: 'Vertibile',
  terzina: 'Terzina simmetrica',
};

export const SPIEGA = {
  complemento: 'novanta meno il numero. È la trasformazione dell\'Ambo Secco '
    + 'Caotico, che gioca il complemento del numero ripetuto.',
  diametrale: 'il numero più quarantacinque, girando a 90. Lotto Facile 5 parte '
    + 'proprio da un ambo fatto di un numero e del suo diametrale.',
  vertibile: 'il numero con le cifre girate, secondo la tavola dei novanta del '
    + 'Metodo Vincente.',
  terzina: 'i tre numeri a distanza trenta l\'uno dall\'altro. Lotto Facile 4 '
    + 'cerca ambi che stanno nella stessa terzina.',
};

/** Le quattro trasformazioni applicate a ciascun numero, una riga per numero. */
export function trasformazioni(numeri) {
  return numeri.map(n => ({
    numero: n,
    complemento: complemento(n),
    diametrale: diametrale(n),
    vertibile: vertibile(n),
    terzina: terzinaDi(n).slice(1),
    figura: figura(n),
    cadenza: cadenza(n),
  }));
}

/** I numeri raggruppati per figura e per cadenza: e' come Fulmine li guarda.
 *  Si tengono solo i gruppi con almeno due numeri — un numero da solo non fa
 *  gruppo, e mostrarlo darebbe l'impressione che qualcosa sia stato trovato. */
export function gruppi(numeri) {
  const raccogli = (fn) => {
    const m = new Map();
    for (const n of numeri) {
      const k = fn(n);
      if (!m.has(k)) m.set(k, []);
      m.get(k).push(n);
    }
    return [...m.entries()]
      .filter(([, v]) => v.length >= 2)
      .map(([chiave, numeri]) => ({ chiave, numeri: numeri.sort((a, b) => a - b) }))
      .sort((a, b) => b.numeri.length - a.numeri.length || a.chiave - b.chiave);
  };
  return { figure: raccogli(figura), cadenze: raccogli(cadenza) };
}

/** Tutti i numeri che escono dalle trasformazioni, senza ripetizioni e senza
 *  quelli di partenza: sono quelli su cui ha senso poi guardare le uscite. */
export function insieme(numeri) {
  const dentro = new Set(numeri);
  const fuori = new Set();
  for (const t of trasformazioni(numeri)) {
    for (const n of [t.complemento, t.diametrale, t.vertibile, ...t.terzina])
      if (!dentro.has(n)) fuori.add(n);
  }
  return [...fuori].sort((a, b) => a - b);
}
