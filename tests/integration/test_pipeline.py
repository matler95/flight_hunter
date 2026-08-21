"""Full-pipeline integration tests, run entirely offline via the mock provider.

Covers plan §41 (integration) and the persistent-dedup / price-history /
notification-dedup requirements from Etap 3-4 of the repo's own
IMPLEMENTATION_PLAN.md.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.db.models import (
    FlightOffer,
    Notification,
    PriceHistory,
    ProviderError,
    Search,
    SearchRun,
)
from app.providers.discovery.mock import MockFlightDiscoveryProvider
from app.services import search_engine


def _make_search(session) -> Search:
    search = Search(
        name="Japan November 2026",
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
    session.refresh(search)
    return search


@pytest.fixture(autouse=True)
def _use_mock_provider(monkeypatch):
    monkeypatch.setattr(search_engine, "build_provider", lambda: MockFlightDiscoveryProvider())


@pytest.fixture()
def _capture_telegram(monkeypatch):
    sent = []

    async def fake_send(self, message, booking_url=None):
        sent.append((message, booking_url))

    monkeypatch.setattr(
        "app.notifications.telegram.TelegramNotificationProvider.send_price_alert", fake_send
    )
    return sent


@pytest.mark.asyncio
async def test_full_pipeline_persists_offers_and_verifies_and_alerts(session_factory, _capture_telegram):
    session = session_factory()
    search = _make_search(session)
    run = SearchRun(search_id=search.id, combinations_total=15, status="running")
    session.add(run)
    session.commit()
    run_id = run.id
    session.close()

    await search_engine.execute_run(run_id)

    session = session_factory()
    run = session.get(SearchRun, run_id)
    assert run.status == "completed"
    assert run.combinations_checked == run.combinations_total == 15
    # 15 date combinations x 3 mock itineraries, all within max_stops=1.
    assert run.offers_found == 45
    assert run.offers_new == 45
    # MAX_OFFERS_TO_VERIFY caps verification, not discovery.
    assert run.offers_verified <= 10

    offers = session.query(FlightOffer).all()
    assert len(offers) == 45
    verified = [o for o in offers if o.verification_status == "verified"]
    assert len(verified) == run.offers_verified
    assert all(o.ticket_type == "single_ticket" for o in verified)

    # All mock prices (3200/3218/3341) are below the 3500 target, so every
    # verified offer should be alert-eligible and attempt a Telegram send.
    assert len(_capture_telegram) == run.offers_verified
    assert session.query(Notification).count() == run.offers_verified


@pytest.mark.asyncio
async def test_persistent_dedup_across_runs_updates_instead_of_duplicating(session_factory):
    session = session_factory()
    search = _make_search(session)
    run1 = SearchRun(search_id=search.id, combinations_total=15, status="running")
    session.add(run1)
    session.commit()
    run1_id = run1.id
    search_id = search.id
    session.close()

    await search_engine.execute_run(run1_id)

    session = session_factory()
    assert session.query(FlightOffer).count() == 45
    assert session.query(PriceHistory).count() == 45
    first_seen = {o.id: o.first_seen_at for o in session.query(FlightOffer).all()}
    session.close()

    session = session_factory()
    run2 = SearchRun(search_id=search_id, combinations_total=15, status="running")
    session.add(run2)
    session.commit()
    run2_id = run2.id
    session.close()

    await search_engine.execute_run(run2_id)

    session = session_factory()
    offers = session.query(FlightOffer).all()
    # Same itineraries found again: no duplicate rows...
    assert len(offers) == 45
    # ...but a price-history row was appended for every one of them.
    assert session.query(PriceHistory).count() == 90
    # Identity is stable and first_seen_at does not move.
    for offer in offers:
        assert offer.first_seen_at == first_seen[offer.id]
        assert offer.last_seen_run_id == run2_id


@pytest.mark.asyncio
async def test_provider_error_on_one_combination_does_not_abort_the_run(session_factory, monkeypatch):
    monkeypatch.setattr(
        search_engine,
        "build_provider",
        lambda: MockFlightDiscoveryProvider(fail_dates={(date(2026, 10, 30), date(2026, 11, 12))}),
    )
    session = session_factory()
    search = _make_search(session)
    run = SearchRun(search_id=search.id, combinations_total=15, status="running")
    session.add(run)
    session.commit()
    run_id = run.id
    session.close()

    await search_engine.execute_run(run_id)

    session = session_factory()
    run = session.get(SearchRun, run_id)
    # The whole run still completes...
    assert run.status == "completed"
    assert run.combinations_checked == run.combinations_total == 15
    # ...one combination's worth of offers (3) is simply missing...
    assert run.offers_found == 42
    # ...and the failure is recorded structurally, without aborting anything.
    errors = session.query(ProviderError).all()
    assert len(errors) == 1
    assert errors[0].origin == "WAW"
    assert errors[0].departure_date == date(2026, 10, 30)
    assert errors[0].return_date == date(2026, 11, 12)
    assert "ProviderQueryError" in errors[0].error_type


@pytest.mark.asyncio
async def test_same_price_does_not_send_a_duplicate_alert(session_factory, _capture_telegram):
    session = session_factory()
    search = _make_search(session)
    search_id = search.id
    run = SearchRun(search_id=search.id, combinations_total=15, status="running")
    session.add(run)
    session.commit()
    run_id = run.id
    session.close()

    await search_engine.execute_run(run_id)
    first_run_alerts = len(_capture_telegram)
    assert first_run_alerts > 0

    session = session_factory()
    run2 = SearchRun(search_id=search_id, combinations_total=15, status="running")
    session.add(run2)
    session.commit()
    run2_id = run2.id
    session.close()

    # Same mock data => same prices => nothing new should be sent.
    await search_engine.execute_run(run2_id)

    assert len(_capture_telegram) == first_run_alerts

    session = session_factory()
    # And the DB-level unique constraint means each offer+type+price is a single row.
    counts = {}
    for notification in session.query(Notification).all():
        key = (notification.flight_offer_id, notification.notification_type, notification.price)
        counts[key] = counts.get(key, 0) + 1
    assert all(count == 1 for count in counts.values())


@pytest.mark.asyncio
async def test_failed_telegram_send_does_not_record_notification(session_factory, monkeypatch):
    async def fail_send(self, message, booking_url=None):
        raise RuntimeError("Telegram is not configured.")

    monkeypatch.setattr(
        "app.notifications.telegram.TelegramNotificationProvider.send_price_alert", fail_send
    )

    session = session_factory()
    search = _make_search(session)
    run = SearchRun(search_id=search.id, combinations_total=15, status="running")
    session.add(run)
    session.commit()
    run_id = run.id
    session.close()

    await search_engine.execute_run(run_id)

    session = session_factory()
    run = session.get(SearchRun, run_id)
    # The run still completes even though every alert attempt failed...
    assert run.status == "completed"
    # ...and nothing is ever marked as successfully sent.
    assert session.query(Notification).count() == 0
    assert "Telegram is not configured" in run.errors
