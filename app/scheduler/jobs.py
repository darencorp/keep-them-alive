from __future__ import annotations

import logging
from datetime import date, datetime

from apscheduler.jobstores.base import JobLookupError
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from app.core.reminder_text import normal_reminder, overdue_nag
from app.core.watering_logic import get_settings, is_due_today, next_due_date, reminder_slot_times
from app.db.models import Plant, TelegramChat
from app.db.session import get_session
from app.state import get_state

logger = logging.getLogger(__name__)


async def _broadcast(text: str, reply_markup=None) -> None:
    state = get_state()
    with get_session() as session:
        chat_ids = [c.chat_id for c in session.query(TelegramChat).filter_by(is_active=True)]
    for chat_id in chat_ids:
        try:
            await state.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        except Exception:
            logger.exception("Failed to send Telegram message to chat %s", chat_id)


def _watered_button(plant_id: int):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ Watered", callback_data=f"water:{plant_id}")]])


def schedule_reminders_for_plant(plant: Plant, settings, today: date, only_future: bool = False) -> None:
    """Schedule (or reschedule) this plant's up-to-3 reminder jobs plus its end-of-day check.

    Deterministic job ids (`reminder:{plant_id}:{date}:{n}`) make this idempotent to re-run —
    a repeat call (e.g. after a crash+restart the same day) just overwrites the same jobs.
    """
    scheduler = get_state().scheduler
    now = datetime.now()
    slots = reminder_slot_times(settings, today)

    any_future_slot = False
    for n, slot in enumerate(slots, start=1):
        if only_future and slot <= now:
            continue
        any_future_slot = True
        scheduler.add_job(
            send_reminder_job,
            trigger=DateTrigger(run_date=slot),
            args=[plant.id, n],
            id=f"reminder:{plant.id}:{today.isoformat()}:{n}",
            replace_existing=True,
            misfire_grace_time=3600,
        )

    if any_future_slot or not only_future:
        eod_time = datetime.combine(today, datetime.min.time()).replace(hour=23, minute=59)
        if eod_time > now:
            scheduler.add_job(
                check_overdue_job,
                trigger=DateTrigger(run_date=eod_time),
                args=[plant.id],
                id=f"eod_check:{plant.id}:{today.isoformat()}",
                replace_existing=True,
                misfire_grace_time=3600,
            )


def schedule_overdue_nag(plant_id: int, settings) -> None:
    scheduler = get_state().scheduler
    hour, minute = (int(part) for part in settings.reminder_start_time.split(":"))
    scheduler.add_job(
        send_overdue_nag_job,
        trigger=CronTrigger(hour=hour, minute=minute),
        args=[plant_id],
        id=f"overdue_nag:{plant_id}",
        replace_existing=True,
        misfire_grace_time=3600,
    )


def rescan_due_plants(only_future: bool = False) -> None:
    """Recompute due dates for all plants and (re)schedule reminders for newly-due ones.

    Shared by the daily scan job, the season-toggle action, and the "add/edit plant" web actions.
    """
    today = date.today()
    with get_session() as session:
        settings = get_settings(session)
        plants = session.query(Plant).filter_by(is_archived=False).all()

        due_plant_ids = []
        for plant in plants:
            plant.next_due_at = next_due_date(plant, settings)
            if plant.is_overdue:
                continue
            if not is_due_today(plant, settings, today):
                continue
            if plant.reminders_sent_date != today:
                plant.reminders_sent_today = 0
                plant.reminders_sent_date = today
            due_plant_ids.append(plant.id)
        session.commit()

        for plant_id in due_plant_ids:
            plant = session.get(Plant, plant_id)
            if plant is not None:
                schedule_reminders_for_plant(plant, settings, today, only_future=only_future)


async def daily_scan_job() -> None:
    logger.info("Running daily watering scan")
    rescan_due_plants(only_future=False)


async def send_reminder_job(plant_id: int, reminder_number: int) -> None:
    with get_session() as session:
        plant = session.query(Plant).filter_by(id=plant_id, is_archived=False).first()
        if plant is None or plant.is_overdue:
            return
        today = date.today()
        if plant.last_watered_at is not None and plant.last_watered_at.date() == today:
            return  # already confirmed today -- nothing to send

        settings = get_settings(session)
        plant.reminders_sent_today = reminder_number
        plant.reminders_sent_date = today
        session.commit()
        name = plant.name
        max_reminders = settings.max_reminders_per_day

    text = normal_reminder(name, reminder_number, max_reminders)
    await _broadcast(text, reply_markup=_watered_button(plant_id))


async def check_overdue_job(plant_id: int) -> None:
    """Fires once at end-of-day for a plant that was due today; flips it to overdue if unconfirmed."""
    today = date.today()
    with get_session() as session:
        plant = session.query(Plant).filter_by(id=plant_id, is_archived=False).first()
        if plant is None:
            return
        if plant.last_watered_at is not None and plant.last_watered_at.date() == today:
            return

        settings = get_settings(session)
        if plant.reminders_sent_today < settings.max_reminders_per_day:
            return  # reminders were missed (e.g. downtime) -- let tomorrow's scan retry normally

        plant.is_overdue = True
        plant.overdue_since = today
        session.commit()
        schedule_overdue_nag(plant_id, settings)


async def send_overdue_nag_job(plant_id: int) -> None:
    with get_session() as session:
        plant = session.query(Plant).filter_by(id=plant_id, is_archived=False).first()
        if plant is None or not plant.is_overdue:
            try:
                get_state().scheduler.remove_job(f"overdue_nag:{plant_id}")
            except JobLookupError:
                pass
            return
        name = plant.name
        since = plant.overdue_since.isoformat() if plant.overdue_since else "?"

    await _broadcast(overdue_nag(name, since))
