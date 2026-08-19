from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Search(Base):
    __tablename__ = "searches"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    origin: Mapped[str] = mapped_column(String(3))
    destination: Mapped[str] = mapped_column(String(3))
    earliest_departure: Mapped[date] = mapped_column(Date)
    latest_departure: Mapped[date] = mapped_column(Date)
    min_trip_days: Mapped[int] = mapped_column(Integer)
    max_trip_days: Mapped[int] = mapped_column(Integer)
    latest_return: Mapped[date] = mapped_column(Date)
    target_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="PLN")
    max_stops: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule: Mapped[str] = mapped_column(String(20), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    runs: Mapped[list["SearchRun"]] = relationship(back_populates="search", cascade="all,delete-orphan")


class SearchRun(Base):
    __tablename__ = "search_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("searches.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")
    combinations_total: Mapped[int] = mapped_column(Integer, default=0)
    combinations_checked: Mapped[int] = mapped_column(Integer, default=0)
    offers_found: Mapped[int] = mapped_column(Integer, default=0)
    offers_verified: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[str] = mapped_column(Text, default="")
    current_query: Mapped[str] = mapped_column(Text, default="")
    search: Mapped[Search] = relationship(back_populates="runs")
    offers: Mapped[list["FlightOffer"]] = relationship(back_populates="run", cascade="all,delete-orphan")


class FlightOffer(Base):
    __tablename__ = "flight_offers"
    id: Mapped[int] = mapped_column(primary_key=True)
    search_run_id: Mapped[int] = mapped_column(ForeignKey("search_runs.id"))
    departure_date: Mapped[date] = mapped_column(Date)
    return_date: Mapped[date] = mapped_column(Date)
    trip_days: Mapped[int] = mapped_column(Integer)
    origin: Mapped[str] = mapped_column(String(3))
    destination: Mapped[str] = mapped_column(String(3))
    airline: Mapped[str] = mapped_column(String(80))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    total_duration_minutes: Mapped[int] = mapped_column(Integer)
    stops: Mapped[int] = mapped_column(Integer)
    stop_airports: Mapped[str] = mapped_column(Text, default="")
    ticket_type: Mapped[str] = mapped_column(String(30), default="unknown")
    verification_status: Mapped[str] = mapped_column(String(20), default="discovered")
    booking_source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    booking_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String(50))
    provider_offer_id: Mapped[str] = mapped_column(String(160))
    identity_key: Mapped[str] = mapped_column(String(300), index=True)
    route: Mapped[str] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    run: Mapped[SearchRun] = relationship(back_populates="offers")
    prices: Mapped[list["PriceHistory"]] = relationship(back_populates="offer", cascade="all,delete-orphan")
    segments: Mapped[list["PersistedFlightSegment"]] = relationship(back_populates="offer", cascade="all,delete-orphan")


class PersistedFlightSegment(Base):
    __tablename__ = "flight_segments"
    id: Mapped[int] = mapped_column(primary_key=True)
    flight_offer_id: Mapped[int] = mapped_column(ForeignKey("flight_offers.id"))
    segment_number: Mapped[int] = mapped_column(Integer)
    direction: Mapped[str] = mapped_column(String(10))
    flight_number: Mapped[str] = mapped_column(String(20))
    marketing_airline: Mapped[str] = mapped_column(String(10))
    operating_airline: Mapped[str] = mapped_column(String(10))
    departure_airport: Mapped[str] = mapped_column(String(3))
    arrival_airport: Mapped[str] = mapped_column(String(3))
    departure_time: Mapped[datetime] = mapped_column(DateTime)
    arrival_time: Mapped[datetime] = mapped_column(DateTime)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    offer: Mapped[FlightOffer] = relationship(back_populates="segments")


class PriceHistory(Base):
    __tablename__ = "price_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    flight_offer_id: Mapped[int] = mapped_column(ForeignKey("flight_offers.id"))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    checked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    offer: Mapped[FlightOffer] = relationship(back_populates="prices")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("flight_offer_id", "notification_type", "price"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    flight_offer_id: Mapped[int] = mapped_column(ForeignKey("flight_offers.id"))
    notification_type: Mapped[str] = mapped_column(String(40))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    sent_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
