from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from apscheduler.jobstores.base import JobLookupError
from sqlalchemy.orm import Session

from app.core.watering_logic import get_settings, next_due_date
from app.db.models import Plant, WateringEvent


@dataclass
class ConfirmResult:
    ok: bool
    plant_name: str = ""
    next_due: date | None = None
    message: str = ""


def _cancel_jobs_for_plant(plant_id: int, today: date) -> None:
    from app.state import get_state

    scheduler = get_state().scheduler
    job_ids = [f"reminder:{plant_id}:{today.isoformat()}:{n}" for n in (1, 2, 3)] + [
        f"eod_check:{plant_id}:{today.isoformat()}",
        f"overdue_nag:{plant_id}",
    ]
    for job_id in job_ids:
        try:
            scheduler.remove_job(job_id)
        except JobLookupError:
            pass


def confirm_watered(session: Session, plant_id: int, source: str) -> ConfirmResult:
    """The single funnel both the Telegram button and the web 'mark watered' action call into."""
    plant = session.query(Plant).filter_by(id=plant_id, is_archived=False).first()
    if plant is None:
        return ConfirmResult(ok=False, message="Plant not found.")

    today = date.today()
    already_watered_today = (
        plant.last_watered_at is not None and plant.last_watered_at.date() == today
    )

    if not already_watered_today:
        now = datetime.now()
        session.add(
            WateringEvent(plant_id=plant.id, watered_at=now, source=source, watering_day=today)
        )
        plant.last_watered_at = now

    settings = get_settings(session)
    plant.next_due_at = next_due_date(plant, settings)
    plant.is_overdue = False
    plant.overdue_since = None
    session.commit()

    _cancel_jobs_for_plant(plant.id, today)

    return ConfirmResult(
        ok=True,
        plant_name=plant.name,
        next_due=plant.next_due_at,
        message="Already marked watered today." if already_watered_today else "Watered! 🎉",
    )
