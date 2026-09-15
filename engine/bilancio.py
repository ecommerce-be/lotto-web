"""Bilancio economico reale: quanto si spende e quanto si incassa applicando
i metodi per 20 anni, con le quote ufficiali del Lotto italiano.
Quote (moltiplicatore della posta, su ruota singola): ambata 11,232 | ambo 250
| terno 4500 | quaterna 120000.  Ritenuta erariale sulle vincite: 8%.
Regola di gioco: 1 euro per sorte, per ruota, per colpo; si sospende la sorte
sulla ruota dove si e' verificata la vincita (come prescrivono i fascicoli).
"""
import sys, random
from pathlib import Path
from collections import defaultdict
from itertools import combinations
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lotto_engine import *
import backtest as bt

random.seed(1)
bt.ANNO_INIZIO = 2006
date, per_data = bt.carica()
idx_di = {d: i for i, d in enumerate(date)}
QUOTA = {"ambata": 11.232, "ambo": 250.0, "terno": 4500.0, "quaterna": 120000.0}
RITENUTA = 0.08

def gioca(p):
    """Ritorna (spesa, vincita_lorda) per una previsione, 1 euro per sorte/ruota/colpo."""
    spesa = vincita = 0.0
    i = idx_di[p.data]
    attive = {(r, s): True for r in p.ruote
              for s in (["A"] if p.ambate else []) + [f"B{k}" for k in range(len(p.ambi))]
              + [f"L{k}" for k in range(len(p.lunghe))]}
    for c in range(1, p.colpi + 1):
        k = i + c
        if k >= len(date): break
        estr = per_data[date[k]]
        for r in p.ruote:
            s = set(estr[r])
            if p.ambate and attive.get((r, "A")):
                spesa += 1
                if any(a in s for a in p.ambate):
                    vincita += QUOTA["ambata"] / max(1, len(p.ambate))
                    attive[(r, "A")] = False
            for kk, (x, y) in enumerate(p.ambi):
                if not attive.get((r, f"B{kk}")): continue
                spesa += 1
                if x in s and y in s:
                    vincita += QUOTA["ambo"]
                    attive[(r, f"B{kk}")] = False
            for kk, L in enumerate(p.lunghe):
                if not attive.get((r, f"L{kk}")): continue
                spesa += 1                      # giocata per ambo e terno in lunga
                dentro = len(s & set(L))
                nc = len(L)
                if dentro >= 3:
                    vincita += QUOTA["terno"] / (nc*(nc-1)*(nc-2)//6)
                    attive[(r, f"L{kk}")] = False
                elif dentro == 2:
                    vincita += QUOTA["ambo"] / (nc*(nc-1)//2)
                    attive[(r, f"L{kk}")] = False
    return spesa, vincita

scanners = {
    "lottofacile5": lambda d, e: [x for r in RUOTE for x in scan_lottofacile5(d, e, r)],
    "lottofacile1": lambda d, e: [x for a, b in combinations(RUOTE, 2) for x in scan_lottofacile1(d, e, a, b)],
    "lottofacile4": lambda d, e: [x for a, b in combinations(RUOTE, 2) for x in scan_lottofacile4(d, e, a, b)],
    "fulmine":      lambda d, e: [x for a, b in combinations(RUOTE, 2) for x in scan_fulmine(d, e, a, b)],
    "unsoloambosecco": lambda d, e: [x for a, b in combinations(RUOTE, 2) for x in scan_unsoloambosecco(d, e, a, b)],
}

print(f"{'metodo':<18}{'previsioni':>11}{'speso':>13}{'incassato':>13}{'saldo':>13}{'ritorno':>9}")
print("-" * 78)
tot_s = tot_v = 0
for nome, fn in scanners.items():
    S = V = 0.0; n = 0
    for d in date:
        for p in fn(d, per_data[d]):
            n += 1
            s, v = gioca(p)
            S += s; V += v * (1 - RITENUTA)
    tot_s += S; tot_v += V
    if S:
        print(f"{nome:<18}{n:>11}{S:>12,.0f}€{V:>12,.0f}€{V-S:>12,.0f}€{100*V/S:>8.1f}%")
print("-" * 78)
print(f"{'TOTALE':<18}{'':>11}{tot_s:>12,.0f}€{tot_v:>12,.0f}€{tot_v-tot_s:>12,.0f}€{100*tot_v/tot_s:>8.1f}%")
print("\nritorno = quanto torna indietro ogni 100 euro giocati.")
