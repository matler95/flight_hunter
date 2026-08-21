"""Deterministic, offline stand-in for a real discovery provider.

Used by the test suite (and optionally for local development without a
network connection) so the whole pipeline — discovery, normalization,
deduplication, persistence, verification, alerting — can be exercised
without ever calling Google Flights.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from app.domain.enums import TicketType, VerificationStatus
from app.domain.models import FlightSegment, RawFlightOffer, VerificationResult
from app.providers.discovery.base import FlightDiscoveryProvider


class ProviderQueryError(RuntimeError):
    """Raised by the mock provider when asked to simulate a provider failure."""


def _seg(flight_number, marketing, operating, dep_airport, arr_airport, dep_dt, minutes) -> FlightSegment:
    return FlightSegment(
        flight_number=flight_number,
        marketing_airline=marketing,
        operating_airline=operating,
        departure_airport=dep_airport,
        arrival_airport=arr_airport,
        departure_time=dep_dt,
        arrival_time=dep_dt + timedelta(minutes=minutes),
        duration_minutes=minutes,
    )


class MockFlightDiscoveryProvider(FlightDiscoveryProvider):
    """Generates the same three itineraries described in the project plan.

    LOT WAW->NRT direct at 3200 PLN, Turkish WAW-IST-NRT at 3218 PLN (1
    stop, single ticket), and Air China WAW-PEK-NRT at 3341 PLN (1 stop,
    single ticket). Pass `fail_dates` to simulate a provider error for
    specific (departure, return) combinations without stopping the run.
    """

    name = "mock"

    def __init__(self, fail_dates: set[tuple[date, date]] | None = None) -> None:
        self.fail_dates = fail_dates or set()

    async def search(
        self, origin: str, destination: str, departure_date: date, return_date: date, currency: str = "PLN"
    ) -> list[RawFlightOffer]:
        if (departure_date, return_date) in self.fail_dates:
            raise ProviderQueryError(f"Simulated provider outage for {departure_date} -> {return_date}")

        dep = datetime.combine(departure_date, time(10, 35))
        ret = datetime.combine(return_date, time(11, 20))
        trip_days = (return_date - departure_date).days

        lot_out = _seg("LO95", "LO", "LO", origin, destination, dep, 600)
        lot_in = _seg("LO96", "LO", "LO", destination, origin, ret, 600)

        tk_out1 = _seg("TK1766", "TK", "TK", origin, "IST", dep, 195)
        tk_out2 = _seg("TK50", "TK", "TK", "IST", destination, tk_out1.arrival_time + timedelta(minutes=105), 705)
        tk_in1 = _seg("TK51", "TK", "TK", destination, "IST", ret, 705)
        tk_in2 = _seg("TK1767", "TK", "TK", "IST", origin, tk_in1.arrival_time + timedelta(minutes=105), 195)

        ca_out1 = _seg("CA939", "CA", "CA", origin, "PEK", dep, 585)
        ca_out2 = _seg("CA429", "CA", "CA", "PEK", destination, ca_out1.arrival_time + timedelta(minutes=120), 195)
        ca_in1 = _seg("CA430", "CA", "CA", destination, "PEK", ret, 195)
        ca_in2 = _seg("CA938", "CA", "CA", "PEK", origin, ca_in1.arrival_time + timedelta(minutes=120), 585)

        offers = [
            RawFlightOffer(
                provider=self.name,
                provider_offer_id=f"mock-lot-{departure_date}-{return_date}",
                price=Decimal("3200"),
                currency=currency,
                origin=origin,
                destination=destination,
                departure=lot_out.departure_time,
                return_date=return_date,
                arrival=lot_in.arrival_time,
                duration_minutes=lot_out.duration_minutes + lot_in.duration_minutes,
                stops=0,
                segments=[lot_out, lot_in],
                outbound_segment_count=1,
                airlines=["LO"],
                booking_url="https://www.lot.com/booking/mock",
                is_self_transfer=False,
            ),
            RawFlightOffer(
                provider=self.name,
                provider_offer_id=f"mock-tk-{departure_date}-{return_date}",
                price=Decimal("3218"),
                currency=currency,
                origin=origin,
                destination=destination,
                departure=tk_out1.departure_time,
                return_date=return_date,
                arrival=tk_in2.arrival_time,
                duration_minutes=1005,
                stops=1,
                segments=[tk_out1, tk_out2, tk_in1, tk_in2],
                outbound_segment_count=2,
                airlines=["TK"],
                booking_url="https://www.turkishairlines.com/booking/mock",
                is_self_transfer=False,
            ),
            RawFlightOffer(
                provider=self.name,
                provider_offer_id=f"mock-ca-{departure_date}-{return_date}",
                price=Decimal("3341"),
                currency=currency,
                origin=origin,
                destination=destination,
                departure=ca_out1.departure_time,
                return_date=return_date,
                arrival=ca_in2.arrival_time,
                duration_minutes=1095,
                stops=1,
                segments=[ca_out1, ca_out2, ca_in1, ca_in2],
                outbound_segment_count=2,
                airlines=["CA"],
                booking_url="https://www.airchina.com/booking/mock",
                is_self_transfer=False,
            ),
        ]
        # trip_days is implied by the caller's date combination; kept for readability only.
        _ = trip_days
        return offers

    async def verify_booking_option(self, provider_offer_id: str) -> VerificationResult:
        """All mock offers are confirmed single-ticket itineraries, so verification is trivial."""
        if not provider_offer_id.startswith("mock-"):
            return VerificationResult(status=VerificationStatus.UNKNOWN, ticket_type=TicketType.UNKNOWN)
        airline = {"lot": "LOT Polish Airlines", "tk": "Turkish Airlines", "ca": "Air China"}.get(
            provider_offer_id.split("-")[1], "Airline"
        )
        return VerificationResult(
            status=VerificationStatus.VERIFIED,
            ticket_type=TicketType.SINGLE_TICKET,
            booking_source=airline,
            booking_url=None,
        )
