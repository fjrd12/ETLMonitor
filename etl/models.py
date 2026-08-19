"""Pydantic ingest models, EventSink domain DTOs, and SQLAlchemy warehouse rows."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------------------------------------------------------------------------
# Ingest models (validate landing-zone JSON before anything touches disk state)
# ---------------------------------------------------------------------------

class CtrlControl(BaseModel):
    model_config = ConfigDict(extra="allow")

    MANDT: str
    DOCNUM: int
    STATUS: str
    SNDPRN: str
    RCVPRN: str
    CREDAT: str
    CRETIM: str
    MESTYP: str
    IDOCTP: str


class CtrlRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    GLOBAL_UUID: str
    CONTROL: CtrlControl


class StatRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    MANDT: str
    DOCNUM: int
    LOGDAT: str
    LOGTIM: str
    COUNTR: int
    STATUS: str
    UNAME: str
    STATXT: str
    SEGNUM: int
    STATYP: str


# ---------------------------------------------------------------------------
# EventSink domain DTOs — the only vocabulary ETL 3 speaks to a sink in.
# Plain dataclasses, deliberately storage-agnostic (see architecture.html §3).
# ---------------------------------------------------------------------------

@dataclass
class MetaField:
    field_name: str
    field_value: str


@dataclass
class EventMeta:
    segment: str
    fields: list[MetaField] = field(default_factory=list)


@dataclass
class Message:
    countr: int
    status: str
    statyp: str
    statxt: str
    uname: str
    logdat: dt.date
    logtim: str


@dataclass
class ErrorEvent:
    event_uuid: str
    docnum: int
    server: str
    sndprn: str
    rcvprn: str
    mestyp: str
    idoctp: str
    status: str
    event_date: dt.date
    event_time: str
    uname: str
    statxt: str
    loaded_at: dt.datetime
    amount: float | None = None
    currency: str | None = None
    severity: str = "unknown"
    monetized: bool = False


# ---------------------------------------------------------------------------
# Warehouse (ETL 3) ORM rows — SqliteEventSink's private storage shape.
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class ErrorEventRow(Base):
    __tablename__ = "ErrorEvents"

    event_uuid: Mapped[str] = mapped_column(String, primary_key=True)
    docnum: Mapped[int] = mapped_column(Integer, index=True)
    server: Mapped[str] = mapped_column(String, index=True)
    sndprn: Mapped[str] = mapped_column(String)
    rcvprn: Mapped[str] = mapped_column(String)
    mestyp: Mapped[str] = mapped_column(String, index=True)
    idoctp: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    event_date: Mapped[dt.date] = mapped_column(Date, index=True)
    event_time: Mapped[str] = mapped_column(String)
    uname: Mapped[str] = mapped_column(String)
    statxt: Mapped[str] = mapped_column(Text)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String, nullable=True)
    severity: Mapped[str] = mapped_column(String, default="unknown")
    monetized: Mapped[bool] = mapped_column(default=False)
    loaded_at: Mapped[dt.datetime] = mapped_column(DateTime)

    meta: Mapped[list["EventMetaRow"]] = relationship(back_populates="event", cascade="all, delete-orphan")
    messages: Mapped[list["MessageRow"]] = relationship(back_populates="event", cascade="all, delete-orphan")


class EventMetaRow(Base):
    __tablename__ = "Event_Meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_uuid: Mapped[str] = mapped_column(ForeignKey("ErrorEvents.event_uuid"), index=True)
    segment: Mapped[str] = mapped_column(String)

    event: Mapped[ErrorEventRow] = relationship(back_populates="meta")
    fields: Mapped[list["EventMetaFieldRow"]] = relationship(back_populates="meta", cascade="all, delete-orphan")


class EventMetaFieldRow(Base):
    __tablename__ = "Event_meta_field"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meta_id: Mapped[int] = mapped_column(ForeignKey("Event_Meta.id"), index=True)
    field_name: Mapped[str] = mapped_column(String)
    field_value: Mapped[str] = mapped_column(Text)

    meta: Mapped[EventMetaRow] = relationship(back_populates="fields")


class MessageRow(Base):
    __tablename__ = "Messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_uuid: Mapped[str] = mapped_column(ForeignKey("ErrorEvents.event_uuid"), index=True)
    countr: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String)
    statyp: Mapped[str] = mapped_column(String)
    statxt: Mapped[str] = mapped_column(Text)
    uname: Mapped[str] = mapped_column(String)
    logdat: Mapped[dt.date] = mapped_column(Date)
    logtim: Mapped[str] = mapped_column(String)

    event: Mapped[ErrorEventRow] = relationship(back_populates="messages")
