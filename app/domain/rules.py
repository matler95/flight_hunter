from decimal import Decimal

from app.domain.enums import TicketType, VerificationStatus


def is_valid_ticket(ticket_type: TicketType) -> bool:
    return ticket_type == TicketType.SINGLE_TICKET


def matches_target(price: Decimal, target: Decimal) -> bool:
    return price <= target


def is_alertable(
    price: Decimal, target: Decimal, stops: int, max_stops: int, ticket_type: TicketType, status: VerificationStatus
) -> bool:
    return (
        matches_target(price, target)
        and stops <= max_stops
        and is_valid_ticket(ticket_type)
        and status == VerificationStatus.VERIFIED
    )
