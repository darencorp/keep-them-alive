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


# Lower number = more urgent = should sort first, both on the web dashboard and in Telegram.
STATUS_ORDER = {"overdue": 0, "due": 1, "watered_today": 2, "ok": 3}


def plant_status_info(plant: Plant, settings: GlobalSettings, today: date | None = None) -> dict:
    """Shared by the web dashboard and Telegram /status so both sort plants the same way:
    most urgent (longest overdue, or soonest due) first.
    """
    today = today or date.today()
    due_date = next_due_date(plant, settings)

    if plant.is_overdue:
        status = "overdue"
        sort_date = plant.overdue_since or due_date
    elif plant.last_watered_at is not None and plant.last_watered_at.date() == today:
        status = "watered_today"
        sort_date = due_date
    elif due_date <= today:
        status = "due"
        sort_date = due_date
    else:
        status = "ok"
        sort_date = due_date

    return {"due_date": due_date, "status": status, "sort_date": sort_date}


def sort_key(info: dict) -> tuple:
    return (STATUS_ORDER[info["status"]], info["sort_date"])
