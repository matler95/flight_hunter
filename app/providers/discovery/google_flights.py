"""Low-volume adapter for the open-source fli Google Flights client."""

import asyncio
import time
from datetime import date
from decimal import Decimal
from urllib.parse import urlencode

from app.core.config import settings
from app.db.database import SessionLocal
from app.domain.enums import TicketType, VerificationStatus
from app.domain.models import FlightSegment, RawFlightOffer, VerificationResult
from app.providers.discovery.base import FlightDiscoveryProvider
from app.services.airports import resolve_airports


class ProviderUnavailableError(RuntimeError):
    """Raised when the local fli dependency or Google Flights is unavailable."""


def _resolve_airport_group(code: str) -> tuple[str, ...]:
    """Resolve a single airport or an airport group (e.g. TYO) via the database."""
    session = SessionLocal()
    try:
        return tuple(resolve_airports(session, code))
    finally:
        session.close()


class GoogleFlightsProvider(FlightDiscoveryProvider):
    name = "google_flights_fli"

    def __init__(self, min_interval_seconds: float | None = None) -> None:
        self.min_interval_seconds = min_interval_seconds or settings.provider_min_interval_seconds
        self._last_request_at = 0.0
        self._lock = asyncio.Lock()
        self._booking_contexts: dict[str, tuple[object, object, object, bool | None]] = {}

    async def _wait_turn(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_seconds:
            await asyncio.sleep(self.min_interval_seconds - elapsed)

    async def search(
        self, origin: str, destination: str, departure_date: date, return_date: date, currency: str = "PLN"
    ) -> list[RawFlightOffer]:
        async with self._lock:
            await self._wait_turn()
            try:
                client, filters, results = await asyncio.to_thread(
                    self._search_sync, origin, destination, departure_date, return_date, currency
                )
            except ImportError as exc:
                raise ProviderUnavailableError(
                    "The open-source 'flights' package is not installed. Run uv sync."
                ) from exc
            except Exception as exc:
                raise ProviderUnavailableError(f"Google Flights discovery failed: {type(exc).__name__}: {exc}") from exc
            finally:
                self._last_request_at = time.monotonic()
        return self._normalize(results, client, filters, origin, destination, departure_date, return_date, currency)

    async def verify_booking_option(self, provider_offer_id: str) -> VerificationResult:
        context = self._booking_contexts.get(provider_offer_id)
        if context is None:
            return VerificationResult(status=VerificationStatus.UNKNOWN, ticket_type=TicketType.UNKNOWN)
        client, filters, pair, self_transfer = context
        if self_transfer is True:
            return VerificationResult(status=VerificationStatus.REJECTED, ticket_type=TicketType.SELF_TRANSFER)
        if self_transfer is None:
            return VerificationResult(status=VerificationStatus.UNKNOWN, ticket_type=TicketType.UNKNOWN)
        async with self._lock:
            await self._wait_turn()
            try:
                options = await asyncio.to_thread(client.get_booking_options, pair, filters)
            except Exception:
                return VerificationResult(status=VerificationStatus.ERROR, ticket_type=TicketType.UNKNOWN)
            finally:
                self._last_request_at = time.monotonic()
        direct = next((option for option in options if option.is_airline_direct and option.booking_url), None)
        if direct is None:
            return VerificationResult(status=VerificationStatus.UNKNOWN, ticket_type=TicketType.UNKNOWN)
        return VerificationResult(
            status=VerificationStatus.VERIFIED,
            ticket_type=TicketType.SINGLE_TICKET,
            booking_source=direct.vendor_name or direct.vendor_code or "Airline website",
            booking_url=direct.booking_url,
        )

    @staticmethod
    def _search_sync(origin: str, destination: str, departure_date: date, return_date: date, currency: str):
        from fli.models import Airport, FlightSearchFilters, PassengerInfo, TripType
        from fli.models import FlightSegment as FliSegment
        from fli.search import SearchFlights

        try:
            origin_airports = [[Airport[code], 0] for code in _resolve_airport_group(origin)]
            destination_airports = [[Airport[code], 0] for code in _resolve_airport_group(destination)]
        except KeyError as exc:
            raise ValueError(f"Unsupported IATA airport code: {exc.args[0]}") from exc
        filters = FlightSearchFilters(
            trip_type=TripType.ROUND_TRIP,
            passenger_info=PassengerInfo(adults=1),
            flight_segments=[
                FliSegment(
                    departure_airport=origin_airports,
                    arrival_airport=destination_airports,
                    travel_date=departure_date.isoformat(),
                ),
                FliSegment(
                    departure_airport=destination_airports,
                    arrival_airport=origin_airports,
                    travel_date=return_date.isoformat(),
                ),
            ],
        )
        client = SearchFlights()
        return (
            client,
            filters,
            client.search(filters, top_n=settings.provider_results_per_query, currency=currency) or [],
        )

    @staticmethod
    def _leg(leg) -> FlightSegment:
        airline = getattr(leg.airline, "value", str(leg.airline))
        operating = getattr(getattr(leg, "operating_airline", None), "value", None) or airline
        return FlightSegment(
            flight_number=f"{airline}{leg.flight_number}",
            marketing_airline=airline,
            operating_airline=operating,
            departure_airport=getattr(leg.departure_airport, "value", str(leg.departure_airport)),
            arrival_airport=getattr(leg.arrival_airport, "value", str(leg.arrival_airport)),
            departure_time=leg.departure_datetime,
            arrival_time=leg.arrival_datetime,
            duration_minutes=int(leg.duration),
        )

    def _normalize(
        self,
        results,
        client,
        filters,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: date,
        currency: str,
    ) -> list[RawFlightOffer]:
        booking_url = "https://www.google.com/travel/flights?" + urlencode(
            {"f": 0, "tfs": 0, "curr": currency, "hl": "en", "gl": "PL"}
        )
        offers = []
        for index, pair in enumerate(results):
            if not isinstance(pair, tuple) or len(pair) != 2:
                continue
            outbound, inbound = pair
            outbound_legs, inbound_legs = (
                [self._leg(leg) for leg in outbound.legs],
                [self._leg(leg) for leg in inbound.legs],
            )
            if not outbound_legs or not inbound_legs or outbound.price is None:
                continue
            self_transfer_values = (getattr(outbound, "self_transfer", None), getattr(inbound, "self_transfer", None))
            self_transfer = (
                True
                if True in self_transfer_values
                else None
                if all(value is None for value in self_transfer_values)
                else False
            )
            offer_id = f"{departure_date}:{return_date}:{index}:{getattr(outbound, 'booking_token', '')}"
            self._booking_contexts[offer_id] = (client, filters, pair, self_transfer)
            all_legs = outbound_legs + inbound_legs
            offers.append(
                RawFlightOffer(
                    provider=self.name,
                    provider_offer_id=offer_id,
                    price=Decimal(str(outbound.price)),
                    currency=getattr(outbound, "currency", None) or currency,
                    origin=origin,
                    destination=outbound_legs[-1].arrival_airport,
                    departure=outbound_legs[0].departure_time,
                    return_date=return_date,
                    arrival=inbound_legs[-1].arrival_time,
                    duration_minutes=int(outbound.duration) + int(inbound.duration),
                    stops=int(outbound.stops) + int(inbound.stops),
                    segments=all_legs,
                    outbound_segment_count=len(outbound_legs),
                    airlines=sorted({leg.marketing_airline for leg in all_legs}),
                    booking_url=booking_url,
                    is_self_transfer=self_transfer,
                )
            )
        return offers
