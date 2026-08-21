from datetime import date
from decimal import Decimal

from fastapi import APIRouter
from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import FlightOffer

router = APIRouter(prefix="/history", tags=["history"])


@router.get("")
def list_history(
    search_id: int | None = None,
    airline: str | None = None,
    status: str | None = None,
    stops: int | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    session = SessionLocal()
    try:
        query = select(FlightOffer).order_by(FlightOffer.id.desc())
        if search_id is not None:
            query = query.where(FlightOffer.search_id == search_id)
        if airline:
            query = query.where(FlightOffer.airline == airline)
        if status:
            query = query.where(FlightOffer.verification_status == status)
        if stops is not None:
            query = query.where(FlightOffer.stops == stops)
        if min_price is not None:
            query = query.where(FlightOffer.price >= min_price)
        if max_price is not None:
            query = query.where(FlightOffer.price <= max_price)
        if date_from is not None:
            query = query.where(FlightOffer.departure_date >= date_from)
        if date_to is not None:
            query = query.where(FlightOffer.departure_date <= date_to)
        offers = session.scalars(query).all()
        return {
            "status": "ok",
            "data": [
                {
                    "id": o.id,
                    "departure_date": o.departure_date.isoformat(),
                    "return_date": o.return_date.isoformat(),
                    "airline": o.airline,
                    "route": o.route,
                    "stops": o.stops,
                    "duration_minutes": o.total_duration_minutes,
                    "price": str(o.price),
                    "currency": o.currency,
                    "status": o.verification_status,
                }
                for o in offers
            ],
        }
    finally:
        session.close()
