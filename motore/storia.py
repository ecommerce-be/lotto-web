"""
Le previsioni di tutto l'archivio, pubblicate un anno per file.

Serve alla scheda Previsioni: si sceglie un concorso qualunque dal 1939 in poi e
si vuole sapere che cosa i sei metodi avrebbero rilevato quel giorno. Un sito
statico non puo' calcolarlo al volo, e le tre strade possibili non si
equivalgono:

  - rifare i sei metodi in JavaScript significa avere due implementazioni della
    stessa cosa. Prima o poi divergono, e il giorno in cui divergono nessuno se
    ne accorge: la pagina direbbe una cosa e il bilancio un'altra;
  - mandare al browser tutte le settantaseimila previsioni della storia sono
    parecchi mega, per leggerne dieci;
  - dividerle per anno costa un file di ottanta chilobyte a domanda, e il
    calcolo resta quello vero, fatto dal motore Python che gira ogni sera.

Si e' scelta la terza. Il conto completo sull'intero archivio dura un paio di
minuti; la sera si rigenera solo l'anno in corso, che sono due secondi.

Il formato e' una riga per previsione, campi separati da barra verticale:

    20151003|lottofacile1|NA,BA|5|1|ambata:34;ambo:34-12|NA/BA somma 46|

cioe' giorno, metodo, ruote, colpi, se vale anche su Tutte, le sorti, la nota e
l'eventuale avviso. Nessun JSON: a parita' di contenuto occupa il doppio, e qui
si paga in tempo di scaricamento sul telefono di chi legge.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .archivio import Archivio
from .rilevamento import rileva

SEPARATORE = "|"


def _riga(p: dict) -> str:
    sorti = ";".join(f"{s['tipo']}:" + "-".join(str(n) for n in s["numeri"])
                     for s in p["sorti"])
    campi = [
        p["giorno"].replace("-", ""),
        p["metodo"],
        ",".join(p["ruote"]),
        str(p["colpi"]),
        "1" if p["anche_tutte"] else "0",
        sorti,
        p["nota"] or "",
        p["avviso"] or "",
    ]
    # Se una nota contenesse una barra verticale la riga si spezzerebbe in
    # silenzio e il browser leggerebbe campi sfalsati: meglio accorgersene qui.
    for c in campi:
        if SEPARATORE in c:
            raise ValueError(f"campo con separatore dentro: {c!r}")
    return SEPARATORE.join(campi)


def anni(arch: Archivio) -> list[int]:
    return sorted({d.year for d in arch.date})


def scrivi_anno(arch: Archivio, anno: int, cartella: Path) -> tuple[Path, int]:
    """Riscrive il file di un anno. Torna il percorso e quante previsioni contiene."""
    cartella.mkdir(parents=True, exist_ok=True)
    righe = []
    for giorno in [d for d in arch.date if d.year == anno]:
        righe.extend(_riga(p) for p in rileva(arch, giorno))
    percorso = cartella / f"{anno}.txt"
    testo = "\n".join([
        f"# Previsioni dei sei metodi sui concorsi del {anno}.",
        "# giorno|metodo|ruote|colpi|anche_tutte|sorti|nota|avviso",
        *righe,
    ]) + "\n"
    percorso.write_text(testo, encoding="utf-8")
    return percorso, len(righe)


def scrivi(arch: Archivio, cartella: Path, solo: list[int] | None = None) -> dict:
    """Scrive gli anni richiesti (tutti, se non se ne indicano) e rifa' l'indice.

    L'indice dice al browser quali anni esistono e quante previsioni hanno: senza,
    la pagina dovrebbe tirare a indovinare e leggere un 404 come se fosse una
    risposta.
    """
    tutti = anni(arch)
    cartella.mkdir(parents=True, exist_ok=True)
    indice_file = cartella / "indice.json"
    conte: dict[str, int] = {}

    for anno in (solo if solo is not None else tutti):
        if anno not in tutti:
            continue
        _, quante = scrivi_anno(arch, anno, cartella)
        conte[str(anno)] = quante

    # Gli anni non riscritti si contano rileggendo il loro file, non fidandosi
    # dell'indice di prima: se l'indice manca - repository appena clonato, file
    # cancellato per sbaglio - fidarsene azzererebbe in silenzio ottant'anni di
    # conteggi, e la pagina direbbe che nel 1975 non e' successo niente.
    for anno in tutti:
        if str(anno) in conte:
            continue
        f = cartella / f"{anno}.txt"
        conte[str(anno)] = (
            sum(1 for r in f.read_text(encoding="utf-8").split("\n")
                if r and not r.startswith("#")) if f.is_file() else 0)
    conte = {str(a): conte[str(a)] for a in tutti}
    indice = {
        "anni": conte,
        "primo": arch.date[0].isoformat() if arch.date else None,
        "ultimo": arch.ultima.isoformat() if arch.ultima else None,
        "previsioni": sum(conte.values()),
    }
    indice_file.write_text(
        json.dumps(indice, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8")
    return indice


def leggi_riga(riga: str) -> dict:
    """L'inverso di `_riga`. Sta qui perche' le prove possano fare il giro completo."""
    giorno, metodo, ruote, colpi, tutte, sorti, nota, avviso = riga.split(SEPARATORE)
    return {
        "giorno": f"{giorno[:4]}-{giorno[4:6]}-{giorno[6:]}",
        "metodo": metodo,
        "ruote": ruote.split(","),
        "colpi": int(colpi),
        "anche_tutte": tutte == "1",
        "sorti": [
            {"tipo": s.split(":")[0],
             "numeri": [int(n) for n in s.split(":")[1].split("-")]}
            for s in sorti.split(";") if s
        ],
        "nota": nota or None,
        "avviso": avviso or None,
    }


if __name__ == "__main__":       # pragma: no cover
    import sys
    import time

    radice = Path(__file__).resolve().parent.parent
    arch = Archivio.carica(radice / "archivio" / "estrazioni.csv")
    solo = [int(a) for a in sys.argv[1:]] or None
    t = time.time()
    indice = scrivi(arch, radice / "docs" / "dati" / "previsioni", solo)
    quali = "tutti gli anni" if solo is None else " ".join(map(str, solo))
    print(f"{quali}: {indice['previsioni']} previsioni in archivio, "
          f"{time.time() - t:.0f}s")
