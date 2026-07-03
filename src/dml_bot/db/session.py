"""Engine/session factory. init_engine() must be called once at startup before session_scope() is used."""
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from dml_bot.db import models  # noqa: F401  (registers all models on Base.metadata)
from dml_bot.db.base import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


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
