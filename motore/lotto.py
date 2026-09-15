"""
Motore di rilevamento e previsione per i metodi del progetto App Lotto.

Implementa i 5 metodi ricostruibili dai fascicoli:
  - lottofacile4  : Ciclo-Pondometria / terzine simmetriche
  - lottofacile1  : somma comune interna + isotopi
  - lottofacile5  : ambo diametrale su ruota singola (tabellare)
  - fulmine       : Manara, somma comune incrociata + cadenza/figura
  - unsoloambosecco: distanza 30 + somma incrociata + tripla figurale

Riferimento: claude/kb-metodi-lotto.md nel progetto.
"""
from itertools import combinations, permutations
from collections import defaultdict

# ---------------------------------------------------------------- primitive

def f90(n: int) -> int:
    """Fuori 90: riporta n nell'intervallo 1..90."""
    n %= 90
    return 90 if n == 0 else n

def complemento(n: int) -> int:
    return 90 - n

def diametrale(n: int) -> int:
    return f90(n + 45)

_VERT_ECC = {11: 19, 19: 11, 22: 29, 29: 22, 33: 39, 39: 33, 44: 49, 49: 44,
             55: 59, 59: 55, 66: 69, 69: 66, 77: 79, 79: 77, 88: 89, 89: 88}

def vertibile(n: int) -> int:
    """Tavola dei 90 vertibili (LottoFacile_IlMetodoVincente.pdf, pag. 3)."""
    if n in _VERT_ECC:
        return _VERT_ECC[n]
    if n < 10:
        return n * 10
    if n % 10 == 0:
        return n // 10
    return (n % 10) * 10 + n // 10

def figura(n: int) -> int:
    return ((n - 1) % 9) + 1

def cadenza(n: int) -> int:
    return n % 10

def dist_ciclo(a: int, b: int) -> int:
    d = abs(a - b)
    return min(d, 90 - d)

def stessa_terzina(a: int, b: int) -> bool:
    """Stessa terzina simmetrica: distanza ciclometrica 30."""
    return dist_ciclo(a, b) == 30

def terzina_di(n: int):
    return (n, f90(n + 30), f90(n + 60))

TRIPLE_FIGURALI = ({1, 4, 7}, {2, 5, 8}, {3, 6, 9})

def stessa_tripla_figurale(numeri) -> bool:
    figs = {figura(x) for x in numeri}
    return any(figs <= t for t in TRIPLE_FIGURALI)

RUOTE = ["BA", "CA", "FI", "GE", "MI", "NA", "PA", "RM", "TO", "VE"]
CONSECUTIVE = {frozenset((RUOTE[i], RUOTE[i + 1])) for i in range(len(RUOTE) - 1)}
DIAMETRALI = {frozenset(p) for p in
              (("BA", "NA"), ("CA", "PA"), ("FI", "RM"), ("GE", "TO"), ("MI", "VE"))}

# ------------------------------------------------------------ previsione

class Previsione:
    __slots__ = ("metodo", "data", "ruote", "ambate", "ambi", "lunghe",
                 "colpi", "tutte", "note")

    def __init__(self, metodo, data, ruote, ambate, ambi, lunghe, colpi,
                 tutte=False, note=""):
        self.metodo = metodo      # str
        self.data = data          # 'YYYY-MM-DD' del rilevamento
        self.ruote = tuple(ruote) # ruote di gioco
        self.ambate = tuple(ambate)
        self.ambi = tuple(tuple(sorted(a)) for a in ambi)
        self.lunghe = tuple(tuple(sorted(l)) for l in lunghe)  # terzine/quartine
        self.colpi = colpi
        self.tutte = tutte        # le lunghe si giocano anche a Tutte
        self.note = note

    def __repr__(self):
        return (f"<{self.metodo} {self.data} {'-'.join(self.ruote)} "
                f"amb={self.ambate} ambi={self.ambi}>")

# ------------------------------------------------------- scanner condivisi

def accoppiamento_incrociato(na, nb):
    """
    Scanner B: cerca un abbinamento uno-a-uno fra i numeri di due ruote tale che
    TUTTE le somme fuori 90 diano lo stesso S. Ritorna la lista di (coppie, S).
    """
    out = []
    for perm in permutations(nb):
        somme = {f90(a + b) for a, b in zip(na, perm)}
        if len(somme) == 1:
            out.append((tuple(zip(na, perm)), somme.pop()))
    return out

# ---------------------------------------------------------------- metodi

