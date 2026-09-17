/**
 * Leggere il passato: l'archivio delle estrazioni, le previsioni che i sei
 * metodi hanno rilevato in ogni anno, e che cosa ne e' venuto fuori.
 *
 * Il sito e' statico e non puo' calcolare niente al volo, quindi le previsioni
 * storiche non si ricalcolano qui: le ha gia' scritte `motore/storia.py`, un
 * file per anno, con lo stesso motore che gira ogni sera. Rifare i sei metodi
 * in JavaScript avrebbe voluto dire avere due implementazioni della stessa
 * cosa, e il giorno in cui divergono nessuno se ne accorge.
 *
 * Quello che invece si fa qui e' il **controllo delle uscite**, e segue alla
 * lettera le regole di `motore/valutazione.py`:
 *
 *   - una sorte ha un esito quando escono almeno `MINIMO_PER_ESITO` dei suoi
 *     numeri sulla stessa ruota nello stesso concorso (una terzina e una
 *     quartina si giocano per ambo: due numeri bastano);
 *   - l'esito conta se e' su una ruota di gioco, o su una qualunque quando la
 *     previsione vale "anche a Tutte";
 *   - quando si verifica su una ruota di gioco la sorte si **sospende**, come
 *     prescrivono i fascicoli: da li' in avanti non si gioca e non si spende.
 *
 * Perche' le due implementazioni non possano divergere in silenzio,
 * `prove/test_storico.mjs` rifa' i conti su un campione di previsioni vere e li
 * confronta con quelli che ha prodotto Python.
 */

export const RUOTE = ['BA', 'CA', 'FI', 'GE', 'MI', 'NA', 'PA', 'RM', 'TO', 'VE'];
const PER_CONCORSO = RUOTE.length * 5;

export const MINIMO_PER_ESITO = { ambata: 1, ambo: 2, terzina: 2, quartina: 2 };

export class StoricoNonValido extends Error {}

/* ------------------------------------------------------- l'archivio */

/** Legge il file pubblicato da motore/pubblica.py.
 *
 *  Il risultato non e' un albero di oggetti ma un solo Uint8Array di
 *  trecentosessanta chilobyte: settemila oggetti con dentro altri diecimila
 *  array sono comodi da scrivere e pesanti da tenere aperti su un telefono,
 *  mentre qui la posizione di ogni numero e' un conto a mente e la memoria e'
 *  quella dei dati e basta. Uno zero vuol dire "quella ruota non ha estratto".
 */
export function leggiStorico(testo) {
  const righe = testo.split('\n').filter(r => r && !r.startsWith('#'));
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
  return { giorni, numeri, ruote: RUOTE, posizione: new Map(giorni.map((g, i) => [g, i])) };
}

const indiceDi = (storico, giorno) => storico.posizione.get(giorno) ?? -1;

/** I cinque numeri di una ruota in un dato giorno, o null se non ha estratto. */
export function estrazione(storico, giorno, ruota) {
  const i = indiceDi(storico, giorno);
  const r = RUOTE.indexOf(ruota);
  if (i < 0 || r < 0) return null;
  const base = i * PER_CONCORSO + r * 5;
  const cinque = [...storico.numeri.subarray(base, base + 5)];
  return cinque.includes(0) ? null : cinque;
}

/** Il quadro completo di un giorno: ogni ruota con i suoi cinque numeri. */
export function quadro(storico, giorno) {
  const i = indiceDi(storico, giorno);
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
  if (storico.posizione.has(giorno)) return giorno;
  let prima = null;
  for (const g of giorni) { if (g <= giorno) prima = g; else break; }
  const dopo = giorni.find(g => g > giorno) ?? null;
  if (!prima) return dopo;
  if (!dopo) return prima;
  const scarto = (a, b) =>
    Math.abs(Date.parse(a + 'T00:00:00') - Date.parse(b + 'T00:00:00'));
  return scarto(prima, giorno) <= scarto(dopo, giorno) ? prima : dopo;
}

/* --------------------------------------- le previsioni gia' rilevate */

/** Legge un file d'anno scritto da motore/storia.py. */
export function leggiPrevisioni(testo) {
  const fuori = [];
  for (const riga of testo.split('\n')) {
    if (!riga || riga.startsWith('#')) continue;
    const campi = riga.split('|');
    if (campi.length !== 8)
      throw new StoricoNonValido(`Riga con ${campi.length} campi invece di 8: ${riga}`);
    const [giorno, metodo, ruote, colpi, tutte, sorti, nota, avviso] = campi;
    fuori.push({
      giorno: `${giorno.slice(0, 4)}-${giorno.slice(4, 6)}-${giorno.slice(6)}`,
      metodo,
      ruote: ruote.split(','),
      colpi: Number(colpi),
      anche_tutte: tutte === '1',
      sorti: sorti.split(';').filter(Boolean).map(s => {
        const [tipo, numeri] = s.split(':');
        return { tipo, numeri: numeri.split('-').map(Number) };
      }),
      nota: nota || null,
      avviso: avviso || null,
    });
  }
  return fuori;
}

