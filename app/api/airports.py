from fastapi import APIRouter, Query, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.db.database import SessionLocal
from app.services.airports import search_airports

router = APIRouter(prefix="/airports", tags=["airports"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/search", response_class=HTMLResponse)
def suggest(request: Request, q: str = "", field: str = "origin") -> HTMLResponse:
    """Returns an HTML fragment of matching airports/groups for the
    origin/destination autocomplete. `field` selects which hidden input
    the client-side picker() call fills in (see search_form.html)."""
    session = SessionLocal()
    try:
        suggestions = search_airports(session, q) if q.strip() else []
        return templates.TemplateResponse(
            request,
            "components/airport_options.html",
            {"suggestions": suggestions, "field": field, "query": q},
        )
    finally:
        session.close()
