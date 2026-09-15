"""
Carica l'archivio storico e, facoltativamente, rileva e valuta le previsioni.

    python scripts/carica_archivio.py
    python scripts/carica_archivio.py --csv ..\\docs\\archivio.csv
    python scripts/carica_archivio.py --rileva-da 2026-01-01 --valuta
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import impostazioni            # noqa: E402
from app.db import (DatabaseNonRaggiungibile, MigrazioniNonApplicate,  # noqa: E402
                    SessionLocale, verifica_schema)
from app.services import importer, rilevatore, valutatore  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Carica l'archivio del Lotto")
    ap.add_argument("--csv", type=Path, default=impostazioni.archivio_csv)
    ap.add_argument("--rileva-da", type=date.fromisoformat, metavar="AAAA-MM-GG",
                    help="genera le previsioni dai concorsi a partire da questa data")
    ap.add_argument("--valuta", action="store_true",
                    help="rivaluta le sorti aperte dopo il rilevamento")
    args = ap.parse_args()

    if not args.csv.is_file():
        print(f"Archivio non trovato: {args.csv}")
        print("Indicalo con --csv, oppure imposta ARCHIVIO_CSV nel file .env")
        return 1

    try:
        verifica_schema()
    except (DatabaseNonRaggiungibile, MigrazioniNonApplicate) as e:
        print(e)
        return 2

    with SessionLocale() as s:
        print(f"import di {args.csv}\n")
        r = importer.importa_csv(s, args.csv,
                                 includi_nazionale=impostazioni.includi_nazionale)
        print(r.riassunto())
        if not r.ordine_di_estrazione:
            print("\nATTENZIONE: i numeri di questo archivio risultano ordinati per")
            print("valore. I metodi che filtrano per isotopia non sono applicabili.")

        if args.rileva_da:
            giorni = importer.concorsi_completi(s, dal=args.rileva_da)
            print(f"\nrilevamento su {len(giorni)} concorsi completi "
                  f"dal {args.rileva_da}")
            totale = 0
            for i, g in enumerate(giorni, 1):
                totale += len(rilevatore.rileva(s, g))
                if i % 50 == 0 or i == len(giorni):
                    print(f"   {i}/{len(giorni)} concorsi, {totale} previsioni")

        if args.valuta:
            print("\nvalutazione delle sorti aperte")
            rv = valutatore.valuta_aperte(s)
            print(f"   esaminate {rv.sorti_esaminate}, nuovi esiti {rv.esiti_nuovi}, "
                  f"vinte {rv.sorti_vinte}, scadute {rv.sorti_scadute}")
            print("\nriepilogo per metodo:")
            for riga in valutatore.riepilogo_metodi(s):
                q = riga["quota_vincente"]
                quota = f"{q:.1%}" if q is not None else "n/d"
                print(f"   {riga['metodo']:<20} vinte {riga['vinte']:>6}  "
                      f"scadute {riga['scadute']:>6}  aperte {riga['aperte']:>5}  "
                      f"quota {quota}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
