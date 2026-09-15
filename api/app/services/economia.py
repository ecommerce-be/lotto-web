"""
Bilancio economico delle previsioni: quanto si e' speso, quanto si e' incassato.

Perche' questo modulo esiste. "Quota vincente 26,8%" e' il genere di numero che
i fascicoli usavano per impressionare: dice che qualcosa e' uscito, non se e'
convenuto. Un metodo che gioca 5 sorti su 2 ruote per 14 colpi spende 140 euro
per previsione; se ne vince una da 250, il 26,8% di "successo" e' comunque una
perdita. L'unico numero onesto e' il saldo.

Convenzioni, le stesse dei fascicoli:
  - 1 euro per sorte, per ruota, per colpo;
  - si sospende la sorte quando si verifica ("in caso di vincita si consiglia
    di sospendere il gioco sulla ruota dove si e' verificata l'uscita");
  - le sorti lunghe (terzina, quartina) sono giocate per ambo e terno, quindi
    la posta si ripartisce sulle combinazioni: un ambo in terzina paga 250/3.

Il gioco "a Tutte" e' facoltativo nei fascicoli, quindi e' tenuto separato:
entra nel conto solo se lo si chiede esplicitamente.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import comb

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import Esito, Previsione, Sorte, StatoSorte, TipoSorte

# quote ufficiali del Lotto italiano, moltiplicatore della posta su ruota singola
QUOTA_ESTRATTO = 11.232
QUOTA_AMBO = 250.0
QUOTA_TERNO = 4500.0
QUOTA_QUATERNA = 120_000.0
RITENUTA = 0.08          # ritenuta erariale sulle vincite
SOGLIA_CAMPIONE = 300    # sotto questa soglia un saldo non e' indicativo

NUMERI_PER_SORTE = {TipoSorte.AMBATA: 1, TipoSorte.AMBO: 2,
                    TipoSorte.TERZINA: 3, TipoSorte.QUARTINA: 4}


def _vincita_lorda(tipo: TipoSorte, quanti_usciti: int) -> float:
    """Quanto paga una sorte, data la posta di 1 euro e i numeri usciti."""
    n = NUMERI_PER_SORTE[tipo]
    if tipo is TipoSorte.AMBATA:
        return QUOTA_ESTRATTO if quanti_usciti >= 1 else 0.0
    if tipo is TipoSorte.AMBO:
        return QUOTA_AMBO if quanti_usciti >= 2 else 0.0
    # sorti lunghe: la posta si ripartisce sulle combinazioni giocate
    if quanti_usciti >= 4 and n >= 4:
        return QUOTA_QUATERNA / comb(n, 4)
    if quanti_usciti >= 3:
        return QUOTA_TERNO / comb(n, 3)
    if quanti_usciti >= 2:
        return QUOTA_AMBO / comb(n, 2)
    return 0.0


@dataclass
class Bilancio:
    previsioni: int = 0
    sorti: int = 0
    speso: float = 0.0
    incassato: float = 0.0          # al netto della ritenuta
    vincite: int = 0
    incassato_a_tutte: float = 0.0  # gioco facoltativo, tenuto separato

    @property
    def saldo(self) -> float:
        return self.incassato - self.speso

    @property
    def ritorno(self) -> float | None:
        """Quanto torna indietro per ogni euro giocato."""
        return self.incassato / self.speso if self.speso else None

    def come_dizionario(self) -> dict:
        return {
            "previsioni": self.previsioni,
            "sorti": self.sorti,
            "vincite": self.vincite,
            "speso": round(self.speso, 2),
            "incassato": round(self.incassato, 2),
            "saldo": round(self.saldo, 2),
            "ritorno": round(self.ritorno, 4) if self.ritorno is not None else None,
            "incassato_a_tutte": round(self.incassato_a_tutte, 2),
        }


def bilancio_per_metodo(sessione: Session, *, includi_tutte: bool = False) -> list[dict]:
    """Bilancio di ogni metodo sulle previsioni presenti in archivio."""
    q = (select(Previsione)
         .options(selectinload(Previsione.sorti).selectinload(Sorte.esiti)))
    acc: dict[str, Bilancio] = {}

    for p in sessione.scalars(q):
        b = acc.setdefault(p.metodo.value, Bilancio())
        b.previsioni += 1
        n_ruote = len(p.ruote)
        for s in p.sorti:
            b.sorti += 1
            # la spesa segue i colpi effettivamente giocati: una sorte vinta al
            # terzo colpo ha pagato tre colpi, non quattordici
            b.speso += s.colpi_valutati * n_ruote
            for e in s.esiti:
                lordo = _vincita_lorda(s.tipo, len(e.numeri_usciti))
                netto = lordo * (1 - RITENUTA)
                if e.a_tutte:
                    b.incassato_a_tutte += netto
                    if includi_tutte:
                        b.incassato += netto
                        b.vincite += 1
                else:
                    b.incassato += netto
                    b.vincite += 1

    fuori = []
    for metodo, b in sorted(acc.items()):
        riga = {"metodo": metodo, **b.come_dizionario()}
        # Un saldo su poche previsioni non significa nulla: una singola quaterna
        # o un terno ribaltano il segno. Il backtest ventennale (23.853
        # rilevamenti) da' un ritorno fra il 62% e il 74% per ogni metodo, con
        # una media del 67,7%: e' quello il valore atteso, non cio' che si legge
        # su qualche mese. Il flag evita che un campione corto venga scambiato
        # per un risultato.
        riga["campione_scarso"] = b.previsioni < SOGLIA_CAMPIONE
        fuori.append(riga)
    return fuori


def bilancio_complessivo(sessione: Session, *, includi_tutte: bool = False) -> dict:
    righe = bilancio_per_metodo(sessione, includi_tutte=includi_tutte)
    speso = sum(r["speso"] for r in righe)
    incassato = sum(r["incassato"] for r in righe)
    return {
        "per_metodo": righe,
        "totale": {
            "previsioni": sum(r["previsioni"] for r in righe),
            "speso": round(speso, 2),
            "incassato": round(incassato, 2),
            "saldo": round(incassato - speso, 2),
            "ritorno": round(incassato / speso, 4) if speso else None,
        },
        "nota": ("Un euro per sorte, per ruota, per colpo; la sorte si sospende quando "
                 "si verifica. Quote ufficiali (estratto 11,232 · ambo 250 · terno 4.500 "
                 "· quaterna 120.000) al netto della ritenuta dell\u20198%. Il gioco a "
                 "Tutte è facoltativo e resta escluso salvo richiesta."),
        "avvertenza": ("Dove è segnalato un campione insufficiente, il saldo non è "
                       "indicativo: le previsioni sono troppo poche e un solo terno ne "
                       "ribalta il segno. Sul backtest di vent\u2019anni il ritorno "
                       "atteso è fra il 62% e il 74% per ogni metodo, in media il 67,7%."),
    }
