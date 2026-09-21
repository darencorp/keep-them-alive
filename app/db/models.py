from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class Plant(Base):
    __tablename__ = "plants"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    species = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    summer_interval_days = Column(Integer, nullable=False)
    winter_interval_days = Column(Integer, nullable=False)
    is_archived = Column(Boolean, nullable=False, default=False)

    # Performance caches, always recomputable from watering_events + global_settings.
    last_watered_at = Column(DateTime, nullable=True)
    next_due_at = Column(Date, nullable=True)
    reminders_sent_today = Column(Integer, nullable=False, default=0)
    reminders_sent_date = Column(Date, nullable=True)
    is_overdue = Column(Boolean, nullable=False, default=False)
    overdue_since = Column(Date, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.now)

    watering_events = relationship(
        "WateringEvent",
        back_populates="plant",
        order_by="WateringEvent.watered_at.desc()",
    )


class WateringEvent(Base):
    __tablename__ = "watering_events"

    id = Column(Integer, primary_key=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    watered_at = Column(DateTime, nullable=False, default=datetime.now)
    source = Column(String, nullable=False)  # "telegram" | "web"
    watering_day = Column(Date, nullable=False)

    plant = relationship("Plant", back_populates="watering_events")


class GlobalSettings(Base):
    __tablename__ = "global_settings"

    id = Column(Integer, primary_key=True)
    season = Column(String, nullable=False, default="summer")  # "summer" | "winter"
    reminder_start_time = Column(String, nullable=False, default="09:00")
    reminder_interval_hours = Column(Integer, nullable=False, default=4)
    max_reminders_per_day = Column(Integer, nullable=False, default=3)
    updated_at = Column(DateTime, nullable=False, default=datetime.now)


class TelegramChat(Base):
    __tablename__ = "telegram_chats"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, nullable=False, unique=True)
    registered_at = Column(DateTime, nullable=False, default=datetime.now)
    is_active = Column(Boolean, nullable=False, default=True)
