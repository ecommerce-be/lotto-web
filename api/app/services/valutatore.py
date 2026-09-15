"""
Rivaluta le sorti aperte sui concorsi successivi al rilevamento.

E' la parte che permette all'app di dire la verita': ogni sorte sa quanti colpi
ha gia' consumato, quando e dove si e' verificata, e quando e' scaduta.
`colpi_valutati` rende l'operazione idempotente — si puo' rilanciare quante
volte si vuole senza contare due volte lo stesso colpo.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (Esito, Estrazione, Previsione, Ruota, Sorte, StatoSorte,
                      TipoSorte)

MINIMO_PER_ESITO = {TipoSorte.AMBATA: 1, TipoSorte.AMBO: 2,
                    TipoSorte.TERZINA: 2, TipoSorte.QUARTINA: 2}


@dataclass
class RapportoValutazione:
    sorti_esaminate: int = 0
    esiti_nuovi: int = 0
    sorti_vinte: int = 0
    sorti_scadute: int = 0


def _calendario(sessione: Session, dal: date) -> list[date]:
    return list(sessione.scalars(
        select(Estrazione.data).where(Estrazione.data > dal)
        .group_by(Estrazione.data).order_by(Estrazione.data)))


def _quadri(sessione: Session, giorni: list[date]) -> dict[date, dict[str, set[int]]]:
    if not giorni:
        return {}
    righe = sessione.scalars(
        select(Estrazione).where(Estrazione.data.in_(giorni),
                                 Estrazione.ruota.in_(Ruota.classiche()))).all()
    fuori: dict[date, dict[str, set[int]]] = {}
    for e in righe:
        fuori.setdefault(e.data, {})[e.ruota.value] = set(e.numeri)
    return fuori


def valuta_aperte(sessione: Session, *, limite: int | None = None) -> RapportoValutazione:
    """Porta avanti tutte le sorti ancora aperte fino all'ultimo concorso noto."""
    rap = RapportoValutazione()
    q = (select(Sorte).join(Previsione)
         .where(Sorte.stato == StatoSorte.APERTA)
         .order_by(Previsione.data_rilevamento))
    if limite:
        q = q.limit(limite)
    sorti = list(sessione.scalars(q))
    if not sorti:
        return rap

    prima = min(s.previsione.data_rilevamento for s in sorti)
    calendario = _calendario(sessione, prima)
    quadri = _quadri(sessione, calendario)
    indice = {d: i for i, d in enumerate(calendario)}

    for s in sorti:
        rap.sorti_esaminate += 1
        p = s.previsione
        successivi = [d for d in calendario if d > p.data_rilevamento]
        base = indice[successivi[0]] if successivi else None
        if base is None:
            continue
        numeri = set(s.numeri)
        minimo = MINIMO_PER_ESITO[s.tipo]
        ruote_gioco = set(p.ruote)
        ruote_tutte = {r.value for r in Ruota.classiche()} if p.anche_tutte else set()

        for colpo in range(s.colpi_valutati + 1, p.colpi + 1):
            pos = base + colpo - 1
            if pos >= len(calendario):
                break                      # colpo non ancora giocato: si riprendera'
            giorno = calendario[pos]
            s.colpi_valutati = colpo
            for ruota, usciti in quadri.get(giorno, {}).items():
                if ruota not in ruote_gioco and ruota not in ruote_tutte:
                    continue
                presi = sorted(numeri & usciti)
                if len(presi) < minimo:
                    continue
                sessione.add(Esito(
                    sorte_id=s.id, data=giorno, ruota=Ruota(ruota), colpo=colpo,
                    numeri_usciti=presi, a_tutte=ruota not in ruote_gioco))
                rap.esiti_nuovi += 1
                if s.stato is StatoSorte.APERTA and ruota in ruote_gioco:
                    s.stato = StatoSorte.VINTA      # si sospende, come da fascicoli
                    rap.sorti_vinte += 1
            if s.stato is StatoSorte.VINTA:
                break
        else:
            if s.colpi_valutati >= p.colpi and s.stato is StatoSorte.APERTA:
                s.stato = StatoSorte.SCADUTA
                rap.sorti_scadute += 1

    sessione.commit()
    return rap


def riepilogo_metodi(sessione: Session) -> list[dict]:
    """Quante previsioni per metodo e quante sorti vinte, aperte, scadute."""
    q = (select(Previsione.metodo, Sorte.stato, func.count())
         .join(Sorte, Sorte.previsione_id == Previsione.id)
         .group_by(Previsione.metodo, Sorte.stato))
    acc: dict[str, dict] = {}
    for metodo, stato, n in sessione.execute(q):
        v = acc.setdefault(metodo.value, {"metodo": metodo.value,
                                          "vinte": 0, "aperte": 0, "scadute": 0})
        v[{StatoSorte.VINTA: "vinte", StatoSorte.APERTA: "aperte",
           StatoSorte.SCADUTA: "scadute"}[stato]] = n
    for v in acc.values():
        chiuse = v["vinte"] + v["scadute"]
        v["quota_vincente"] = round(v["vinte"] / chiuse, 4) if chiuse else None
    return sorted(acc.values(), key=lambda x: x["metodo"])
