from __future__ import annotations

import os
from pathlib import Path

import pytest

# Test environment defaults must be set at import time, before test modules
# import application code that reads Settings().
os.environ["AGENTOPS_LLM_BACKEND"] = "mock"
os.environ["AGENTOPS_REPOSITORY_BACKEND"] = "inmemory"
os.environ["AGENTOPS_ENVIRONMENT"] = "test"

from src.persistence.sqlite_repository import SQLiteSessionRepository


@pytest.fixture
def sqlite_repository(tmp_path: Path) -> SQLiteSessionRepository:
    db_path = tmp_path / "test_agentops_triage.db"
    sqlite_url = f"sqlite:///{db_path}"
    return SQLiteSessionRepository(sqlite_url=sqlite_url)

