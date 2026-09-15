"""
Aggiornamento automatico dentro l'applicazione.

Perche' non l'utilita' di pianificazione di Windows, che sarebbe il posto
giusto: su questa macchina l'account con cui si lavora non e' amministratore e
il servizio nega sia la registrazione sia la semplice lettura delle attivita'
(HRESULT 0x80070005, "Accesso negato", tanto da Register-ScheduledTask quanto
da schtasks /query). Non e' una configurazione da aggiustare: e' un permesso
che questo profilo non ha.

Il compromesso e' esplicito e va detto, non nascosto: **funziona finche' il
server e' acceso**. Una sera a server spento non viene aggiornata. Non e' pero'
una perdita permanente, perche' l'aggiornatore non scarica "l'estrazione di
ieri" ma tutti i concorsi mancanti fra l'ultimo in archivio e oggi: al primo
avvio successivo il recupero e' automatico, e il recupero e' anche cio' che
parte all'avvio.

Due precauzioni che sembrano dettagli e non lo sono:

* il risveglio e' a fette di un minuto e l'orario bersaglio viene ricalcolato
  ogni volta. Un `sleep` lungo quanto l'attesa sarebbe sbagliato su un portatile:
  se il PC va in sospensione l'attesa si congela e il ciclo parte con ore di
  ritardo, o non parte affatto;
* l'ultimo tentativo viene annotato su file. Senza, ogni riavvio di uvicorn
  --reload (cioe' ogni salvataggio, durante lo sviluppo) scatenerebbe un giro
  completo sulla fonte ufficiale.
"""
from __future__ import annotations

import threading
from datetime import datetime, time, timedelta

from .config import impostazioni
from .services import ciclo

SEGNALIBRO = ciclo.CARTELLA_LOG / "ultimo-tentativo.txt"
PAUSA_AVVIO_MINUTI = 30      # entro questa distanza dall'ultimo tentativo, all'avvio non si riparte
FETTA_S = 60                 # granularita' del risveglio

_ferma = threading.Event()
_thread: threading.Thread | None = None

stato: dict = {
    "attivo": False,
    "motivo_inattivo": None,
    "ora": None,
    "prossima_esecuzione": None,
    "ultimo_avvio": None,
    "ultimo_esito": None,
}


def _ora_bersaglio() -> time:
    try:
        h, m = impostazioni.ora_aggiornamento.split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        raise ValueError(
            f"ORA_AGGIORNAMENTO non valida: {impostazioni.ora_aggiornamento!r}. "
            "Formato atteso HH:MM, per esempio 20:45.") from None


def _prossima(da: datetime, bersaglio: time) -> datetime:
    oggi = datetime.combine(da.date(), bersaglio)
    return oggi if oggi > da else oggi + timedelta(days=1)


def _leggi_segnalibro() -> datetime | None:
    try:
        return datetime.fromisoformat(SEGNALIBRO.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return None


def _scrivi_segnalibro(quando: datetime) -> None:
    try:
        SEGNALIBRO.parent.mkdir(exist_ok=True)
        SEGNALIBRO.write_text(quando.isoformat(timespec="seconds"), encoding="ascii")
    except OSError:
        pass                      # un segnalibro che non si scrive non ferma il lavoro


def _gira(etichetta: str) -> None:
    stato["ultimo_avvio"] = datetime.now().isoformat(timespec="seconds")
    _scrivi_segnalibro(datetime.now())
    esito = ciclo.esegui(etichetta=etichetta)
    stato["ultimo_esito"] = esito.come_dizionario()


def _ciclo_di_vita(bersaglio: time) -> None:
    # recupero all'avvio, se l'ultimo tentativo non e' recentissimo
    ultimo = _leggi_segnalibro()
    if ultimo is None or datetime.now() - ultimo > timedelta(minutes=PAUSA_AVVIO_MINUTI):
        _gira("avvio")

    while not _ferma.is_set():
        prossima = _prossima(datetime.now(), bersaglio)
        stato["prossima_esecuzione"] = prossima.isoformat(timespec="seconds")
        # si dorme a fette e si ricontrolla l'orologio: cosi' una sospensione
        # del PC non sposta l'appuntamento, al massimo lo fa scattare al risveglio
        while not _ferma.is_set() and datetime.now() < prossima:
            _ferma.wait(FETTA_S)
        if _ferma.is_set():
            return
        _gira("pianificato")


def avvia() -> None:
    """Chiamata all'avvio dell'applicazione. Non solleva: al massimo non parte."""
    global _thread
    stato["attivo"] = False
    if not impostazioni.aggiornamento_automatico:
        stato["motivo_inattivo"] = "disattivato da AGGIORNAMENTO_AUTOMATICO nel .env"
        return
    try:
        bersaglio = _ora_bersaglio()
    except ValueError as e:
        stato["motivo_inattivo"] = str(e)
        print(f"\nPianificatore non avviato. {e}\n")
        return

    _ferma.clear()
    _thread = threading.Thread(target=_ciclo_di_vita, args=(bersaglio,),
                               name="pianificatore-lotto", daemon=True)
    _thread.start()
    stato["attivo"] = True
    stato["motivo_inattivo"] = None
    stato["ora"] = bersaglio.strftime("%H:%M")


def ferma() -> None:
    _ferma.set()
    stato["attivo"] = False


def esegui_adesso() -> bool:
    """Lancia un ciclo fuori orario. False se ce n'e' gia' uno in corso."""
    if ciclo.in_corso():
        return False
    threading.Thread(target=_gira, args=("richiesto",), daemon=True).start()
    return True
