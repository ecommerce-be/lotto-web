from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

RADICE = Path(__file__).resolve().parent.parent      # .../App_Lotto/api


class Impostazioni(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=RADICE / ".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://lotto:lotto@localhost:5432/lotto"
    archivio_csv: Path = RADICE.parent / "docs" / "lotto-archivio-completo-1939-oggi.csv"
    # la Nazionale non entra nei metodi: e' nata nel 2005 e i fascicoli
    # ragionano sulle dieci ruote storiche
    includi_nazionale: bool = False

    # L'aggiornamento serale vive dentro l'applicazione invece che nell'utilita'
    # di pianificazione di Windows, che su questo profilo non e' accessibile.
    # Metterlo a false ha senso solo se si torna a schedularlo da fuori: due
    # aggiornamenti che partono per conto loro non si danneggiano (il ciclo ha un
    # lucchetto), ma raddoppiano le chiamate alla fonte per niente.
    aggiornamento_automatico: bool = True
    ora_aggiornamento: str = "20:45"          # ora locale, HH:MM. L'estrazione e' alle 20


impostazioni = Impostazioni()
