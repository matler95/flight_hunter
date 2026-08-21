"""Resolves a user-entered IATA code to one or more concrete airports.

`TYO` (a metropolitan grouping) resolves to `HND` + `NRT`. A plain airport
code such as `HND` resolves to itself. Offers always persist the concrete
airport actually flown, never the group code.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Airport, AirportGroup, AirportGroupMember

# Seed data applied by the initial Alembic migration. Kept here too so the
# resolver still works against a database that has not been seeded yet
# (e.g. a fresh in-memory database used in tests).
SEED_GROUPS: dict[str, tuple[str, tuple[tuple[str, str, str], ...]]] = {
    "TYO": ("Tokyo", (("HND", "Tokyo Haneda", "Japan"), ("NRT", "Tokyo Narita", "Japan"))),
    "LON": (
        "London",
        (
            ("LHR", "London Heathrow", "United Kingdom"),
            ("LGW", "London Gatwick", "United Kingdom"),
            ("STN", "London Stansted", "United Kingdom"),
            ("LTN", "London Luton", "United Kingdom"),
        ),
    ),
    "NYC": (
        "New York",
        (
            ("JFK", "John F. Kennedy International", "United States"),
            ("EWR", "Newark Liberty International", "United States"),
            ("LGA", "LaGuardia", "United States"),
        ),
    ),
}


def seed_airport_groups(session: Session) -> None:
    """Idempotently insert the built-in airport groups. Safe to call repeatedly."""
    for group_code, (group_name, airports) in SEED_GROUPS.items():
        group = session.get(AirportGroup, group_code)
        if group is None:
            group = AirportGroup(code=group_code, name=group_name)
            session.add(group)
        for airport_code, airport_name, country in airports:
            airport = session.get(Airport, airport_code)
            if airport is None:
                session.add(Airport(code=airport_code, name=airport_name, city=group_name, country=country))
            member = session.scalar(
                select(AirportGroupMember).where(
                    AirportGroupMember.group_code == group_code, AirportGroupMember.airport_code == airport_code
                )
            )
            if member is None:
                session.add(AirportGroupMember(group_code=group_code, airport_code=airport_code))
    session.commit()


def resolve_airports(session: Session, code: str) -> list[str]:
    """Return the concrete airport codes represented by `code`.

    Falls back to treating `code` as a single airport (the common case) when
    it is not a known group, so the resolver degrades gracefully.
    """
    code = code.upper()
    members = session.scalars(
        select(AirportGroupMember.airport_code).where(AirportGroupMember.group_code == code)
    ).all()
    if members:
        return list(members)
    if code in SEED_GROUPS:
        return [airport_code for airport_code, _, _ in SEED_GROUPS[code][1]]
    return [code]


def describe(session: Session, code: str) -> str:
    """Human-readable label for a single airport or group, for the UI."""
    code = code.upper()
    group = session.get(AirportGroup, code)
    if group is not None:
        members = resolve_airports(session, code)
        return f"{group.name} ({' + '.join(members)})"
    if code in SEED_GROUPS:
        name, airports = SEED_GROUPS[code]
        return f"{name} ({' + '.join(a[0] for a in airports)})"
    airport = session.get(Airport, code)
    return f"{airport.name} ({code})" if airport is not None else code
