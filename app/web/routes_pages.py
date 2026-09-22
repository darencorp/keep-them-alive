from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.watering_logic import STATUS_ORDER, get_settings, plant_status_info, sort_key
from app.db.models import Plant, WateringEvent
from app.db.session import get_db

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    settings = get_settings(db)
    plants = db.query(Plant).filter_by(is_archived=False).order_by(Plant.name).all()
    rows = [{"plant": p, **plant_status_info(p, settings, today)} for p in plants]
    rows.sort(key=sort_key)

    counts = {status: sum(1 for r in rows if r["status"] == status) for status in STATUS_ORDER}

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
