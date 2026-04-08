from src.config import settings
from src.persistence.protocols import SessionRepository
from src.persistence.repository import InMemorySessionRepository
from src.persistence.sqlite_repository import SQLiteSessionRepository


def create_session_repository() -> SessionRepository:
    backend = settings.repository_backend.lower()

    if backend == "inmemory":
        return InMemorySessionRepository()

    if backend == "sqlite":
        return SQLiteSessionRepository(sqlite_url=settings.sqlite_url)

    msg = (
        "Unsupported repository backend: "
        f"{settings.repository_backend}. "
        "Expected 'inmemory' or 'sqlite'."
    )
    raise ValueError(msg)
