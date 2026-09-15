"""
App Lotto — API.

Prima tranche: dominio, persistenza, import dell'archivio, rilevamento e
valutazione. Gli endpoint sono quelli necessari a far girare il ciclo completo
(importa -> rileva -> valuta -> consulta), non ancora quelli di prodotto.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import pianificatore
from .config import impostazioni
from .db import (DatabaseNonRaggiungibile, MigrazioniNonApplicate,
                 get_sessione, verifica_schema)
from .models import Estrazione, Metodo, Previsione, Ruota, Sorte, StatoSorte
from .services import (calendario, ciclo, consultazione, economia, importer,
                       rilevatore, schedina, valutatore)

app = FastAPI(title="App Lotto", version="0.1.0",
              description="Assistente per le giocate del Lotto basato sui metodi storici")


@app.on_event("startup")
def avvio() -> None:
    try:
        verifica_schema()
    except (DatabaseNonRaggiungibile, MigrazioniNonApplicate) as e:
        # meglio partire e rispondere "database non raggiungibile" sugli endpoint
        # che morire con un traceback illeggibile prima ancora di aprire la porta
        print(e)
        app.state.db_ko = str(e)
        return
    app.state.db_ko = None
    # Con lo schema a posto parte il pianificatore: senza database non avrebbe
    # nulla da aggiornare e riproverebbe ogni sera contro un muro.
    pianificatore.avvia()


@app.on_event("shutdown")
def spegnimento() -> None:
    pianificatore.ferma()


# ----------------------------------------------------------------- schemi
class SorteOut(BaseModel):
    tipo: str
    numeri: list[int]
    stato: str
    colpi_valutati: int

    model_config = {"from_attributes": True}


class PrevisioneOut(BaseModel):
    id: int
    metodo: str
    data_rilevamento: date
    ruote: list[str]
    colpi: int
    anche_tutte: bool
    nota: str | None = None
    avviso: str | None = None
    sorti: list[SorteOut]

    model_config = {"from_attributes": True}


class EstrazioneOut(BaseModel):
    data: date
    ruota: str
    numeri: list[int]

    model_config = {"from_attributes": True}


class RichiestaSchedina(BaseModel):
    numeri: list[int] = Field(..., description="da 1 a 10 numeri, fra 1 e 90")
    ruote: list[str] = Field(..., description='sigle delle ruote, oppure ["TUTTE"]')
    sorti: list[str] = Field(..., description="estratto, ambo, terno, quaterna, cinquina")
    importo: float = Field(5.0, gt=0, description="quanto si punta in tutto, in euro")


class RichiestaImport(BaseModel):
    percorso: str | None = Field(
        None, description="percorso del CSV; se assente usa ARCHIVIO_CSV dalla configurazione")


# ------------------------------------------------------------- estrazioni
@app.post("/estrazioni/import", tags=["estrazioni"])
def importa(req: RichiestaImport, sessione: Session = Depends(get_sessione)):
    percorso = impostazioni.archivio_csv if req.percorso is None else req.percorso
    from pathlib import Path
    percorso = Path(percorso)
    if not percorso.is_file():
        raise HTTPException(404, f"archivio non trovato: {percorso}")
    r = importer.importa_csv(sessione, percorso,
                             includi_nazionale=impostazioni.includi_nazionale)
    if not r.ordine_di_estrazione:
        # non blocca l'import, ma va detto forte: i metodi con filtro isotopi
        # su questo archivio misurerebbero qualcos'altro
        return {"avviso": "I numeri risultano ORDINATI PER VALORE: i metodi che "
                          "filtrano per isotopia non sono applicabili a questo archivio.",
                **r.__dict__}
    return r.__dict__


@app.post("/estrazioni/aggiorna", tags=["estrazioni"])
def aggiorna(fino_a: date | None = None, solo_scarica: bool = False):
    """
    Scarica i concorsi mancanti dalla fonte ufficiale, poi rileva e valuta.

    E' lo stesso identico ciclo dello script e del pianificatore serale: una
    sola implementazione, cosi' non ci si ritrova con tre comportamenti diversi
    a seconda di chi ha premuto il pulsante.
    """
    esito = ciclo.esegui(fino_a=fino_a, solo_scarica=solo_scarica, etichetta="api")
    if esito.codice == ciclo.GIA_IN_CORSO:
        raise HTTPException(409, esito.motivo)
    if esito.codice == ciclo.FONTE_KO:
        raise HTTPException(503, esito.motivo)
    if esito.codice == ciclo.DATABASE_KO:
        raise HTTPException(503, esito.motivo)
    return esito.come_dizionario()


@app.get("/estrazioni", response_model=list[EstrazioneOut], tags=["estrazioni"])
def estrazioni(giorno: date, sessione: Session = Depends(get_sessione)):
    righe = sessione.scalars(
        select(Estrazione).where(Estrazione.data == giorno).order_by(Estrazione.ruota)).all()
    if not righe:
        raise HTTPException(404, f"nessuna estrazione per il {giorno}")
    return [EstrazioneOut(data=e.data, ruota=e.ruota.value, numeri=list(e.numeri))
            for e in righe]


@app.get("/estrazioni/ultima", tags=["estrazioni"])
def ultima(sessione: Session = Depends(get_sessione)):
    d = sessione.scalar(select(func.max(Estrazione.data)))
    if d is None:
        raise HTTPException(404, "archivio vuoto: eseguire prima /estrazioni/import")
    return {"data": d}


# ------------------------------------------------------------- previsioni
@app.post("/previsioni/rileva", response_model=list[PrevisioneOut], tags=["previsioni"])
def rileva(giorno: date, sessione: Session = Depends(get_sessione)):
    esistenti = sessione.scalar(
        select(func.count()).select_from(Previsione)
        .where(Previsione.data_rilevamento == giorno))
    if esistenti:
        raise HTTPException(409, f"il {giorno} ha gia' {esistenti} previsioni rilevate")
    fuori = rilevatore.rileva(sessione, giorno)
    if not fuori:
        raise HTTPException(404, f"nessun rilevamento il {giorno} "
                                 "(concorso assente o incompleto)")
    return fuori


@app.get("/previsioni", response_model=list[PrevisioneOut], tags=["previsioni"])
def elenco(giorno: date | None = None,
           metodo: Metodo | None = None,
           solo_aperte: bool = False,
           limite: int = Query(100, le=1000),
           sessione: Session = Depends(get_sessione)):
    q = select(Previsione).order_by(Previsione.data_rilevamento.desc(), Previsione.id)
    if giorno:
        q = q.where(Previsione.data_rilevamento == giorno)
    if metodo:
        q = q.where(Previsione.metodo == metodo)
    if solo_aperte:
        q = q.join(Sorte).where(Sorte.stato == StatoSorte.APERTA).distinct()
    return list(sessione.scalars(q.limit(limite)))


@app.get("/previsioni/aperte", tags=["previsioni"])
def aperte(limite: int = Query(100, le=500), sessione: Session = Depends(get_sessione)):
    """Cosa e' ancora in gioco, con i colpi che restano. E' la vista dell'app."""
    return consultazione.previsioni_in_corso(sessione, limite=limite)


