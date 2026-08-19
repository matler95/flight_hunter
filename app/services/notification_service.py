from app.core.dates import format_duration
from app.core.money import format_money
from app.db.models import FlightOffer, Notification, Search
from app.domain.enums import TicketType, VerificationStatus
from app.domain.rules import is_alertable
from app.notifications.telegram import TelegramNotificationProvider

PRICE_TARGET_REACHED = "price_target_reached"


def price_alert_message(offer: FlightOffer, search: Search) -> str:
    stops = f"{offer.stops} stop" if offer.stops == 1 else f"{offer.stops} stops"
    return "\n".join(
        [
            "✈️ Flight Hunter alert",
            "",
            f"{offer.origin} → {offer.destination}",
            f"Departure: {offer.departure_date:%d %b %Y}",
            f"Return: {offer.return_date:%d %b %Y}",
            f"Trip: {offer.trip_days} days",
            f"Airline: {offer.airline}",
            f"Price: {format_money(offer.price, offer.currency)}",
            f"Route: {offer.route}",
            f"Stops: {stops}",
            f"Total travel time: {format_duration(offer.total_duration_minutes)}",
            "Ticket: ✓ Single ticket",
            f"Target: {format_money(search.target_price, search.currency)}",
        ]
    )


async def notify_if_eligible(session, offer: FlightOffer, search: Search) -> bool:
    eligible = is_alertable(
        offer.price,
        search.target_price,
        offer.stops,
        search.max_stops,
        TicketType(offer.ticket_type),
        VerificationStatus(offer.verification_status),
    )
    if not eligible:
        return False
    existing = (
        session.query(Notification)
        .filter_by(
            flight_offer_id=offer.id,
            notification_type=PRICE_TARGET_REACHED,
            price=offer.price,
        )
        .first()
    )
    if existing:
        return False
    await TelegramNotificationProvider().send_price_alert(price_alert_message(offer, search), offer.booking_url)
    session.add(Notification(flight_offer_id=offer.id, notification_type=PRICE_TARGET_REACHED, price=offer.price))
    return True
