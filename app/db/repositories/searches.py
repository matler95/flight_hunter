"""Persistence operations for searches."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Search


def get(session: Session, search_id: int) -> Search | None:
    return session.get(Search, search_id)


def list_all(session: Session) -> list[Search]:
    return list(session.scalars(select(Search).order_by(Search.created_at.desc())).all())


def list_active_with_schedule(session: Session, schedule: str) -> list[Search]:
    return list(
        session.scalars(select(Search).where(Search.active.is_(True), Search.schedule == schedule)).all()
    )