@app.post("/previsioni/valuta", tags=["previsioni"])
def valuta(limite: int | None = None, sessione: Session = Depends(get_sessione)):
    return valutatore.valuta_aperte(sessione, limite=limite).__dict__


@app.get("/statistiche/metodi", tags=["statistiche"])
def statistiche(sessione: Session = Depends(get_sessione)):
    """Esiti reali per metodo. Non le percentuali dei fascicoli: queste."""
    return valutatore.riepilogo_metodi(sessione)


@app.get("/statistiche/economia", tags=["statistiche"])
def economia_(includi_tutte: bool = False, sessione: Session = Depends(get_sessione)):
    """Quanto si e' speso e quanto si e' incassato, per metodo e in totale.

    E' il numero che conta: una "quota vincente" alta puo' benissimo
    accompagnarsi a un saldo pesantemente negativo.
    """
    return economia.bilancio_complessivo(sessione, includi_tutte=includi_tutte)


# -------------------------------------------------------------- schedina
@app.get("/prossima-estrazione", tags=["schedina"])
def prossima_estrazione(quante: int = Query(3, ge=1, le=10),
                        sessione: Session = Depends(get_sessione)):
    """
    Le prossime date di concorso, dal calendario ufficiale.

    Se la fonte non risponde la risposta arriva lo stesso, ma con
    `stimato: true` e il motivo: una data sbagliata data per certa e' peggio di
    una dichiarata incerta.
    """
    return calendario.prossime(sessione, quante=quante)


