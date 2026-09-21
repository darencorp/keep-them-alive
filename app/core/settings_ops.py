from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.watering_logic import get_settings, next_due_date
from app.db.models import Plant


def set_season(session: Session, season: str) -> None:
    """Shared by the web settings form and the Telegram /season command."""
    if season not in ("summer", "winter"):
        raise ValueError(f"Invalid season: {season}")

    settings = get_settings(session)
    settings.season = season
    settings.updated_at = datetime.now()

    # Recompute due dates going forward; never touches watering_events history.
    for plant in session.query(Plant).filter_by(is_archived=False, is_overdue=False):
        plant.next_due_at = next_due_date(plant, settings)

    session.commit()

    # Reschedule immediately so newly-due plants don't wait for the next daily scan.
    from app.scheduler.jobs import rescan_due_plants

    rescan_due_plants(only_future=True)
