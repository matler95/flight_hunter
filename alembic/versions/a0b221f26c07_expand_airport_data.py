"""expand airport data for autocomplete

Revision ID: a0b221f26c07
Revises: 465067facec3
Create Date: 2026-08-21 12:00:00.000000

Adds a much larger set of airports and metropolitan groups (plan §7) so the
origin/destination autocomplete has good global coverage -- e.g. typing
"modl" resolves Warsaw Modlin (WMI), typing "tok" resolves both Tokyo
airports (HND, NRT). Only inserts rows that don't already exist, so it's
safe to run against a database that already has the original seed data.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.services.airport_data import AIRPORTS, GROUPS

# revision identifiers, used by Alembic.
revision: str = "a0b221f26c07"
down_revision: Union[str, Sequence[str], None] = "465067facec3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


airports_table = sa.table(
    "airports",
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("city", sa.String),
    sa.column("country", sa.String),
)
airport_groups_table = sa.table(
    "airport_groups", sa.column("code", sa.String), sa.column("name", sa.String)
)
airport_group_members_table = sa.table(
    "airport_group_members",
    sa.column("group_code", sa.String),
    sa.column("airport_code", sa.String),
)


def upgrade() -> None:
    bind = op.get_bind()

    existing_airports = {
        row[0] for row in bind.execute(sa.select(airports_table.c.code))
    }
    new_airports = [
        {"code": code, "name": name, "city": city, "country": country}
        for code, (name, city, country) in AIRPORTS.items()
        if code not in existing_airports
    ]
    if new_airports:
        op.bulk_insert(airports_table, new_airports)

    existing_groups = {
        row[0] for row in bind.execute(sa.select(airport_groups_table.c.code))
    }
    new_groups = [
        {"code": code, "name": name}
        for code, (name, _members) in GROUPS.items()
        if code not in existing_groups
    ]
    if new_groups:
        op.bulk_insert(airport_groups_table, new_groups)

    existing_members = {
        (row[0], row[1])
        for row in bind.execute(
            sa.select(
                airport_group_members_table.c.group_code,
                airport_group_members_table.c.airport_code,
            )
        )
    }
    new_members = [
        {"group_code": group_code, "airport_code": airport_code}
        for group_code, (_name, members) in GROUPS.items()
        for airport_code in members
        if (group_code, airport_code) not in existing_members
    ]
    if new_members:
        op.bulk_insert(airport_group_members_table, new_members)


_ORIGINAL_AIRPORT_CODES = {"HND", "NRT", "LHR", "LGW", "STN", "LTN", "JFK", "EWR", "LGA"}
_ORIGINAL_GROUP_CODES = {"TYO", "LON", "NYC"}


def downgrade() -> None:
    # Only remove rows this migration actually added, leaving the original
    # seed data (from the initial schema migration) untouched.
    added_airport_codes = [c for c in AIRPORTS if c not in _ORIGINAL_AIRPORT_CODES]
    added_group_codes = [c for c in GROUPS if c not in _ORIGINAL_GROUP_CODES]

    op.execute(
        airport_group_members_table.delete().where(
            airport_group_members_table.c.group_code.in_(added_group_codes)
        )
    )
    op.execute(airport_groups_table.delete().where(airport_groups_table.c.code.in_(added_group_codes)))
    op.execute(airports_table.delete().where(airports_table.c.code.in_(added_airport_codes)))
