"""
Genera i file che la pagina web legge.

Il sito e' statico: non c'e' niente che possa interrogare l'archivio al volo,
quindi tutto cio' che serve va calcolato qui e scritto come JSON. Il criterio e'
mandare al browser il minimo indispensabile: l'archivio completo e' due mega e
mezzo e non serve a nessuno sul telefono di mia madre, mentre le previsioni in
corso sono qualche decina di righe.

L'ordinamento delle previsioni in corso e' la cosa meno ovvia di questo file.
I sei metodi hanno selettivita' molto diverse - "Lotto Facile 1" scatta
centinaia di volte l'anno, "Fulmine" poche decine - e ordinare per data
significa seppellire il metodo raro sotto quello prolifico, dando l'impressione
che valgano uguale. Qui si ordina per **rarita' del metodo**: cio' che capita di
rado viene prima, e accanto c'e' scritto quanto di rado capita.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, time, timedelta
from pathlib import Path

from . import economia, fonte
from .archivio import NOMI_RUOTE, RUOTE, Archivio
from .valutazione import colpi_residui

RADICE = Path(__file__).resolve().parent.parent
DATI = RADICE / "archivio"
USCITA = RADICE / "docs" / "dati"

ORA_ESTRAZIONE = time(20, 0)
NOMI_METODI = {
    "lottofacile1": "Lotto Facile — Il Metodo Vincente",
    "lottofacile4": "Lotto Facile 4 — Ciclo-Pondometria",
    "lottofacile5": "Lotto Facile 5 — Rita Calone",
    "fulmine": "Fulmine — Osvaldo Manara",
    "unsoloambosecco": "Un Solo Ambo Secco",
    "ambosecco_caotico": "Ambo Secco Caotico — Antonio Longo",
}


def _scrivi(nome: str, contenuto) -> Path:
    USCITA.mkdir(parents=True, exist_ok=True)
    percorso = USCITA / nome
    percorso.write_text(
        json.dumps(contenuto, ensure_ascii=False, indent=1, sort_keys=True,
                   default=str) + "\n", encoding="utf-8")
    return percorso


def storico(arch: Archivio) -> str:
    """Tutto l'archivio in un file di testo che il browser sa scorrere.

    La ricerca delle ripetizioni deve poter guardare all'indietro di decenni, e
    un sito statico non ha nessuno a cui chiedere: o i dati sono nel browser o
    la ricerca non esiste. Il CSV di partenza pero' e' due mega e mezzo, e il
    telefono di chi usa questo sito non merita due mega e mezzo.

    Da qui il formato: una riga per giorno, la data senza trattini, poi le dieci
    ruote in ordine fisso, cinque numeri a due cifre l'uno, le ruote mancanti
    scritte come trattini. Sono 108 caratteri per riga invece di circa 350, il
    file scende sotto il mega e, servito compresso come qualunque testo, arriva
    a poche centinaia di chilobyte. Resta leggibile a occhio, che in questo
    progetto conta: un file che nessuno puo' controllare e' un file di cui
    bisogna fidarsi.

    La pagina lo carica solo quando si apre la scheda Previsioni: chi guarda
    soltanto la Schedina non lo scarica mai.
    """
    righe = [
        "# Storico delle estrazioni del Lotto.",
        "# Una riga per concorso: data (AAAAMMGG), poi le ruote "
        + " ".join(RUOTE) + ",",
        "# cinque numeri a due cifre ciascuna; '--' se quella ruota non ha estratto.",
        f"# {len(arch.date)} concorsi, dal {arch.date[0]} al {arch.ultima}."
        if arch.date else "# Archivio vuoto.",
    ]
    for giorno in arch.date:
        quadro = arch.quadri.get(giorno, {})
        pezzi = [giorno.strftime("%Y%m%d")]
        for ruota in RUOTE:
            numeri = quadro.get(ruota)
            pezzi.append("".join(f"{n:02d}" for n in numeri) if numeri else "-" * 10)
        righe.append("".join(pezzi))
    return "\n".join(righe) + "\n"


def concorsi_per_anno(arch: Archivio) -> int:
    """Quanti concorsi si tengono in un anno, misurati sull'ultimo anno reale."""
    if not arch.date:
        return 0
    limite = arch.ultima - timedelta(days=365)
    return sum(1 for d in arch.date if d > limite) or 1


def rarita(previsioni: list[dict], arch: Archivio) -> dict[str, dict]:
    """Quanto spesso scatta ciascun metodo, misurato sullo storico rilevato."""
    giorni = {p["giorno"] for p in previsioni}
    if not giorni:
        return {}
    primo, ultimo = min(giorni), max(giorni)
    coperti = sum(1 for d in arch.date if primo <= d.isoformat() <= ultimo) or 1
    per_anno_concorsi = concorsi_per_anno(arch)
    conteggio = Counter(p["metodo"] for p in previsioni)
    return {m: {"rilevamenti": n,
                "per_anno": round(n / coperti * per_anno_concorsi),
                "una_ogni_concorsi": round(coperti / n, 1) if n else None}
            for m, n in conteggio.items()}


