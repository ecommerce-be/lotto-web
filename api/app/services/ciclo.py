"""
Il ciclo di aggiornamento, in un posto solo.

    scarica i concorsi mancanti -> rileva le previsioni -> valuta le sorti aperte

Lo chiamano in tre: lo script da console, l'endpoint, e il pianificatore
interno che gira da solo ogni sera. Prima viveva dentro lo script; quando e'
servito farlo eseguire anche all'applicazione, copiarlo avrebbe significato due
comportamenti destinati a divergere in silenzio - ed e' esattamente il genere di
divergenza che ci si accorge di avere sei mesi dopo, guardando due numeri che
non tornano.

Il registro (logs/aggiorna.log) e' scritto in puro ASCII di proposito:
PowerShell 5.1 legge i file come ANSI e trasforma qualunque accento in
sequenze illeggibili, il che rende inutile proprio il file che si va a
consultare quando qualcosa e' andato storto.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime

from ..config import RADICE
from ..db import (DatabaseNonRaggiungibile, MigrazioniNonApplicate,
                  SessionLocale, verifica_schema)
from . import aggiornatore, rilevatore, valutatore

CARTELLA_LOG = RADICE / "logs"

# Un solo ciclo per volta: lo stesso lavoro puo' partire dalla console, dal
# pulsante dell'interfaccia e dal pianificatore, e due esecuzioni sovrapposte
# scriverebbero le stesse previsioni due volte.
_lucchetto = threading.Lock()

OK, FONTE_KO, DATABASE_KO, GIA_IN_CORSO = 0, 1, 2, 3


@dataclass
class EsitoCiclo:
    codice: int = OK
    motivo: str | None = None
    dal: date | None = None
    al: date | None = None
    concorsi_attesi: int = 0
    concorsi_scaricati: int = 0
    righe_scritte: int = 0
    previsioni_generate: int = 0
    esiti_nuovi: int = 0
    sorti_vinte: int = 0
    sorti_scadute: int = 0
    giorni_falliti: list[str] = field(default_factory=list)
    inizio: datetime | None = None
    durata_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.codice == OK

    def come_dizionario(self) -> dict:
        return {
            "ok": self.ok,
            "codice": self.codice,
            "motivo": self.motivo,
            "dal": self.dal,
            "al": self.al,
            "concorsi_attesi": self.concorsi_attesi,
            "concorsi_scaricati": self.concorsi_scaricati,
            "righe_scritte": self.righe_scritte,
            "previsioni_generate": self.previsioni_generate,
            "esiti_nuovi": self.esiti_nuovi,
            "sorti_vinte": self.sorti_vinte,
            "sorti_scadute": self.sorti_scadute,
            "giorni_falliti": self.giorni_falliti,
            "inizio": self.inizio.isoformat(timespec="seconds") if self.inizio else None,
            "durata_s": round(self.durata_s, 1),
        }


@contextmanager
def registro():
    """
    Stampa a video e in coda a logs/aggiorna.log.

    Quando il ciclo parte dal pianificatore nessuno guarda la console: senza
    registro l'unico segnale sarebbe il codice d'uscita, che dice "e' fallito"
    ma non perche'. Un registro che non si apre non ferma il lavoro.
    """
    try:
        CARTELLA_LOG.mkdir(exist_ok=True)
        f = open(CARTELLA_LOG / "aggiorna.log", "a", encoding="utf-8")
    except OSError:
        f = None

    def stampa(*parti):
        testo = " ".join(str(p) for p in parti)
        print(testo)
        if f:
            f.write(testo + "\n")
            f.flush()

    try:
        yield stampa
    finally:
        if f:
            f.close()


def in_corso() -> bool:
    return _lucchetto.locked()


def esegui(*, fino_a: date | None = None, solo_scarica: bool = False,
           etichetta: str = "manuale") -> EsitoCiclo:
    """Il ciclo completo. Non solleva eccezioni: l'esito sta nel codice."""
    if not _lucchetto.acquire(blocking=False):
        return EsitoCiclo(codice=GIA_IN_CORSO,
                          motivo="un aggiornamento e' gia' in corso")
    try:
        with registro() as stampa:
            return _esegui(stampa, fino_a=fino_a, solo_scarica=solo_scarica,
                           etichetta=etichetta)
    finally:
        _lucchetto.release()


def _esegui(stampa, *, fino_a, solo_scarica, etichetta) -> EsitoCiclo:
    e = EsitoCiclo(inizio=datetime.now())
    stampa(f"\n=== {e.inizio:%Y-%m-%d %H:%M:%S} - avvio aggiornamento ({etichetta}) ===")

    def chiudi(codice=OK, motivo=None):
        e.codice, e.motivo = codice, motivo
        e.durata_s = (datetime.now() - e.inizio).total_seconds()
        stampa(f"esito: {'OK' if e.ok else 'FALLITO'}"
               + (f" ({motivo})" if motivo else "")
               + f"  (durata {e.durata_s:.0f}s)")
        return e

    try:
        verifica_schema()
    except (DatabaseNonRaggiungibile, MigrazioniNonApplicate) as errore:
        stampa(str(errore))
        return chiudi(DATABASE_KO, "database non pronto")

    with SessionLocale() as s:
        try:
            rap = aggiornatore.aggiorna(s, fino_a=fino_a)
        except aggiornatore.FonteNonDisponibile as errore:
            stampa(f"\nFonte non disponibile.\n\n   {errore}\n\n"
                   "Se il problema persiste la fonte potrebbe aver cambiato formato:\n"
                   "in quel caso l'archivio resta caricabile a mano dal CSV con\n"
                   "   python scripts\\carica_archivio.py --csv percorso\\del\\file.csv\n")
            return chiudi(FONTE_KO, "fonte non disponibile")

        e.dal, e.al = rap.dal, rap.al
        e.concorsi_attesi = rap.concorsi_attesi
        e.concorsi_scaricati = rap.concorsi_scaricati
        e.righe_scritte = rap.righe_scritte
        e.giorni_falliti = list(rap.giorni_falliti)

        if not rap.concorsi_attesi:
            stampa(f"Nessun concorso nuovo: l'archivio e' gia' aggiornato "
                   f"(ultima estrazione prima del {rap.dal}).")
            return chiudi()

        stampa(f"concorsi attesi     {rap.concorsi_attesi}  ({rap.dal} -> {rap.al})")
        stampa(f"concorsi scaricati  {rap.concorsi_scaricati}")
        stampa(f"righe scritte       {rap.righe_scritte}")
        for g in rap.giorni_falliti:
            stampa(f"   non scaricato: {g}")

        if solo_scarica or not rap.nuove_date:
            return chiudi()

        stampa(f"\nrilevamento su {len(rap.nuove_date)} nuovi concorsi")
        for giorno in rap.nuove_date:
            e.previsioni_generate += len(rilevatore.rileva(s, giorno))
        stampa(f"   {e.previsioni_generate} previsioni generate")

        stampa("\nvalutazione delle sorti aperte")
        rv = valutatore.valuta_aperte(s)
        e.esiti_nuovi, e.sorti_vinte = rv.esiti_nuovi, rv.sorti_vinte
        e.sorti_scadute = rv.sorti_scadute
        stampa(f"   esaminate {rv.sorti_esaminate}, nuovi esiti {rv.esiti_nuovi}, "
               f"vinte {rv.sorti_vinte}, scadute {rv.sorti_scadute}")
        return chiudi()
