from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings


def build_scheduler() -> AsyncIOScheduler:
    """A persistent jobstore in the same SQLite file lets pending jobs survive a restart.

    It gets its own connection string rather than sharing the app's engine/session —
    keeps APScheduler's internal connection lifecycle independent of the app's.
    """
    jobstores = {"default": SQLAlchemyJobStore(url=f"sqlite:///{settings.db_path}")}
    executors = {"default": AsyncIOExecutor()}
    job_defaults = {"coalesce": True, "misfire_grace_time": 3600}
    return AsyncIOScheduler(
        jobstores=jobstores,
        executors=executors,
        timezone=settings.timezone,
        job_defaults=job_defaults,
    )
