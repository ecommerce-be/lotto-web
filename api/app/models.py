"""
Modello dati di App Lotto.

Tre concetti, e uno solo di questi e' un fatto: l'estrazione.
  Estrazione  — cosa e' uscito. Dato oggettivo, immutabile.
  Previsione  — cosa un metodo ha suggerito a partire da una certa estrazione.
  Sorte       — ogni singola giocata dentro una previsione (l'ambata, ciascun
                ambo, la terzina...), perche' ognuna ha un esito proprio.
  Esito       — quando e dove una sorte si e' verificata. Zero, uno o piu' per
                sorte: lo stesso ambo puo' uscire su due ruote.

La separazione Sorte/Esito e' cio' che permette di dire la verita' all'utente:
quanto e' costata una previsione, quanto ha reso, e quali sorti sono ancora
in corso. Senza, si potrebbe solo dire "ha vinto" senza sapere quanto.
"""
from __future__ import annotations
import enum
from datetime import date, datetime

from sqlalchemy import (Boolean, Date, DateTime, Enum, ForeignKey, Integer,
                        SmallInteger, String, Text, UniqueConstraint, func, Index)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Ruota(str, enum.Enum):
    BA = "BA"; CA = "CA"; FI = "FI"; GE = "GE"; MI = "MI"
    NA = "NA"; PA = "PA"; RM = "RM"; TO = "TO"; VE = "VE"
    RN = "RN"          # Nazionale, dal 2005: esclusa dai metodi

    @classmethod
    def classiche(cls) -> list["Ruota"]:
        return [r for r in cls if r is not cls.RN]


class Metodo(str, enum.Enum):
    LOTTOFACILE1 = "lottofacile1"
    LOTTOFACILE4 = "lottofacile4"
    LOTTOFACILE5 = "lottofacile5"
    FULMINE = "fulmine"
    UN_SOLO_AMBO_SECCO = "unsoloambosecco"
    AMBO_SECCO_CAOTICO = "ambosecco_caotico"


class TipoSorte(str, enum.Enum):
    AMBATA = "ambata"
    AMBO = "ambo"
    TERZINA = "terzina"      # giocata per ambo e terno
    QUARTINA = "quartina"    # giocata per ambo e terno


class StatoSorte(str, enum.Enum):
    APERTA = "aperta"        # colpi ancora disponibili
    VINTA = "vinta"          # si e' verificata, gioco sospeso
    SCADUTA = "scaduta"      # colpi esauriti senza esito


class Estrazione(Base):
    """Un concorso, una ruota, cinque numeri IN ORDINE DI ESTRAZIONE.

    L'ordine e' sostanza, non presentazione: quattro metodi su sei filtrano per
    isotopia (stessa posizione estrazionale su due ruote). Un archivio che
    riordina i numeri per valore rende quei metodi inapplicabili senza dirlo.
    """
    __tablename__ = "estrazione"
    __table_args__ = (
        UniqueConstraint("data", "ruota", name="uq_estrazione_data_ruota"),
        Index("ix_estrazione_data", "data"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    ruota: Mapped[Ruota] = mapped_column(Enum(Ruota, name="ruota"), nullable=False)
    numeri: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), nullable=False)

    def __repr__(self) -> str:
        return f"<Estrazione {self.data} {self.ruota.value} {self.numeri}>"


class Previsione(Base):
    """Cosa un metodo ha suggerito a partire dall'estrazione di `data_rilevamento`."""
    __tablename__ = "previsione"
    __table_args__ = (
        Index("ix_previsione_data_metodo", "data_rilevamento", "metodo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    metodo: Mapped[Metodo] = mapped_column(Enum(Metodo, name="metodo"), nullable=False)
    data_rilevamento: Mapped[date] = mapped_column(Date, nullable=False)
    ruote: Mapped[list[str]] = mapped_column(ARRAY(String(2)), nullable=False)
    colpi: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    anche_tutte: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # nota dello scanner: posizioni, somma comune, rilevamento di partenza...
    nota: Mapped[str | None] = mapped_column(Text)
    # avviso non bloccante (es. LottoFacile 5 "potenza ridotta")
    avviso: Mapped[str | None] = mapped_column(Text)
    creata_il: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)

    sorti: Mapped[list["Sorte"]] = relationship(
        back_populates="previsione", cascade="all, delete-orphan", lazy="selectin")

    def __repr__(self) -> str:
        return (f"<Previsione {self.metodo.value} {self.data_rilevamento} "
                f"{'-'.join(self.ruote)}>")


class Sorte(Base):
    """Una singola giocata dentro una previsione, con il suo stato."""
    __tablename__ = "sorte"
    __table_args__ = (
        Index("ix_sorte_stato", "stato"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    previsione_id: Mapped[int] = mapped_column(
        ForeignKey("previsione.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo: Mapped[TipoSorte] = mapped_column(Enum(TipoSorte, name="tipo_sorte"), nullable=False)
    numeri: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), nullable=False)
    stato: Mapped[StatoSorte] = mapped_column(
        Enum(StatoSorte, name="stato_sorte"), default=StatoSorte.APERTA, nullable=False)
    # quanti colpi sono gia' stati valutati: rende la rivalutazione idempotente
    colpi_valutati: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)

    previsione: Mapped[Previsione] = relationship(back_populates="sorti")
    esiti: Mapped[list["Esito"]] = relationship(
        back_populates="sorte", cascade="all, delete-orphan", lazy="selectin")


class Esito(Base):
    """Quando e dove una sorte si e' verificata."""
    __tablename__ = "esito"
    __table_args__ = (
        UniqueConstraint("sorte_id", "data", "ruota", name="uq_esito_sorte_data_ruota"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sorte_id: Mapped[int] = mapped_column(
        ForeignKey("sorte.id", ondelete="CASCADE"), nullable=False, index=True)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    ruota: Mapped[Ruota] = mapped_column(Enum(Ruota, name="ruota"), nullable=False)
    colpo: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # numeri della sorte effettivamente usciti (2 per un ambo, 3 per un terno
    # in terzina): serve a distinguere un ambo in quartina da un terno
    numeri_usciti: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), nullable=False)
    # true quando la sorte era giocata a Tutte e l'uscita e' su una ruota
    # diversa da quelle di rilevamento
    a_tutte: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    sorte: Mapped[Sorte] = relationship(back_populates="esiti")
