from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.db.database import Base, SessionLocal, engine
from app.db.models import FlightOffer, PriceHistory, Search, SearchRun
from app.domain.enums import TicketType, VerificationStatus
from app.providers.discovery.google_flights import GoogleFlightsProvider
from app.services.date_generator import generate_date_combinations
from app.services.deduplicator import deduplicate, itinerary_key


@asynccontextmanager
async def lifespan(app):
    Path("data").mkdir(exist_ok=True)
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Flight Hunter", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["money"] = lambda value, currency: f"{value:,.0f} {currency}".replace(",", " ")
templates.env.filters["duration"] = lambda minutes: f"{minutes // 60}h {minutes % 60:02d}m"


def db():
    return SessionLocal()


def get_search(search_id):
    session = db()
    item = session.get(Search, search_id)
    if not item:
        session.close()
        raise HTTPException(404, "Search not found")
    return session, item


async def execute(search_id):
    session, search = get_search(search_id)
    combos = list(
        generate_date_combinations(
            search.earliest_departure,
            search.latest_departure,
            search.min_trip_days,
            search.max_trip_days,
            search.latest_return,
        )
    )
    run = SearchRun(search_id=search.id, combinations_total=len(combos))
    session.add(run)
    session.commit()
    session.refresh(run)
    provider = GoogleFlightsProvider()
    all_offers = []
    errors = []
    for departure, returning in combos:
        try:
            all_offers.extend(
                await provider.search(search.origin, search.destination, departure, returning, search.currency)
            )
        except Exception as exc:
            errors.append(str(exc))
        run.combinations_checked += 1
        session.commit()
    unique = deduplicate(all_offers)
    run.offers_found = len(all_offers)
    for raw in unique:
        if raw.stops > search.max_stops:
            continue
        # Discovery cannot prove ticketing; false self-transfer is not proof of one ticket.
        ticket = TicketType.SELF_TRANSFER if raw.is_self_transfer else TicketType.UNKNOWN
        status = VerificationStatus.UNKNOWN
        key = itinerary_key(raw)
        offer = FlightOffer(
            search_run_id=run.id,
            departure_date=raw.departure.date(),
            return_date=raw.return_date,
            trip_days=(raw.return_date - raw.departure.date()).days,
            origin=raw.origin,
            destination=raw.destination,
            airline=raw.airlines[0],
            price=raw.price,
            currency=raw.currency,
            total_duration_minutes=raw.duration_minutes,
            stops=raw.stops,
            stop_airports=",".join(s.arrival_airport for s in raw.segments[:-1]),
            ticket_type=ticket.value,
            verification_status=status.value,
            booking_url=raw.booking_url,
            provider=raw.provider,
            provider_offer_id=raw.provider_offer_id,
            identity_key=key,
            route=" → ".join([raw.origin] + [s.arrival_airport for s in raw.segments]),
        )
        session.add(offer)
        session.flush()
        session.add(PriceHistory(flight_offer_id=offer.id, price=raw.price, currency=raw.currency))
        run.offers_verified += int(status == VerificationStatus.VERIFIED)
    run.status = "completed"
    run.finished_at = datetime.now()
    run.errors = "\n".join(errors)
    search.last_run_at = datetime.now()
    session.commit()
    session.close()


@app.get("/", response_class=HTMLResponse)
@app.get("/searches", response_class=HTMLResponse)
def dashboard(request: Request):
    session = db()
    searches = session.scalars(select(Search).order_by(Search.created_at.desc())).all()
    return templates.TemplateResponse(request, "dashboard.html", {"searches": searches})


@app.get("/searches/new", response_class=HTMLResponse)
def new_search(request: Request):
    return templates.TemplateResponse(request, "search_form.html", {})


@app.post("/searches")
async def create_search(
    name: str = Form(...),
    origin: str = Form(...),
    destination: str = Form(...),
    earliest_departure: str = Form(...),
    latest_departure: str = Form(...),
    min_trip_days: int = Form(...),
    max_trip_days: int = Form(...),
    latest_return: str = Form(...),
    target_price: Decimal = Form(...),
    currency: str = Form("PLN"),
    max_stops: int = Form(1),
):
    session = db()
    search = Search(
        name=name,
        origin=origin.upper(),
        destination=destination.upper(),
        earliest_departure=earliest_departure,
        latest_departure=latest_departure,
        min_trip_days=min_trip_days,
        max_trip_days=max_trip_days,
        latest_return=latest_return,
        target_price=target_price,
        currency=currency.upper(),
        max_stops=max_stops,
    )
    session.add(search)
    session.commit()
    session.refresh(search)
    sid = search.id
    session.close()
    await execute(sid)
    return RedirectResponse(f"/searches/{sid}", 303)


@app.get("/searches/{search_id}", response_class=HTMLResponse)
@app.get("/searches/{search_id}/results", response_class=HTMLResponse)
def results(request: Request, search_id: int):
    session, item = get_search(search_id)
    run = session.scalar(select(SearchRun).where(SearchRun.search_id == search_id).order_by(SearchRun.id.desc()))
    offers = (
        []
        if not run
        else session.scalars(
            select(FlightOffer)
            .where(FlightOffer.search_run_id == run.id)
            .order_by(FlightOffer.price, FlightOffer.stops, FlightOffer.total_duration_minutes)
        ).all()
    )
    return templates.TemplateResponse(request, "results.html", {"search": item, "run": run, "offers": offers})


@app.post("/searches/{search_id}/run")
async def run(search_id: int):
    await execute(search_id)
    return RedirectResponse(f"/searches/{search_id}", 303)


@app.post("/searches/{search_id}/toggle")
def toggle(search_id: int):
    session, item = get_search(search_id)
    item.active = not item.active
    session.commit()
    return RedirectResponse("/", 303)


@app.delete("/searches/{search_id}")
def delete(search_id: int):
    session, item = get_search(search_id)
    session.delete(item)
    session.commit()
    return {"status": "ok", "data": {}}


@app.get("/searches/{search_id}/history", response_class=HTMLResponse)
@app.get("/history", response_class=HTMLResponse)
def history(request: Request, search_id: int | None = None):
    session = db()
    query = select(FlightOffer).join(SearchRun).order_by(FlightOffer.id.desc())
    if search_id:
        query = query.where(SearchRun.search_id == search_id)
    return templates.TemplateResponse(request, "history.html", {"offers": session.scalars(query).all()})


@app.get("/flights/{offer_id}", response_class=HTMLResponse)
def flight(request: Request, offer_id: int):
    session = db()
    offer = session.get(FlightOffer, offer_id)
    if not offer:
        raise HTTPException(404, "Flight not found")
    return templates.TemplateResponse(request, "flight_detail.html", {"offer": offer, "history": offer.prices})


@app.get("/api/searches/{search_id}/progress")
def progress(search_id: int):
    session, item = get_search(search_id)
    run = session.scalar(select(SearchRun).where(SearchRun.search_id == search_id).order_by(SearchRun.id.desc()))
    return {
        "status": "ok",
        "data": {}
        if not run
        else {
            "status": run.status,
            "checked": run.combinations_checked,
            "total": run.combinations_total,
            "offers_found": run.offers_found,
            "verified": run.offers_verified,
        },
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "data": {"provider": "google_flights_fli", "database": "ok"}}
