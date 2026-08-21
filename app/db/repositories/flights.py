"""Persistence operations for flight offers.

Encapsulates the persistent-dedup rule: the same itinerary (identity_key)
for the same search is always one `FlightOffer` row, updated in place, with
one new `PriceHistory` row appended on every check.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FlightOffer, PersistedFlightSegment, PriceHistory
from app.domain.models import RawFlightOffer


def get_by_identity(session: Session, search_id: int, identity_key: str) -> FlightOffer | None:
    return session.scalar(
        select(FlightOffer).where(FlightOffer.search_id == search_id, FlightOffer.identity_key == identity_key)
    )


def _route(raw: RawFlightOffer) -> str:
    return " → ".join([raw.origin] + [segment.arrival_airport for segment in raw.segments])


def _stop_airports(raw: RawFlightOffer) -> str:
    return ",".join(segment.arrival_airport for segment in raw.segments[:-1])


def create_offer(
    session: Session,
    *,
    search_id: int,
    run_id: int,
    identity_key: str,
    raw: RawFlightOffer,
    ticket_type: str,
    verification_status: str,
) -> FlightOffer:
    offer = FlightOffer(
        search_id=search_id,
        first_seen_run_id=run_id,
        last_seen_run_id=run_id,
        departure_date=raw.departure.date(),
        return_date=raw.return_date,
        trip_days=(raw.return_date - raw.departure.date()).days,
        origin=raw.origin,
        destination=raw.destination,
        airline=raw.airlines[0] if raw.airlines else "Unknown airline",
        marketing_airlines=",".join(sorted({s.marketing_airline for s in raw.segments})),
        operating_airlines=",".join(sorted({s.operating_airline for s in raw.segments})),
        price=raw.price,
        currency=raw.currency,
        total_duration_minutes=raw.duration_minutes,
        stops=raw.stops,
        stop_airports=_stop_airports(raw),
        ticket_type=ticket_type,
        verification_status=verification_status,
        booking_source=None,
        booking_url=raw.booking_url,
        provider=raw.provider,
        provider_offer_id=raw.provider_offer_id,
        identity_key=identity_key,
        route=_route(raw),
    )
    session.add(offer)
    session.flush()
    for position, segment in enumerate(raw.segments, start=1):
        session.add(
            PersistedFlightSegment(
                flight_offer_id=offer.id,
                segment_number=position,
                direction="outbound" if position <= raw.outbound_segment_count else "return",
                flight_number=segment.flight_number,
                marketing_airline=segment.marketing_airline,
                operating_airline=segment.operating_airline,
                departure_airport=segment.departure_airport,
                arrival_airport=segment.arrival_airport,
                departure_time=segment.departure_time,
                arrival_time=segment.arrival_time,
                duration_minutes=segment.duration_minutes,
            )
        )
    record_price(session, offer, raw.price, raw.currency, run_id)
    return offer


def refresh_offer(session: Session, offer: FlightOffer, *, run_id: int, raw: RawFlightOffer) -> None:
    """Update a previously-seen itinerary with the latest check's data."""
    offer.last_seen_run_id = run_id
    offer.last_seen_at = datetime.now()
    offer.price = raw.price
    offer.currency = raw.currency
    offer.total_duration_minutes = raw.duration_minutes
    offer.provider_offer_id = raw.provider_offer_id
    offer.booking_url = raw.booking_url or offer.booking_url
    record_price(session, offer, raw.price, raw.currency, run_id)


def record_price(session: Session, offer: FlightOffer, price, currency: str, run_id: int) -> None:
    session.add(PriceHistory(flight_offer_id=offer.id, price=price, currency=currency, search_run_id=run_id))
