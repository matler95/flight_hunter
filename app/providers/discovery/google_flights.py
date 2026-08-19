from datetime import date

from app.providers.discovery.base import FlightDiscoveryProvider


class GoogleFlightsProvider(FlightDiscoveryProvider):
    name = "google_flights"

    async def search(
        self, origin: str, destination: str, departure_date: date, return_date: date, currency: str = "PLN"
    ):
        raise RuntimeError("Google Flights adapter is not configured. Select the mock provider for offline use.")
