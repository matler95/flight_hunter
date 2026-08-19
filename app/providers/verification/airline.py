from app.domain.enums import TicketType, VerificationStatus
from app.domain.models import NormalizedFlightOffer, VerificationResult
from app.providers.verification.base import FlightVerificationProvider


class UnknownAirlineVerifier(FlightVerificationProvider):
    async def verify(self, offer: NormalizedFlightOffer) -> VerificationResult:
        return VerificationResult(status=VerificationStatus.UNKNOWN, ticket_type=TicketType.UNKNOWN)


AIRLINE_VERIFIERS = {"TK": UnknownAirlineVerifier(), "LO": UnknownAirlineVerifier(), "AY": UnknownAirlineVerifier()}
