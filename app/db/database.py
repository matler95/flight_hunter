from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def ensure_additive_schema() -> None:
    """Apply safe additive SQLite upgrades until Alembic revisions are introduced."""
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    if "searches" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("searches")}
        if "schedule" not in columns:
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE searches ADD COLUMN schedule VARCHAR(20) NOT NULL DEFAULT 'manual'")
                )
    if "flight_offers" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("flight_offers")}
        if "booking_source" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE flight_offers ADD COLUMN booking_source VARCHAR(80)"))
    if "search_runs" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("search_runs")}
        if "current_query" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE search_runs ADD COLUMN current_query TEXT NOT NULL DEFAULT ''"))
