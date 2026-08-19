"""Low-volume adapter for the open-source fli Google Flights client."""

import asyncio
import time
from datetime import date
from decimal import Decimal
from urllib.parse import urlencode

from app.core.config import settings
from app.domain.models import FlightSegment, RawFlightOffer
from app.providers.discovery.base import FlightDiscoveryProvider


class ProviderUnavailableError(RuntimeError):
    """Raised when the local fli dependency or Google Flights is unavailable."""


AIRPORT_GROUPS = {"TYO": ("HND", "NRT")}


class GoogleFlightsProvider(FlightDiscoveryProvider):
    name = "google_flights_fli"

    def __init__(self, min_interval_seconds: float | None = None) -> None:
        self.min_interval_seconds = min_interval_seconds or settings.provider_min_interval_seconds
        self._last_request_at = 0.0
        self._lock = asyncio.Lock()

    async def search(
        self, origin: str, destination: str, departure_date: date, return_date: date, currency: str = "PLN"
    ) -> list[RawFlightOffer]:
        async with self._lock:
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self.min_interval_seconds:
                await asyncio.sleep(self.min_interval_seconds - elapsed)
            try:
                results = await asyncio.to_thread(
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
        return self._normalize(results, origin, destination, departure_date, return_date, currency)

    @staticmethod
    def _search_sync(origin: str, destination: str, departure_date: date, return_date: date, currency: str):
        from fli.models import Airport, FlightSearchFilters, PassengerInfo, TripType
        from fli.models import FlightSegment as FliSegment
        from fli.search import SearchFlights

        try:
            origin_airports = [[Airport[code], 0] for code in AIRPORT_GROUPS.get(origin, (origin,))]
            destination_airports = [[Airport[code], 0] for code in AIRPORT_GROUPS.get(destination, (destination,))]
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
        return SearchFlights().search(filters, top_n=settings.provider_results_per_query, currency=currency) or []

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
        self, results, origin: str, destination: str, departure_date: date, return_date: date, currency: str
    ) -> list[RawFlightOffer]:
        booking_url = "https://www.google.com/travel/flights?" + urlencode(
            {"f": 0, "tfs": 0, "curr": currency, "hl": "en", "gl": "PL"}
        )
        offers = []
        for index, pair in enumerate(results):
            if not isinstance(pair, tuple) or len(pair) != 2:
                continue
            outbound, inbound = pair
            outbound_legs = [self._leg(leg) for leg in outbound.legs]
            inbound_legs = [self._leg(leg) for leg in inbound.legs]
            if not outbound_legs or not inbound_legs:
                continue
            all_legs = outbound_legs + inbound_legs
            offers.append(
                RawFlightOffer(
                    provider=self.name,
                    provider_offer_id=f"{departure_date}:{return_date}:{index}:{getattr(outbound, 'booking_token', '')}",
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
                    is_self_transfer=bool(
                        getattr(outbound, "self_transfer", False) or getattr(inbound, "self_transfer", False)
                    ),
                )
            )
        return offers
