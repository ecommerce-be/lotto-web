"""
Regression test del simulatore di schedina.

Il banco di prova sono le probabilita' note del Lotto, che sono pubbliche e non
opinabili: estratto una su 18, ambo secco una su 400,5, terno secco una su
11.748, quaterna una su 511.038, cinquina una su 43.949.268. Se il modulo
riproduce quelle, la ripartizione della posta e il resto stanno in piedi.

    python test_schedina.py
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services import calendario, schedina          # noqa: E402
from app.services.economia import RITENUTA             # noqa: E402

ok = fail = 0


def check(nome, cond, dettaglio=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  OK   {nome}")
    else:
        fail += 1
        print(f"  FAIL {nome}  {dettaglio}")


def vicino(a, b, tolleranza=1e-9):
    return abs(a - b) <= tolleranza * max(1.0, abs(b))


print("PROBABILITA' NOTE (sorte secca, una ruota)")
attese = {1: 18, 2: 400.5, 3: 11748, 4: 511038, 5: 43949268}
for k, una_su in attese.items():
    p = schedina.probabilita_presi(k, k)
    check(f"{k} numer{'o' if k == 1 else 'i'}: una su {una_su:,.1f}".replace(",", "."),
          vicino(1 / p, una_su, 1e-6), f"ottenuto una su {1/p:,.2f}")

print("\nLA DISTRIBUZIONE E' COMPLETA")
for giocati in (1, 5, 10):
    totale = sum(schedina.probabilita_presi(giocati, m) for m in range(0, 6))
    check(f"{giocati} numeri giocati: le probabilita' sommano a 1",
          vicino(totale, 1.0, 1e-12), str(totale))

print("\nAMBO SECCO, 1 EURO, UNA RUOTA")
r = schedina.simula(numeri=[37, 39], ruote=["NA"], sorti=["ambo"], importo=1)
riga = r["righe"][0]
check("una sola combinazione", riga["combinazioni"] == 1)
check("vincita lorda 250", vicino(riga["scenari"][0]["lordo"], 250.0))
check("vincita netta 230 (ritenuta 8%)",
      vicino(riga["scenari"][0]["netto"], 250 * (1 - RITENUTA)), str(riga["scenari"][0]["netto"]))
check("probabilita' una su 400,5 (non 400: l'arrotondamento nascondeva mezzo punto)",
      riga["scenari"][0]["una_su"] == 400.5, str(riga["scenari"][0]["una_su"]))
check("ritorno atteso 0,574 per euro",
      vicino(r["ritorno_atteso_per_euro"], 250 / 400.5 * (1 - RITENUTA), 1e-3),
      str(r["ritorno_atteso_per_euro"]))

print("\nLA POSTA SI RIPARTISCE")
r = schedina.simula(numeri=[1, 2, 3, 4, 5], ruote=["BA", "NA"],
                    sorti=["ambo", "terno"], importo=10)
ambo = next(x for x in r["righe"] if x["sorte"] == "ambo")
terno = next(x for x in r["righe"] if x["sorte"] == "terno")
check("2 ruote x 2 sorti: 2,50 per ruota e sorte",
      vicino(ambo["posta_per_ruota"], 2.5), str(ambo["posta_per_ruota"]))
check("5 numeri per ambo sono 10 combinazioni", ambo["combinazioni"] == 10)
check("quindi 0,25 per ambo", vicino(ambo["posta_per_combinazione"], 0.25),
      str(ambo["posta_per_combinazione"]))
check("5 numeri per terno sono 10 combinazioni", terno["combinazioni"] == 10)
check("con 3 numeri usciti si vincono 3 ambi",
      next(s for s in ambo["scenari"] if s["presi"] == 3)["combinazioni_vincenti"] == 3)
check("con 5 numeri usciti si vincono 10 ambi",
      next(s for s in ambo["scenari"] if s["presi"] == 5)["combinazioni_vincenti"] == 10)
check("e un solo terno con 3 usciti",
      next(s for s in terno["scenari"] if s["presi"] == 3)["combinazioni_vincenti"] == 1)

print("\nIL RITORNO ATTESO NON DIPENDE DA QUANTI NUMERI NE' DA QUANTE RUOTE")
# e' il punto che i fascicoli non dicono mai: allargare la giocata sposta la
# probabilita' di vincere qualcosa, non il valore della giocata
atteso_ambo = 250 / 400.5 * (1 - RITENUTA)
for numeri, ruote, importo in (([7, 21], ["MI"], 1), ([7, 21, 55], ["MI"], 3),
                               ([1, 2, 3, 4, 5, 6], ["BA", "CA", "FI"], 50),
                               (list(range(1, 11)), ["TUTTE"], 20)):
    r = schedina.simula(numeri=numeri, ruote=ruote, sorti=["ambo"], importo=importo)
    check(f"{len(numeri)} numeri su {len(r['ruote'])} ruote: 0,574 per euro",
          vicino(r["ritorno_atteso_per_euro"], atteso_ambo, 1e-3),
          str(r["ritorno_atteso_per_euro"]))

print("\nPIU' RUOTE: PIU' PROBABILE VINCERE, STESSO VALORE")
una = schedina.simula(numeri=[7, 21], ruote=["MI"], sorti=["ambo"], importo=10)
dieci = schedina.simula(numeri=[7, 21], ruote=["TUTTE"], sorti=["ambo"], importo=10)
check("la probabilita' di vincere qualcosa cresce",
      dieci["qualcosa_almeno_una_ruota"] > una["qualcosa_almeno_una_ruota"] * 9)
check("ma il ritorno atteso resta lo stesso",
      vicino(dieci["ritorno_atteso"], una["ritorno_atteso"], 1e-6),
      f"{una['ritorno_atteso']} vs {dieci['ritorno_atteso']}")
check("e la vincita si divide per dieci",
      vicino(dieci["righe"][0]["vincita_minima_netta"] * 10,
             una["righe"][0]["vincita_minima_netta"], 1e-6))

print("\nLE SORTI LUNGHE PAGANO PEGGIO (e va detto)")
ritorni = {}
for sorte in ("estratto", "ambo", "terno", "quaterna", "cinquina"):
    n = schedina.SORTI[sorte][0]
    r = schedina.simula(numeri=list(range(1, n + 1)), ruote=["RM"],
                        sorti=[sorte], importo=1)
    ritorni[sorte] = r["ritorno_atteso_per_euro"]
check("estratto e ambo sono quasi identici (~0,574)",
      vicino(ritorni["estratto"], ritorni["ambo"], 5e-3), str(ritorni))
check("il terno rende meno dell'ambo", ritorni["terno"] < ritorni["ambo"])
check("la quaterna meno del terno", ritorni["quaterna"] < ritorni["terno"])
check("la cinquina e' la peggiore", ritorni["cinquina"] < ritorni["quaterna"])
check("nessuna sorte restituisce piu' di quanto costa",
      all(v < 1 for v in ritorni.values()), str(ritorni))

print("\nGIOCATE IMPOSSIBILI: RIFIUTATE CON UNA SPIEGAZIONE")
casi = [
    ("numero fuori scala", dict(numeri=[91], ruote=["NA"], sorti=["estratto"], importo=1), "90"),
    ("numero ripetuto", dict(numeri=[7, 7], ruote=["NA"], sorti=["ambo"], importo=1), "due volte"),
    ("undici numeri", dict(numeri=list(range(1, 12)), ruote=["NA"], sorti=["ambo"], importo=1), "Massimo"),
    ("nessun numero", dict(numeri=[], ruote=["NA"], sorti=["ambo"], importo=1), "almeno un numero"),
    ("terno con due numeri", dict(numeri=[7, 21], ruote=["NA"], sorti=["terno"], importo=1), "ne servono almeno 3"),
    ("ruota inesistente", dict(numeri=[7, 21], ruote=["XX"], sorti=["ambo"], importo=1), "sconosciute"),
    ("nessuna ruota", dict(numeri=[7, 21], ruote=[], sorti=["ambo"], importo=1), "almeno una ruota"),
    ("sorte inventata", dict(numeri=[7, 21], ruote=["NA"], sorti=["sestina"], importo=1), "sconosciute"),
    ("importo zero", dict(numeri=[7, 21], ruote=["NA"], sorti=["ambo"], importo=0), "maggiore di zero"),
]
for nome, argomenti, atteso in casi:
    try:
        schedina.simula(**argomenti)
        check(nome, False, "accettata invece di essere rifiutata")
    except schedina.GiocataNonValida as e:
        check(f"{nome}: {e}", atteso.lower() in str(e).lower(), str(e))

print("\nTUTTE = le dieci ruote classiche")
r = schedina.simula(numeri=[7, 21], ruote=["tutte"], sorti=["ambo"], importo=10)
check("dieci ruote", len(r["ruote"]) == 10, str(r["ruote"]))
check("la Nazionale non c'e'", "RN" not in r["ruote"], str(r["ruote"]))

print("\nPROSSIMA ESTRAZIONE: PRIMA E DOPO LE 20")
check("alle 18 il giorno utile e' oggi",
      calendario._primo_giorno_utile(datetime(2026, 9, 15, 18, 0))
      == datetime(2026, 9, 15).date())
check("alle 20:30 e' domani",
      calendario._primo_giorno_utile(datetime(2026, 9, 15, 20, 30))
      == datetime(2026, 9, 16).date())
check("alle 20 in punto e' gia' domani",
      calendario._primo_giorno_utile(datetime(2026, 9, 15, 20, 0))
      == datetime(2026, 9, 16).date())
check("dicembre passa a gennaio dell'anno dopo",
      calendario._mese_dopo(datetime(2026, 12, 3).date()) == datetime(2027, 1, 1).date())

print(f"\n{'='*60}\nRISULTATO: {ok} OK, {fail} FAIL")
sys.exit(1 if fail else 0)
