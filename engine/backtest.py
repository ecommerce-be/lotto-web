"""
Backtest dei metodi su archivio storico reale, con baseline casuale di controllo.

Uso:  python3 backtest.py [anno_inizio]
"""
import csv, sys, os, random, time
from pathlib import Path
from collections import defaultdict, Counter
from itertools import combinations
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lotto_engine import *

def trova_archivio():
    """
    Cerca il CSV delle estrazioni, nell'ordine:
      1. variabile d'ambiente LOTTO_CSV
      2. secondo argomento da riga di comando
      3. cartelle tipiche accanto allo script (../docs, ./docs, ., ../)
    """
    def esplicito(p, origine):
        p = Path(p)
        if not p.is_file():
            raise SystemExit(
                f"\nArchivio non trovato: {p}\n"
                f"(indicato da {origine})\n\n"
                "Controlla il percorso, oppure lascia che lo script lo cerchi da solo:\n"
                "   Remove-Item Env:\\LOTTO_CSV      # se avevi impostato la variabile\n"
                "   python backtest.py 2006          # senza indicare il file\n")
        return p

    if os.environ.get("LOTTO_CSV"):
        return esplicito(os.environ["LOTTO_CSV"], "variabile d'ambiente LOTTO_CSV")
    if len(sys.argv) > 2:
        return esplicito(sys.argv[2], "argomento da riga di comando")
    base = Path(__file__).resolve().parent
    for d in (base.parent / "docs", base / "docs", base, base.parent,
              Path("/mnt/user-data/uploads/App_Lotto/docs")):
        for pat in ("lotto-archivio-completo-*.csv", "lotto-archivio-*.csv", "*.csv"):
            trovati = sorted(d.glob(pat)) if d.is_dir() else []
            if trovati:
                return trovati[0]
    raise SystemExit(
        "Archivio CSV non trovato.\n"
        "Mettilo in App_Lotto\\docs, oppure indicalo con:\n"
        "   python backtest.py 2006 percorso\\del\\file.csv\n"
        "   $env:LOTTO_CSV = 'percorso\\del\\file.csv'")

CSV = None                       # risolto alla prima chiamata di carica()
ANNO_INIZIO = int(sys.argv[1]) if len(sys.argv) > 1 else 2006
RUOTE_GIOCO = RUOTE                      # 10 ruote classiche, Nazionale esclusa
random.seed(20260912)

# ------------------------------------------------------------- caricamento
def carica():
    global CSV
    if CSV is None:
        CSV = trova_archivio()
        print(f"archivio: {CSV}")
    per_data = defaultdict(dict)
    with open(CSV, encoding="utf-8", errors="replace") as fh:
        for r in csv.reader(fh, delimiter=";"):
            if len(r) != 8 or r[1] not in RUOTE_GIOCO:
                continue
            if int(r[0][:4]) < ANNO_INIZIO:
                continue
            per_data[r[0]][r[1]] = [int(x) for x in r[3:8]]
    date = sorted(per_data)
    # tiene solo i concorsi completi (tutte e 10 le ruote)
    date = [d for d in date if len(per_data[d]) == len(RUOTE_GIOCO)]
    return date, per_data

# --------------------------------------------------------- verifica esiti
def verifica(prev, date, per_data, idx):
    """
    Ritorna dict con il colpo del primo esito per ciascuna sorte, o None.
    Le sorti sono valutate solo sulle ruote di gioco (e a Tutte dove previsto).
    """
    out = {"ambata": None, "ambo": None, "ambo_lunga": None, "ambo_tutte": None}
    for c in range(1, prev.colpi + 1):
        k = idx + c
        if k >= len(date):
            break
        estr = per_data[date[k]]
        setr = {r: set(v) for r, v in estr.items()}
        for r in prev.ruote:
            s = setr[r]
            if out["ambata"] is None and any(a in s for a in prev.ambate):
                out["ambata"] = c
            if out["ambo"] is None and any(x in s and y in s for x, y in prev.ambi):
                out["ambo"] = c
            if out["ambo_lunga"] is None:
                for L in prev.lunghe:
                    if len(s & set(L)) >= 2:
                        out["ambo_lunga"] = c
                        break
        if prev.tutte and out["ambo_tutte"] is None:
            for r in RUOTE_GIOCO:
                s = setr[r]
                if any(x in s and y in s for x, y in prev.ambi) or \
                   any(len(s & set(L)) >= 2 for L in prev.lunghe):
                    out["ambo_tutte"] = c
                    break
        if all(v is not None for v in out.values()):
            break
    return out

def placebo(prev):
    """
    Previsione di controllo per RIETICHETTATURA: ogni numero usato dalla
    previsione viene sostituito con un numero casuale, mantenendo identica la
    struttura combinatoria (quali ambi condividono l'ambata, quanti numeri
    distinti in gioco, quali stanno nella stessa lunga). E' l'unico confronto
    a parita' di esposizione: cambia SOLO quali numeri, non come sono giocati.
    """
    usati = set(prev.ambate)
    for a in prev.ambi:
        usati.update(a)
    for L in prev.lunghe:
        usati.update(L)
    usati = sorted(usati)
    nuovi = random.sample(range(1, 91), len(usati))
    m = dict(zip(usati, nuovi))
    return Previsione(prev.metodo, prev.data, prev.ruote,
                      [m[x] for x in prev.ambate],
                      [tuple(m[x] for x in a) for a in prev.ambi],
                      [tuple(m[x] for x in L) for L in prev.lunghe],
                      prev.colpi, prev.tutte, "placebo")

