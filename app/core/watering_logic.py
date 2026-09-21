from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models import GlobalSettings, Plant


def get_settings(session: Session) -> GlobalSettings:
    """Load the single global settings row, creating it with defaults on first use."""
    settings = session.query(GlobalSettings).filter_by(id=1).first()
    if settings is None:
        settings = GlobalSettings(id=1)
        session.add(settings)
        session.commit()
    return settings


def active_interval_days(plant: Plant, settings: GlobalSettings) -> int:
    return plant.summer_interval_days if settings.season == "summer" else plant.winter_interval_days


def next_due_date(plant: Plant, settings: GlobalSettings) -> date:
    """A plant never watered before is due immediately."""
    if plant.last_watered_at is None:
        return date.today()
    interval = active_interval_days(plant, settings)
    return plant.last_watered_at.date() + timedelta(days=interval)


def is_due_today(plant: Plant, settings: GlobalSettings, today: date | None = None) -> bool:
    today = today or date.today()
    return next_due_date(plant, settings) <= today


def reminder_slot_times(settings: GlobalSettings, on_date: date) -> list[datetime]:
    """The clock times on `on_date` at which normal reminders should fire."""
    hour, minute = (int(part) for part in settings.reminder_start_time.split(":"))
    start = datetime.combine(on_date, datetime.min.time()).replace(hour=hour, minute=minute)
    return [
        start + timedelta(hours=settings.reminder_interval_hours * n)
        for n in range(settings.max_reminders_per_day)
    ]