def scan_lottofacile4(data, estr, ruota_a, ruota_b):
    """
    LOTTO FACILE 4 — Ciclo-Pondometria.
    Due ambi isotopi appartenenti a terzine simmetriche, letti in verticale,
    orizzontale o diagonale. Ambata = diametrale(2 * somma dei 4 numeri).
    """
    A, B = estr[ruota_a], estr[ruota_b]
    res = []
    for i, j in combinations(range(5), 2):
        a1, a2, b1, b2 = A[i], A[j], B[i], B[j]
        letture = []
        if stessa_terzina(a1, a2) and stessa_terzina(b1, b2):
            letture.append("orizzontale")
        if stessa_terzina(a1, b1) and stessa_terzina(a2, b2):
            letture.append("verticale")
        if stessa_terzina(a1, b2) and stessa_terzina(a2, b1):
            letture.append("diagonale")
        if not letture:
            continue
        S = f90(a1 + a2 + b1 + b2)
        N1 = f90(S * 2)
        Am = diametrale(N1)
        N2, N3 = f90(Am + 30), f90(Am + 60)
        res.append(Previsione(
            "lottofacile4", data, (ruota_a, ruota_b),
            ambate=[Am],
            ambi=[(Am, N1), (Am, N2), (Am, N3)],
            lunghe=[(N1, N2, N3)],
            colpi=14, tutte=True,
            note=f"pos {i+1}-{j+1} {'/'.join(letture)}"))
    return res

def scan_lottofacile1(data, estr, ruota_a, ruota_b):
    """
    LOTTO FACILE — Il Metodo Vincente.
    Due ambi isotopi con la stessa somma interna. Ambata = 2 * primo numero
    della SECONDA ruota in ordine alfabetico (convenzione fissata).
    """
    if ruota_a > ruota_b:
        ruota_a, ruota_b = ruota_b, ruota_a
    A, B = estr[ruota_a], estr[ruota_b]
    res = []
    for i, j in combinations(range(5), 2):
        a1, a2, b1, b2 = A[i], A[j], B[i], B[j]
        Sc = f90(a1 + a2)
        if Sc != f90(b1 + b2):
            continue
        Am = f90(2 * b1)
        compl = complemento(Sc)
        if compl < 1:          # Sc == 90 -> complemento non giocabile
            continue
        vert = vertibile(compl)
        ambi = [(Am, compl)]
        if vert != compl:
            ambi.append((Am, vert))
        res.append(Previsione(
            "lottofacile1", data, (ruota_a, ruota_b),
            ambate=[Am], ambi=ambi,
            lunghe=[tuple({Am, compl, vert})] if len({Am, compl, vert}) == 3 else [],
            colpi=6,
            note=f"pos {i+1}-{j+1} somma {Sc}"))
    return res

# tabella Lotto Facile 5 (Rita Calone) — rilevamento n -> (A1, A2, B1, B2)
# implementata ALLA LETTERA, refuso della riga 39 incluso (vedi kb).
TAB_LF5 = {
    1: (84, 39, 20, 65),  2: (6, 51, 85, 40),  3: (90, 45, 42, 87),
    4: (12, 57, 89, 44),  5: (6, 51, 64, 19),  6: (9, 54, 75, 30),
    7: (21, 66, 5, 50),   8: (15, 60, 7, 52),  9: (18, 63, 12, 57),
    10: (21, 66, 29, 74), 11: (33, 78, 13, 58), 12: (27, 72, 51, 6),
    13: (30, 75, 62, 17), 14: (33, 78, 73, 28), 15: (36, 81, 84, 39),
    16: (48, 3, 23, 68),  17: (51, 6, 25, 70),  18: (45, 90, 27, 72),
    19: (48, 3, 38, 83),  20: (51, 6, 49, 4),   21: (54, 9, 60, 15),
    22: (66, 21, 35, 80), 23: (60, 15, 82, 37), 24: (72, 27, 39, 84),
    25: (75, 30, 41, 86), 26: (78, 33, 43, 88), 27: (72, 27, 36, 81),
    28: (75, 30, 47, 2),  29: (78, 33, 58, 13), 30: (90, 45, 51, 6),
    31: (84, 39, 80, 35), 32: (87, 42, 1, 46),  33: (90, 45, 12, 57),
    34: (12, 57, 59, 14), 35: (6, 51, 34, 79),  36: (9, 54, 45, 90),
    37: (12, 57, 56, 11), 38: (24, 69, 67, 22), 39: (18, 63, 12, 57),
    40: (21, 66, 89, 44), 41: (33, 78, 73, 28), 42: (27, 72, 21, 66),
    43: (30, 75, 32, 77), 44: (42, 87, 79, 34), 45: (36, 81, 54, 9),
}

