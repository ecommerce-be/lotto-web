"""
Regression test del pianificatore interno.

Copre la parte che non si puo' provare guardandola girare: l'orario del
prossimo appuntamento, il lucchetto che impedisce due cicli sovrapposti, e il
segnalibro che evita un giro sulla fonte ufficiale a ogni riavvio di uvicorn.
Il ciclo vero non viene mai eseguito - viene sostituito da una spia.

    python test_pianificatore.py
"""
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import pianificatore as pf          # noqa: E402
from app.services import ciclo               # noqa: E402

ok = fail = 0


def check(nome, cond, dettaglio=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  OK   {nome}")
    else:
        fail += 1
        print(f"  FAIL {nome}  {dettaglio}")


print("ORARIO DEL PROSSIMO APPUNTAMENTO")
bersaglio = time(20, 45)
mattina = datetime(2026, 9, 15, 9, 0)
check("di mattina punta a stasera",
      pf._prossima(mattina, bersaglio) == datetime(2026, 9, 15, 20, 45))
check("dopo l'ora punta a domani",
      pf._prossima(datetime(2026, 9, 15, 21, 0), bersaglio)
      == datetime(2026, 9, 16, 20, 45))
check("esattamente all'ora punta a domani (non riparte subito)",
      pf._prossima(datetime(2026, 9, 15, 20, 45), bersaglio)
      == datetime(2026, 9, 16, 20, 45))
check("l'ultimo del mese passa al primo del mese dopo",
      pf._prossima(datetime(2026, 9, 30, 23, 59), bersaglio)
      == datetime(2026, 10, 1, 20, 45))

print("\nLETTURA DELL'ORA DAL .env")
originale = pf.impostazioni.ora_aggiornamento
pf.impostazioni.ora_aggiornamento = "07:05"
check("07:05 viene letta", pf._ora_bersaglio() == time(7, 5))
for sbagliata in ("20.45", "venti e quarantacinque", "", "25:00"):
    pf.impostazioni.ora_aggiornamento = sbagliata
    try:
        pf._ora_bersaglio()
        check(f"{sbagliata!r} respinta", False, "non ha sollevato")
    except ValueError as e:
        check(f"{sbagliata!r} respinta con un messaggio leggibile",
              "HH:MM" in str(e), str(e))
pf.impostazioni.ora_aggiornamento = originale

print("\nLUCCHETTO: un solo ciclo per volta")
ciclo._lucchetto.acquire()
try:
    e = ciclo.esegui(etichetta="test")
    check("il secondo ciclo non parte", e.codice == ciclo.GIA_IN_CORSO, str(e.codice))
    check("e lo dice invece di fingere di aver lavorato",
          e.motivo is not None and not e.ok, str(e.motivo))
    check("esegui_adesso rifiuta mentre e' in corso", pf.esegui_adesso() is False)
finally:
    ciclo._lucchetto.release()
check("a lucchetto libero in_corso() e' falso", ciclo.in_corso() is False)

print("\nSEGNALIBRO: niente giro sulla fonte a ogni --reload")
giri = []
pf._gira = lambda etichetta: giri.append(etichetta)     # spia al posto del ciclo
pf._ferma.set()                                          # il loop serale esce subito

pf._scrivi_segnalibro(datetime.now())
check("il segnalibro si rilegge",
      pf._leggi_segnalibro() is not None
      and abs((pf._leggi_segnalibro() - datetime.now()).total_seconds()) < 5)
giri.clear()
pf._ciclo_di_vita(bersaglio)
check("tentativo appena fatto: all'avvio non si riparte", giri == [], str(giri))

pf._scrivi_segnalibro(datetime.now() - timedelta(minutes=pf.PAUSA_AVVIO_MINUTI + 1))
giri.clear()
pf._ciclo_di_vita(bersaglio)
check("tentativo vecchio: all'avvio si recupera", giri == ["avvio"], str(giri))

pf.SEGNALIBRO.unlink(missing_ok=True)
giri.clear()
pf._ciclo_di_vita(bersaglio)
check("nessun segnalibro: si recupera", giri == ["avvio"], str(giri))

pf.SEGNALIBRO.write_text("non una data", encoding="ascii")
check("un segnalibro illeggibile non fa esplodere nulla",
      pf._leggi_segnalibro() is None)
pf.SEGNALIBRO.unlink(missing_ok=True)

print("\nAVVIO DISATTIVATO DA .env")
pf._ferma.clear()
originale_auto = pf.impostazioni.aggiornamento_automatico
pf.impostazioni.aggiornamento_automatico = False
pf.avvia()
check("non parte", pf.stato["attivo"] is False)
check("e dice perche'", "AGGIORNAMENTO_AUTOMATICO" in (pf.stato["motivo_inattivo"] or ""),
      str(pf.stato["motivo_inattivo"]))
pf.impostazioni.aggiornamento_automatico = originale_auto

pf.impostazioni.ora_aggiornamento = "mezzanotte"
pf.avvia()
check("ora invalida: non parte invece di partire a un'ora a caso",
      pf.stato["attivo"] is False)
check("e il motivo finisce nello stato, non solo a video",
      "HH:MM" in (pf.stato["motivo_inattivo"] or ""), str(pf.stato["motivo_inattivo"]))
pf.impostazioni.ora_aggiornamento = originale
pf.ferma()

print(f"\n{'='*60}\nRISULTATO: {ok} OK, {fail} FAIL")
sys.exit(1 if fail else 0)
