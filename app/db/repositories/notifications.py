"""Persistence operations for notifications."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Notification


def already_sent(session: Session, flight_offer_id: int, notification_type: str, price) -> bool:
    return (
        session.scalar(
            select(Notification.id).where(
                Notification.flight_offer_id == flight_offer_id,
                Notification.notification_type == notification_type,
                Notification.price == price,
            )
        )
        is not None
    )


def record_sent(session: Session, flight_offer_id: int, notification_type: str, price) -> Notification:
    notification = Notification(flight_offer_id=flight_offer_id, notification_type=notification_type, price=price)
    session.add(notification)
    return notification
