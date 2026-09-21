from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.core.confirm import confirm_watered
from app.core.settings_ops import set_season
from app.db.session import get_session


async def water_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    plant_id = int(query.data.split(":", 1)[1])

    with get_session() as session:
        result = confirm_watered(session, plant_id, source="telegram")

    await query.answer(result.message)
    if result.ok:
        try:
            await query.edit_message_text(f"✅ {result.plant_name} watered! Next due: {result.next_due}")
        except Exception:
            pass


async def season_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    season = query.data.split(":", 1)[1]

    with get_session() as session:
        set_season(session, season)

    await query.answer(f"Season set to {season}")
    try:
        await query.edit_message_text(f"🗓 Season set to {season.capitalize()}")
    except Exception:
        pass
