"""Groups flight-offer rows for the History page.

Multiple offers can exist for the same trip period (same route, same
departure/return dates) -- different airlines, different stop patterns, or
just different prices seen over time. Rather than listing every one of
those as its own top-level row, we group them by period and let the UI
show the cheapest with a "+N more" expandable list.
"""
from dataclasses import dataclass, field

from app.db.models import FlightOffer


@dataclass(slots=True)
class OfferGroup:
    origin: str
    destination: str
    departure_date: object
    return_date: object
    offers: list[FlightOffer] = field(default_factory=list)

    @property
    def cheapest(self) -> FlightOffer:
        return self.offers[0]

    @property
    def more_count(self) -> int:
        return len(self.offers) - 1


def group_offers_by_period(offers: list[FlightOffer]) -> list[OfferGroup]:
    """Group `offers` by (origin, destination, departure_date, return_date).

    Within each group offers are sorted cheapest-first. Groups are ordered
    by their cheapest offer's most recent `last_seen_at`, so freshly-seen
    trip periods surface first -- matching the previous flat ordering.
    """
    groups: dict[tuple, OfferGroup] = {}
    for offer in offers:
        key = (offer.origin, offer.destination, offer.departure_date, offer.return_date)
        group = groups.get(key)
        if group is None:
            group = OfferGroup(
                origin=offer.origin,
                destination=offer.destination,
                departure_date=offer.departure_date,
                return_date=offer.return_date,
            )
            groups[key] = group
        group.offers.append(offer)

    result = list(groups.values())
    for group in result:
        group.offers.sort(key=lambda o: (o.price, o.stops, o.total_duration_minutes))
    result.sort(key=lambda g: max(o.last_seen_at for o in g.offers), reverse=True)
    return result
