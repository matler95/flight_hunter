from datetime import date, datetime
from decimal import Decimal

import pytest

from app.domain.enums import TicketType, VerificationStatus
from app.domain.models import FlightSegment, NormalizedFlightOffer
from app.services.verifier import FlightVerifier


@pytest.mark.asyncio
async def test_missing_airline_verifier_remains_unknown():
    segment = FlightSegment(
        flight_number="ZZ1",
        marketing_airline="ZZ",
        operating_airline="ZZ",
        departure_airport="WAW",
        arrival_airport="NRT",
        departure_time=datetime(2026, 10, 29, 10),
        arrival_time=datetime(2026, 10, 29, 20),
        duration_minutes=600,
    )
    offer = NormalizedFlightOffer(
        provider="fixture",
        provider_offer_id="one",
        price=Decimal(3200),
        currency="PLN",
        origin="WAW",
        destination="NRT",
        departure=segment.departure_time,
        return_date=date(2026, 11, 12),
        arrival=segment.arrival_time,
        duration_minutes=600,
        stops=0,
        segments=[segment],
        airlines=["Unknown"],
    )
    status, ticket_type, _, _ = await FlightVerifier().verify(offer)
    assert status is VerificationStatus.UNKNOWN
    assert ticket_type is TicketType.UNKNOWN
