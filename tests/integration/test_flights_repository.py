from datetime import date
from decimal import Decimal

from app.db.models import FlightOffer, PriceHistory, Search, SearchRun
from app.db.repositories import flights as flights_repo


def _make_offer(session) -> FlightOffer:
    search = Search(
        name="Test",
        origin="WAW",
        destination="TYO",
        earliest_departure=date(2026, 10, 29),
        latest_departure=date(2026, 11, 1),
        min_trip_days=13,
        max_trip_days=16,
        latest_return=date(2026, 11, 16),
        target_price=Decimal("3500"),
        currency="PLN",
        max_stops=1,
    )
    session.add(search)
    session.commit()

    run = SearchRun(search_id=search.id, combinations_total=1, status="running")
    session.add(run)
    session.commit()

    offer = FlightOffer(
        search_id=search.id,
        first_seen_run_id=run.id,
        last_seen_run_id=run.id,
        departure_date=date(2026, 10, 29),
        return_date=date(2026, 11, 11),
        trip_days=13,
        origin="WAW",
        destination="TYO",
        airline="LOT",
        price=Decimal("3200"),
        currency="PLN",
        total_duration_minutes=630,
        stops=0,
        ticket_type="single_ticket",
        verification_status="discovered",
        provider="mock",
        provider_offer_id="mock-1",
        identity_key="mock-1-key",
        route="WAW → TYO",
    )
    session.add(offer)
    session.commit()
    session.refresh(offer)
    return offer


def test_record_price_skips_unchanged_price(session_factory):
    session = session_factory()
    offer = _make_offer(session)
    run_id = offer.first_seen_run_id

    flights_repo.record_price(session, offer, Decimal("3200"), "PLN", run_id)
    flights_repo.record_price(session, offer, Decimal("3200"), "PLN", run_id)
    flights_repo.record_price(session, offer, Decimal("3200"), "PLN", run_id)
    session.commit()

    assert session.query(PriceHistory).filter_by(flight_offer_id=offer.id).count() == 1


def test_record_price_logs_actual_changes(session_factory):
    session = session_factory()
    offer = _make_offer(session)
    run_id = offer.first_seen_run_id

    flights_repo.record_price(session, offer, Decimal("3200"), "PLN", run_id)
    flights_repo.record_price(session, offer, Decimal("3200"), "PLN", run_id)  # duplicate, skipped
    flights_repo.record_price(session, offer, Decimal("3100"), "PLN", run_id)  # price drop, logged
    flights_repo.record_price(session, offer, Decimal("3100"), "PLN", run_id)  # duplicate, skipped
    flights_repo.record_price(session, offer, Decimal("3250"), "PLN", run_id)  # price rise, logged
    session.commit()

    prices = [
        p.price
        for p in session.query(PriceHistory)
        .filter_by(flight_offer_id=offer.id)
        .order_by(PriceHistory.id)
        .all()
    ]
    assert prices == [Decimal("3200"), Decimal("3100"), Decimal("3250")]
