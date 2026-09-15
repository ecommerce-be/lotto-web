"""Regression test: il motore deve riprodurre gli esempi pubblicati nei fascicoli."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lotto_engine import *

ok = fail = 0
def check(nome, cond, dettaglio=""):
    global ok, fail
    if cond:
        ok += 1; print(f"  OK   {nome}")
    else:
        fail += 1; print(f"  FAIL {nome}  {dettaglio}")

print("LOTTO FACILE 4 — applicazione pratica 03/05/1999 (GE 19-82 / MI 49-22, pos 1-3)")
estr = {"GE": [19, 25, 82, 54, 23], "MI": [49, 88, 22, 47, 15]}
p = [x for x in scan_lottofacile4("1999-05-03", estr, "GE", "MI") if x.ambate == (29,)]
check("ambata 29", bool(p), "nessuna previsione con ambata 29")
if p:
    check("ambi 29-59 / 29-89 / 29-74",
          set(p[0].ambi) == {(29, 59), (29, 89), (29, 74)}, str(p[0].ambi))
    check("terzina 59-89-74", p[0].lunghe == ((59, 74, 89),), str(p[0].lunghe))

print("\nLOTTO FACILE 4 — casi della tabella statistica")
casi_lf4 = [
    ("1999-01-07", {"BA": [0, 60, 90, 0, 0], "NA": [0, 10, 70, 0, 0]}, "BA", "NA", 55),
    ("1999-01-07", {"CA": [0, 0, 72, 80, 0], "RM": [0, 0, 20, 42, 0]}, "CA", "RM", 23),
    ("1999-01-20", {"GE": [0, 0, 0, 45, 52], "TO": [0, 0, 0, 22, 75]}, "GE", "TO", 73),
]
for data, estr, ra, rb, atteso in casi_lf4:
    trovate = {x.ambate[0] for x in scan_lottofacile4(data, estr, ra, rb)}
    check(f"{data} {ra}-{rb} -> ambata {atteso}", atteso in trovate, f"trovate {trovate}")

print("\nLOTTO FACILE 1 — 03/05/1993 (CA 41/13 pos 3-5, FI 33/21 pos 3-5)")
estr = {"CA": [35, 58, 41, 65, 13], "FI": [31, 52, 33, 49, 21]}
p = [x for x in scan_lottofacile1("1993-05-03", estr, "CA", "FI") if x.ambate == (66,)]
check("ambata 66", bool(p))
if p:
    check("ambi 66-36 e 66-63", set(p[0].ambi) == {(36, 66), (63, 66)}, str(p[0].ambi))

print("\nLOTTO FACILE 1 — 01/10/1997 (CA 87/69 pos 4-5, MI 85/71 pos 4-5)")
estr = {"CA": [74, 62, 77, 87, 69], "MI": [89, 23, 7, 85, 71]}
p = [x for x in scan_lottofacile1("1997-10-01", estr, "CA", "MI") if x.ambate == (80,)]
check("ambata 80", bool(p))
if p:
    check("ambi 80-24 e 80-42", set(p[0].ambi) == {(24, 80), (42, 80)}, str(p[0].ambi))

print("\nFULMINE — tre esempi di Manara")
casi_f = [
    ("1998-12-02", {"MI": [67, 47, 1, 2, 3], "PA": [77, 57, 4, 5, 6]}, "MI", "PA", 77),
    ("1998-12-09", {"RM": [73, 82, 1, 2, 3], "VE": [19, 28, 4, 5, 6]}, "RM", "VE", 82),
    ("1998-12-02", {"MI": [9, 39, 1, 2, 3], "VE": [29, 59, 4, 5, 6]}, "MI", "VE", 59),
]
for data, estr, ra, rb, atteso in casi_f:
    # filtro_vertibile disattivato: l'esempio RM-VE del 09/12/1998 pubblicato da
    # Manara come successo viola la sua stessa controindicazione 3 (ambata 82,
    # vertibile 28 presente nella formazione).
    prev = scan_fulmine(data, estr, ra, rb, filtro_vertibile=False)
    trovate = {x.ambate[0] for x in prev}
    check(f"{data} {ra}-{rb} -> ambata {atteso}", atteso in trovate, f"trovate {trovate}")
    p = [x for x in prev if x.ambate == (atteso,)]
    if p:
        altri = set(p[0].lunghe[0]) - {atteso}
        check(f"   quartina di {atteso}", len(p[0].lunghe[0]) == 4, str(p[0].lunghe))

print("\nUN SOLO AMBO SECCO — 14/03/1998 (CA 19-52-82 pos 3-4-5, GE 13-46-73 pos 1-2-3)")
estr = {"CA": [1, 2, 19, 52, 82], "GE": [13, 46, 73, 4, 5]}
prev = scan_unsoloambosecco("1998-03-14", estr, "CA", "GE")
check("ambo secco 65-40", any(x.ambi == ((40, 65),) for x in prev),
      str([x.ambi for x in prev]))

print("\nLOTTO FACILE 5 — quattro rilevamenti dagli esempi statistici")
casi_lf5 = [
    ("TO", [21, 66, 1, 2, 3], (54, 9), {(15, 54), (54, 60), (9, 15), (9, 60)}),
    ("PA", [12, 57, 1, 2, 3], (27, 72), {(27, 51), (6, 27), (51, 72), (6, 72)}),
    ("VE", [51, 6, 1, 2, 3], (9, 54), {(9, 75), (9, 30), (54, 75), (30, 54)}),
    ("CA", [89, 44, 1, 2, 3], (42, 87), {(42, 79), (34, 42), (79, 87), (34, 87)}),
]
for ruota, nums, amb_att, ambi_att in casi_lf5:
    prev = scan_lottofacile5("1999-08-28", {ruota: nums}, ruota)
    check(f"{ruota} {nums[0]}-{nums[1]} -> ambate {amb_att}",
          any(x.ambate == amb_att for x in prev),
          str([x.ambate for x in prev]))
    p = [x for x in prev if x.ambate == amb_att]
    if p:
        check(f"   ambi secchi", set(p[0].ambi) == ambi_att, str(set(p[0].ambi)))

print("\nAMBO SECCO CAOTICO — 18/07/1998 (NA 41, MI 49, VE 41)")
a1, a2 = ambi_caotico(41, 49)
check("formula: ambi 37-39 e 85-49", {a1, a2} == {(37, 39), (85, 49)}, f"{a1} {a2}")
estr = {"NA": [41, 1, 2, 3, 4], "MI": [49, 5, 6, 7, 8], "VE": [41, 9, 10, 11, 12]}
prev = scan_ambosecco_caotico("1998-07-18", estr)
check("condizione: A ripetuto su 2 ruote + complemento su una terza",
      any(set(p.ambi) == {(37, 39), (49, 85)} for p in prev),
      str([p.ambi for p in prev]))

print(f"\n{'='*60}\nRISULTATO: {ok} OK, {fail} FAIL")
sys.exit(1 if fail else 0)
