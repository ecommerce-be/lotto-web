"""
Esegue i sei metodi su un concorso e produce le previsioni.

Il motore (`motore/lotto.py`) resta puro: lavora su dizionari
{ruota: [numeri]} e non sa nulla di file, date o formati. Qui avviene la sola
traduzione verso la forma che viene salvata e pubblicata.

Ogni previsione ha una **chiave deterministica**, calcolata da metodo, giorno,
ruote e numeri. Non e' un vezzo: senza, rilanciare il rilevamento sullo stesso
concorso - cosa che succede ogni volta che si ricostruisce lo storico -
creerebbe duplicati silenziosi, e il bilancio comincerebbe a contare due volte
le stesse giocate.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import date
from itertools import combinations

from . import lotto
from .archivio import RUOTE, Archivio

FINESTRA_RITARDI = 200      # concorsi guardati indietro per calcolare i ritardi


def chiave(metodo: str, giorno: date, ruote, sorti) -> str:
    """Identita' di una previsione: gli stessi ingredienti danno la stessa chiave."""
    impronta = "|".join([
        metodo, giorno.isoformat(), ",".join(ruote),
        ";".join(f"{s['tipo']}:" + "-".join(map(str, s["numeri"])) for s in sorti),
    ])
    return hashlib.sha1(impronta.encode("utf-8")).hexdigest()[:12]


def _ritardi(arch: Archivio, giorno: date):
    """Ritardo di ogni (ruota, numero) alla data indicata, contato in concorsi."""
    precedenti = [d for d in arch.date if d <= giorno][-FINESTRA_RITARDI:]
    if not precedenti:
        return (lambda r, x: 10 ** 6), {}

    ultima: dict[tuple[str, int], int] = {}
    for i, d in enumerate(precedenti):
        for r, numeri in arch.quadro(d).items():
            for x in numeri:
                ultima[(r, x)] = i
    fine = len(precedenti) - 1

    def ritardo(r: str, x: int) -> int:
        u = ultima.get((r, x))
        return 10 ** 6 if u is None else fine - u

    usciti6: dict[str, set[int]] = defaultdict(set)
    for d in precedenti[-6:]:
        for r, numeri in arch.quadro(d).items():
            usciti6[r].update(numeri)
    return ritardo, usciti6


def _storico_ambate(arch: Archivio, giorno: date, ruote: tuple[str, ...]) -> set[int]:
    """Numeri usciti sulle ruote indicate nelle quattro estrazioni precedenti."""
    precedenti = [d for d in arch.date if d < giorno][-4:]
    return {x for d in precedenti for r, numeri in arch.quadro(d).items()
            if r in ruote for x in numeri}


def _sorti_da(p) -> list[dict]:
    sorti = [{"tipo": "ambata", "numeri": [a]} for a in p.ambate]
    sorti += [{"tipo": "ambo", "numeri": list(a)} for a in p.ambi]
    for lunga in p.lunghe:
        sorti.append({"tipo": "terzina" if len(lunga) == 3 else "quartina",
                      "numeri": list(lunga)})
    for s in sorti:
        s.update(stato="aperta", colpi_valutati=0, esiti=[])
    return sorti


def rileva(arch: Archivio, giorno: date) -> list[dict]:
    """Tutte le previsioni che i sei metodi producono su questo concorso."""
    estr = arch.quadro(giorno)
    if len(estr) < len(RUOTE):
        return []                      # concorso incompleto: non si rileva

    grezze = list(lotto.scan_ambosecco_caotico(str(giorno), estr))

    ritardo, usciti6 = _ritardi(arch, giorno)
    for r in RUOTE:
        grezze += lotto.scan_lottofacile5(str(giorno), estr, r, ritardo_fn=ritardo,
                                          presenti_6=usciti6.get(r, set()))
    for ra, rb in combinations(RUOTE, 2):
        grezze += lotto.scan_lottofacile4(str(giorno), estr, ra, rb)
        grezze += lotto.scan_lottofacile1(str(giorno), estr, ra, rb)
        grezze += lotto.scan_fulmine(str(giorno), estr, ra, rb,
                                     storico_ambate=_storico_ambate(arch, giorno, (ra, rb)))
        grezze += lotto.scan_unsoloambosecco(str(giorno), estr, ra, rb)

    fuori = []
    for g in grezze:
        # la nota del motore puo' contenere un avviso fra parentesi quadre:
        # va separato, perche' nell'interfaccia ha un peso diverso
        nota, avviso = g.note, None
        if "[" in nota:
            nota, _, resto = nota.partition("[")
            avviso = resto.rstrip("]").strip() or None
        sorti = _sorti_da(g)
        if not sorti:
            continue
        fuori.append({
            "chiave": chiave(g.metodo, giorno, g.ruote, sorti),
            "metodo": g.metodo,
            "giorno": giorno.isoformat(),
            "ruote": list(g.ruote),
            "colpi": g.colpi,
            "anche_tutte": bool(g.tutte),
            "nota": nota.strip() or None,
            "avviso": avviso,
            "sorti": sorti,
        })
    return fuori