def scan_lottofacile5(data, estr, ruota, ritardo_fn=None, presenti_6=None):
    """
    LOTTO FACILE 5 — Rita Calone. Ruota singola.
    Rilevamento: un ambo diametrale (distanza 45) nell'estrazione.
    Condizione (a): si scarta l'ambata con ritardo > 20 sulla ruota.
    Condizione (b): warning (non veto) se l'ambata è uscita nelle 6 estrazioni
    precedenti -> previsione marcata "potenza ridotta".
    """
    nums = estr[ruota]
    res = []
    for a, b in combinations(sorted(nums), 2):
        if b - a != 45:
            continue
        n = a                                  # rilevamento 1..45
        A1, A2, B1, B2 = TAB_LF5[n]
        ambate = [A1, A2]
        if ritardo_fn is not None:
            ambate = [x for x in ambate if ritardo_fn(ruota, x) <= 20]
            if not ambate:
                continue
        note = f"rilevamento {a}-{b}"
        if presenti_6 and any(x in presenti_6 for x in ambate):
            note += " [potenza ridotta: ambata uscita negli ultimi 6 concorsi]"
        ambi, lunghe = [], []
        for Am in ambate:
            for Bx in (B1, B2):
                ambi.append((Am, Bx))
                lunghe.append((Am,) + terzina_di(Bx))
        res.append(Previsione(
            "lottofacile5", data, (ruota,), ambate=ambate, ambi=ambi,
            lunghe=lunghe, colpi=9, tutte=False, note=note))
    return res

def scan_fulmine(data, estr, ruota_a, ruota_b, vincolo_ruote="nessuno",
                 solo_isotopi=False, storico_ambate=None, filtro_vertibile=True):
    """
    FULMINE — Osvaldo Manara.
    4 elementi di stessa cadenza o stessa figura, 2 per ruota, che ammettono
    una partizione INCROCIATA in due coppie di somma uguale. Ambata = massimo.

    vincolo_ruote: 'nessuno' | 'consecutive' | 'consecutive+diametrali'
    storico_ambate: set dei numeri usciti su queste ruote nelle 4 estrazioni
                    precedenti (controindicazione 1).
    """
    coppia = frozenset((ruota_a, ruota_b))
    if vincolo_ruote == "consecutive" and coppia not in CONSECUTIVE:
        return []
    if vincolo_ruote == "consecutive+diametrali" and coppia not in (CONSECUTIVE | DIAMETRALI):
        return []

    A, B = estr[ruota_a], estr[ruota_b]
    tutti = set(A) | set(B)
    res = []
    for ia, ja in combinations(range(5), 2):
        if solo_isotopi:
            pos_b = [(ia, ja)]
        else:
            pos_b = list(combinations(range(5), 2))
        a1, a2 = A[ia], A[ja]
        for ib, jb in pos_b:
            b1, b2 = B[ib], B[jb]
            quat = [a1, a2, b1, b2]
            if len(set(quat)) != 4:
                continue
            # stessa cadenza o stessa figura
            if len({cadenza(x) for x in quat}) == 1:
                tipo = "cadenza"
            elif len({figura(x) for x in quat}) == 1:
                tipo = "figura"
            else:
                continue
            # partizione incrociata a somma uguale
            if a1 + b1 == a2 + b2:
                coppie = ((a1, b1), (a2, b2))
            elif a1 + b2 == a2 + b1:
                coppie = ((a1, b2), (a2, b1))
            else:
                continue
            Am = max(quat)
            # controindicazione 3: vertibile dell'ambata nella stessa estrazione.
            # NB: l'esempio RM-VE del 09/12/1998 pubblicato da Manara come successo
            # viola questa sua stessa regola (ambata 82, vertibile 28 presente
            # nella formazione) -> parametro, cosi' il backtest puo' misurarla.
            if filtro_vertibile and vertibile(Am) in tutti:
                continue
            # controindicazione 1: ambata presente nelle 4 estrazioni precedenti
            if storico_ambate and Am in storico_ambate:
                continue
            altri = [x for x in quat if x != Am]
            res.append(Previsione(
                "fulmine", data, (ruota_a, ruota_b),
                ambate=[Am],
                ambi=[(Am, x) for x in altri],
                lunghe=[tuple(quat)],
                colpi=12, tutte=False,
                note=f"{tipo}, coppie {coppie}"))
    return res

