from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot


@dataclass
class AppState:
    scheduler: AsyncIOScheduler
    bot: Bot


_state: Optional[AppState] = None


def set_state(state: AppState) -> None:
    global _state
    _state = state


def get_state() -> AppState:
    if _state is None:
        raise RuntimeError("AppState has not been initialized yet")
    return _state
