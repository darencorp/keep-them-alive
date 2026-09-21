from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.confirm import confirm_watered
from app.core.settings_ops import set_season
from app.core.watering_logic import get_settings
from app.db.models import Plant
from app.db.session import get_db

router = APIRouter()


@router.post("/plants")
def create_plant(
    name: str = Form(...),
    species: str = Form(""),
    notes: str = Form(""),
    summer_interval_days: int = Form(...),
    winter_interval_days: int = Form(...),
    db: Session = Depends(get_db),
):
    plant = Plant(
        name=name.strip(),
        species=species.strip() or None,
        notes=notes.strip() or None,
        summer_interval_days=summer_interval_days,
        winter_interval_days=winter_interval_days,
    )
    db.add(plant)
    db.commit()

    from app.scheduler.jobs import rescan_due_plants

    rescan_due_plants(only_future=True)

    return RedirectResponse(url="/plants", status_code=303)


@router.post("/plants/{plant_id}/edit")
def update_plant(
    plant_id: int,
    name: str = Form(...),
    species: str = Form(""),
    notes: str = Form(""),
    summer_interval_days: int = Form(...),
    winter_interval_days: int = Form(...),
    db: Session = Depends(get_db),
):
    plant = db.query(Plant).filter_by(id=plant_id).first()
    if plant is not None:
        plant.name = name.strip()
        plant.species = species.strip() or None
        plant.notes = notes.strip() or None
        plant.summer_interval_days = summer_interval_days
        plant.winter_interval_days = winter_interval_days
        db.commit()

        from app.scheduler.jobs import rescan_due_plants

        rescan_due_plants(only_future=True)

    return RedirectResponse(url=f"/plants/{plant_id}", status_code=303)


@router.post("/plants/{plant_id}/archive")
def archive_plant(plant_id: int, db: Session = Depends(get_db)):
    plant = db.query(Plant).filter_by(id=plant_id).first()
    if plant is not None:
        plant.is_archived = True
        db.commit()
    return RedirectResponse(url="/plants", status_code=303)


@router.post("/plants/{plant_id}/water")
def water_plant(plant_id: int, db: Session = Depends(get_db)):
    confirm_watered(db, plant_id, source="web")
    return RedirectResponse(url="/", status_code=303)


@router.post("/settings/season")
def update_season(season: str = Form(...), db: Session = Depends(get_db)):
    set_season(db, season)
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/settings/reminders")
def update_reminder_settings(
    reminder_start_time: str = Form(...),
    reminder_interval_hours: int = Form(...),
    max_reminders_per_day: int = Form(...),
    db: Session = Depends(get_db),
):
    settings = get_settings(db)
    settings.reminder_start_time = reminder_start_time
    settings.reminder_interval_hours = reminder_interval_hours
    settings.max_reminders_per_day = max_reminders_per_day
    settings.updated_at = datetime.now()
    db.commit()
    return RedirectResponse(url="/settings", status_code=303)
