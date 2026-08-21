from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import Search, SearchRun

router = APIRouter(prefix="/searches", tags=["searches"])


@router.get("/{search_id}/progress")
def progress(search_id: int) -> dict:
    session = SessionLocal()
    try:
        search = session.get(Search, search_id)
        if search is None:
            raise HTTPException(404, detail={"status": "error", "error": {"code": "SEARCH_NOT_FOUND", "message": "Search not found"}})
        run = session.scalar(select(SearchRun).where(SearchRun.search_id == search_id).order_by(SearchRun.id.desc()))
        if run is None:
            return {"status": "ok", "data": {}}
        return {
            "status": "ok",
            "data": {
                "status": run.status,
                "checked": run.combinations_checked,
                "total": run.combinations_total,
                "offers_found": run.offers_found,
                "offers_new": run.offers_new,
                "verified": run.offers_verified,
                "current_query": run.current_query,
            },
        }
    finally:
        session.close()
