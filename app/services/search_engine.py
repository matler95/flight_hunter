"""Background orchestration for real, low-volume flight searches."""

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import FlightOffer, PersistedFlightSegment, PriceHistory, Search, SearchRun
from app.domain.enums import TicketType, VerificationStatus
from app.providers.discovery.google_flights import GoogleFlightsProvider
from app.services.date_generator import generate_date_combinations
from app.services.deduplicator import deduplicate, itinerary_key

logger = logging.getLogger(__name__)
_running_tasks: set[asyncio.Task] = set()


def create_run(search_id: int) -> int:
    session = SessionLocal()
    try:
        search = session.get(Search, search_id)
        if search is None:
            raise LookupError("Search not found")
        existing = session.scalar(
            select(SearchRun).where(SearchRun.search_id == search_id, SearchRun.status == "running")
        )
        if existing is not None:
            return existing.id
        total = len(
            list(
                generate_date_combinations(
                    search.earliest_departure,
                    search.latest_departure,
                    search.min_trip_days,
                    search.max_trip_days,
                    search.latest_return,
                )
            )
        )
        run = SearchRun(search_id=search.id, combinations_total=total, status="running")
        session.add(run)
        session.commit()
        return run.id
    finally:
        session.close()


def enqueue_run(search_id: int) -> int:
    run_id = create_run(search_id)
    task = asyncio.create_task(execute_run(run_id))
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)
    return run_id


async def execute_run(run_id: int) -> None:
    session = SessionLocal()
    try:
        run = session.get(SearchRun, run_id)
        if run is None:
            return
        search = session.get(Search, run.search_id)
        if search is None:
            run.status = "failed"
            run.errors = "Search was deleted before execution."
            session.commit()
            return
        combinations = list(
            generate_date_combinations(
                search.earliest_departure,
                search.latest_departure,
                search.min_trip_days,
                search.max_trip_days,
                search.latest_return,
            )
        )
        provider = GoogleFlightsProvider()
        discovered = []
        errors: list[str] = []
        for departure, returning in combinations:
            run.current_query = f"{search.origin} → {search.destination}: {departure} → {returning}"
            session.commit()
            try:
                discovered.extend(
                    await provider.search(search.origin, search.destination, departure, returning, search.currency)
                )
            except Exception as exc:  # Continue remaining combinations by design.
                message = f"{departure} → {returning}: {type(exc).__name__}: {exc}"
                logger.warning("provider_query_failed run_id=%s %s", run_id, message)
                errors.append(message)
            run.combinations_checked += 1
            session.commit()

        run.offers_found = len(discovered)
        for raw in deduplicate(discovered):
            if raw.stops > search.max_stops:
                continue
            identity = itinerary_key(raw)
            offer = FlightOffer(
                search_run_id=run.id,
                departure_date=raw.departure.date(),
                return_date=raw.return_date,
                trip_days=(raw.return_date - raw.departure.date()).days,
                origin=raw.origin,
                destination=raw.destination,
                airline=raw.airlines[0] if raw.airlines else "Unknown airline",
                price=raw.price,
                currency=raw.currency,
                total_duration_minutes=raw.duration_minutes,
                stops=raw.stops,
                stop_airports=",".join(segment.arrival_airport for segment in raw.segments[:-1]),
                ticket_type=(TicketType.SELF_TRANSFER if raw.is_self_transfer else TicketType.UNKNOWN).value,
                verification_status=VerificationStatus.UNKNOWN.value,
                booking_url=raw.booking_url,
                provider=raw.provider,
                provider_offer_id=raw.provider_offer_id,
                identity_key=identity,
                route=" → ".join([raw.origin] + [segment.arrival_airport for segment in raw.segments]),
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
            session.add(PriceHistory(flight_offer_id=offer.id, price=raw.price, currency=raw.currency))
        run.status = "completed"
        run.finished_at = datetime.now()
        run.current_query = ""
        run.errors = "\n".join(errors)
        search.last_run_at = datetime.now()
        session.commit()
    except Exception as exc:
        session.rollback()
        run = session.get(SearchRun, run_id)
        if run is not None:
            run.status = "failed"
            run.errors = f"Unhandled execution error: {type(exc).__name__}: {exc}"
            run.finished_at = datetime.now()
            session.commit()
        logger.exception("search_run_failed run_id=%s", run_id)
    finally:
        session.close()
