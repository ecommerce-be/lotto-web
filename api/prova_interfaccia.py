"""
Banco di prova dell'interfaccia, senza database.

Serve la pagina vera e i dati finti, tranne la simulazione della schedina che e'
quella autentica (non tocca il database: e' solo aritmetica sulle regole del
gioco). Cosi' si puo' guardare la pagina - anche da un browser automatico - senza
dover avere PostgreSQL acceso.

    python prova_interfaccia.py        # poi http://127.0.0.1:8100/app/
"""
import json
import sys
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

RADICE = Path(__file__).resolve().parent
sys.path.insert(0, str(RADICE))

from app.services import schedina  # noqa: E402

OGGI = date.today()


def _giorno(scarto):
    return (OGGI + timedelta(days=scarto)).isoformat()


FINTI = {
    "/salute": {
        "estrazioni": 73111, "previsioni": 1540,
        "ultima_estrazione": _giorno(-1),
        "ruote": ["BA", "CA", "FI", "GE", "MI", "NA", "PA", "RM", "TO", "VE"],
        "metodi": ["lottofacile1", "fulmine"], "aggiornamento_automatico": True,
    },
    "/servizio/aggiornamento": {
        "attivo": True, "motivo_inattivo": None, "ora": "20:45", "in_corso": False,
        "ultimo_avvio": datetime.now().replace(hour=20, minute=45).isoformat(timespec="seconds"),
        "prossima_esecuzione": None,
        "ultimo_esito": {"ok": True, "concorsi_scaricati": 1, "previsioni_generate": 12,
                         "motivo": None},
    },
    "/prossima-estrazione": {
        "date": [_giorno(1), _giorno(3), _giorno(5)],
        "stimato": False, "motivo": None, "ora": "20:00",
    },
    "/previsioni/aperte": [
        {"id": 1, "metodo": "ambosecco_caotico", "data_rilevamento": _giorno(-1),
         "ruote": ["NA", "MI"], "colpi": 9, "colpi_residui": 8, "anche_tutte": False,
         "nota": "A=41 ripetuto su NA e VE", "avviso": None,
         "sorti": [{"tipo": "ambo", "numeri": [37, 39], "colpi_giocati": 1, "colpi_residui": 8},
                   {"tipo": "ambo", "numeri": [49, 85], "colpi_giocati": 1, "colpi_residui": 8}]},
        {"id": 2, "metodo": "lottofacile4", "data_rilevamento": _giorno(-3),
         "ruote": ["GE", "MI"], "colpi": 14, "colpi_residui": 11, "anche_tutte": True,
         "nota": None, "avviso": None,
         "sorti": [{"tipo": "ambata", "numeri": [29], "colpi_giocati": 3, "colpi_residui": 11},
                   {"tipo": "terzina", "numeri": [59, 74, 89], "colpi_giocati": 3,
                    "colpi_residui": 11}]},
    ],
    "/statistiche/economia": {
        "per_metodo": [
            {"metodo": "lottofacile1", "previsioni": 787, "speso": 9820.0,
             "incassato": 6390.0, "saldo": -3430.0, "ritorno": 0.6507,
             "campione_scarso": False},
            {"metodo": "fulmine", "previsioni": 79, "speso": 1106.0, "incassato": 782.0,
             "saldo": -324.0, "ritorno": 0.7071, "campione_scarso": True},
        ],
        "totale": {"previsioni": 866, "speso": 10926.0, "incassato": 7172.0,
                   "saldo": -3754.0, "ritorno": 0.6564},
        "nota": "Un euro per sorte, per ruota, per colpo.",
        "avvertenza": "Dati finti: questa e' la pagina di prova dell'interfaccia.",
    },
}


class Gestore(BaseHTTPRequestHandler):
    def _invia(self, corpo: bytes, tipo="application/json", codice=200):
        self.send_response(codice)
        self.send_header("Content-Type", f"{tipo}; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        percorso = self.path.split("?")[0]
        if percorso in ("/", "/app", "/app/", "/app/index.html"):
            pagina = (RADICE / "app" / "web" / "index.html").read_bytes()
            return self._invia(pagina, "text/html")
        if percorso in FINTI:
            return self._invia(json.dumps(FINTI[percorso], default=str).encode())
        if percorso == "/schedina/sorti":
            return self._invia(json.dumps(schedina.descrizione_sorti()).encode())
        self._invia(b'{"detail":"non previsto dal banco di prova"}', codice=404)

    def do_POST(self):
        if self.path != "/schedina/simula":
            return self._invia(b'{"detail":"non previsto"}', codice=404)
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"] or 0)))
        try:
            r = schedina.simula(numeri=corpo["numeri"], ruote=corpo["ruote"],
                                sorti=corpo["sorti"], importo=corpo["importo"])
        except schedina.GiocataNonValida as e:
            return self._invia(json.dumps({"detail": str(e)}).encode(), codice=422)
        self._invia(json.dumps(r, default=str).encode())

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8100
    print(f"banco di prova su http://127.0.0.1:{porta}/app/")
    HTTPServer(("127.0.0.1", porta), Gestore).serve_forever()
