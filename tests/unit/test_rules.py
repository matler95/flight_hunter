from datetime import datetime
from decimal import Decimal

from app.domain.enums import TicketType, VerificationStatus
from app.domain.models import FlightSegment, RawFlightOffer
from app.domain.rules import is_alertable, is_valid_ticket, matches_target
from app.services.deduplicator import deduplicate


def test_price_ticket_and_stops_rules():
    assert matches_target(Decimal(3218), Decimal(3500))
    assert not matches_target(Decimal(3501), Decimal(3500))
    assert is_valid_ticket(TicketType.SINGLE_TICKET)
    assert not is_valid_ticket(TicketType.UNKNOWN)
    assert is_alertable(Decimal(3200), Decimal(3500), 1, 1, TicketType.SINGLE_TICKET, VerificationStatus.VERIFIED)
    assert not is_alertable(Decimal(3200), Decimal(3500), 2, 1, TicketType.SINGLE_TICKET, VerificationStatus.VERIFIED)


def test_deduplication_keeps_lower_price():
    seg = FlightSegment(
        flight_number="LO1",
        marketing_airline="LO",
        operating_airline="LO",
        departure_airport="WAW",
        arrival_airport="NRT",
        departure_time=datetime(2026, 10, 29, 10),
        arrival_time=datetime(2026, 10, 29, 20),
        duration_minutes=600,
    )
    base = dict(
        provider="mock",
        provider_offer_id="one",
        currency="PLN",
        origin="WAW",
        destination="NRT",
        departure=seg.departure_time,
        arrival=seg.arrival_time,
        duration_minutes=600,
        stops=0,
        segments=[seg],
        airlines=["LOT"],
    )
    assert (
        len(deduplicate([RawFlightOffer(price=Decimal(3200), **base), RawFlightOffer(price=Decimal(3100), **base)]))
        == 1
    )