@app.get("/schedina/sorti", tags=["schedina"])
def sorti_giocabili():
    """Cosa si puo' giocare, quanti numeri serve avere scelto, quanto paga."""
    return schedina.descrizione_sorti()


@app.post("/schedina/simula", tags=["schedina"])
def simula_schedina(req: RichiestaSchedina):
    """
    Quanto si punta, quanto si puo' prendere e con quale probabilita'.

    Non tocca il database: e' un calcolo sulle regole del gioco, non una
    previsione. Sta sul server e non nella pagina perche' le quote e la
    ritenuta devono avere una sola definizione, la stessa che usa il bilancio.
    """
    try:
        return schedina.simula(numeri=req.numeri, ruote=req.ruote,
                               sorti=req.sorti, importo=req.importo)
    except schedina.GiocataNonValida as e:
        raise HTTPException(422, str(e))


# -------------------------------------------------------------- servizio
@app.get("/servizio/aggiornamento", tags=["servizio"])
def aggiornamento():
    """
    Stato dell'aggiornamento automatico: se e' attivo, a che ora, com'e' andato
    l'ultimo giro e quando e' il prossimo.

    Serve all'interfaccia per dire a colpo d'occhio se i numeri che si stanno
    guardando sono di ieri sera o di tre settimane fa - che e' la differenza fra
    una previsione e un ricordo.
    """
    return {**pianificatore.stato, "in_corso": ciclo.in_corso()}


@app.post("/servizio/aggiornamento/esegui", tags=["servizio"])
def aggiorna_adesso():
    """Lancia il ciclo subito, senza aspettare l'ora. Non blocca la risposta."""
    if not pianificatore.esegui_adesso():
        raise HTTPException(409, "un aggiornamento e' gia' in corso")
    return {"avviato": True}


@app.middleware("http")
async def blocca_se_db_ko(request, call_next):
    """Se il database non e' raggiungibile lo si dice una volta sola, in chiaro."""
    from fastapi.responses import JSONResponse
    ko = getattr(app.state, "db_ko", None)
    if ko and not request.url.path.startswith("/app") and \
            request.url.path not in ("/", "/docs", "/openapi.json", "/redoc",
                                     "/servizio/aggiornamento"):
        return JSONResponse(status_code=503,
                            content={"errore": "database non pronto",
                                     "dettaglio": ko})
    return await call_next(request)


WEB = Path(__file__).resolve().parent / "web"
if WEB.is_dir():
    app.mount("/app", StaticFiles(directory=WEB, html=True), name="app")


@app.get("/", include_in_schema=False)
def radice():
    """La radice porta all'interfaccia; la documentazione resta su /docs."""
    return RedirectResponse("/app/" if WEB.is_dir() else "/docs")


@app.get("/salute", tags=["servizio"])
def salute(sessione: Session = Depends(get_sessione)):
    return {
        "estrazioni": sessione.scalar(select(func.count()).select_from(Estrazione)),
        "previsioni": sessione.scalar(select(func.count()).select_from(Previsione)),
        "ultima_estrazione": sessione.scalar(select(func.max(Estrazione.data))),
        "ruote": [r.value for r in Ruota.classiche()],
        "metodi": [m.value for m in Metodo],
        "aggiornamento_automatico": pianificatore.stato["attivo"],
    }
