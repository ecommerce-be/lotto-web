"""
Letture pensate per l'interfaccia, non per il motore.

Chi guarda l'app non vuole sapere quante sorti sono aperte in astratto: vuole
sapere **cosa e' ancora in gioco stasera** e **quanti colpi restano**. Il calcolo
dei colpi residui sta qui e non nel modello perche' dipende da quanti concorsi
si sono tenuti dopo il rilevamento, cioe' da un'informazione di calendario.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..models import Estrazione, Previsione, Sorte, StatoSorte


def _calendario_da(sessione: Session, dal: date) -> list[date]:
    return list(sessione.scalars(
        select(Estrazione.data).where(Estrazione.data > dal)
        .group_by(Estrazione.data).order_by(Estrazione.data)))


def previsioni_in_corso(sessione: Session, *, limite: int = 100) -> list[dict]:
    """Previsioni con almeno una sorte ancora giocabile, piu' recenti per prime."""
    ultima = sessione.scalar(select(func.max(Estrazione.data)))
    if ultima is None:
        return []

    q = (select(Previsione)
         .join(Sorte)
         .where(Sorte.stato == StatoSorte.APERTA)
         .options(selectinload(Previsione.sorti))
         .distinct()
         .order_by(Previsione.data_rilevamento.desc(), Previsione.id)
         .limit(limite))

    fuori = []
    for p in sessione.scalars(q):
        giocati = len(_calendario_da(sessione, p.data_rilevamento))
        sorti = []
        for s in p.sorti:
            if s.stato is not StatoSorte.APERTA:
                continue
            residui = max(0, p.colpi - max(s.colpi_valutati, min(giocati, p.colpi)))
            sorti.append({
                "tipo": s.tipo.value,
                "numeri": list(s.numeri),
                "colpi_giocati": s.colpi_valutati,
                "colpi_residui": residui,
            })
        if not sorti:
            continue
        fuori.append({
            "id": p.id,
            "metodo": p.metodo.value,
            "data_rilevamento": p.data_rilevamento,
            "ruote": list(p.ruote),
            "colpi": p.colpi,
            "anche_tutte": p.anche_tutte,
            "nota": p.nota,
            "avviso": p.avviso,
            "colpi_residui": max((s["colpi_residui"] for s in sorti), default=0),
            "sorti": sorti,
        })
    return fuori
