"""
Import dell'archivio storico da CSV, con validazione.

Formato atteso (quello di Ratio 90 / Overlab):
    2026-06-20;TO;Torino;61;34;65;59;27

La validazione non e' burocrazia: l'unico controllo che conta davvero e'
`ordine_di_estrazione`. Molti archivi in circolazione riordinano i cinque numeri
per valore. Se succede, i metodi che filtrano per isotopia continuano a girare
ma misurano qualcos'altro, senza che nulla segnali il problema.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..models import Estrazione, Ruota


@dataclass
class Rapporto:
    righe_lette: int = 0
    righe_valide: int = 0
    scritte: int = 0          # inserite o aggiornate (upsert)
    scartate: dict[str, int] = field(default_factory=dict)
    prima_data: date | None = None
    ultima_data: date | None = None
    quota_crescenti: float = 0.0
    ordine_di_estrazione: bool = True

    def scarta(self, motivo: str) -> None:
        self.scartate[motivo] = self.scartate.get(motivo, 0) + 1

    def riassunto(self) -> str:
        righe = [
            f"righe lette      {self.righe_lette}",
            f"righe valide     {self.righe_valide}",
            f"scritte          {self.scritte}",
            f"periodo          {self.prima_data} -> {self.ultima_data}",
            f"quota crescenti  {self.quota_crescenti:.2%}  (atteso dal caso 0.83%)",
            f"ordine estratti  {'ORDINE DI ESTRAZIONE' if self.ordine_di_estrazione else 'ORDINATI PER VALORE — isotopia inutilizzabile'}",
        ]
        if self.scartate:
            righe.append("scartate:")
            righe += [f"   {k}: {v}" for k, v in sorted(self.scartate.items())]
        return "\n".join(righe)


def importa_csv(sessione: Session, percorso: Path, *,
                includi_nazionale: bool = False,
                dimensione_lotto: int = 5000) -> Rapporto:
    r = Rapporto()
    ammesse = {x.value for x in (Ruota if includi_nazionale else Ruota.classiche())}
    buffer: list[dict] = []
    crescenti = 0

    def scarica() -> None:
        nonlocal buffer
        if not buffer:
            return
        stmt = insert(Estrazione).values(buffer)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_estrazione_data_ruota",
            set_={"numeri": stmt.excluded.numeri},
        )
        sessione.execute(stmt)
        r.scritte += len(buffer)
        sessione.commit()
        buffer = []

    with percorso.open(encoding="utf-8", errors="replace", newline="") as fh:
        for riga in csv.reader(fh, delimiter=";"):
            r.righe_lette += 1
            if len(riga) != 8:
                r.scarta("numero di colonne errato"); continue
            sigla = riga[1].strip().upper()
            if sigla not in ammesse:
                r.scarta(f"ruota esclusa ({sigla})"); continue
            try:
                giorno = date.fromisoformat(riga[0].strip())
                numeri = [int(x) for x in riga[3:8]]
            except ValueError:
                r.scarta("data o numeri non interpretabili"); continue
            if any(n < 1 or n > 90 for n in numeri):
                r.scarta("numero fuori 1-90"); continue
            if len(set(numeri)) != 5:
                r.scarta("numeri ripetuti nella stessa estrazione"); continue

            r.righe_valide += 1
            if numeri == sorted(numeri):
                crescenti += 1
            r.prima_data = giorno if r.prima_data is None else min(r.prima_data, giorno)
            r.ultima_data = giorno if r.ultima_data is None else max(r.ultima_data, giorno)
            buffer.append({"data": giorno, "ruota": Ruota(sigla), "numeri": numeri})
            if len(buffer) >= dimensione_lotto:
                scarica()
    scarica()

    if r.righe_valide:
        r.quota_crescenti = crescenti / r.righe_valide
        # con 5 numeri le permutazioni sono 120: se fossero in ordine di
        # estrazione ci si aspetta 1/120 = 0,83% di sequenze gia' crescenti.
        # Una quota molto piu' alta significa che l'archivio li ha riordinati.
        r.ordine_di_estrazione = r.quota_crescenti < 0.05
    return r


def concorsi_completi(sessione: Session, *, dal: date | None = None) -> list[date]:
    """Date in cui sono presenti tutte e dieci le ruote classiche."""
    q = select(Estrazione.data).where(
        Estrazione.ruota.in_(Ruota.classiche()))
    if dal:
        q = q.where(Estrazione.data >= dal)
    q = q.group_by(Estrazione.data).having(
        func.count() == len(Ruota.classiche())
    ).order_by(Estrazione.data)
    return list(sessione.scalars(q))