# ------------------------------------------------------------------ main
def main():
    t0 = time.time()
    date, per_data = carica()
    print(f"Archivio: {len(date)} concorsi completi, {date[0]} -> {date[-1]}\n")

    # ritardi incrementali per LottoFacile 5
    ultima_uscita = {}      # (ruota, numero) -> indice concorso
    n_concorsi = defaultdict(int)

    previsioni = []
    coppie_ruote = list(combinations(RUOTE_GIOCO, 2))

    for idx, d in enumerate(date):
        estr = per_data[d]
        # aggiorna storico uscite (l'estrazione corrente conta nel ritardo)
        for r, nums in estr.items():
            n_concorsi[r] += 1
            for x in nums:
                ultima_uscita[(r, x)] = n_concorsi[r]

        def ritardo(r, x):
            u = ultima_uscita.get((r, x))
            return 10**6 if u is None else n_concorsi[r] - u

        # --- tutte le ruote insieme
        previsioni += scan_ambosecco_caotico(d, estr)

        # --- ruota singola
        for r in RUOTE_GIOCO:
            usciti6 = set()
            for k in range(max(0, idx - 5), idx + 1):
                usciti6.update(per_data[date[k]][r])
            previsioni += scan_lottofacile5(d, estr, r, ritardo_fn=ritardo,
                                            presenti_6=usciti6)

        # --- coppie di ruote
        for ra, rb in coppie_ruote:
            previsioni += scan_lottofacile4(d, estr, ra, rb)
            previsioni += scan_lottofacile1(d, estr, ra, rb)
            storico = set()
            for k in range(max(0, idx - 3), idx):
                storico.update(per_data[date[k]][ra])
                storico.update(per_data[date[k]][rb])
            previsioni += scan_fulmine(d, estr, ra, rb, storico_ambate=storico)
            previsioni += scan_unsoloambosecco(d, estr, ra, rb)

    print(f"Rilevamenti generati: {len(previsioni)}  ({time.time()-t0:.0f}s)\n")

    idx_di = {d: i for i, d in enumerate(date)}
    stat = defaultdict(lambda: defaultdict(int))
    attese = defaultdict(list)

    REP = 5          # ripetizioni della baseline, per ridurne il rumore
    for p in previsioni:
        i = idx_di[p.data]
        reale = verifica(p, date, per_data, i)
        s = stat[p.metodo]
        s["n"] += 1
        for sorte in ("ambata", "ambo", "ambo_lunga", "ambo_tutte"):
            if reale[sorte] is not None:
                s[sorte] += 1
                attese[(p.metodo, sorte)].append(reale[sorte])
        for _ in range(REP):
            fin = verifica(placebo(p), date, per_data, i)
            for sorte in ("ambata", "ambo", "ambo_lunga", "ambo_tutte"):
                if fin[sorte] is not None:
                    s[sorte + "_rnd"] += 1 / REP

    # ------------------------------------------------------------- report
    def z(reale, atteso, n):
        """Scarto in deviazioni standard fra metodo e baseline."""
        p = atteso / n
        if n == 0 or p <= 0 or p >= 1:
            return 0.0
        import math
        return (reale - atteso) / math.sqrt(n * p * (1 - p))

    print("=" * 100)
    print(f"{'metodo':<18}{'rilev.':>8}{'/anno':>7} | "
          f"{'AMBATA: metodo':>15}{'caso':>8}{'scarto':>9} | "
          f"{'AMBO: metodo':>14}{'caso':>8}{'scarto':>9}")
    print("=" * 100)
    anni = (int(date[-1][:4]) - int(date[0][:4])) + 1
    for m in ("lottofacile5", "lottofacile1", "lottofacile4", "fulmine",
              "unsoloambosecco", "ambosecco_caotico"):
        s = stat.get(m)
        if not s or not s["n"]:
            print(f"{m:<18}{'0':>8}   nessun rilevamento")
            continue
        n = s["n"]
        pa, pa_r = 100*s["ambata"]/n, 100*s["ambata_rnd"]/n
        pb, pb_r = 100*s["ambo"]/n, 100*s["ambo_rnd"]/n
        za = z(s["ambata"], s["ambata_rnd"], n)
        zb = z(s["ambo"], s["ambo_rnd"], n)
        ca = f"{pa:6.1f}%{pa_r:8.1f}%{za:+8.1f}σ" if (s["ambata"] or s["ambata_rnd"]) \
             else f"{'-':>7}{'-':>9}{'-':>9}"
        print(f"{m:<18}{n:>8}{n/anni:>7.0f} | {ca} | "
              f"{pb:6.1f}%{pb_r:8.1f}%{zb:+8.1f}σ")
    print("=" * 100)
    print("caso = stessa identica forma di giocata (stessi ambi, stesse ruote, stessi colpi,")
    print("stessa struttura) ma con i numeri sostituiti a sorte, media di 5 ripetizioni.")
    print("scarto: entro ±2σ il metodo è indistinguibile dal caso.")

    print("\nDettaglio ambo in terzina/quartina e gioco a Tutte:")
    for m in ("lottofacile5", "lottofacile1", "lottofacile4", "fulmine",
              "unsoloambosecco", "ambosecco_caotico"):
        s = stat.get(m)
        if not s or not s["n"]:
            continue
        n = s["n"]
        r = f"  {m:<18} ambo in lunga {100*s['ambo_lunga']/n:5.1f}% (caso {100*s['ambo_lunga_rnd']/n:5.1f}%)"
        if s["ambo_tutte"] or s["ambo_tutte_rnd"]:
            r += f" | a Tutte {100*s['ambo_tutte']/n:5.1f}% (caso {100*s['ambo_tutte_rnd']/n:5.1f}%)"
        print(r)
    print(f"\ntempo totale {time.time()-t0:.0f}s")

if __name__ == "__main__":
    main()
