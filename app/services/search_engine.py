"""Background orchestration for a single search run.

Flow (see plan §35): load search -> generate date combinations -> discovery
per combination (continuing past individual failures) -> normalize ->
deduplicate within the run -> persist-or-update itinerary (persistent
dedup across runs, §19/Etap 4) -> filter by max stops -> select cheapest
candidates -> verify up to MAX_OFFERS_TO_VERIFY -> record verification ->
update price history -> check alert rules -> notify -> complete run.
"""

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import Search, SearchRun
from app.db.repositories import flights as flights_repo
from app.db.repositories import runs as runs_repo
from app.domain.enums import TicketType, VerificationStatus
from app.domain.models import NormalizedFlightOffer
from app.providers.discovery.base import FlightDiscoveryProvider
from app.providers.discovery.google_flights import GoogleFlightsProvider
from app.providers.discovery.mock import MockFlightDiscoveryProvider
from app.services.date_generator import generate_date_combinations
from app.services.deduplicator import deduplicate, itinerary_key
from app.services.notification_service import notify_if_eligible
from app.services.verifier import FlightVerifier

logger = logging.getLogger(__name__)
_running_tasks: set[asyncio.Task] = set()


def build_provider() -> FlightDiscoveryProvider:
    if settings.discovery_provider == "mock":
        return MockFlightDiscoveryProvider()
    return GoogleFlightsProvider()


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


def _http_status(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None)


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
        provider = build_provider()
        discovered = []
        error_summaries: list[str] = []
        for departure, returning in combinations:
            run.current_query = f"{search.origin} → {search.destination}: {departure} → {returning}"
            session.commit()
            try:
                discovered.extend(
                    await provider.search(search.origin, search.destination, departure, returning, search.currency)
                )
            except Exception as exc:  # Continue remaining combinations by design (plan §32).
                message = f"{departure} → {returning}: {type(exc).__name__}: {exc}"
                logger.warning("provider_query_failed run_id=%s %s", run_id, message)
                error_summaries.append(message)
                runs_repo.record_provider_error(
                    session,
                    run_id=run.id,
                    provider=getattr(provider, "name", "unknown"),
                    origin=search.origin,
                    destination=search.destination,
                    departure_date=departure,
                    return_date=returning,
                    http_status=_http_status(exc),
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                session.commit()
            run.combinations_checked += 1
            session.commit()

        run.offers_found = len(discovered)
        verification_candidates: list[tuple] = []
        offers_new = 0
        for raw in deduplicate(discovered):
            if raw.stops > search.max_stops:
                continue
            identity = itinerary_key(raw)
            ticket_type = (TicketType.SELF_TRANSFER if raw.is_self_transfer else TicketType.UNKNOWN).value

            existing = flights_repo.get_by_identity(session, search.id, identity)
            if existing is None:
                offer = flights_repo.create_offer(
                    session,
                    search_id=search.id,
                    run_id=run.id,
                    identity_key=identity,
                    raw=raw,
                    ticket_type=ticket_type,
                    verification_status=VerificationStatus.DISCOVERED.value,
                )
                offers_new += 1
            else:
                offer = existing
                flights_repo.refresh_offer(session, offer, run_id=run.id, raw=raw)
            session.flush()

            verification_candidates.append(
                (
                    offer,
                    NormalizedFlightOffer(
                        **raw.model_dump(),
                        ticket_type=TicketType.SELF_TRANSFER if raw.is_self_transfer else TicketType.UNKNOWN,
                    ),
                )
            )

        run.offers_new = offers_new
        verifier = FlightVerifier()
        for offer, normalized in sorted(verification_candidates, key=lambda candidate: candidate[0].price)[
            : settings.max_offers_to_verify
        ]:
            status, ticket_type, booking_source, booking_url = await verifier.verify(normalized, provider)
            offer.verification_status = status.value
            offer.ticket_type = ticket_type.value
            offer.booking_source = booking_source
            if booking_url:
                offer.booking_url = booking_url
            run.offers_verified += int(status is VerificationStatus.VERIFIED)
            try:
                await notify_if_eligible(session, offer, search)
            except Exception as exc:
                error_summaries.append(f"notification offer={offer.id}: {type(exc).__name__}: {exc}")

        run.status = "completed"
        run.finished_at = datetime.now()
        run.current_query = ""
        run.errors = "\n".join(error_summaries)
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
