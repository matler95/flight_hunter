from datetime import date, datetime, time, timedelta
from decimal import Decimal

from app.domain.models import FlightSegment, RawFlightOffer
from app.providers.discovery.base import FlightDiscoveryProvider


class MockFlightProvider(FlightDiscoveryProvider):
    name = "mock"

    async def search(
        self, origin: str, destination: str, departure_date: date, return_date: date, currency: str = "PLN"
    ) -> list[RawFlightOffer]:
        destination = "NRT" if destination == "TYO" else destination
        start = datetime.combine(departure_date, time(10, 35))
        finish = start + timedelta(minutes=840)

        def offer(code, airline, price, via=None):
            segments = [
                FlightSegment(
                    flight_number=code + "1",
                    marketing_airline=code,
                    operating_airline=code,
                    departure_airport=origin,
                    arrival_airport=via or destination,
                    departure_time=start,
                    arrival_time=start + timedelta(minutes=90 if via else 840),
                    duration_minutes=90 if via else 840,
                )
            ]
            if via:
                segments.append(
                    FlightSegment(
                        flight_number=code + "2",
                        marketing_airline=code,
                        operating_airline=code,
                        departure_airport=via,
                        arrival_airport=destination,
                        departure_time=start + timedelta(minutes=150),
                        arrival_time=finish,
                        duration_minutes=690,
                    )
                )
            return RawFlightOffer(
                provider=self.name,
                provider_offer_id=f"{code}-{departure_date}-{return_date}",
                price=Decimal(price),
                currency=currency,
                origin=origin,
                destination=destination,
                departure=start,
                arrival=finish,
                duration_minutes=840,
                stops=int(via is not None),
                segments=segments,
                airlines=[airline],
                booking_url="https://www.google.com/travel/flights",
                is_self_transfer=False,
            )

        return [
            offer("LO", "LOT Polish Airlines", "3200"),
            offer("TK", "Turkish Airlines", "3218", "IST"),
            offer("CA", "Air China", "3341", "PEK"),
        ]
