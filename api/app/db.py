from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from .config import RADICE, impostazioni
from .models import Base

engine = create_engine(impostazioni.database_url, pool_pre_ping=True, future=True)
SessionLocale = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class DatabaseNonRaggiungibile(RuntimeError):
    """Errore di connessione, riscritto in una forma che si possa leggere."""


def _diagnosi(e: OperationalError) -> str:
    testo = str(e.orig) if e.orig else str(e)
    url = impostazioni.database_url
    # non stampare mai la password nel messaggio d'errore
    if "@" in url and "//" in url:
        schema, _, resto = url.partition("//")
        credenziali, _, host = resto.partition("@")
        utente = credenziali.split(":")[0]
        url = f"{schema}//{utente}:***@{host}"

    if "password" in testo.lower() or "autenticazione" in testo.lower():
        causa = ("Il server PostgreSQL risponde, ma utente o password non sono validi.\n"
                 "Molto probabilmente il database e l'utente non esistono ancora.\n\n"
                 "Crearli (verra' chiesta la password dell'utente postgres):\n"
                 '   & "C:\\Program Files\\PostgreSQL\\16\\bin\\psql.exe" -U postgres '
                 "-c \"CREATE USER lotto WITH PASSWORD 'lotto' CREATEDB;\"\n"
                 '   & "C:\\Program Files\\PostgreSQL\\16\\bin\\createdb.exe" -U postgres '
                 "-O lotto lotto\n\n"
                 "In alternativa, se preferisci usare un utente che hai gia', "
                 "cambia DATABASE_URL nel file .env.")
    elif "does not exist" in testo or "non esiste" in testo:
        causa = ("Il server risponde e le credenziali sono valide, ma il database non esiste.\n\n"
                 '   & "C:\\Program Files\\PostgreSQL\\16\\bin\\createdb.exe" -U postgres '
                 "-O lotto lotto")
    else:
        causa = ("Nessun server PostgreSQL in ascolto all'indirizzo indicato.\n\n"
                 "Se usi il container (porta 5433), dalla cartella api:\n"
                 "   docker compose up -d\n"
                 "   docker compose ps          # deve risultare 'running'\n"
                 "Richiede Docker Desktop avviato.\n\n"
                 "Se invece usi il PostgreSQL installato (porta 5432):\n"
                 "   Get-Service *postgres*\n"
                 "   Start-Service postgresql-x64-16\n\n"
                 "La porta indicata sopra dice a quale dei due stai puntando.")

    return (f"\nNon riesco a connettermi al database.\n\n"
            f"   URL        {url}\n"
            f"   PostgreSQL {testo.strip().splitlines()[0] if testo.strip() else 'nessuna risposta'}\n\n"
            f"{causa}\n")


def verifica_connessione() -> None:
    """Solleva un errore leggibile invece di un traceback di cento righe."""
    try:
        with engine.connect() as c:
            c.execute(text("select 1"))
    except OperationalError as e:
        raise DatabaseNonRaggiungibile(_diagnosi(e)) from None


class MigrazioniNonApplicate(RuntimeError):
    """Lo schema del database non e' allineato alle migrazioni."""


def _revisione_attesa() -> str | None:
    """L'ultima revisione presente fra gli script di migrazione."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        cfg = Config(str(RADICE / "alembic.ini"))
        cfg.set_main_option("script_location", str(RADICE / "migrazioni"))
        return ScriptDirectory.from_config(cfg).get_current_head()
    except Exception:
        return None


def _revisione_applicata() -> str | None:
    with engine.connect() as c:
        try:
            return c.execute(text("select version_num from alembic_version")).scalar()
        except Exception:
            return None


def verifica_schema() -> None:
    """
    Controlla che lo schema sia allineato, senza crearlo di nascosto.

    `create_all` era comodo finche' il modello non esisteva ancora; ora che ci
    sono dati dentro sarebbe pericoloso, perche' crea le tabelle mancanti ma
    NON modifica quelle esistenti: un campo aggiunto al modello resterebbe
    assente nel database e l'errore comparirebbe solo alla prima query.
    """
    verifica_connessione()
    attesa, applicata = _revisione_attesa(), _revisione_applicata()
    if attesa is None:
        return                                   # nessuno script: nulla da verificare
    if applicata == attesa:
        return
    if applicata is None:
        motivo = "Il database non ha ancora nessuna migrazione applicata."
    else:
        motivo = (f"Il database e' alla revisione {applicata}, "
                  f"gli script arrivano alla {attesa}.")
    raise MigrazioniNonApplicate(
        f"\nSchema del database non allineato.\n\n   {motivo}\n\n"
        "Allinealo con:\n"
        "   alembic upgrade head\n\n"
        "Per vedere cosa verrebbe applicato:\n"
        "   alembic history --verbose\n")


def crea_schema() -> None:
    """Mantenuto per compatibilita': oggi si limita a verificare."""
    verifica_schema()


def get_sessione() -> Iterator[Session]:
    """Dipendenza FastAPI."""
    with SessionLocale() as s:
        yield s
