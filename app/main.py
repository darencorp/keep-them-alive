from __future__ import annotations

import asyncio
import logging
import signal
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from telegram.error import InvalidToken

from app.config import settings
from app.db.base import Base, engine
from app.scheduler.reconcile import startup_reconciliation
from app.scheduler.setup import build_scheduler
from app.state import AppState, set_state
from app.telegram_bot.bot import build_application
from app.web.routes_actions import router as actions_router
from app.web.routes_pages import router as pages_router

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# httpx/httpcore log full request URLs at INFO, and python-telegram-bot's API calls embed the
# bot token in the URL path (https://api.telegram.org/bot<TOKEN>/method) -- silence them so the
# token never lands in logs (and from there, potentially in a terminal scrollback, log file, or
# support/chat transcript).
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def create_fastapi_app() -> FastAPI:
    fastapi_app = FastAPI(title="Keep Them Alive")
    fastapi_app.mount(
        "/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static"
    )
    fastapi_app.include_router(pages_router)
    fastapi_app.include_router(actions_router)

    @fastapi_app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return fastapi_app


async def main() -> None:
    Base.metadata.create_all(bind=engine)

    scheduler = build_scheduler()
    telegram_app = build_application()
    set_state(AppState(scheduler=scheduler, bot=telegram_app.bot))

    startup_reconciliation()
    scheduler.start()

    telegram_started = False
    try:
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.updater.start_polling()
        telegram_started = True
        logger.info("Telegram bot polling started")
    except InvalidToken:
        # python-telegram-bot's own exception message embeds the raw token -- never let
        # logger.exception() (or str(e)) anywhere near this one.
        logger.error(
            "Telegram bot failed to start: TELEGRAM_BOT_TOKEN is invalid or was rejected by "
            "Telegram. Continuing with the web dashboard only -- fix .env and restart to retry."
        )
    except Exception:
        logger.exception(
            "Telegram bot failed to start (network issue?) -- "
            "continuing with the web dashboard only. It will retry on next restart."
        )

    fastapi_app = create_fastapi_app()
    config = uvicorn.Config(
        fastapi_app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, AttributeError):
            pass

    server_task = asyncio.create_task(server.serve())
    logger.info("Web server started on http://%s:%s", settings.host, settings.port)

    await stop_event.wait()
    logger.info("Shutdown signal received, stopping...")

    server.should_exit = True
    await server_task

    if telegram_started:
        await telegram_app.updater.stop()
        await telegram_app.stop()
        await telegram_app.shutdown()
    scheduler.shutdown(wait=False)
    engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
