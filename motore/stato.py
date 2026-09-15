"""
Lo stato persistente: le previsioni, una per riga, in un file JSONL.

Perche' JSONL e non un JSON solo. Il file vive in un repository git e viene
riscritto ogni sera da un processo automatico: con un unico array JSON ogni
aggiornamento produrrebbe un diff illeggibile, mentre una riga per previsione
fa comparire nel diff esattamente cio' che e' cambiato - la previsione nuova, o
la sorte che e' passata da aperta a vinta. Le chiavi sono ordinate e le righe
pure, cosi' due esecuzioni sugli stessi dati producono lo stesso file byte per
byte e git non registra modifiche fantasma.
"""
from __future__ import annotations

import json
from pathlib import Path


def carica(percorso: Path) -> list[dict]:
    if not percorso.is_file():
        return []
    fuori = []
    for numero, riga in enumerate(percorso.read_text(encoding="utf-8").splitlines(), 1):
        riga = riga.strip()
        if not riga:
            continue
        try:
            fuori.append(json.loads(riga))
        except json.JSONDecodeError as e:
            raise ValueError(
                f"{percorso}: riga {numero} non e' JSON valido ({e}). "
                "Il file e' versionato: 'git checkout' lo riporta all'ultima "
                "versione buona.") from None
    return fuori


def salva(percorso: Path, previsioni: list[dict]) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    ordinate = sorted(previsioni, key=lambda p: (p["giorno"], p["metodo"], p["chiave"]))
    testo = "\n".join(json.dumps(p, ensure_ascii=False, sort_keys=True)
                      for p in ordinate)
    temporaneo = percorso.with_suffix(percorso.suffix + ".tmp")
    temporaneo.write_text(testo + "\n" if testo else "", encoding="utf-8")
    temporaneo.replace(percorso)


def unisci(esistenti: list[dict], nuove: list[dict]) -> tuple[list[dict], int]:
    """Aggiunge solo le previsioni mai viste. Torna l'elenco e quante ne ha aggiunte."""
    viste = {p["chiave"] for p in esistenti}
    aggiunte = [p for p in nuove if p["chiave"] not in viste]
    return esistenti + aggiunte, len(aggiunte)
