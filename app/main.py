from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.db.database import Base, SessionLocal, engine
from app.db.models import FlightOffer, Search, SearchRun
from app.scheduler.scheduler import sync_daily_jobs
from app.services.search_engine import enqueue_run


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
    schedule: str = Form("manual"),
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
    enqueue_run(search_id)
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


@app.get("/searches/{search_id}/progress", response_class=HTMLResponse)
def progress_fragment(request: Request, search_id: int):
    session, search = get_search(search_id)
    run = session.scalar(select(SearchRun).where(SearchRun.search_id == search_id).order_by(SearchRun.id.desc()))
    return templates.TemplateResponse(request, "components/search_progress.html", {"search": search, "run": run})


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
            "current_query": run.current_query,
        },
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "data": {"provider": "google_flights_fli", "database": "ok"}}
