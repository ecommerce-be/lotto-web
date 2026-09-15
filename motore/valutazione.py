"""
Porta avanti le sorti aperte sui concorsi successivi al rilevamento.

E' la parte che permette all'app di dire la verita': ogni sorte sa quanti colpi
ha gia' consumato, quando e su quale ruota si e' verificata, e quando e'
scaduta senza esito. `colpi_valutati` rende l'operazione **idempotente**: si
puo' rilanciare quante volte si vuole senza contare due volte lo stesso colpo,
che e' esattamente cio' che serve a un processo che gira ogni sera e ogni tanto
viene rilanciato a mano.

Come da fascicoli, la sorte si **sospende** quando si verifica sulla ruota di
gioco: da li' in avanti non si gioca piu' e non si spende piu'.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .archivio import RUOTE, Archivio

# quanti numeri devono uscire perche' ci sia un esito. Una terzina si gioca per
# ambo (e terno): due numeri bastano.
MINIMO_PER_ESITO = {"ambata": 1, "ambo": 2, "terzina": 2, "quartina": 2}


@dataclass
class RapportoValutazione:
    sorti_esaminate: int = 0
    esiti_nuovi: int = 0
    sorti_vinte: int = 0
    sorti_scadute: int = 0


def valuta(previsioni: list[dict], arch: Archivio) -> RapportoValutazione:
    """Modifica le previsioni sul posto. Torna cosa e' cambiato."""
    rap = RapportoValutazione()
    quadri = {d: {r: set(n) for r, n in arch.quadro(d).items()} for d in arch.date}
    calendario = arch.date
    posizione = {d: i for i, d in enumerate(calendario)}

    for p in previsioni:
        aperte = [s for s in p["sorti"] if s["stato"] == "aperta"]
        if not aperte:
            continue
        rilevata = date.fromisoformat(p["giorno"])
        successivi = [d for d in calendario if d > rilevata]
        if not successivi:
            continue                       # nessun concorso dopo: niente da valutare
        base = posizione[successivi[0]]
        ruote_gioco = set(p["ruote"])
        ruote_tutte = set(RUOTE) if p["anche_tutte"] else set()

        for s in aperte:
            rap.sorti_esaminate += 1
            numeri = set(s["numeri"])
            minimo = MINIMO_PER_ESITO[s["tipo"]]

            for colpo in range(s["colpi_valutati"] + 1, p["colpi"] + 1):
                pos = base + colpo - 1
                if pos >= len(calendario):
                    break                  # colpo non ancora giocato: si riprendera'
                giorno = calendario[pos]
                s["colpi_valutati"] = colpo
                for ruota, usciti in quadri.get(giorno, {}).items():
                    if ruota not in ruote_gioco and ruota not in ruote_tutte:
                        continue
                    presi = sorted(numeri & usciti)
                    if len(presi) < minimo:
                        continue
                    s["esiti"].append({
                        "giorno": giorno.isoformat(), "ruota": ruota, "colpo": colpo,
                        "usciti": presi, "a_tutte": ruota not in ruote_gioco,
                    })
                    rap.esiti_nuovi += 1
                    if s["stato"] == "aperta" and ruota in ruote_gioco:
                        s["stato"] = "vinta"        # si sospende, come da fascicoli
                        rap.sorti_vinte += 1
                if s["stato"] == "vinta":
                    break
            else:
                if s["colpi_valutati"] >= p["colpi"] and s["stato"] == "aperta":
                    s["stato"] = "scaduta"
                    rap.sorti_scadute += 1
    return rap


def colpi_residui(p: dict, s: dict, arch: Archivio) -> int:
    """Quante estrazioni restano prima che questa sorte scada."""
    if s["stato"] != "aperta":
        return 0
    giocati = len(arch.date_dopo(date.fromisoformat(p["giorno"])))
    return max(0, p["colpi"] - max(s["colpi_valutati"], min(giocati, p["colpi"])))