def ambi_caotico(A, B):
    """
    AMBO SECCO CAOTICO — Antonio Longo. Formula ricostruita dall'esempio
    del 18/07/1998 (NA 41, MI 49, VE 41 -> ambi 37-39 e 85-49).

    Si moltiplica A per 90 ottenendo un numero di 4 cifre, e lo si legge in due
    modi, sommando B una volta al numero intero e una volta a ciascuna meta':

        P = A x 90                              41 x 90 = 3690
        ambo 1 = le due meta' di (P + B)        3739 -> 37 | 39
        ambo 2 = le due meta' di P, ciascuna    3690 -> 36 | 90
                 sommata a B, fuori 90          36+49=85 ; 90+49=139->49

    Entrambi gli ambi pubblicati nel documento sono riprodotti esattamente.
    """
    P = A * 90
    tot = P + B
    ambo1 = (tot // 100, tot % 100)
    ambo2 = (f90(P // 100 + B), f90(P % 100 + B))
    return ambo1, ambo2

def scan_ambosecco_caotico(data, estr, condizione="complemento"):
    """
    Condizione di ricerca IPOTETICA, ricavata dall'unico esempio disponibile:
    un numero A uscito su DUE ruote diverse, e il suo complemento a 90 presente
    su una TERZA ruota (nell'esempio: 41 su NA e VE, 49 = 90-41 su MI).

    condizione: 'complemento' (stretta, come l'esempio)
                'ripetuto'    (larga: A su due ruote, B qualunque altro estratto)
    Giocata: 1-2 ambi secchi, 1-2 colpi, a Tutte.
    """
    dove = defaultdict(list)
    for r, nums in estr.items():
        for x in nums:
            dove[x].append(r)
    res = []
    for A, ruote_a in dove.items():
        if len(ruote_a) < 2:
            continue
        if condizione == "complemento":
            candidati = [complemento(A)] if 1 <= complemento(A) <= 90 else []
        else:
            candidati = [x for x in dove if x != A]
        for B in candidati:
            ruote_b = [r for r in dove.get(B, []) if r not in ruote_a]
            if not ruote_b:
                continue
            a1, a2 = ambi_caotico(A, B)
            if not all(1 <= x <= 90 for x in a1 + a2):
                continue
            res.append(Previsione(
                "ambosecco_caotico", data, tuple(ruote_a + ruote_b),
                ambate=[], ambi=[a1, a2], lunghe=[],
                colpi=2, tutte=True,
                note=f"A={A} su {'/'.join(ruote_a)}, B={B} su {'/'.join(ruote_b)}"))
    return res

def scan_unsoloambosecco(data, estr, ruota_a, ruota_b):
    """
    UN SOLO AMBO SECCO.
    Due ambi a distanza ciclometrica 30 (uno per ruota) che si accoppiano in
    modo incrociato a somma costante S, piu' una terza coppia con la stessa S.
    I sei numeri devono stare nella stessa tripla figurale.
    Giocata: un solo ambo secco S - fuori90(2S), 4 colpi, su 2 ruote e a Tutte.
    """
    A, B = estr[ruota_a], estr[ruota_b]
    res, visti = [], set()
    for x1, x2 in combinations(A, 2):
        if not stessa_terzina(x1, x2):
            continue
        for y1, y2 in combinations(B, 2):
            if not stessa_terzina(y1, y2):
                continue
            # accoppiamento incrociato a somma costante
            if f90(x1 + y1) == f90(x2 + y2):
                S = f90(x1 + y1)
            elif f90(x1 + y2) == f90(x2 + y1):
                S = f90(x1 + y2)
            else:
                continue
            # terza coppia con la stessa somma
            for x3 in A:
                if x3 in (x1, x2):
                    continue
                for y3 in B:
                    if y3 in (y1, y2):
                        continue
                    if f90(x3 + y3) != S:
                        continue
                    sei = [x1, x2, x3, y1, y2, y3]
                    if not stessa_tripla_figurale(sei):
                        continue
                    N = f90(2 * S)
                    if N == S:
                        continue
                    chiave = (S, N)
                    if chiave in visti:
                        continue
                    visti.add(chiave)
                    res.append(Previsione(
                        "unsoloambosecco", data, (ruota_a, ruota_b),
                        ambate=[], ambi=[(S, N)], lunghe=[],
                        colpi=4, tutte=True,
                        note=f"S={S} su {sorted(sei)}"))
    return res
