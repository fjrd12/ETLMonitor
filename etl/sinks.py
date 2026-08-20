"""EventSink interface + the SQLite implementation ETL 3 talks to.

Swapping storage later (Dataverse, a central log) means adding a new
EventSink subclass — ETL 1/2 and the dashboard generator never import
sqlite/SQLAlchemy directly, only this module's ABC.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from etl.models import (
    Base,
    ErrorEvent,
    ErrorEventRow,
    EventMeta,
    EventMetaFieldRow,
    EventMetaRow,
    Message,
    MessageRow,
    Valuation,
    ValuationRow,
)

# (view_name, SELECT body) — created after the schema, dropped/recreated each
# run so they stay in sync with the tables. Kept as plain SQL: SQLite has no
# materialized views, and these are cheap enough to compute on read.
AGGREGATE_VIEWS: list[tuple[str, str]] = [
    (
        "agg_monthly",
        """
        SELECT strftime('%Y-%m', event_date) AS month,
               COUNT(*) AS event_count,
               COALESCE(SUM(amount), 0) AS total_amount
        FROM ErrorEvents
        GROUP BY month
        """,
    ),
    (
        "agg_by_system",
        """
        SELECT server, sndprn, rcvprn,
               COUNT(*) AS event_count,
               COALESCE(SUM(amount), 0) AS total_amount
        FROM ErrorEvents
        GROUP BY server, sndprn, rcvprn
        """,
    ),
    (
        "agg_by_error_type",
        """
        SELECT mestyp, status,
               COUNT(*) AS event_count,
               COALESCE(SUM(amount), 0) AS total_amount
        FROM ErrorEvents
        GROUP BY mestyp, status
        """,
    ),
    (
        "agg_cost",
        """
        SELECT server,
               COUNT(*) AS event_count,
               COALESCE(SUM(amount), 0) AS total_amount,
               currency
        FROM ErrorEvents
        WHERE amount IS NOT NULL
        GROUP BY server, currency
        """,
    ),
    (
        "agg_valuation_by_type",
        """
        SELECT mestyp, valuation_type, valuation_unit,
               COUNT(*) AS event_count,
               COALESCE(SUM(valuation_value), 0) AS total_value
        FROM ErrorEvents
        GROUP BY mestyp, valuation_type, valuation_unit
        """,
    ),
]


class EventSink(ABC):
    @abstractmethod
    def upsert_event(self, event: ErrorEvent) -> None: ...

    @abstractmethod
    def upsert_messages(self, event_uuid: str, messages: list[Message]) -> None: ...

    @abstractmethod
    def upsert_meta(self, event_uuid: str, meta: list[EventMeta]) -> None: ...

    @abstractmethod
    def upsert_valuations(self, event_uuid: str, valuations: list[Valuation]) -> None: ...


class SqliteEventSink(EventSink):
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(self._engine)
        self._create_views()

    def _create_views(self) -> None:
        with self._engine.begin() as conn:
            for name, body in AGGREGATE_VIEWS:
                conn.execute(text(f"DROP VIEW IF EXISTS {name}"))
                conn.execute(text(f"CREATE VIEW {name} AS {body}"))

    def upsert_event(self, event: ErrorEvent) -> None:
        with Session(self._engine) as session:
            row = session.get(ErrorEventRow, event.event_uuid)
            if row is None:
                row = ErrorEventRow(event_uuid=event.event_uuid)
                session.add(row)
            row.docnum = event.docnum
            row.server = event.server
            row.sndprn = event.sndprn
            row.rcvprn = event.rcvprn
            row.mestyp = event.mestyp
            row.idoctp = event.idoctp
            row.status = event.status
            row.event_date = event.event_date
            row.event_time = event.event_time
            row.uname = event.uname
            row.statxt = event.statxt
            row.amount = event.amount
            row.currency = event.currency
            row.severity = event.severity
            row.monetized = event.monetized
            row.valuation_type = event.valuation_type
            row.valuation_value = event.valuation_value
            row.valuation_unit = event.valuation_unit
            row.valuation_status = event.valuation_status
            row.valuation_source = event.valuation_source
            row.loaded_at = event.loaded_at
            session.commit()

    def upsert_messages(self, event_uuid: str, messages: list[Message]) -> None:
        with Session(self._engine) as session:
            session.query(MessageRow).filter_by(event_uuid=event_uuid).delete()
            for m in messages:
                session.add(
                    MessageRow(
                        event_uuid=event_uuid,
                        countr=m.countr,
                        status=m.status,
                        statyp=m.statyp,
                        statxt=m.statxt,
                        uname=m.uname,
                        logdat=m.logdat,
                        logtim=m.logtim,
                    )
                )
            session.commit()

    def upsert_meta(self, event_uuid: str, meta: list[EventMeta]) -> None:
        with Session(self._engine) as session:
            session.query(EventMetaRow).filter_by(event_uuid=event_uuid).delete()
            for m in meta:
                meta_row = EventMetaRow(event_uuid=event_uuid, segment=m.segment)
                meta_row.fields = [
                    EventMetaFieldRow(field_name=f.field_name, field_value=f.field_value) for f in m.fields
                ]
                session.add(meta_row)
            session.commit()

    def upsert_valuations(self, event_uuid: str, valuations: list[Valuation]) -> None:
        with Session(self._engine) as session:
            session.query(ValuationRow).filter_by(event_uuid=event_uuid).delete()
            for v in valuations:
                session.add(
                    ValuationRow(
                        event_uuid=event_uuid,
                        type=v.type,
                        value=v.value,
                        unit=v.unit,
                        source=v.source,
                        status=v.status,
                        is_primary=v.primary,
                    )
                )
            session.commit()
