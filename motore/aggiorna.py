"""
Il ciclo completo, unico punto d'ingresso.

    scarica i concorsi nuovi -> rileva le previsioni -> valuta le sorti aperte
    -> riscrive i file che legge il sito

E' cio' che GitHub esegue ogni sera, e cio' che si lancia a mano quando serve.

    python -m motore.aggiorna
    python -m motore.aggiorna --senza-rete          # solo rileva, valuta, pubblica
    python -m motore.aggiorna --ricostruisci 2025-09-01
    python -m motore.aggiorna --fino-a 2026-09-11

Codici d'uscita: 0 tutto bene, 1 la fonte non risponde, 2 l'archivio non e'
leggibile. Servono a GitHub per distinguere "stasera il sito era giu'" da "il
repository e' rotto", che sono due problemi diversi.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

if __package__ in (None, ""):                      # lanciato come file, non come modulo
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motore import fonte, pubblica, stato, storia              # noqa: E402
from motore.archivio import Archivio, ArchivioNonTrovato       # noqa: E402
from motore.rilevamento import rileva                          # noqa: E402
from motore.valutazione import valuta                          # noqa: E402

RADICE = Path(__file__).resolve().parent.parent
ESTRAZIONI = RADICE / "archivio" / "estrazioni.csv"
PREVISIONI = RADICE / "archivio" / "previsioni.jsonl"
CARTELLA_STORIA = RADICE / "docs" / "dati" / "previsioni"
MAX_CONCORSI = 200        # un tetto: se l'archivio e' fermo da anni non si scarica mezzo secolo


def scarica_mancanti(arch: Archivio, fino_a: date | None) -> tuple[list[date], list[str]]:
    """Aggiunge all'archivio i concorsi fra l'ultimo presente e oggi."""
    if arch.ultima is None:
        raise fonte.FonteNonDisponibile(
            "Archivio vuoto: la fonte ufficiale copre solo le estrazioni recenti, "
            "non lo storico dal 1939. Il file archivio/estrazioni.csv e' versionato "
            "nel repository: se manca, il repository non e' completo.")
    fino_a = fino_a or date.today()
    da = arch.ultima
    if da >= fino_a:
        return [], []

    attesi = [g for g in fonte.calendario(da, mesi=4) if da < g <= fino_a][:MAX_CONCORSI]
    nuovi, falliti = [], []
    for giorno in attesi:
        try:
            quadro = fonte.scarica(giorno)
        except fonte.FonteNonDisponibile as e:
            falliti.append(f"{giorno}: {e}")
            continue
        if not quadro:
            falliti.append(f"{giorno}: la fonte non ha l'estrazione")
            continue
        arch.aggiungi(giorno, quadro)
        nuovi.append(giorno)
    return nuovi, falliti


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Aggiorna estrazioni, previsioni e sito")
    ap.add_argument("--senza-rete", action="store_true",
                    help="non contatta la fonte: rileva, valuta e pubblica soltanto")
    ap.add_argument("--fino-a", type=date.fromisoformat, metavar="AAAA-MM-GG",
                    help="ultima data da scaricare (default: oggi)")
    ap.add_argument("--ricostruisci", type=date.fromisoformat, metavar="AAAA-MM-GG",
                    help="rileva da capo su tutti i concorsi a partire da questa data")
    ap.add_argument("--tutti-gli-anni", action="store_true",
                    help="riscrive le previsioni storiche di ogni anno (un paio di minuti)")
    args = ap.parse_args(argv)

    avvio = datetime.now()
    print(f"=== {avvio:%Y-%m-%d %H:%M:%S} - aggiornamento ===")

    try:
        arch = Archivio.carica(ESTRAZIONI)
    except ArchivioNonTrovato as e:
        print(e)
        return 2
    print(f"archivio            {len(arch.date)} concorsi, ultimo {arch.ultima}")

    nuovi: list[date] = []
    if not args.senza_rete:
        try:
            nuovi, falliti = scarica_mancanti(arch, args.fino_a)
        except fonte.FonteNonDisponibile as e:
            print(f"\nFonte non disponibile: {e}\n"
                  "Il sito resta con i dati di ieri invece di restare senza dati.")
            return 1
        print(f"concorsi scaricati  {len(nuovi)}"
              + (f"  ({nuovi[0]} -> {nuovi[-1]})" if nuovi else ""))
        for g in falliti:
            print(f"   non scaricato: {g}")
        if nuovi:
            arch.salva(ESTRAZIONI)

    previsioni = stato.carica(PREVISIONI)
    da_rilevare = list(nuovi)
    if args.ricostruisci:
        # il rilevamento e' deterministico e le chiavi sono stabili: ripassare su
        # giorni gia' visti non crea doppioni, aggiunge solo cio' che mancava
        da_rilevare = [d for d in arch.date if d >= args.ricostruisci]
        print(f"ricostruzione su    {len(da_rilevare)} concorsi dal {args.ricostruisci}")

    aggiunte = 0
    for giorno in da_rilevare:
        if not arch.completo(giorno):
            continue
        previsioni, n = stato.unisci(previsioni, rileva(arch, giorno))
        aggiunte += n
    print(f"previsioni nuove    {aggiunte}  (in archivio {len(previsioni)})")

    rap = valuta(previsioni, arch)
    print(f"valutazione         esaminate {rap.sorti_esaminate}, "
          f"nuovi esiti {rap.esiti_nuovi}, vinte {rap.sorti_vinte}, "
          f"scadute {rap.sorti_scadute}")
    stato.salva(PREVISIONI, previsioni)

    scritti = pubblica.tutto(arch, previsioni, aggiornato_il=avvio)
    print(f"sito aggiornato     {', '.join(scritti)}")

    # Le previsioni storiche stanno in un file per anno. Rifarli tutti sono due
    # minuti; ogni sera cambia solo l'anno dell'ultimo concorso, e nei primi
    # giorni di gennaio anche quello prima, perche' un concorso del 31 dicembre
    # scaricato in ritardo finisce nel file dell'anno vecchio.
    anni = sorted({d.year for d in (nuovi or arch.date[-1:])}
                  | {d.year for d in da_rilevare})
    if args.tutti_gli_anni:
        anni = None
    ind = storia.scrivi(arch, CARTELLA_STORIA, anni)
    quali = "tutti" if anni is None else " ".join(map(str, anni))
    print(f"previsioni storiche {ind['previsioni']} in totale (riscritti: {quali})")
    print(f"esito: OK  (durata {(datetime.now()-avvio).total_seconds():.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
