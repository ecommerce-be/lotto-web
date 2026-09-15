"""
L'archivio delle estrazioni: un file CSV, letto in memoria.

Senza database il posto dove vivono i dati e' un file di testo versionato
insieme al codice. Non e' un ripiego: settantaseimila righe stanno in due mega
e mezzo, si leggono in un secondo, e ogni modifica e' visibile in un diff.
Il formato e' quello di Ratio 90, lo stesso da cui l'archivio storico e' stato
scaricato:

    1939-01-07;BA;Bari;58;22;47;49;69

Il controllo che non va tolto e' `quota_crescenti`. Molti archivi in giro
riordinano i cinque numeri per valore; se succede, i metodi che filtrano per
isotopia (la posizione di estrazione) continuano a girare ma misurano
qualcos'altro, senza che nulla lo segnali. Cinque numeri gia' in ordine
crescente per puro caso capitano una volta su 120, cioe' lo 0,83%: una quota
molto piu' alta e' la firma di un archivio riordinato.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

RUOTE: tuple[str, ...] = ("BA", "CA", "FI", "GE", "MI", "NA", "PA", "RM", "TO", "VE")
NAZIONALE = "RN"          # dal 2005, esclusa dai metodi: i fascicoli non la conoscono

NOMI_RUOTE = {
    "BA": "Bari", "CA": "Cagliari", "FI": "Firenze", "GE": "Genova", "MI": "Milano",
    "NA": "Napoli", "PA": "Palermo", "RM": "Roma", "TO": "Torino", "VE": "Venezia",
    "RN": "Nazionale",
}


class ArchivioNonTrovato(FileNotFoundError):
    pass


class Archivio:
    """Tutte le estrazioni, indicizzate per giorno e ruota."""

    def __init__(self, quadri: dict[date, dict[str, list[int]]]):
        self.quadri = quadri
        self._date: list[date] | None = None

    # ------------------------------------------------------------ lettura
    @classmethod
    def carica(cls, percorso: Path) -> "Archivio":
        if not percorso.is_file():
            raise ArchivioNonTrovato(
                f"Archivio non trovato: {percorso}\n"
                "E' il file con lo storico delle estrazioni, versionato nel "
                "repository: se manca, il repository non e' completo.")
        quadri: dict[date, dict[str, list[int]]] = {}
        with percorso.open(encoding="utf-8", newline="") as f:
            for riga in csv.reader(f, delimiter=";"):
                letta = cls._leggi_riga(riga)
                if letta is None:
                    continue
                giorno, ruota, numeri = letta
                quadri.setdefault(giorno, {})[ruota] = numeri
        return cls(quadri)

    @staticmethod
    def _leggi_riga(riga: list[str]) -> tuple[date, str, list[int]] | None:
        """Una riga malformata viene saltata, non fa cadere l'import."""
        if len(riga) < 8:
            return None
        try:
            giorno = date.fromisoformat(riga[0].strip())
            ruota = riga[1].strip().upper()
            numeri = [int(x) for x in riga[3:8]]
        except ValueError:
            return None
        if ruota not in RUOTE and ruota != NAZIONALE:
            return None
        if len(numeri) != 5 or len(set(numeri)) != 5:
            return None
        if not all(1 <= n <= 90 for n in numeri):
            return None
        return giorno, ruota, numeri

    # ------------------------------------------------------------ lettura comoda
    @property
    def date(self) -> list[date]:
        if self._date is None:
            self._date = sorted(self.quadri)
        return self._date

    @property
    def ultima(self) -> date | None:
        return self.date[-1] if self.date else None

    def quadro(self, giorno: date, *, solo_classiche: bool = True) -> dict[str, list[int]]:
        q = self.quadri.get(giorno, {})
        return {r: n for r, n in q.items() if r in RUOTE} if solo_classiche else dict(q)

    def completo(self, giorno: date) -> bool:
        """Un concorso serve solo se ci sono tutte e dieci le ruote classiche."""
        return len(self.quadro(giorno)) == len(RUOTE)

    def date_dopo(self, giorno: date) -> list[date]:
        return [d for d in self.date if d > giorno]

    # ------------------------------------------------------------ scrittura
    def aggiungi(self, giorno: date, quadro: dict[str, list[int]]) -> int:
        """Inserisce o sostituisce un concorso. Torna quante ruote ha scritto."""
        pulito = {r.upper(): list(n) for r, n in quadro.items()
                  if r.upper() in RUOTE or r.upper() == NAZIONALE}
        if not pulito:
            return 0
        self.quadri.setdefault(giorno, {}).update(pulito)
        self._date = None
        return len(pulito)

    def salva(self, percorso: Path) -> None:
        """Riscrive il file per intero, ordinato: cosi' il diff resta leggibile."""
        temporaneo = percorso.with_suffix(percorso.suffix + ".tmp")
        with temporaneo.open("w", encoding="utf-8", newline="") as f:
            scrittore = csv.writer(f, delimiter=";", lineterminator="\n")
            for giorno in sorted(self.quadri):
                for ruota in sorted(self.quadri[giorno]):
                    scrittore.writerow([giorno.isoformat(), ruota, NOMI_RUOTE[ruota],
                                        *self.quadri[giorno][ruota]])
        temporaneo.replace(percorso)

    # ------------------------------------------------------------ diagnosi
    def quota_crescenti(self, ultimi: int = 5000) -> float:
        """Quota di quadri con i cinque numeri gia' in ordine crescente."""
        campione = [n for g in self.date[-ultimi:] for n in self.quadro(g).values()]
        if not campione:
            return 0.0
        return sum(1 for n in campione if n == sorted(n)) / len(campione)

    def ordine_di_estrazione(self, ultimi: int = 5000) -> bool:
        # 0,83% atteso dal caso; sopra il 5% l'archivio e' certamente riordinato
        return self.quota_crescenti(ultimi) < 0.05
