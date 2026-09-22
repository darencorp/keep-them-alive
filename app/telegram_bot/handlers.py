from __future__ import annotations

from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.core.watering_logic import get_settings, plant_status_info, sort_key
from app.db.models import Plant, TelegramChat
from app.db.session import get_session


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    with get_session() as session:
        existing = session.query(TelegramChat).filter_by(chat_id=chat_id).first()
        if existing is None:
            session.add(TelegramChat(chat_id=chat_id))
            session.commit()
        elif not existing.is_active:
            existing.is_active = True
            session.commit()

    await update.message.reply_text(
        "🌿 Keep Them Alive is now watching your plants!\n\n"
        "Commands:\n"
        "/status - see what's due today\n"
        "/season - switch summer/winter mode\n"
        "/help - show this again"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "/status - dashboard of due/overdue plants\n"
        "/season - toggle summer/winter watering interval\n"
        "/start - register this chat for reminders"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today = date.today()
    with get_session() as session:
        settings = get_settings(session)
        plants = session.query(Plant).filter_by(is_archived=False).order_by(Plant.name).all()
        # Sorted most urgent first: longest-overdue, then soonest-due, then soonest-upcoming.
        rows = sorted(
            ({"plant": p, **plant_status_info(p, settings, today)} for p in plants),
            key=sort_key,
        )
        season = settings.season

    due_lines, overdue_lines, ok_lines, buttons = [], [], [], []

    for row in rows:
        plant, due_date, status = row["plant"], row["due_date"], row["status"]
        if status == "overdue":
            overdue_lines.append(f"🥀 {plant.name} (overdue since {plant.overdue_since})")
            buttons.append(
                [InlineKeyboardButton(f"✅ Water {plant.name}", callback_data=f"water:{plant.id}")]
            )
        elif status == "due":
            due_lines.append(f"💧 {plant.name} (due {due_date})")
            buttons.append(
                [InlineKeyboardButton(f"✅ Water {plant.name}", callback_data=f"water:{plant.id}")]
            )
        else:
            ok_lines.append(f"🌱 {plant.name} (next due {due_date})")

    lines = [f"🗓 Season: {season.capitalize()}", ""]
    if overdue_lines:
        lines.append(f"🚨 Overdue ({len(overdue_lines)}):")
        lines.extend(overdue_lines)
        lines.append("")
    if due_lines:
        lines.append(f"💧 Due today ({len(due_lines)}):")
        lines.extend(due_lines)
        lines.append("")
    if ok_lines:
        lines.append(f"✅ All good ({len(ok_lines)}):")
        lines.extend(ok_lines)

    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
    await update.message.reply_text("\n".join(lines).strip(), reply_markup=reply_markup)


async def season_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as session:
        current = get_settings(session).season

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "☀️ Summer" + (" (current)" if current == "summer" else ""),
                    callback_data="season:summer",
                ),
                InlineKeyboardButton(
                    "❄️ Winter" + (" (current)" if current == "winter" else ""),
                    callback_data="season:winter",
                ),
            ]
        ]
    )
    await update.message.reply_text(f"Current season: {current.capitalize()}", reply_markup=keyboard)
