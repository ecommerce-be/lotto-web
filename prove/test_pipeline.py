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
check("se sono stimate lo dichiara",
      (not prossime["stimato"]) or bool(prossime["motivo"]))

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

print(f"\n{'=' * 60}\nRISULTATO: {ok} OK, {fail} FAIL")
sys.exit(1 if fail else 0)
