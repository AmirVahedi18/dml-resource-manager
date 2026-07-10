"""Engine/session factory. init_engine() must be called once at startup before session_scope() is used."""
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from dml_core.db import models  # noqa: F401  (registers all models on Base.metadata)
from dml_core.db.base import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def _add_missing_columns(engine: Engine) -> None:
    """Additive, non-destructive schema patch for DB files created before a column existed.
    `create_all()` only creates missing *tables*, not missing columns on existing ones, and this
    project has no migration framework -- so newly added nullable columns are backfilled here via
    `ALTER TABLE ... ADD COLUMN`, which SQLite supports without touching existing data."""
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                col_type = column.type.compile(engine.dialect)
                conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}"))


def init_engine(db_path: str, echo: bool = False) -> Engine:
    global _engine, _SessionLocal

    if db_path == ":memory:":
        _engine = create_engine(
            "sqlite:///:memory:",
            echo=echo,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{db_path}", echo=echo, connect_args={"check_same_thread": False}
        )

    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    Base.metadata.create_all(_engine)
    _add_missing_columns(_engine)
    return _engine


def dispose_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


@contextmanager
def session_scope() -> Iterator[Session]:
    if _SessionLocal is None:
        raise RuntimeError("Database engine not initialized; call init_engine() first")
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
