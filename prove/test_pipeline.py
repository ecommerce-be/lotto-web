"""
Prove della catena: archivio -> rilevamento -> valutazione -> bilancio -> sito.

Le proprieta' che contano davvero sono tre, e nessuna si vede guardando il sito:

  * **determinismo** — gli stessi dati producono le stesse previsioni, con le
    stesse chiavi. Senza, ogni ricostruzione dello storico creerebbe doppioni;
  * **idempotenza** — rilanciare l'aggiornamento non conta due volte lo stesso
    colpo. E' cio' che permette al processo serale di essere rilanciato a mano
    senza paura;
  * **stabilita' su file** — due esecuzioni sugli stessi dati scrivono file
    identici byte per byte, altrimenti git registrerebbe modifiche fantasma
    ogni sera.

    python prove/test_pipeline.py
"""
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from motore import economia, pubblica, stato                 # noqa: E402
from motore.archivio import Archivio                          # noqa: E402
from motore.rilevamento import chiave, rileva                  # noqa: E402
from motore.valutazione import colpi_residui, valuta           # noqa: E402

ok = fail = 0


def check(nome, cond, dettaglio=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  OK   {nome}")
    else:
        fail += 1
        print(f"  FAIL {nome}  {dettaglio}")


print("ARCHIVIO")
arch = Archivio.carica(RADICE / "archivio" / "estrazioni.csv")
check("si carica", len(arch.date) > 7000, f"{len(arch.date)} concorsi")
check("l'ultimo concorso ha tutte e dieci le ruote", arch.completo(arch.ultima))
check("i numeri sono in ordine di estrazione, non riordinati",
      arch.ordine_di_estrazione(), f"quota crescenti {arch.quota_crescenti():.2%}")
check("la quota di quadri crescenti e' quella attesa dal caso (0,83%)",
      0.005 < arch.quota_crescenti() < 0.015, f"{arch.quota_crescenti():.4f}")

with tempfile.TemporaryDirectory() as tmp:
    copia = Path(tmp) / "estrazioni.csv"
    arch.salva(copia)
    riletto = Archivio.carica(copia)
    check("salvare e rileggere non perde nulla",
          riletto.quadri == arch.quadri)
    arch.salva(copia)
    primo = copia.read_bytes()
    arch.salva(copia)
    check("due salvataggi producono lo stesso file", primo == copia.read_bytes())

print("\nRILEVAMENTO")
giorno = arch.ultima
prime = rileva(arch, giorno)
seconde = rileva(arch, giorno)
check("produce qualcosa sull'ultimo concorso", len(prime) > 0, f"{len(prime)} previsioni")
check("e' deterministico: stesse chiavi due volte",
      [p["chiave"] for p in prime] == [p["chiave"] for p in seconde])
check("le chiavi sono tutte diverse",
      len({p["chiave"] for p in prime}) == len(prime))
check("ogni previsione ha almeno una sorte", all(p["sorti"] for p in prime))
check("i numeri sono tutti giocabili",
      all(1 <= n <= 90 for p in prime for s in p["sorti"] for n in s["numeri"]))
check("le ruote sono sigle vere",
      all(r in arch.quadro(giorno) for p in prime for r in p["ruote"]))

diverse = chiave("fulmine", date(2026, 1, 1), ["BA"],
                 [{"tipo": "ambo", "numeri": [1, 2]}])
uguali = chiave("fulmine", date(2026, 1, 1), ["BA"],
                [{"tipo": "ambo", "numeri": [1, 2]}])
altra = chiave("fulmine", date(2026, 1, 1), ["BA"],
               [{"tipo": "ambo", "numeri": [1, 3]}])
check("la chiave dipende solo dagli ingredienti", diverse == uguali)
check("numeri diversi, chiave diversa", diverse != altra)

print("\nUNIONE: NIENTE DOPPIONI")
insieme, aggiunte = stato.unisci([], prime)
check(f"la prima volta le aggiunge tutte ({len(prime)})", aggiunte == len(prime))
insieme, aggiunte = stato.unisci(insieme, rileva(arch, giorno))
check("la seconda volta non aggiunge niente", aggiunte == 0, str(aggiunte))
check("e l'elenco non cresce", len(insieme) == len(prime))

print("\nVALUTAZIONE: IDEMPOTENTE")
# si rileva su un concorso vecchio, cosi' ci sono estrazioni successive da valutare
vecchio = arch.date[-40]
previsioni = rileva(arch, vecchio)
primo = valuta(previsioni, arch)
esiti_dopo_uno = sum(len(s["esiti"]) for p in previsioni for s in p["sorti"])
secondo = valuta(previsioni, arch)
esiti_dopo_due = sum(len(s["esiti"]) for p in previsioni for s in p["sorti"])
check("la prima valutazione fa qualcosa", primo.sorti_esaminate > 0)
check("la seconda non aggiunge esiti", esiti_dopo_uno == esiti_dopo_due,
      f"{esiti_dopo_uno} -> {esiti_dopo_due}")
check("e non ne dichiara di nuovi", secondo.esiti_nuovi == 0, str(secondo.esiti_nuovi))
check("nessuna sorte supera i colpi previsti",
      all(s["colpi_valutati"] <= p["colpi"] for p in previsioni for s in p["sorti"]))
check("una sorte vinta non e' anche scaduta",
      all(s["stato"] in ("aperta", "vinta", "scaduta")
          for p in previsioni for s in p["sorti"]))
vinte = [s for p in previsioni for s in p["sorti"] if s["stato"] == "vinta"]
check("ogni sorte vinta ha un esito sulla ruota di gioco",
      all(s["esiti"] for s in vinte), f"{len(vinte)} vinte")
check("le sorti chiuse non hanno colpi residui",
      all(colpi_residui(p, s, arch) == 0
          for p in previsioni for s in p["sorti"] if s["stato"] != "aperta"))

print("\nSTATO SU FILE: STABILE")
with tempfile.TemporaryDirectory() as tmp:
    f = Path(tmp) / "previsioni.jsonl"
    stato.salva(f, previsioni)
    uno = f.read_bytes()
    stato.salva(f, list(reversed(previsioni)))     # ordine d'ingresso diverso
    check("l'ordine d'ingresso non cambia il file", uno == f.read_bytes())
    riletto = stato.carica(f)
    check("si rilegge identico",
          sorted(json.dumps(p, sort_keys=True) for p in riletto)
          == sorted(json.dumps(p, sort_keys=True) for p in previsioni))
    (Path(tmp) / "rotto.jsonl").write_text("{non json}\n", encoding="utf-8")
    try:
        stato.carica(Path(tmp) / "rotto.jsonl")
        check("un file corrotto viene segnalato", False, "nessun errore")
    except ValueError as e:
        check(f"un file corrotto viene segnalato: {str(e)[:60]}…", "riga 1" in str(e))

print("\nECONOMIA")
check("ambo secco: 250", economia.vincita_lorda("ambo", 2) == 250)
check("ambata: 11,232", economia.vincita_lorda("ambata", 1) == 11.232)
check("ambo dentro una terzina: 250/3", abs(economia.vincita_lorda("terzina", 2) - 250 / 3) < 1e-9)
check("terno dentro una terzina: 4.500", economia.vincita_lorda("terzina", 3) == 4500)
check("un solo numero non paga un ambo", economia.vincita_lorda("ambo", 1) == 0)

finta = [{
    "chiave": "x", "metodo": "prova", "giorno": "2026-01-01", "ruote": ["NA", "MI"],
    "colpi": 9, "anche_tutte": False, "nota": None, "avviso": None,
    "sorti": [{"tipo": "ambo", "numeri": [37, 39], "stato": "vinta", "colpi_valutati": 3,
               "esiti": [{"giorno": "2026-01-08", "ruota": "NA", "colpo": 3,
                          "usciti": [37, 39], "a_tutte": False}]}],
}]
b = economia.bilancio(finta)["per_metodo"][0]
check("spesa = colpi giocati x ruote = 3 x 2 = 6", b["speso"] == 6.0, str(b["speso"]))
check("incasso = 250 meno l'8% = 230", b["incassato"] == 230.0, str(b["incassato"]))
check("saldo = 224", b["saldo"] == 224.0, str(b["saldo"]))
check("il campione scarso e' segnalato", b["campione_scarso"] is True)

finta[0]["sorti"][0]["esiti"][0]["a_tutte"] = True
b = economia.bilancio(finta)["per_metodo"][0]
check("il gioco a Tutte resta fuori dal saldo", b["incassato"] == 0.0, str(b["incassato"]))
check("ma viene contato a parte", b["incassato_a_tutte"] == 230.0)

print("\nPUBBLICAZIONE")
rarita = pubblica.rarita(previsioni, arch)
check("misura la frequenza di ogni metodo", all("per_anno" in v for v in rarita.values()),
      str(rarita))
prossime = pubblica.prossime_estrazioni(arch)
check("propone delle date", len(prossime["date"]) >= 1, str(prossime))
check("le date proposte sono nel futuro",
      all(d >= date.today().isoformat() for d in prossime["date"]), str(prossime["date"]))
check("se sono proiettate lo dichiara",
      (not prossime["stimato"]) or bool(prossime["motivo"]))

# Il caso che ci ha fregato in produzione: la fonte risponde ma non ha date
# future, perche' l'endpoint elenca i concorsi GIA' AVVENUTI. In sviluppo non si
# vedeva, perche' con l'archivio vecchio le date "gia' avvenute" erano comunque
# nel futuro rispetto all'ultimo concorso caricato.
vera = pubblica.fonte.calendario
try:
    pubblica.fonte.calendario = lambda da, mesi=3: []
    muta = pubblica.prossime_estrazioni(arch)
    check("fonte senza date future: le proietta comunque",
          len(muta["date"]) >= 1, str(muta))
    check("e dichiara che sono proiettate", muta["stimato"] is True)
    check("spiegando perche'", "gia' avvenuti" in (muta["motivo"] or ""), str(muta["motivo"]))

    def esplode(da, mesi=3):
        raise pubblica.fonte.FonteNonDisponibile("prova")
    pubblica.fonte.calendario = esplode
    giu = pubblica.prossime_estrazioni(arch)
    check("fonte irraggiungibile: le proietta comunque", len(giu["date"]) >= 1, str(giu))
    check("e lo dice", "non raggiungibile" in (giu["motivo"] or ""), str(giu["motivo"]))
finally:
    pubblica.fonte.calendario = vera

dati = RADICE / "docs" / "dati"
attesi = {"stato.json", "in-corso.json", "bilancio.json", "calendario.json",
          "ultime-estrazioni.json", "quote.json"}
presenti = {f.name for f in dati.glob("*.json")}
check("il sito ha tutti i file che si aspetta", attesi <= presenti,
      str(sorted(attesi - presenti)))
for nome in sorted(presenti):
    try:
        json.loads((dati / nome).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        check(f"{nome} e' JSON valido", False, str(e))

in_corso = json.loads((dati / "in-corso.json").read_text(encoding="utf-8"))
frequenze = [p["per_anno"] for p in in_corso if p.get("per_anno")]
check("le previsioni in corso sono ordinate dal metodo piu' raro al piu' comune",
      frequenze == sorted(frequenze), str(frequenze[:8]))
check("tutte hanno almeno un colpo residuo",
      all(p["colpi_residui"] > 0 for p in in_corso))

quote_sito = json.loads((dati / "quote.json").read_text(encoding="utf-8"))
check("le quote pubblicate sono quelle che usa il motore",
      quote_sito["moltiplicatori"]["ambo"] == economia.MOLTIPLICATORI["ambo"]
      and quote_sito["ritenuta"] == economia.RITENUTA)

# ------------------------------------------------- il timbro sulla pagina
# I moduli JS si importano per nome relativo e il browser li tiene in cache; i
# dati invece portano una marca temporale e si riscaricano sempre. Senza timbro
# si finisce a leggere dati nuovi con codice vecchio - e' successo sul serio, e
# da fuori sembra che la modifica non sia mai stata fatta.
import re                                                      # noqa: E402

pagina = (RADICE / "docs" / "index.html").read_text(encoding="utf-8")
v = pubblica.impronta()
check("l'impronta e' otto caratteri esadecimali",
      re.fullmatch(r"[0-9a-f]{8}", v) is not None, v)
check("il foglio di stile e' timbrato", f'href="stile.css?v={v}"' in pagina)
check("il modulo d'avvio e' timbrato", f'src="app.js?v={v}"' in pagina)

mappa = json.loads(re.search(r'<script type="importmap">(.*?)</script>',
                             pagina, re.S).group(1))["imports"]
check("la mappa timbra tutti i moduli tranne quello d'avvio",
      set(mappa) == {f"./{m}" for m in pubblica.MODULI if m != "app.js"},
      str(sorted(mappa)))
check("e li timbra con l'impronta corrente",
      all(dest.endswith(f"?v={v}") for dest in mappa.values()))

# La prova che conta: un modulo nuovo, importato ma dimenticato in MODULI,
# resterebbe in cache per sempre senza che nessuno se ne accorga.
importati = set()
for f in (RADICE / "docs").glob("*.js"):
    importati.update(re.findall(r"from\s+'\./([\w.-]+\.js)'", f.read_text(encoding="utf-8")))
check("ogni modulo importato da qualcuno e' nell'elenco da timbrare",
      importati <= set(pubblica.MODULI),
      f"manca: {sorted(importati - set(pubblica.MODULI))}")
check("e non si timbrano moduli che non esistono",
      all((RADICE / "docs" / m).is_file() for m in pubblica.MODULI))

prima = pagina
pubblica.timbra_pagina()
check("timbrare due volte non cambia la pagina",
      (RADICE / "docs" / "index.html").read_text(encoding="utf-8") == prima)

with tempfile.TemporaryDirectory() as tmp:
    finta = Path(tmp) / "app.js"
    finta.write_text("// niente\n", encoding="utf-8")
    originale = pubblica.SITO
    try:
        pubblica.SITO = Path(tmp)
        for nome in pubblica.MODULI[1:] + ["stile.css"]:
            (Path(tmp) / nome).write_text("// niente\n", encoding="utf-8")
        uno = pubblica.impronta()
        finta.write_text("// cambiato\n", encoding="utf-8")
        due = pubblica.impronta()
    finally:
        pubblica.SITO = originale
    check("cambiare un file cambia l'impronta", uno != due, f"{uno} {due}")

# ---------------------------------------------------------- i dieci colpi
# Il pavimento vale sulle previsioni nuove, ma in archivio ce ne sono migliaia
# rilevate quando valevano i colpi dei fascicoli: senza allinearle il sito
# mostrerebbe due regole diverse a seconda di quando una previsione e' nata.
from motore.rilevamento import COLPI_MINIMI                     # noqa: E402
from motore.valutazione import allinea_colpi                    # noqa: E402

nuove = rileva(arch, arch.date[-40])
check("nessuna previsione nuova nasce sotto i dieci colpi",
      all(p["colpi"] >= COLPI_MINIMI for p in nuove),
      str(sorted({p["colpi"] for p in nuove})))
check("i metodi che il fascicolo manda oltre i dieci colpi non vengono accorciati",
      all(p["colpi"] >= 12 for p in rileva(arch, arch.date[-40])
          if p["metodo"] in ("fulmine", "lottofacile4")))

vecchie = [{
    "chiave": "x", "metodo": "ambosecco_caotico", "giorno": arch.date[-30].isoformat(),
    "ruote": ["NA", "BA"], "colpi": 2, "anche_tutte": False, "nota": None,
    "avviso": None,
    "sorti": [
        {"tipo": "ambo", "numeri": [7, 23], "stato": "scaduta",
         "colpi_valutati": 2, "esiti": []},
        {"tipo": "ambo", "numeri": [8, 24], "stato": "vinta",
         "colpi_valutati": 1, "esiti": [{"giorno": "2026-01-01", "ruota": "NA",
                                         "colpo": 1, "usciti": [8, 24],
                                         "a_tutte": False}]},
    ],
}, {
    "chiave": "y", "metodo": "lottofacile4", "giorno": arch.date[-30].isoformat(),
    "ruote": ["MI"], "colpi": 14, "anche_tutte": False, "nota": None, "avviso": None,
    "sorti": [{"tipo": "ambo", "numeri": [1, 2], "stato": "scaduta",
               "colpi_valutati": 14, "esiti": []}],
}]
allungate, riaperte = allinea_colpi(vecchie, COLPI_MINIMI)
check("le previsioni sotto il pavimento vengono allungate",
      allungate == 1 and vecchie[0]["colpi"] == COLPI_MINIMI, str(allungate))
check("quelle gia' sopra restano come sono", vecchie[1]["colpi"] == 14)
check("una sorte scaduta con colpi da giocare torna aperta",
      vecchie[0]["sorti"][0]["stato"] == "aperta" and riaperte == 1)
check("una sorte vinta resta vinta: si era sospesa",
      vecchie[0]["sorti"][1]["stato"] == "vinta")
check("i colpi gia' valutati non si perdono",
      vecchie[0]["sorti"][0]["colpi_valutati"] == 2)
check("rilanciarlo non cambia piu' niente: e' idempotente",
      allinea_colpi(vecchie, COLPI_MINIMI) == (0, 0))

# --------------------------------------------------------------- riferimento
# La pagina rifa' in JavaScript il controllo delle uscite (docs/storico.js), e
# due implementazioni della stessa regola divergono sempre, prima o poi. Qui si
# scrive quello che ha calcolato Python su un campione di previsioni vere;
# prove/test_storico.mjs lo rilegge e pretende di ottenere lo stesso. Se un
# giorno le due si allontanano, la prova diventa rossa invece di lasciare che la
# pagina racconti una storia e il bilancio un'altra.
from motore import storia                                      # noqa: E402

CAMPIONE = 300
riferimento = []
giorni_utili = [d for d in arch.date if d >= arch.date[-400]]
viste = 0
for giorno in giorni_utili:
    for prev in rileva(arch, giorno):
        if viste >= CAMPIONE:
            break
        viste += 1
        copia = json.loads(json.dumps(prev))
        valuta([copia], arch)
        riferimento.append({
            "previsione": storia._riga(prev),
            "sorti": [{"tipo": s["tipo"], "numeri": s["numeri"], "stato": s["stato"],
                       "esiti": s["esiti"]} for s in copia["sorti"]],
        })
    if viste >= CAMPIONE:
        break

fixture = RADICE / "prove" / "dati" / "esiti-riferimento.json"
fixture.parent.mkdir(parents=True, exist_ok=True)
fixture.write_text(json.dumps(riferimento, ensure_ascii=False, indent=1,
                              sort_keys=True) + "\n", encoding="utf-8")
check("il riferimento per le prove JavaScript contiene qualcosa",
      len(riferimento) == CAMPIONE, str(len(riferimento)))
check("e almeno una sorte si e' verificata, se no non proverebbe niente",
      any(s["stato"] == "vinta" for r in riferimento for s in r["sorti"]))

# --------------------------------------------------------- previsioni per anno
with tempfile.TemporaryDirectory() as tmp:
    cartella = Path(tmp)
    anno = arch.ultima.year
    ind = storia.scrivi(arch, cartella, [anno])
    righe = [r for r in (cartella / f"{anno}.txt").read_text(encoding="utf-8")
             .split("\n") if r and not r.startswith("#")]
    check("il file dell'anno contiene le previsioni di quell'anno",
          len(righe) == ind["anni"][str(anno)] > 0, str(len(righe)))
    check("ogni riga ha otto campi", all(r.count("|") == 7 for r in righe))
    rilette = [storia.leggi_riga(r) for r in righe]
    attese = [p for g in arch.date if g.year == anno for p in rileva(arch, g)]
    check("rileggere una riga rida' la previsione di partenza",
          all(a["metodo"] == b["metodo"] and a["ruote"] == b["ruote"]
              and a["colpi"] == b["colpi"] and a["giorno"] == b["giorno"]
              and [s["numeri"] for s in a["sorti"]] == [s["numeri"] for s in b["sorti"]]
              for a, b in zip(rilette, attese)))
    check("l'indice elenca ogni anno dell'archivio",
          set(ind["anni"]) == {str(d.year) for d in arch.date})
    prima = (cartella / f"{anno}.txt").read_bytes()
    storia.scrivi(arch, cartella, [anno])
    check("riscrivere lo stesso anno da' un file identico byte per byte",
          (cartella / f"{anno}.txt").read_bytes() == prima)

    # L'indice si ricava dai file, non dall'indice di prima: se sparisce, i
    # conteggi degli altri anni non devono azzerarsi in silenzio.
    altro = arch.date[0].year
    storia.scrivi(arch, cartella, [altro])
    (cartella / "indice.json").unlink()
    rifatto = storia.scrivi(arch, cartella, [anno])
    check("senza indice i conteggi si rileggono dai file invece di azzerarsi",
          rifatto["anni"][str(altro)] > 0, str(rifatto["anni"][str(altro)]))
    check("e gli anni di cui non c'e' il file valgono zero, non spariscono",
          set(rifatto["anni"]) == {str(d.year) for d in arch.date}
          and rifatto["anni"][str(arch.date[0].year + 1)] == 0)

print(f"\n{'=' * 60}\nRISULTATO: {ok} OK, {fail} FAIL")
sys.exit(1 if fail else 0)
