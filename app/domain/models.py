from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.domain.enums import TicketType, VerificationStatus


class FlightSegment(BaseModel):
    flight_number: str
    marketing_airline: str
    operating_airline: str
    departure_airport: str
    arrival_airport: str
    departure_time: datetime
    arrival_time: datetime
    duration_minutes: int


class RawFlightOffer(BaseModel):
    provider: str
    provider_offer_id: str
    price: Decimal
    currency: str
    origin: str
    destination: str
    departure: datetime
    return_date: date
    arrival: datetime
    duration_minutes: int
    stops: int
    segments: list[FlightSegment] = Field(default_factory=list)
    outbound_segment_count: int = 0
    airlines: list[str] = Field(default_factory=list)
    booking_url: str | None = None
    is_self_transfer: bool | None = None


class NormalizedFlightOffer(RawFlightOffer):
    ticket_type: TicketType = TicketType.UNKNOWN


class VerificationResult(BaseModel):
    status: VerificationStatus
    ticket_type: TicketType = TicketType.UNKNOWN
    booking_source: str | None = None
    booking_url: str | None = None