/** Le previsioni di un certo giorno, quelle che toccano una ruota prima. */
export function previsioniDi(previsioni, giorno, ruota = null) {
  const suo = previsioni.filter(p => p.giorno === giorno);
  if (!ruota) return suo;
  const tocca = p => p.ruote.includes(ruota);
  return [...suo.filter(tocca), ...suo.filter(p => !tocca(p))];
}

/* ------------------------------------------ che cosa ne e' venuto fuori */

/**
 * Controlla una previsione sui concorsi successivi.
 *
 * Per ogni sorte torna:
 *   - `esiti`, cioe' i colpi in cui la sorte si e' verificata secondo le regole
 *     dei fascicoli (vedi l'intestazione del file), sulle ruote che contano;
 *   - `altrove`, le uscite sulle ruote che NON erano in gioco. Non valgono
 *     niente per la giocata, ma sono la risposta alla domanda "su quali ruote
 *     sono usciti questi numeri", ed e' una domanda legittima;
 *   - `stato`: vinta, scaduta, o aperta se i colpi non sono ancora finiti;
 *   - `oltre`, la prima volta che la sorte si sarebbe verificata DOPO la
 *     scadenza dei colpi, cercata per `oltreColpi` concorsi. Si guarda solo se
 *     la sorte e' scaduta, e si dichiara per quello che e': fuori giocata.
 */
export function verifica(storico, previsione, { oltreColpi = 200 } = {}) {
  const inizio = indiceDi(storico, previsione.giorno);
  if (inizio < 0) return null;

  const gioco = new Set(previsione.ruote);
  const valide = previsione.anche_tutte ? new Set(RUOTE) : gioco;

  const usciti = (i, ruota) => {
    const base = i * PER_CONCORSO + RUOTE.indexOf(ruota) * 5;
    const c = storico.numeri.subarray(base, base + 5);
    return c.includes(0) ? null : c;
  };

  const sorti = previsione.sorti.map((s) => {
    const numeri = new Set(s.numeri);
    const minimo = MINIMO_PER_ESITO[s.tipo] ?? 2;
    const esiti = [], altrove = [];
    let stato = 'aperta', colpiGiocati = 0;

    for (let colpo = 1; colpo <= previsione.colpi; colpo++) {
      const i = inizio + colpo;
      if (i >= storico.giorni.length) break;   // colpo non ancora giocato
      colpiGiocati = colpo;
      for (const ruota of RUOTE) {
        const c = usciti(i, ruota);
        if (!c) continue;
        const presi = [...c].filter(n => numeri.has(n)).sort((a, b) => a - b);
        if (!presi.length) continue;
        const riga = { giorno: storico.giorni[i], ruota, colpo, usciti: presi };
        if (valide.has(ruota) && presi.length >= minimo)
          esiti.push({ ...riga, a_tutte: !gioco.has(ruota) });
        else
          altrove.push(riga);
      }
      if (esiti.some(e => !e.a_tutte)) { stato = 'vinta'; break; }
    }
    if (stato === 'aperta' && colpiGiocati >= previsione.colpi) stato = 'scaduta';

    // Dopo la scadenza: quando si sarebbe verificata, se si fosse continuato?
    let oltre = null;
    if (stato === 'scaduta') {
      for (let colpo = previsione.colpi + 1; colpo <= previsione.colpi + oltreColpi; colpo++) {
        const i = inizio + colpo;
        if (i >= storico.giorni.length) break;
        for (const ruota of previsione.ruote) {
          const c = usciti(i, ruota);
          if (!c) continue;
          const presi = [...c].filter(n => numeri.has(n)).sort((a, b) => a - b);
          if (presi.length >= minimo) {
            oltre = { giorno: storico.giorni[i], ruota, colpo, usciti: presi };
            break;
          }
        }
        if (oltre) break;
      }
    }

    return { ...s, minimo, stato, colpiGiocati, esiti, altrove, oltre };
  });

  return { ...previsione, sorti, verificata: true };
}

/** Su quali ruote e' uscito ciascun numero, nei concorsi subito successivi.
 *  E' la domanda in chiaro — senza sorti, senza colpi di gioco — sui numeri
 *  derivati, che non appartengono a nessuna previsione e quindi non hanno ne'
 *  ruote di gioco ne' una scadenza. */
export function usciteDi(storico, numeri, giorno, { concorsi = 12 } = {}) {
  const inizio = indiceDi(storico, giorno);
  if (inizio < 0) return [];
  const cerco = new Set(numeri);
  const per = new Map(numeri.map(n => [n, []]));

  for (let colpo = 1; colpo <= concorsi; colpo++) {
    const i = inizio + colpo;
    if (i >= storico.giorni.length) break;
    for (const ruota of RUOTE) {
      const base = i * PER_CONCORSO + RUOTE.indexOf(ruota) * 5;
      const c = storico.numeri.subarray(base, base + 5);
      if (c.includes(0)) continue;
      for (const n of c)
        if (cerco.has(n))
          per.get(n).push({ giorno: storico.giorni[i], ruota, colpo });
    }
  }
  return [...per.entries()]
    .map(([numero, uscite]) => ({
      numero,
      uscite,
      ruote: [...new Set(uscite.map(u => u.ruota))].sort(),
      prima: uscite[0] ?? null,
    }))
    .sort((a, b) => b.uscite.length - a.uscite.length || a.numero - b.numero);
}
