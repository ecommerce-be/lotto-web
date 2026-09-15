"""
Aggiornamento delle estrazioni dalla fonte ufficiale.

Endpoint individuati ispezionando le chiamate di www.lotto-italia.it (il sito
e' una SPA che li usa per la propria pagina "estratti per ruota"):

  POST /gdl/estrazioni-e-vincite/calendario-estrazioni-del-lotto.json
       body {"mese": 9, "anno": 2026}      ->  [1, 3, 4, 5, 8, 10, 11]
       i giorni del mese in cui si e' tenuto un concorso

  POST /gdl/estrazioni-e-vincite/estrazioni-del-lotto.json
       body {"data": "20260911"}           ->  {"esito": "OK", "data": <ms>,
                                                "estrazione": [{"ruota": "BA",
                                                "numeri": [53,20,40,62,16]}, ...]}

Il formato della data e' una **stringa AAAAMMGG**: con un timestamp numerico
l'endpoint risponde "Errore nel recupero dell'estrazione", il che costa un'ora
di tentativi se non si sa gia'.

Verificato che la fonte concordi con l'archivio storico: il 20/06/2026 restituisce
per Bari 90-24-74-14-75, identico al CSV di Ratio 90, ordine compreso.

Non essendo un'API pubblica documentata, puo' cambiare senza preavviso: per
questo il parser e' difensivo e `aggiorna()` riporta ogni giorno fallito invece
di interrompersi.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..models import Estrazione, Ruota

BASE = "https://www.lotto-italia.it/gdl/estrazioni-e-vincite"
INTESTAZIONI = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    # un User-Agent da browser: alcuni front-end rifiutano i client anonimi
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"),
}


class FonteNonDisponibile(RuntimeError):
    """La fonte non risponde o ha cambiato formato."""


def _post(percorso: str, corpo: dict, *, timeout: float = 20.0):
    richiesta = urllib.request.Request(
        f"{BASE}/{percorso}", method="POST",
        data=json.dumps(corpo).encode("utf-8"), headers=INTESTAZIONI)
    try:
        with urllib.request.urlopen(richiesta, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise FonteNonDisponibile(
            f"{BASE}/{percorso} non raggiungibile: {getattr(e, 'reason', e)}") from None
    except json.JSONDecodeError:
        raise FonteNonDisponibile(
            f"{BASE}/{percorso} ha risposto qualcosa che non e' JSON: "
            "probabilmente il sito e' cambiato") from None


def giorni_di_concorso(anno: int, mese: int) -> list[date]:
    """I giorni del mese in cui si e' tenuto un concorso, secondo la fonte."""
    dati = _post("calendario-estrazioni-del-lotto.json", {"mese": mese, "anno": anno})
    if not isinstance(dati, list):
        raise FonteNonDisponibile(
            f"calendario {anno}-{mese:02d}: attesa una lista di giorni, ricevuto "
            f"{type(dati).__name__}")
    ultimo = monthrange(anno, mese)[1]
    return [date(anno, mese, g) for g in dati if isinstance(g, int) and 1 <= g <= ultimo]


def scarica(giorno: date) -> dict[str, list[int]] | None:
    """Il quadro estrattivo di un concorso, o None se la fonte non ce l'ha."""
    dati = _post("estrazioni-del-lotto.json", {"data": giorno.strftime("%Y%m%d")})
    if not isinstance(dati, dict) or dati.get("esito") != "OK":
        return None
    quadro: dict[str, list[int]] = {}
    for voce in dati.get("estrazione") or []:
        sigla = str(voce.get("ruota", "")).upper()
        numeri = voce.get("numeri")
        if sigla not in Ruota.__members__ or not isinstance(numeri, list):
            continue
        if len(numeri) != 5 or not all(isinstance(n, int) and 1 <= n <= 90 for n in numeri):
            continue
        if len(set(numeri)) != 5:
            continue
        quadro[sigla] = numeri
    return quadro or None


@dataclass
class RapportoAggiornamento:
    dal: date | None = None
    al: date | None = None
    concorsi_attesi: int = 0
    concorsi_scaricati: int = 0
    righe_scritte: int = 0
    giorni_falliti: list[str] = field(default_factory=list)
    nuove_date: list[date] = field(default_factory=list)

    def come_dizionario(self) -> dict:
        return {
            "dal": self.dal, "al": self.al,
            "concorsi_attesi": self.concorsi_attesi,
            "concorsi_scaricati": self.concorsi_scaricati,
            "righe_scritte": self.righe_scritte,
            "giorni_falliti": self.giorni_falliti,
            "nuove_date": [d.isoformat() for d in self.nuove_date],
        }


def aggiorna(sessione: Session, *, fino_a: date | None = None,
             includi_nazionale: bool = False,
             max_concorsi: int = 200) -> RapportoAggiornamento:
    """
    Scarica i concorsi mancanti fra l'ultima estrazione in archivio e oggi.

    Non chiede alla fonte giorno per giorno alla cieca: prima legge il calendario
    del mese, cosi' interroga solo le date in cui un concorso c'e' stato davvero.
    """
    rap = RapportoAggiornamento()
    ultima = sessione.scalar(select(func.max(Estrazione.data)))
    if ultima is None:
        raise FonteNonDisponibile(
            "Archivio vuoto: caricare prima lo storico con carica_archivio.py. "
            "Questa fonte copre solo le estrazioni recenti, non dal 1939.")

    fino_a = fino_a or date.today()
    rap.dal, rap.al = ultima + timedelta(days=1), fino_a
    if rap.dal > fino_a:
        return rap

    # calendario mese per mese, dalla prima data mancante a oggi
    da_scaricare: list[date] = []
    cursore = date(rap.dal.year, rap.dal.month, 1)
    while cursore <= fino_a:
        for g in giorni_di_concorso(cursore.year, cursore.month):
            if rap.dal <= g <= fino_a:
                da_scaricare.append(g)
        cursore = date(cursore.year + (cursore.month == 12),
                       cursore.month % 12 + 1, 1)

    da_scaricare = sorted(da_scaricare)[:max_concorsi]
    rap.concorsi_attesi = len(da_scaricare)
    ammesse = {r.value for r in (Ruota if includi_nazionale else Ruota.classiche())}

    for giorno in da_scaricare:
        try:
            quadro = scarica(giorno)
        except FonteNonDisponibile as e:
            rap.giorni_falliti.append(f"{giorno}: {e}")
            continue
        if not quadro:
            rap.giorni_falliti.append(f"{giorno}: la fonte non ha l'estrazione")
            continue
        righe = [{"data": giorno, "ruota": Ruota(s), "numeri": n}
                 for s, n in quadro.items() if s in ammesse]
        if not righe:
            rap.giorni_falliti.append(f"{giorno}: nessuna ruota utilizzabile")
            continue
        stmt = insert(Estrazione).values(righe)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_estrazione_data_ruota", set_={"numeri": stmt.excluded.numeri})
        sessione.execute(stmt)
        sessione.commit()
        rap.concorsi_scaricati += 1
        rap.righe_scritte += len(righe)
        rap.nuove_date.append(giorno)

    return rap
