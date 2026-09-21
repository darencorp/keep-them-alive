from __future__ import annotations

import logging
from datetime import date, datetime

from app.core.watering_logic import get_settings, is_due_today, next_due_date, reminder_slot_times
from app.db.models import Plant
from app.db.session import get_session
from app.scheduler.jobs import daily_scan_job, schedule_overdue_nag, schedule_reminders_for_plant
from app.state import get_state

logger = logging.getLogger(__name__)


def startup_reconciliation() -> None:
    """Rebuild the entire schedule from DB truth. Runs once, before the scheduler starts
    processing jobs, so a crash/power-loss at any point can never leave reminders lost,
    duplicated, or the app confused about what's already been sent today.
    """
    today = date.today()
    now = datetime.now()
    scheduler = get_state().scheduler

    due_plant_ids: list[int] = []
    overdue_plant_ids: list[int] = []

    with get_session() as session:
        settings = get_settings(session)
        plants = session.query(Plant).filter_by(is_archived=False).all()

        for plant in plants:
            plant.next_due_at = next_due_date(plant, settings)

            watered_today = (
                plant.last_watered_at is not None and plant.last_watered_at.date() == today
            )
            if watered_today:
                plant.is_overdue = False
                plant.overdue_since = None
                continue

            if plant.reminders_sent_date != today:
                # Counters are from a previous day (or never set) -- today starts fresh.
                plant.reminders_sent_today = 0
                plant.reminders_sent_date = today

            if plant.is_overdue:
                overdue_plant_ids.append(plant.id)
                continue

            if is_due_today(plant, settings, today):
                due_plant_ids.append(plant.id)

        session.commit()

    for plant_id in due_plant_ids:
        with get_session() as session:
            plant = session.query(Plant).filter_by(id=plant_id).first()
            settings = get_settings(session)
            if plant is None:
                continue
            slots = reminder_slot_times(settings, today)
            has_future_slot = any(slot > now for slot in slots)
            reminders_sent = plant.reminders_sent_today
            max_reminders = settings.max_reminders_per_day

        if has_future_slot:
            # Deliberately do NOT catch up on missed slots after a long outage -- only
            # schedule what's still ahead today, so a restart never blasts a flood of nags.
            with get_session() as session:
                plant = session.query(Plant).filter_by(id=plant_id).first()
                settings = get_settings(session)
                schedule_reminders_for_plant(plant, settings, today, only_future=True)
        elif reminders_sent >= max_reminders:
            # All of today's slots already passed and all reminders were sent -- the
            # end-of-day check job that would normally do this may itself have been missed.
            with get_session() as session:
                plant = session.query(Plant).filter_by(id=plant_id).first()
                plant.is_overdue = True
                plant.overdue_since = today
                session.commit()
            schedule_overdue_nag(plant_id, settings)
        # else: today's slots passed but not all reminders went out (long outage) --
        # leave it as a normal due plant; tomorrow's daily scan gives it a fresh cycle.

    for plant_id in overdue_plant_ids:
        with get_session() as session:
            settings = get_settings(session)
        schedule_overdue_nag(plant_id, settings)

    scheduler.add_job(
        daily_scan_job,
        trigger="cron",
        hour=0,
        minute=5,
        id="daily_scan",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    logger.info(
        "Startup reconciliation complete: %d due today, %d overdue",
        len(due_plant_ids),
        len(overdue_plant_ids),
    )
