"""
Simulazione di una schedina: quanto si punta, quanto si puo' vincere, e con
quale probabilita'.

La differenza fra questo modulo ed `economia.py` e' il tempo. `economia`
guarda indietro e dice cosa e' successo davvero alle previsioni gia' giocate;
qui si guarda avanti, a una giocata che non e' ancora stata fatta, e l'unica
cosa che si puo' dire di vero e' la distribuzione: questa vincita con questa
probabilita'. Un simulatore che mostrasse solo "potresti vincere 12.500 euro"
sarebbe pubblicita'; mostrata accanto alla sua probabilita' (una su 400), la
stessa cifra diventa un'informazione.

Le regole del gioco, che sono la parte che si sbaglia piu' facilmente:

* la posta si **ripartisce**. Se giochi 10 euro su due ruote chiedendo ambo e
  terno, su ciascuna ruota e ciascuna sorte vanno 2,50 euro. Non 10;
* si ripartisce **una seconda volta** sulle combinazioni. Cinque numeri giocati
  per ambo sono C(5,2) = 10 ambi: quei 2,50 euro diventano 25 centesimi per
  ambo. E' il motivo per cui giocare molti numeri non moltiplica la vincita
  come sembra;
* se escono piu' numeri del minimo, vincono **tutte** le combinazioni
  contenute: con 5 numeri giocati per ambo e 3 numeri usciti si vincono C(3,2)
  = 3 ambi;
* ogni ruota e' un'estrazione a se'. Giocare su piu' ruote aumenta la
  probabilita' che *almeno una* vinca, ma divide la posta: il valore atteso non
  cambia di un centesimo.

Quote ufficiali e ritenuta stanno in `economia.py`: una sola fonte, altrimenti
il conto del passato e quello del futuro finirebbero per raccontare due storie
diverse.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import comb

from ..models import Ruota
from .economia import (QUOTA_AMBO, QUOTA_ESTRATTO, QUOTA_QUATERNA, QUOTA_TERNO,
                       RITENUTA)

QUOTA_CINQUINA = 6_000_000.0

# nome della sorte -> (quanti numeri servono, moltiplicatore della posta)
SORTI: dict[str, tuple[int, float]] = {
    "estratto": (1, QUOTA_ESTRATTO),
    "ambo": (2, QUOTA_AMBO),
    "terno": (3, QUOTA_TERNO),
    "quaterna": (4, QUOTA_QUATERNA),
    "cinquina": (5, QUOTA_CINQUINA),
}

ESTRATTI_PER_RUOTA = 5
TOTALE_NUMERI = 90
MAX_NUMERI_GIOCABILI = 10


class GiocataNonValida(ValueError):
    """Quello che e' stato chiesto non e' una giocata possibile."""


def probabilita_presi(giocati: int, presi: int) -> float:
    """
    Probabilita' che, su una ruota, escano esattamente `presi` dei numeri giocati.

    E' l'ipergeometrica: cinque numeri estratti da novanta, senza reimmissione.
    """
    if presi > giocati or presi > ESTRATTI_PER_RUOTA:
        return 0.0
    return (comb(giocati, presi) * comb(TOTALE_NUMERI - giocati, ESTRATTI_PER_RUOTA - presi)
            / comb(TOTALE_NUMERI, ESTRATTI_PER_RUOTA))


@dataclass
class Scenario:
    """Uno degli esiti possibili: quanti numeri escono, cosa si incassa."""
    presi: int
    combinazioni_vincenti: int
    lordo: float
    netto: float
    probabilita: float           # su una singola ruota

    def come_dizionario(self) -> dict:
        return {
            "presi": self.presi,
            "combinazioni_vincenti": self.combinazioni_vincenti,
            "lordo": round(self.lordo, 2),
            "netto": round(self.netto, 2),
            "probabilita": self.probabilita,
            "una_su": round(1 / self.probabilita, 1) if self.probabilita else None,
        }


def _normalizza_numeri(numeri) -> list[int]:
    try:
        puliti = [int(n) for n in numeri]
    except (TypeError, ValueError):
        raise GiocataNonValida("I numeri devono essere interi.") from None
    if not puliti:
        raise GiocataNonValida("Serve almeno un numero.")
    fuori = [n for n in puliti if not 1 <= n <= TOTALE_NUMERI]
    if fuori:
        raise GiocataNonValida(
            f"Il Lotto arriva a 90: {', '.join(map(str, sorted(set(fuori))))} "
            "non e' un numero giocabile.")
    if len(set(puliti)) != len(puliti):
        raise GiocataNonValida("Lo stesso numero compare due volte: "
                               "in una giocata ogni numero vale una volta sola.")
    if len(puliti) > MAX_NUMERI_GIOCABILI:
        raise GiocataNonValida(
            f"Massimo {MAX_NUMERI_GIOCABILI} numeri per giocata (ne sono stati "
            f"indicati {len(puliti)}).")
    return sorted(puliti)


def _normalizza_ruote(ruote) -> list[str]:
    classiche = [r.value for r in Ruota.classiche()]
    if not ruote:
        raise GiocataNonValida("Serve almeno una ruota.")
    scelte = [str(r).upper() for r in ruote]
    if "TUTTE" in scelte:
        return classiche
    ignote = [r for r in scelte if r not in Ruota.__members__]
    if ignote:
        raise GiocataNonValida(f"Ruote sconosciute: {', '.join(sorted(set(ignote)))}.")
    return sorted(set(scelte), key=scelte.index)


def _normalizza_sorti(sorti, quanti_numeri: int) -> list[str]:
    if not sorti:
        raise GiocataNonValida("Serve almeno una sorte (estratto, ambo, terno...).")
    scelte = [str(s).lower() for s in sorti]
    ignote = [s for s in scelte if s not in SORTI]
    if ignote:
        raise GiocataNonValida(
            f"Sorti sconosciute: {', '.join(sorted(set(ignote)))}. "
            f"Sono ammesse: {', '.join(SORTI)}.")
    troppo = [s for s in scelte if SORTI[s][0] > quanti_numeri]
    if troppo:
        nome = troppo[0]
        raise GiocataNonValida(
            f"Con {quanti_numeri} numer{'o' if quanti_numeri == 1 else 'i'} non si "
            f"puo' giocare {nome}: ne servono almeno {SORTI[nome][0]}.")
    # in ordine di lunghezza, come su una schedina vera
    return sorted(set(scelte), key=lambda s: SORTI[s][0])


def simula(*, numeri, ruote, sorti, importo: float) -> dict:
    """
    Il quadro completo di una giocata: cosa si punta e cosa si puo' prendere.

    Non arrotonda la posta al centesimo come farebbe una ricevitoria vera:
    servirebbe a far tornare lo scontrino, non a capire la giocata.
    """
    numeri = _normalizza_numeri(numeri)
    ruote = _normalizza_ruote(ruote)
    sorti = _normalizza_sorti(sorti, len(numeri))

    try:
        importo = float(importo)
    except (TypeError, ValueError):
        raise GiocataNonValida("L'importo non e' un numero.") from None
    if importo <= 0:
        raise GiocataNonValida("L'importo deve essere maggiore di zero.")

    n_giocati = len(numeri)
    quota_per_sorte_e_ruota = importo / (len(ruote) * len(sorti))

    righe, atteso_totale = [], 0.0
    for nome in sorti:
        k, quota = SORTI[nome]
        combinazioni = comb(n_giocati, k)
        posta = quota_per_sorte_e_ruota / combinazioni

        scenari, atteso_per_ruota, prob_vincente = [], 0.0, 0.0
        for presi in range(k, min(n_giocati, ESTRATTI_PER_RUOTA) + 1):
            vincenti = comb(presi, k)
            lordo = posta * quota * vincenti
            netto = lordo * (1 - RITENUTA)
            p = probabilita_presi(n_giocati, presi)
            atteso_per_ruota += p * netto
            prob_vincente += p
            scenari.append(Scenario(presi, vincenti, lordo, netto, p))

        atteso_totale += atteso_per_ruota * len(ruote)
        righe.append({
            "sorte": nome,
            "numeri_necessari": k,
            "combinazioni": combinazioni,
            "posta_per_combinazione": round(posta, 4),
            "posta_per_ruota": round(quota_per_sorte_e_ruota, 4),
            "probabilita_per_ruota": prob_vincente,
            "probabilita_almeno_una_ruota": 1 - (1 - prob_vincente) ** len(ruote),
            "vincita_minima_netta": round(scenari[0].netto, 2),
            "vincita_massima_netta": round(scenari[-1].netto, 2),
            "scenari": [s.come_dizionario() for s in scenari],
        })

    # probabilita' che la schedina porti a casa qualcosa: basta la sorte piu'
    # corta, che e' sempre la piu' probabile e la contiene tutte
    p_minima = righe[0]["probabilita_per_ruota"]
    return {
        "numeri": numeri,
        "ruote": ruote,
        "sorti": sorti,
        "importo": round(importo, 2),
        "righe": righe,
        "qualcosa_per_ruota": p_minima,
        "qualcosa_almeno_una_ruota": 1 - (1 - p_minima) ** len(ruote),
        "ritorno_atteso": round(atteso_totale, 2),
        "ritorno_atteso_per_euro": round(atteso_totale / importo, 4),
        "nota": ("La posta si ripartisce fra le ruote, fra le sorti scelte e fra le "
                 "combinazioni di ciascuna sorte. Le vincite sono al netto della "
                 "ritenuta dell'8%. Giocare su piu' ruote aumenta la probabilita' "
                 "che almeno una vinca, ma divide la posta: il ritorno atteso non "
                 "cambia."),
    }


def descrizione_sorti() -> list[dict]:
    """
    Le sorti giocabili, con quanti numeri servono e quanto pagano.

    Serve all'interfaccia per sapere cosa proporre: con tre numeri selezionati
    si puo' chiedere ambo e terno, non quaterna. E' anche il posto dove si
    chiarisce un equivoco che i fascicoli alimentano - i metodi producono
    *gruppi di numeri* (una terzina), non sorti: sulla terzina poi si gioca
    ambo, e volendo terno.
    """
    return [{"sorte": nome, "numeri_necessari": k, "quota": quota,
             "una_su": round(1 / probabilita_presi(k, k), 1)}
            for nome, (k, quota) in SORTI.items()]
