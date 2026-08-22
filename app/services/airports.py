"""Resolves a user-entered IATA code to one or more concrete airports, and
powers the origin/destination autocomplete (search by code, airport name, or
city name -- e.g. "modl" -> WMI, "tok" -> HND + NRT).

`TYO` (a metropolitan grouping) resolves to `HND` + `NRT`. A plain airport
code such as `HND` resolves to itself. Offers always persist the concrete
airport actually flown, never the group code.
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Airport, AirportGroup, AirportGroupMember
from app.services.airport_data import AIRPORTS, GROUPS

# Kept as module-level aliases so a database that hasn't been migrated/seeded
# yet (e.g. a fresh in-memory database used in tests) still works.
SEED_AIRPORTS = AIRPORTS
SEED_GROUPS = GROUPS


def seed_airport_groups(session: Session) -> None:
    """Idempotently insert the built-in airports and airport groups. Safe to call repeatedly."""
    for code, (name, city, country) in AIRPORTS.items():
        if session.get(Airport, code) is None:
            session.add(Airport(code=code, name=name, city=city, country=country))
    session.flush()

    for group_code, (group_name, member_codes) in GROUPS.items():
        group = session.get(AirportGroup, group_code)
        if group is None:
            group = AirportGroup(code=group_code, name=group_name)
            session.add(group)
        for airport_code in member_codes:
            member = session.scalar(
                select(AirportGroupMember).where(
                    AirportGroupMember.group_code == group_code,
                    AirportGroupMember.airport_code == airport_code,
                )
            )
            if member is None:
                session.add(
                    AirportGroupMember(group_code=group_code, airport_code=airport_code)
                )
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
        return list(SEED_GROUPS[code][1])
    return [code]


def describe(session: Session, code: str) -> str:
    """Human-readable label for a single airport or group, for the UI."""
    code = code.upper()
    group = session.get(AirportGroup, code)
    if group is not None:
        members = resolve_airports(session, code)
        return f"{group.name} ({' + '.join(members)})"
    if code in SEED_GROUPS:
        name, members = SEED_GROUPS[code]
        return f"{name} ({' + '.join(members)})"
    airport = session.get(Airport, code)
    if airport is not None:
        return f"{airport.name} ({code})"
    if code in SEED_AIRPORTS:
        name, _city, _country = SEED_AIRPORTS[code]
        return f"{name} ({code})"
    return code


@dataclass(slots=True)
class AirportSuggestion:
    code: str
    label: str          # short: shown in the input once selected, e.g. "Warsaw Modlin (WMI)"
    detail: str          # e.g. "Warsaw, Poland" or "HND + NRT"
    is_group: bool = False


def search_airports(session: Session, query: str, limit: int = 8) -> list[AirportSuggestion]:
    """Match `query` against airport codes, airport names, and city names,
    plus metropolitan groups (matched by code or name). Falls back to the
    in-memory seed data so this also works before the DB has been seeded.
    """
    q = (query or "").strip().lower()
    if not q:
        return []

    results: list[tuple[int, AirportSuggestion]] = []

    def rank(code: str, name: str, city: str) -> int | None:
        code_l, name_l, city_l = code.lower(), name.lower(), city.lower()
        if code_l == q:
            return 0
        if code_l.startswith(q):
            return 1
        if city_l.startswith(q):
            return 2
        if name_l.startswith(q):
            return 3
        if q in city_l or q in name_l:
            return 4
        return None

    # Airports: prefer DB rows (covers anything a user/admin added later),
    # fall back to the static seed so this still works pre-migration.
    db_airports = list(session.scalars(select(Airport)))
    seen_codes = {a.code for a in db_airports}
    airport_rows: list[tuple[str, str, str, str]] = [
        (a.code, a.name, a.city, a.country) for a in db_airports
    ]
    for code, (name, city, country) in AIRPORTS.items():
        if code not in seen_codes:
            airport_rows.append((code, name, city, country))

    for code, name, city, country in airport_rows:
        r = rank(code, name, city)
        if r is not None:
            results.append(
                (r, AirportSuggestion(code=code, label=f"{name} ({code})", detail=f"{city}, {country}"))
            )

    # Groups
    db_groups = list(session.scalars(select(AirportGroup)))
    seen_group_codes = {g.code for g in db_groups}
    group_rows: list[tuple[str, str, tuple[str, ...]]] = []
    for g in db_groups:
        members = resolve_airports(session, g.code)
        group_rows.append((g.code, g.name, tuple(members)))
    for code, (name, members) in GROUPS.items():
        if code not in seen_group_codes:
            group_rows.append((code, name, members))

    for code, name, members in group_rows:
        r = rank(code, name, "")
        if r is not None:
            results.append(
                (
                    r,
                    AirportSuggestion(
                        code=code,
                        label=f"{name} ({code})",
                        detail=" + ".join(members),
                        is_group=True,
                    ),
                )
            )

    results.sort(key=lambda pair: (pair[0], pair[1].label))
    # De-duplicate by code (DB + seed fallback could both match).
    dedup: dict[str, AirportSuggestion] = {}
    for _rank, suggestion in results:
        dedup.setdefault(suggestion.code, suggestion)
    return list(dedup.values())[:limit]
