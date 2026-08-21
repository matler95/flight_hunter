"""Persistence operations for search runs and provider errors."""

from sqlalchemy.orm import Session

from app.db.models import ProviderError, SearchRun


def record_provider_error(
    session: Session,
    *,
    run_id: int,
    provider: str,
    origin: str,
    destination: str,
    departure_date,
    return_date,
    http_status: int | None,
    error_type: str,
    error_message: str,
) -> ProviderError:
    error = ProviderError(
        search_run_id=run_id,
        provider=provider,
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
        http_status=http_status,
        error_type=error_type,
        error_message=error_message[:2000],
    )
    session.add(error)
    return error


def latest_run(session: Session, search_id: int) -> SearchRun | None:
    from sqlalchemy import select

    return session.scalar(select(SearchRun).where(SearchRun.search_id == search_id).order_by(SearchRun.id.desc()))
