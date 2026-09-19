/**
 * L'elenco: una riga per ogni numero giocato, su ogni ruota, a ogni concorso.
 *
 * Una previsione vale su due o tre ruote insieme, ma al botteghino si gioca una
 * ruota alla volta, e la domanda a cui questo elenco risponde e' "su questa
 * ruota, questi numeri, com'e' andata". Quindi la riga e' la terna
 * (previsione, sorte, ruota), non la previsione: filtrare per Napoli deve dare
 * davvero solo Napoli.
 *
 * LA COSA CHE NON E' OVVIA e' l'esito per ruota. Come da fascicoli, la sorte si
 * **sospende** quando si verifica su una ruota di gioco: da quel momento non si
 * gioca piu' e non si spende piu', **nemmeno sulle altre ruote della stessa
 * previsione**. Cosi' una riga su Cagliari puo' finire senza esito non perche'
 * i numeri non siano usciti, ma perche' la giocata si era gia' chiusa su Bari
 * due colpi prima. Dirlo "scaduta" sarebbe falso, e dirlo "uscita" pure: qui si
 * chiama `sospesa` e si dice dove e quando. Sono tre stati diversi e l'elenco
 * li tiene distinti:
 *
 *   uscita   - su QUESTA ruota, entro i colpi. E' la riga che ha pagato.
 *   sospesa  - la giocata si e' chiusa su un'altra ruota prima che qui uscisse.
 *   scaduta  - i colpi sono finiti e non e' uscita da nessuna parte.
 *   aperta   - i colpi non sono ancora finiti: si sapra'.
 *
 * Gli esiti non si ricalcolano qui: li da' `verifica()` di storico.js, che e'
 * la stessa regola di motore/valutazione.py e ha una prova che le confronta.
 */
import { verifica, RUOTE } from './storico.js';

export const ESITI = ['uscita', 'sospesa', 'scaduta', 'aperta'];

/** Espande le previsioni di un anno in righe (previsione, sorte, ruota).
 *
 *  `oltreColpi: 0` perche' l'elenco non mostra il "sarebbe uscita dopo": e' il
 *  pezzo piu' caro del controllo (duecento concorsi per ogni sorte scaduta) e
 *  qui si moltiplicherebbe per sedicimila righe.
 */
export function righe(storico, previsioni, { oltreColpi = 0 } = {}) {
  const fuori = [];
  for (const p of previsioni) {
    const v = verifica(storico, p, { oltreColpi });
    if (!v) continue;
    for (const s of v.sorti) {
      // Il colpo in cui la giocata si e' chiusa, se si e' chiusa: il primo
      // esito su una ruota di gioco (non quelli validi solo "a Tutte").
      const chiusura = s.esiti.find(e => !e.a_tutte) ?? null;
      for (const ruota of p.ruote) {
        const qui = s.esiti.find(e => e.ruota === ruota) ?? null;
        let esito, colpo = null, usciti = null, dove = null;
        if (qui) {
          esito = 'uscita';
          colpo = qui.colpo;
          usciti = qui.usciti;
        } else if (chiusura) {
          esito = 'sospesa';
          colpo = chiusura.colpo;
          dove = chiusura.ruota;
        } else {
          esito = s.stato === 'aperta' ? 'aperta' : 'scaduta';
        }
        fuori.push({
          giorno: p.giorno, metodo: p.metodo, ruota, tipo: s.tipo,
          numeri: s.numeri, colpi: p.colpi, anche_tutte: p.anche_tutte,
          nota: p.nota, esito, colpo, usciti, dove,
          // le uscite sulle ruote fuori gioco, per questa ruota soltanto:
          // servono a spiegare una riga "scaduta" che scaduta sembra strana
          sfiorata: s.altrove.filter(a => a.ruota === ruota),
        });
      }
    }
  }
  return fuori;
}

/** I filtri della pagina. Un valore vuoto vuol dire "non filtrare". */
export function filtra(tutte, { ruota = '', metodo = '', tipo = '', esito = '' } = {}) {
  return tutte.filter(r =>
    (!ruota || r.ruota === ruota)
    && (!metodo || r.metodo === metodo)
    && (!tipo || r.tipo === tipo)
    && (!esito || r.esito === esito));
}

/** Quante righe per ciascun esito: il riassunto sopra la tabella. */
export function conteggio(righe) {
  const c = Object.fromEntries(ESITI.map(e => [e, 0]));
  for (const r of righe) c[r.esito]++;
  c.totale = righe.length;
  return c;
}

/** Una pagina di risultati. Le pagine partono da 1; oltre l'ultima si torna
 *  all'ultima invece di mostrare il vuoto. */
export function pagina(righe, numero = 1, perPagina = 200) {
  const pagine = Math.max(1, Math.ceil(righe.length / perPagina));
  const n = Math.min(Math.max(1, Math.trunc(numero) || 1), pagine);
  return {
    numero: n, pagine, perPagina,
    da: righe.length ? (n - 1) * perPagina + 1 : 0,
    a: Math.min(n * perPagina, righe.length),
    righe: righe.slice((n - 1) * perPagina, n * perPagina),
  };
}

/** Le ruote e i metodi presenti davvero, per riempire le tendine con le voci
 *  che daranno un risultato invece che con tutte le possibili. */
export function presenti(tutte) {
  const metodi = [...new Set(tutte.map(r => r.metodo))].sort();
  const tipi = [...new Set(tutte.map(r => r.tipo))].sort();
  const ruote = RUOTE.filter(x => tutte.some(r => r.ruota === x));
  return { metodi, tipi, ruote };
}

/**
 * Le righe in CSV, per aprirle con Excel.
 *
 * Punto e virgola e non virgola: Excel in italiano si aspetta quello, e con la
 * virgola infila tutta la riga in una cella sola. Il BOM davanti serve allo
 * stesso Excel per capire che e' UTF-8, se no "Cagliari" diventa "CagliariÃ ".
 */
export function csv(righe, { nomiRuote = {}, nomiMetodi = {} } = {}) {
  const campo = (v) => {
    const s = String(v ?? '');
    return /[";\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
  };
  const intestazione = ['giorno', 'metodo', 'ruota', 'sorte', 'numeri', 'colpi',
                        'esito', 'colpo', 'usciti', 'chiusa su', 'nota'];
  const corpo = righe.map(r => [
    r.giorno,
    nomiMetodi[r.metodo] ?? r.metodo,
    nomiRuote[r.ruota] ?? r.ruota,
    r.tipo,
    r.numeri.join(' '),
    r.colpi,
    r.esito,
    r.colpo ?? '',
    r.usciti ? r.usciti.join(' ') : '',
    r.dove ? (nomiRuote[r.dove] ?? r.dove) : '',
    r.nota ?? '',
  ].map(campo).join(';'));
  return '﻿' + [intestazione.join(';'), ...corpo].join('\r\n') + '\r\n';
}
