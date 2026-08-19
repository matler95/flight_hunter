"""Safe verification orchestration. Unknown is the only valid fallback."""

from app.domain.enums import TicketType, VerificationStatus
from app.domain.models import NormalizedFlightOffer
from app.providers.verification.airline import AIRLINE_VERIFIERS
from app.providers.verification.base import FlightVerificationProvider


class FlightVerifier:
    def verifier_for(self, offer: NormalizedFlightOffer) -> FlightVerificationProvider | None:
        primary_code = offer.segments[0].marketing_airline if offer.segments else None
        return AIRLINE_VERIFIERS.get(primary_code)

    async def verify(self, offer: NormalizedFlightOffer, discovery_provider=None):
        verify_booking_option = getattr(discovery_provider, "verify_booking_option", None)
        if verify_booking_option is not None:
            return await verify_booking_option(offer.provider_offer_id)
        verifier = self.verifier_for(offer)
        if verifier is None:
            return VerificationStatus.UNKNOWN, TicketType.UNKNOWN, None, None
        try:
            result = await verifier.verify(offer)
        except Exception:
            return VerificationStatus.ERROR, TicketType.UNKNOWN, None, None
        return result.status, result.ticket_type, result.booking_source, result.booking_url
