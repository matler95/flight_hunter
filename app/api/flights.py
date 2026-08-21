from fastapi import APIRouter, HTTPException

from app.db.database import SessionLocal
from app.db.models import FlightOffer

router = APIRouter(prefix="/flights", tags=["flights"])


def _serialize(offer: FlightOffer) -> dict:
    return {
        "id": offer.id,
        "search_id": offer.search_id,
        "origin": offer.origin,
        "destination": offer.destination,
        "departure_date": offer.departure_date.isoformat(),
        "return_date": offer.return_date.isoformat(),
        "trip_days": offer.trip_days,
        "airline": offer.airline,
        "price": str(offer.price),
        "currency": offer.currency,
        "stops": offer.stops,
        "route": offer.route,
        "ticket_type": offer.ticket_type,
        "verification_status": offer.verification_status,
        "booking_url": offer.booking_url,
        "first_seen_at": offer.first_seen_at.isoformat(),
        "last_seen_at": offer.last_seen_at.isoformat(),
        "price_history": [
            {"price": str(p.price), "currency": p.currency, "checked_at": p.checked_at.isoformat()}
            for p in offer.prices
        ],
    }


@router.get("/{offer_id}")
def get_flight(offer_id: int) -> dict:
    session = SessionLocal()
    try:
        offer = session.get(FlightOffer, offer_id)
        if offer is None:
            raise HTTPException(404, detail={"status": "error", "error": {"code": "FLIGHT_NOT_FOUND", "message": "Flight not found"}})
        return {"status": "ok", "data": _serialize(offer)}
    finally:
        session.close()
