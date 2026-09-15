"""
Quand'e' la prossima estrazione.

Sembra una domanda banale e non lo e': i giorni di concorso sono cambiati piu'
volte nella storia del Lotto - tre alla settimana per decenni, poi quattro, poi
cinque - e continuano a saltare per le feste. Dedurli dal giorno della settimana
vuol dire sbagliare a Ferragosto e a Natale.

Per questo la risposta arriva dal calendario ufficiale, lo stesso endpoint che
usa l'aggiornatore. Se la fonte non risponde si ripiega su una stima ricavata
dai giorni della settimana visti in archivio negli ultimi mesi - ed e'
dichiarata come stima, perche' una data sbagliata presentata con sicurezza e'
peggio di un "non lo so".
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Estrazione
from .aggiornatore import FonteNonDisponibile, giorni_di_concorso

ORA_ESTRAZIONE = time(20, 0)
VALIDITA_CACHE = timedelta(hours=6)
FINESTRA_STIMA = 120          # giorni di archivio da cui dedurre i giorni di concorso

_cache: dict = {"calcolata": None, "primo_giorno_utile": None, "valore": None}


def _primo_giorno_utile(adesso: datetime | None = None) -> date:
    """Oggi se l'estrazione deve ancora tenersi, domani se e' gia' passata."""
    adesso = adesso or datetime.now()
    return adesso.date() if adesso.time() < ORA_ESTRAZIONE \
        else adesso.date() + timedelta(days=1)


def _mese_dopo(d: date) -> date:
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def _dalla_fonte(da: date, quante: int) -> list[date]:
    trovate: list[date] = []
    cursore = date(da.year, da.month, 1)
    # tre mesi bastano: anche la pausa piu' lunga del calendario non li supera
    for _ in range(3):
        for g in giorni_di_concorso(cursore.year, cursore.month):
            if g >= da:
                trovate.append(g)
        if len(trovate) >= quante:
            break
        cursore = _mese_dopo(cursore)
    return sorted(trovate)[:quante]


def _stimate(sessione: Session, da: date, quante: int) -> list[date]:
    """
    Ripiego: i giorni della settimana in cui si e' estratto di recente.

    Si richiede che un giorno compaia almeno tre volte nella finestra, cosi' un
    recupero straordinario in un giorno insolito non entra nella stima.
    """
    inizio = da - timedelta(days=FINESTRA_STIMA)
    giorni = sessione.scalars(
        select(Estrazione.data).where(Estrazione.data >= inizio)
        .group_by(Estrazione.data)).all()
    if not giorni:
        return []
    conteggio = Counter(g.weekday() for g in giorni)
    settimanali = {g for g, n in conteggio.items() if n >= 3}
    if not settimanali:
        return []
    fuori, cursore = [], da
    while len(fuori) < quante and (cursore - da).days < 30:
        if cursore.weekday() in settimanali:
            fuori.append(cursore)
        cursore += timedelta(days=1)
    return fuori


def prossime(sessione: Session, *, quante: int = 3,
             adesso: datetime | None = None) -> dict:
    """Le prossime date di concorso, dalla fonte ufficiale o stimate."""
    da = _primo_giorno_utile(adesso)
    ora = datetime.now()
    if (_cache["valore"] is not None
            and _cache["primo_giorno_utile"] == da
            and ora - _cache["calcolata"] < VALIDITA_CACHE
            and len(_cache["valore"]["date"]) >= quante):
        risposta = dict(_cache["valore"])
        risposta["date"] = risposta["date"][:quante]
        return risposta

    try:
        date_ = _dalla_fonte(da, max(quante, 5))
        stimato, motivo = False, None
    except FonteNonDisponibile as e:
        date_ = _stimate(sessione, da, max(quante, 5))
        stimato = True
        motivo = (f"Calendario ufficiale non raggiungibile ({e}); "
                  "date dedotte dai giorni di concorso recenti.")

    valore = {
        "date": date_,
        "stimato": stimato,
        "motivo": motivo,
        "ora": ORA_ESTRAZIONE.strftime("%H:%M"),
    }
    if date_:                                  # non si mette in cache un buco
        _cache.update(calcolata=ora, primo_giorno_utile=da, valore=valore)
    risposta = dict(valore)
    risposta["date"] = risposta["date"][:quante]
    return risposta


def svuota_cache() -> None:
    _cache.update(calcolata=None, primo_giorno_utile=None, valore=None)
