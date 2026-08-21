from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.db.database import SessionLocal

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health_check() -> dict:
    database_status = "ok"
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - defensive
        database_status = f"error: {type(exc).__name__}"
    finally:
        session.close()
    return {
        "status": "ok",
        "data": {"provider": settings.discovery_provider, "database": database_status},
    }
