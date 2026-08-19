from abc import ABC, abstractmethod
from datetime import date

from app.domain.models import RawFlightOffer


class FlightDiscoveryProvider(ABC):
    @abstractmethod
    async def search(
        self, origin: str, destination: str, departure_date: date, return_date: date, currency: str = "PLN"
    ) -> list[RawFlightOffer]: ...
