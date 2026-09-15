"""
La fonte ufficiale delle estrazioni.

Endpoint individuati ispezionando le chiamate di www.lotto-italia.it (il sito e'
una SPA che li usa per la propria pagina "estratti per ruota"):

  POST /gdl/estrazioni-e-vincite/calendario-estrazioni-del-lotto.json
       {"mese": 9, "anno": 2026}   ->  [1, 3, 4, 5, 8, 10, 11]
       i giorni del mese in cui si e' tenuto un concorso

  POST /gdl/estrazioni-e-vincite/estrazioni-del-lotto.json
       {"data": "20260911"}        ->  {"esito": "OK", "estrazione": [...]}

La data va passata come **stringa AAAAMMGG**: con un timestamp numerico
l'endpoint risponde "Errore nel recupero dell'estrazione" senza spiegare
perche', e ci si perde un'ora.

Il calendario viene letto prima delle estrazioni, cosi' si interrogano solo i
giorni in cui un concorso c'e' stato davvero invece di tentare tutte le date.
Non essendo un'API pubblica documentata puo' cambiare senza preavviso: per
questo il parser scarta in silenzio le voci malformate invece di fidarsi, e chi
chiama riceve i giorni falliti invece di un'eccezione a meta' lavoro.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from calendar import monthrange
from datetime import date

from .archivio import NAZIONALE, RUOTE

BASE = "https://www.lotto-italia.it/gdl/estrazioni-e-vincite"
INTESTAZIONI = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    # un User-Agent da browser: alcuni front-end rifiutano i client anonimi
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"),
}
AMMESSE = set(RUOTE) | {NAZIONALE}


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
    """I giorni del mese in cui si e' tenuto (o si terra') un concorso."""
    dati = _post("calendario-estrazioni-del-lotto.json", {"mese": mese, "anno": anno})
    if not isinstance(dati, list):
        raise FonteNonDisponibile(
            f"calendario {anno}-{mese:02d}: attesa una lista di giorni, "
            f"ricevuto {type(dati).__name__}")
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
        if sigla not in AMMESSE or not isinstance(numeri, list):
            continue
        if len(numeri) != 5 or not all(isinstance(n, int) and 1 <= n <= 90 for n in numeri):
            continue
        if len(set(numeri)) != 5:
            continue
        quadro[sigla] = numeri
    return quadro or None


def mese_dopo(d: date) -> date:
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def calendario(da: date, *, mesi: int = 3) -> list[date]:
    """I giorni di concorso a partire da una data, leggendo mese per mese."""
    trovati: list[date] = []
    cursore = date(da.year, da.month, 1)
    for _ in range(mesi):
        trovati += [g for g in giorni_di_concorso(cursore.year, cursore.month) if g >= da]
        cursore = mese_dopo(cursore)
    return sorted(trovati)
