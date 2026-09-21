from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from app.config import settings
from app.telegram_bot.callbacks import season_callback, water_callback
from app.telegram_bot.handlers import help_command, season_command, start_command, status_command


def build_application() -> Application:
    application = Application.builder().token(settings.telegram_bot_token).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("dashboard", status_command))
    application.add_handler(CommandHandler("season", season_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(water_callback, pattern=r"^water:\d+$"))
    application.add_handler(CallbackQueryHandler(season_callback, pattern=r"^season:(summer|winter)$"))

    return application
