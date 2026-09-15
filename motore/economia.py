"""
Bilancio economico: quanto sarebbe costato giocare le previsioni, quanto avrebbero reso.

Perche' questo modulo esiste. "Quota vincente 26,8%" e' il genere di numero che
i fascicoli usavano per impressionare: dice che qualcosa e' uscito, non se e'
convenuto. Un metodo che gioca cinque sorti su due ruote per quattordici colpi
spende 140 euro per previsione; se ne vince una da 250, quel 26,8% di
"successo" e' comunque una perdita. L'unico numero onesto e' il saldo.

Convenzioni, le stesse dei fascicoli:
  - un euro per sorte, per ruota, per colpo;
  - si sospende la sorte quando si verifica sulla ruota di gioco;
  - le sorti lunghe (terzina, quartina) si giocano per ambo e terno, quindi la
    posta si ripartisce sulle combinazioni: un ambo in terzina paga 250/3.

Il gioco "a Tutte" e' facoltativo nei fascicoli, quindi resta contato a parte:
entra nel saldo solo se lo si chiede.
"""
from __future__ import annotations

import json
from math import comb
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
QUOTE = json.loads((RADICE / "archivio" / "quote.json").read_text(encoding="utf-8"))
MOLTIPLICATORI = QUOTE["moltiplicatori"]
RITENUTA = QUOTE["ritenuta"]

NUMERI_PER_SORTE = {"ambata": 1, "ambo": 2, "terzina": 3, "quartina": 4}


def vincita_lorda(tipo: str, quanti_usciti: int) -> float:
    """Quanto paga una sorte con posta di 1 euro, dati i numeri usciti."""
    n = NUMERI_PER_SORTE[tipo]
    if tipo == "ambata":
        return MOLTIPLICATORI["estratto"] if quanti_usciti >= 1 else 0.0
    if tipo == "ambo":
        return MOLTIPLICATORI["ambo"] if quanti_usciti >= 2 else 0.0
    # sorti lunghe: la posta si ripartisce sulle combinazioni giocate
    if quanti_usciti >= 4 and n >= 4:
        return MOLTIPLICATORI["quaterna"] / comb(n, 4)
    if quanti_usciti >= 3:
        return MOLTIPLICATORI["terno"] / comb(n, 3)
    if quanti_usciti >= 2:
        return MOLTIPLICATORI["ambo"] / comb(n, 2)
    return 0.0


def bilancio(previsioni: list[dict], *, includi_tutte: bool = False) -> dict:
    acc: dict[str, dict] = {}
    for p in previsioni:
        v = acc.setdefault(p["metodo"], {
            "metodo": p["metodo"], "previsioni": 0, "sorti": 0, "vincite": 0,
            "speso": 0.0, "incassato": 0.0, "incassato_a_tutte": 0.0,
            "vinte": 0, "aperte": 0, "scadute": 0})
        v["previsioni"] += 1
        n_ruote = len(p["ruote"])
        for s in p["sorti"]:
            v["sorti"] += 1
            v[{"vinta": "vinte", "aperta": "aperte", "scaduta": "scadute"}[s["stato"]]] += 1
            # la spesa segue i colpi effettivamente giocati: una sorte vinta al
            # terzo colpo ha pagato tre colpi, non quattordici
            v["speso"] += s["colpi_valutati"] * n_ruote
            for e in s["esiti"]:
                netto = vincita_lorda(s["tipo"], len(e["usciti"])) * (1 - RITENUTA)
                if e["a_tutte"]:
                    v["incassato_a_tutte"] += netto
                    if includi_tutte:
                        v["incassato"] += netto
                        v["vincite"] += 1
                else:
                    v["incassato"] += netto
                    v["vincite"] += 1

    soglia = json.loads((RADICE / "archivio" / "backtest.json")
                        .read_text(encoding="utf-8"))["soglia_campione"]
    righe = []
    for v in sorted(acc.values(), key=lambda x: x["metodo"]):
        v["saldo"] = v["incassato"] - v["speso"]
        v["ritorno"] = v["incassato"] / v["speso"] if v["speso"] else None
        chiuse = v["vinte"] + v["scadute"]
        v["quota_vincente"] = v["vinte"] / chiuse if chiuse else None
        # Un saldo su poche previsioni non significa nulla: un solo terno ne
        # ribalta il segno. Il flag evita che un campione corto passi per risultato.
        v["campione_scarso"] = v["previsioni"] < soglia
        for c in ("speso", "incassato", "saldo", "incassato_a_tutte"):
            v[c] = round(v[c], 2)
        for c in ("ritorno", "quota_vincente"):
            v[c] = round(v[c], 4) if v[c] is not None else None
        righe.append(v)

    speso = sum(r["speso"] for r in righe)
    incassato = sum(r["incassato"] for r in righe)
    return {
        "per_metodo": righe,
        "totale": {
            "previsioni": sum(r["previsioni"] for r in righe),
            "speso": round(speso, 2),
            "incassato": round(incassato, 2),
            "saldo": round(incassato - speso, 2),
            "ritorno": round(incassato / speso, 4) if speso else None,
        },
    }
