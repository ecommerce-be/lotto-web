"""
Esegue gli scanner dei sei metodi su un concorso e persiste le previsioni.

Il motore (app/engine/core.py) resta puro: non conosce il database, lavora su
dizionari {ruota: [numeri]} e restituisce oggetti in memoria. Qui avviene la
sola traduzione verso le entita' persistenti.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from itertools import combinations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..engine import core
from ..models import (Estrazione, Metodo, Previsione, Ruota, Sorte, TipoSorte)

RUOTE = [r.value for r in Ruota.classiche()]


def quadro(sessione: Session, giorno: date) -> dict[str, list[int]]:
    """Il quadro estrattivo di un concorso: {sigla ruota: [5 numeri]}."""
    righe = sessione.scalars(
        select(Estrazione).where(Estrazione.data == giorno,
                                 Estrazione.ruota.in_(Ruota.classiche())))
    return {e.ruota.value: list(e.numeri) for e in righe}


def _ritardi(sessione: Session, giorno: date, finestra: int = 200):
    """Ritardo per (ruota, numero) alla data indicata, contato in concorsi."""
    date_prec = sessione.scalars(
        select(Estrazione.data).where(Estrazione.data <= giorno)
        .group_by(Estrazione.data).order_by(Estrazione.data.desc()).limit(finestra)).all()
    if not date_prec:
        return lambda r, x: 10 ** 6, set()
    date_prec = sorted(date_prec)
    righe = sessione.scalars(
        select(Estrazione).where(Estrazione.data.in_(date_prec))).all()
    per_data = defaultdict(dict)
    for e in righe:
        per_data[e.data][e.ruota.value] = list(e.numeri)

    ultima: dict[tuple[str, int], int] = {}
    for i, d in enumerate(date_prec):
        for r, nums in per_data[d].items():
            for x in nums:
                ultima[(r, x)] = i
    n = len(date_prec) - 1

    def ritardo(r: str, x: int) -> int:
        u = ultima.get((r, x))
        return 10 ** 6 if u is None else n - u

    # numeri usciti negli ultimi 6 concorsi, per ruota
    usciti6: dict[str, set[int]] = defaultdict(set)
    for d in date_prec[-6:]:
        for r, nums in per_data[d].items():
            usciti6[r].update(nums)
    return ritardo, usciti6


def _storico_ambate(sessione: Session, giorno: date, ruote: tuple[str, ...]) -> set[int]:
    """Numeri usciti sulle ruote indicate nelle 4 estrazioni precedenti."""
    date_prec = sessione.scalars(
        select(Estrazione.data).where(Estrazione.data < giorno)
        .group_by(Estrazione.data).order_by(Estrazione.data.desc()).limit(4)).all()
    if not date_prec:
        return set()
    righe = sessione.scalars(
        select(Estrazione).where(Estrazione.data.in_(date_prec),
                                 Estrazione.ruota.in_([Ruota(r) for r in ruote]))).all()
    return {x for e in righe for x in e.numeri}


def _sorti_da(p: core.Previsione) -> list[Sorte]:
    sorti = [Sorte(tipo=TipoSorte.AMBATA, numeri=[a]) for a in p.ambate]
    sorti += [Sorte(tipo=TipoSorte.AMBO, numeri=list(a)) for a in p.ambi]
    for L in p.lunghe:
        tipo = TipoSorte.TERZINA if len(L) == 3 else TipoSorte.QUARTINA
        sorti.append(Sorte(tipo=tipo, numeri=list(L)))
    return sorti


def rileva(sessione: Session, giorno: date, *, persisti: bool = True) -> list[Previsione]:
    """Esegue tutti gli scanner sul concorso e restituisce le previsioni."""
    estr = quadro(sessione, giorno)
    if len(estr) < len(RUOTE):
        return []                      # concorso incompleto: non si rileva

    grezze: list[core.Previsione] = []
    grezze += core.scan_ambosecco_caotico(str(giorno), estr)

    ritardo, usciti6 = _ritardi(sessione, giorno)
    for r in RUOTE:
        grezze += core.scan_lottofacile5(str(giorno), estr, r,
                                         ritardo_fn=ritardo,
                                         presenti_6=usciti6.get(r, set()))
    for ra, rb in combinations(RUOTE, 2):
        grezze += core.scan_lottofacile4(str(giorno), estr, ra, rb)
        grezze += core.scan_lottofacile1(str(giorno), estr, ra, rb)
        grezze += core.scan_fulmine(str(giorno), estr, ra, rb,
                                    storico_ambate=_storico_ambate(sessione, giorno, (ra, rb)))
        grezze += core.scan_unsoloambosecco(str(giorno), estr, ra, rb)

    fuori: list[Previsione] = []
    for g in grezze:
        nota, avviso = g.note, None
        if "[" in nota:
            nota, _, resto = nota.partition("[")
            avviso = resto.rstrip("]").strip() or None
        p = Previsione(
            metodo=Metodo(g.metodo),
            data_rilevamento=giorno,
            ruote=list(g.ruote),
            colpi=g.colpi,
            anche_tutte=g.tutte,
            nota=nota.strip() or None,
            avviso=avviso,
        )
        p.sorti = _sorti_da(g)
        fuori.append(p)

    if persisti and fuori:
        sessione.add_all(fuori)
        sessione.commit()
    return fuori
