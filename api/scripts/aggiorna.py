"""
Ciclo completo di aggiornamento, da console.

    scarica i concorsi mancanti -> rileva le previsioni -> valuta le sorti aperte

    python scripts/aggiorna.py
    python scripts/aggiorna.py --solo-scarica
    python scripts/aggiorna.py --fino-a 2026-09-11

Il lavoro vero sta in app/services/ciclo.py, perche' lo stesso ciclo lo esegue
anche il pianificatore interno dell'applicazione: qui restano solo gli argomenti
da riga di comando e il codice d'uscita.

Esce con 0 se e' andato a buon fine, 1 se la fonte non risponde, 2 se il
database non e' pronto, 3 se un altro aggiornamento e' gia' in corso.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import ciclo  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Aggiorna estrazioni, previsioni ed esiti")
    ap.add_argument("--fino-a", type=date.fromisoformat, metavar="AAAA-MM-GG",
                    help="ultima data da scaricare (default: oggi)")
    ap.add_argument("--solo-scarica", action="store_true",
                    help="scarica le estrazioni senza rilevare ne' valutare")
    args = ap.parse_args()

    esito = ciclo.esegui(fino_a=args.fino_a, solo_scarica=args.solo_scarica,
                         etichetta="console")
    if esito.codice == ciclo.GIA_IN_CORSO:
        print("\nUn aggiornamento e' gia' in corso (probabilmente dal pianificatore\n"
              "interno dell'applicazione). Non ne parte un secondo.\n")
    return esito.codice


if __name__ == "__main__":
    raise SystemExit(main())
