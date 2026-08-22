from datetime import date, datetime
from decimal import Decimal

from app.db.models import FlightOffer
from app.services.history_grouping import group_offers_by_period


def _offer(**overrides) -> FlightOffer:
    defaults = dict(
        id=1,
        search_id=1,
        first_seen_run_id=1,
        last_seen_run_id=1,
        origin="WAW",
        destination="TYO",
        departure_date=date(2026, 10, 29),
        return_date=date(2026, 11, 11),
        trip_days=13,
        airline="LOT",
        price=Decimal("3200"),
        currency="PLN",
        total_duration_minutes=630,
        stops=0,
        ticket_type="single_ticket",
        verification_status="verified",
        provider="mock",
        provider_offer_id="mock-1",
        identity_key="key-1",
        route="WAW → TYO",
        last_seen_at=datetime(2026, 8, 1, 10, 0),
    )
    defaults.update(overrides)
    return FlightOffer(**defaults)


def test_offers_for_same_period_are_grouped_cheapest_first():
    offers = [
        _offer(id=1, price=Decimal("3341"), airline="Air China", identity_key="k1"),
        _offer(id=2, price=Decimal("3200"), airline="LOT", identity_key="k2"),
        _offer(id=3, price=Decimal("3218"), airline="Turkish Airlines", identity_key="k3"),
    ]
    groups = group_offers_by_period(offers)

    assert len(groups) == 1
    group = groups[0]
    assert group.cheapest.airline == "LOT"
    assert group.cheapest.price == Decimal("3200")
    assert group.more_count == 2
    assert [o.id for o in group.offers] == [2, 3, 1]


def test_offers_for_different_periods_are_not_grouped():
    offers = [
        _offer(id=1, departure_date=date(2026, 10, 29), identity_key="k1"),
        _offer(id=2, departure_date=date(2026, 10, 30), identity_key="k2"),
    ]
    groups = group_offers_by_period(offers)

    assert len(groups) == 2
    assert all(g.more_count == 0 for g in groups)


def test_groups_ordered_by_most_recently_seen_first():
    offers = [
        _offer(
            id=1,
            departure_date=date(2026, 10, 29),
            identity_key="k1",
            last_seen_at=datetime(2026, 8, 1, 9, 0),
        ),
        _offer(
            id=2,
            departure_date=date(2026, 10, 30),
            identity_key="k2",
            last_seen_at=datetime(2026, 8, 2, 9, 0),
        ),
    ]
    groups = group_offers_by_period(offers)

    assert groups[0].departure_date == date(2026, 10, 30)
    assert groups[1].departure_date == date(2026, 10, 29)
