from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def create_engine_and_sessionmaker(
    sqlite_url: str,
) -> tuple[Engine, sessionmaker]:
    engine = create_engine(
        sqlite_url,
        future=True,
    )
    session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )
    return engine, session_local

