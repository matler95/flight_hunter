from abc import ABC, abstractmethod

from app.domain.models import NormalizedFlightOffer, VerificationResult


class FlightVerificationProvider(ABC):
    @abstractmethod
    async def verify(self, offer: NormalizedFlightOffer) -> VerificationResult: ...
