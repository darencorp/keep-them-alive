from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.watering_logic import get_settings, next_due_date
from app.db.models import Plant, WateringEvent
from app.db.session import get_db

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

_STATUS_ORDER = {"overdue": 0, "due": 1, "watered_today": 2, "ok": 3}


def _plant_status(plant: Plant, settings, today: date) -> dict:
    due_date = next_due_date(plant, settings)
    if plant.is_overdue:
        status = "overdue"
    elif plant.last_watered_at is not None and plant.last_watered_at.date() == today:
        status = "watered_today"
    elif due_date <= today:
        status = "due"
    else:
        status = "ok"
    return {"plant": plant, "due_date": due_date, "status": status}


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    settings = get_settings(db)
    plants = db.query(Plant).filter_by(is_archived=False).order_by(Plant.name).all()
    rows = [_plant_status(p, settings, today) for p in plants]
    rows.sort(key=lambda r: _STATUS_ORDER[r["status"]])

    counts = {status: sum(1 for r in rows if r["status"] == status) for status in _STATUS_ORDER}

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"rows": rows, "counts": counts, "settings": settings},
    )


@router.get("/plants")
def plants_list(request: Request, db: Session = Depends(get_db)):
    plants = db.query(Plant).filter_by(is_archived=False).order_by(Plant.name).all()
    return templates.TemplateResponse(request, "plants_list.html", {"plants": plants})


@router.get("/plants/new")
def new_plant_form(request: Request):
    return templates.TemplateResponse(request, "plant_form.html", {"plant": None})


@router.get("/plants/{plant_id}")
def plant_detail(request: Request, plant_id: int, db: Session = Depends(get_db)):
    plant = db.query(Plant).filter_by(id=plant_id).first()
    events = (
        db.query(WateringEvent)
        .filter_by(plant_id=plant_id)
        .order_by(WateringEvent.watered_at.desc())
        .limit(30)
        .all()
    )
    return templates.TemplateResponse(
        request, "plant_detail.html", {"plant": plant, "events": events}
    )


@router.get("/plants/{plant_id}/edit")
def edit_plant_form(request: Request, plant_id: int, db: Session = Depends(get_db)):
    plant = db.query(Plant).filter_by(id=plant_id).first()
    return templates.TemplateResponse(request, "plant_form.html", {"plant": plant})


@router.get("/settings")
def settings_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    return templates.TemplateResponse(request, "settings.html", {"settings": settings})
