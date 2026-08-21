from contextlib import asynccontextmanager
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.api import flights as flights_api
from app.api import health as health_api
from app.api import history as history_api
from app.api import searches as searches_api
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.database import SessionLocal
from app.db.models import FlightOffer, Search, SearchRun
from app.domain.enums import TicketType, VerificationStatus
from app.domain.rules import is_alertable
from app.scheduler.scheduler import start_scheduler, stop_scheduler, sync_daily_jobs
from app.services.search_engine import enqueue_run

SORT_OPTIONS = {
    "price": (FlightOffer.price, FlightOffer.stops, FlightOffer.total_duration_minutes),
    "duration": (FlightOffer.total_duration_minutes, FlightOffer.price),
    "departure": (FlightOffer.departure_date, FlightOffer.price),
    "stops": (FlightOffer.stops, FlightOffer.price),
}


@asynccontextmanager
async def lifespan(app):
    configure_logging(settings.log_level)
    Path("data").mkdir(exist_ok=True)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Flight Hunter", lifespan=lifespan)
app.include_router(health_api.router, prefix="/api")
app.include_router(searches_api.router, prefix="/api")
app.include_router(flights_api.router, prefix="/api")
app.include_router(history_api.router, prefix="/api")
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


@app.get("/", response_class=HTMLResponse)
@app.get("/searches", response_class=HTMLResponse)
def dashboard(request: Request):
    session = db()
    searches = session.scalars(select(Search).order_by(Search.created_at.desc())).all()
    cards = []
    for search in searches:
        run = _latest_run(session, search.id)
        best_offer = None
        target_reached = False
        if run is not None:
            best_offer = session.scalar(
                select(FlightOffer)
                .where(FlightOffer.search_id == search.id, FlightOffer.last_seen_run_id == run.id)
                .order_by(FlightOffer.price)
            )
            if best_offer is not None:
                target_reached = is_alertable(
                    best_offer.price,
                    search.target_price,
                    best_offer.stops,
                    search.max_stops,
                    TicketType(best_offer.ticket_type),
                    VerificationStatus(best_offer.verification_status),
                )
        cards.append({"search": search, "run": run, "best_offer": best_offer, "target_reached": target_reached})
    return templates.TemplateResponse(request, "dashboard.html", {"cards": cards})


@app.get("/searches/new", response_class=HTMLResponse)
def new_search(request: Request):
    return templates.TemplateResponse(request, "search_form.html", {})


@app.post("/searches")
async def create_search(
    name: str = Form(...),
    origin: str = Form(...),
    destination: str = Form(...),
    earliest_departure: date = Form(...),
    latest_departure: date = Form(...),
    min_trip_days: int = Form(...),
    max_trip_days: int = Form(...),
    latest_return: date = Form(...),
    target_price: Decimal = Form(...),
    currency: str = Form("PLN"),
    max_stops: int = Form(1),
    schedule: str = Form("manual"),
):
    if earliest_departure > latest_departure:
        raise HTTPException(400, "Earliest departure must not be after latest departure.")
    if min_trip_days > max_trip_days:
        raise HTTPException(400, "Minimum trip days must not exceed maximum trip days.")
    if earliest_departure + timedelta(days=min_trip_days) > latest_return:
        raise HTTPException(400, "Latest return is too early for the shortest possible trip.")
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
        schedule=schedule if schedule in {"manual", "daily"} else "manual",
    )
    session.add(search)
    session.commit()
    session.refresh(search)
    sid = search.id
    session.close()
    sync_daily_jobs()
    enqueue_run(sid)
    return RedirectResponse(f"/searches/{sid}", 303)


def _latest_run(session, search_id: int) -> SearchRun | None:
    return session.scalar(select(SearchRun).where(SearchRun.search_id == search_id).order_by(SearchRun.id.desc()))


@app.get("/searches/{search_id}", response_class=HTMLResponse)
@app.get("/searches/{search_id}/results", response_class=HTMLResponse)
def results(request: Request, search_id: int, sort: str = "price"):
    session, item = get_search(search_id)
    run = _latest_run(session, search_id)
    order_by = SORT_OPTIONS.get(sort, SORT_OPTIONS["price"])
    offers = (
        []
        if not run
        else session.scalars(
            select(FlightOffer)
            .where(FlightOffer.search_id == search_id, FlightOffer.last_seen_run_id == run.id)
            .order_by(*order_by)
        ).all()
    )
    for offer in offers:
        # UI must never show "below target" for a merely-discovered price (plan §50):
        # only a verified, single-ticket, in-stops-budget offer counts.
        offer.is_alertable = is_alertable(
            offer.price,
            item.target_price,
            offer.stops,
            item.max_stops,
            TicketType(offer.ticket_type),
            VerificationStatus(offer.verification_status),
        )
    return templates.TemplateResponse(
        request, "results.html", {"search": item, "run": run, "offers": offers, "sort": sort}
    )


@app.post("/searches/{search_id}/run")
async def run(search_id: int):
    enqueue_run(search_id)
    return RedirectResponse(f"/searches/{search_id}", 303)


@app.post("/searches/{search_id}/toggle")
def toggle(search_id: int):
    session, item = get_search(search_id)
    item.active = not item.active
    session.commit()
    sync_daily_jobs()
    return RedirectResponse("/", 303)


@app.delete("/searches/{search_id}")
def delete(search_id: int):
    session, item = get_search(search_id)
    session.delete(item)
    session.commit()
    sync_daily_jobs()
    return {"status": "ok", "data": {}}


@app.get("/searches/{search_id}/history", response_class=HTMLResponse)
@app.get("/history", response_class=HTMLResponse)
def history(
    request: Request,
    search_id: int | None = None,
    airline: str | None = None,
    status: str | None = None,
    stops: int | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
):
    session = db()
    query = select(FlightOffer).order_by(FlightOffer.id.desc())
    if search_id:
        query = query.where(FlightOffer.search_id == search_id)
    if airline:
        query = query.where(FlightOffer.airline == airline)
    if status:
        query = query.where(FlightOffer.verification_status == status)
    if stops is not None:
        query = query.where(FlightOffer.stops == stops)
    if min_price is not None:
        query = query.where(FlightOffer.price >= min_price)
    if max_price is not None:
        query = query.where(FlightOffer.price <= max_price)
    offers = session.scalars(query).all()
    airlines = sorted({row[0] for row in session.execute(select(FlightOffer.airline).distinct())})
    return templates.TemplateResponse(
        request,
        "history.html",
        {
            "offers": offers,
            "airlines": airlines,
            "filters": {
                "search_id": search_id,
                "airline": airline,
                "status": status,
                "stops": stops,
                "min_price": min_price,
                "max_price": max_price,
            },
        },
    )


@app.get("/flights/{offer_id}", response_class=HTMLResponse)
def flight(request: Request, offer_id: int):
    session = db()
    offer = session.get(FlightOffer, offer_id)
    if not offer:
        raise HTTPException(404, "Flight not found")
    return templates.TemplateResponse(request, "flight_detail.html", {"offer": offer, "history": offer.prices})


@app.get("/searches/{search_id}/progress", response_class=HTMLResponse)
def progress_fragment(request: Request, search_id: int):
    session, search = get_search(search_id)
    run = _latest_run(session, search_id)
    return templates.TemplateResponse(request, "components/search_progress.html", {"search": search, "run": run})