def prossime_estrazioni(arch: Archivio, quante: int = 3) -> dict:
    """
    Le prossime date di concorso.

    Attenzione a cosa e' il "calendario ufficiale": l'endpoint
    calendario-estrazioni-del-lotto elenca i giorni del mese in cui un concorso
    **si e' gia' tenuto**, non quelli programmati. Interrogato per i giorni
    futuri risponde con una lista vuota - cosa che si scopre solo in produzione,
    perche' in sviluppo l'archivio era vecchio e sembrava funzionare.

    Quindi la data del prossimo concorso si **proietta** dai giorni della
    settimana in cui si e' estratto negli ultimi mesi. E' affidabile ma non
    infallibile: le feste possono spostare o saltare un concorso. Per questo la
    proiezione viene sempre dichiarata come tale invece di essere spacciata per
    un dato ufficiale - una data sbagliata data per certa e' peggio di una
    dichiarata incerta.

    La fonte viene interrogata lo stesso, prima: se un giorno cominciasse a
    pubblicare il calendario in anticipo, quella risposta ha la precedenza.
    """
    adesso = datetime.now()
    da = adesso.date() if adesso.time() < ORA_ESTRAZIONE \
        else adesso.date() + timedelta(days=1)
    ora = ORA_ESTRAZIONE.strftime("%H:%M")

    irraggiungibile = None
    try:
        ufficiali = [d for d in fonte.calendario(da, mesi=2) if d >= da][:quante]
    except fonte.FonteNonDisponibile as e:
        ufficiali, irraggiungibile = [], str(e)
    if ufficiali:
        return {"date": [d.isoformat() for d in ufficiali], "stimato": False,
                "motivo": None, "ora": ora}

    motivo = (f"Calendario ufficiale non raggiungibile ({irraggiungibile})."
              if irraggiungibile else
              "Il calendario ufficiale elenca solo i concorsi gia' avvenuti.")
    return {"date": [d.isoformat() for d in _stimate(arch, da, quante)],
            "stimato": True, "ora": ora,
            "motivo": motivo + " Date proiettate dai giorni di concorso "
                               "recenti: le feste possono spostarle."}


def _stimate(arch: Archivio, da: date, quante: int) -> list[date]:
    """Ripiego: i giorni della settimana in cui si e' estratto negli ultimi mesi."""
    recenti = [d for d in arch.date if d >= da - timedelta(days=120)]
    conteggio = Counter(d.weekday() for d in recenti)
    # almeno tre occorrenze: un recupero straordinario non entra nella stima
    settimanali = {g for g, n in conteggio.items() if n >= 3}
    if not settimanali:
        return []
    fuori, cursore = [], da
    while len(fuori) < quante and (cursore - da).days < 30:
        if cursore.weekday() in settimanali:
            fuori.append(cursore)
        cursore += timedelta(days=1)
    return fuori


def tutto(arch: Archivio, previsioni: list[dict], *, aggiornato_il=None) -> list[str]:
    """Scrive tutti i file del sito. Torna i nomi scritti."""
    aggiornato_il = aggiornato_il or datetime.now()
    frequenze = rarita(previsioni, arch)

    # ---------------------------------------------------------- in corso
    in_corso = []
    for p in previsioni:
        aperte = [s for s in p["sorti"] if s["stato"] == "aperta"]
        sorti = []
        for s in aperte:
            residui = colpi_residui(p, s, arch)
            if residui <= 0:
                continue
            sorti.append({"tipo": s["tipo"], "numeri": s["numeri"],
                          "colpi_giocati": s["colpi_valutati"], "colpi_residui": residui})
        if not sorti:
            continue
        in_corso.append({
            "chiave": p["chiave"], "metodo": p["metodo"],
            "nome_metodo": NOMI_METODI.get(p["metodo"], p["metodo"]),
            "giorno": p["giorno"], "ruote": p["ruote"], "colpi": p["colpi"],
            "anche_tutte": p["anche_tutte"], "nota": p["nota"], "avviso": p["avviso"],
            "colpi_residui": max(s["colpi_residui"] for s in sorti),
            "per_anno": frequenze.get(p["metodo"], {}).get("per_anno"),
            "sorti": sorti,
        })
    # il metodo raro viene prima: e' il senso di avere sei metodi invece di uno
    in_corso.sort(key=lambda x: (x["per_anno"] or 10 ** 6, x["giorno"]))
    in_corso = [*in_corso]

    # ---------------------------------------------------------- bilancio
    bil = economia.bilancio(previsioni)
    for riga in bil["per_metodo"]:
        riga["nome_metodo"] = NOMI_METODI.get(riga["metodo"], riga["metodo"])
        riga.update(frequenze.get(riga["metodo"], {}))
    bil["riferimento"] = json.loads((DATI / "backtest.json").read_text(encoding="utf-8"))
    bil["riferimento"].pop("_commento", None)

    # ---------------------------------------------------------- stato
    stato = {
        "concorsi": len(arch.date),
        "estrazioni": sum(len(q) for q in arch.quadri.values()),
        "prima_estrazione": arch.date[0].isoformat() if arch.date else None,
        "ultima_estrazione": arch.ultima.isoformat() if arch.ultima else None,
        "previsioni": len(previsioni),
        "aggiornato_il": aggiornato_il.isoformat(timespec="seconds"),
        "quota_crescenti": round(arch.quota_crescenti(), 4),
        "ordine_di_estrazione": arch.ordine_di_estrazione(),
        "ruote": {s: NOMI_RUOTE[s] for s in RUOTE},
        "metodi": NOMI_METODI,
    }

    ultime = [{"giorno": d.isoformat(), "quadro": arch.quadro(d)}
              for d in arch.date[-8:][::-1]]

    scritti = [
        _scrivi("stato.json", stato).name,
        _scrivi("in-corso.json", in_corso).name,
        _scrivi("bilancio.json", bil).name,
        _scrivi("calendario.json", prossime_estrazioni(arch)).name,
        _scrivi("ultime-estrazioni.json", ultime).name,
        _scrivi("quote.json", json.loads((DATI / "quote.json").read_text(encoding="utf-8"))).name,
    ]

    USCITA.mkdir(parents=True, exist_ok=True)
    (USCITA / "storico.txt").write_text(storico(arch), encoding="utf-8")
    scritti.append("storico.txt")
    return scritti
