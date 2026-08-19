"""Single-process daily scheduling for local Flight Hunter installations."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import Search
from app.services.search_engine import enqueue_run

scheduler = AsyncIOScheduler()


def sync_daily_jobs() -> None:
    """Register active searches configured for daily execution."""
    session = SessionLocal()
    try:
        searches = session.scalars(select(Search).where(Search.active.is_(True), Search.schedule == "daily")).all()
        desired_ids = {f"daily-search-{search.id}" for search in searches}
        for job in scheduler.get_jobs():
            if job.id.startswith("daily-search-") and job.id not in desired_ids:
                scheduler.remove_job(job.id)
        for search in searches:
            scheduler.add_job(
                enqueue_run,
                "cron",
                hour=settings.daily_search_hour,
                minute=0,
                args=[search.id],
                id=f"daily-search-{search.id}",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
    finally:
        session.close()


def start_scheduler() -> None:
    if not scheduler.running:
        scheduler.start()
    sync_daily_jobs()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
