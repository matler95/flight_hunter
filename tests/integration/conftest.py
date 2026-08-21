"""Shared fixtures for integration tests: an isolated in-memory database."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.db.database as database_module
import app.db.models  # noqa: F401  (registers all tables on Base.metadata)


@pytest.fixture()
def session_factory(monkeypatch):
    """A fresh, isolated in-memory SQLite database per test, wired into app.db.database."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    database_module.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(database_module, "SessionLocal", factory)
    # search_engine and notification_service import SessionLocal directly at module
    # load time, so patch their references too.
    import app.services.search_engine as search_engine_module

    monkeypatch.setattr(search_engine_module, "SessionLocal", factory)

    yield factory
    engine.dispose()
