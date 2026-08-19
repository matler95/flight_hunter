from app.domain.models import RawFlightOffer


def itinerary_key(offer: RawFlightOffer) -> str:
    segments = "|".join(
        f"{s.flight_number}:{s.departure_airport}:{s.arrival_airport}:{s.departure_time.isoformat()}"
        for s in offer.segments
    )
    return f"{offer.origin}:{offer.destination}:{offer.departure.isoformat()}:{offer.arrival.isoformat()}:{segments}"


def deduplicate(offers: list[RawFlightOffer]) -> list[RawFlightOffer]:
    found = {}
    for offer in offers:
        key = itinerary_key(offer)
        if key not in found or offer.price < found[key].price:
            found[key] = offer
    return list(found.values())


class FlightDeduplicator:
    deduplicate = staticmethod(deduplicate)
