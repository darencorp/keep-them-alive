from __future__ import annotations

import random

NORMAL_TEMPLATES = [
    "💧 Reminder {n}/{max}: {name} could use some water today!",
    "🌱 Psst... {name} is thirsty. Reminder {n}/{max}.",
    "🚿 Don't forget {name} today! (Reminder {n}/{max})",
    "🪴 {name} is waiting for its drink. Reminder {n}/{max}.",
]

OVERDUE_TEMPLATES = [
    "🥀😱 {name} is BEGGING for water! Overdue since {since}.",
    "🆘🌵 {name} has gone full drought mode. Please help!",
    "😭💀 {name} is dangerously dry (overdue since {since}). Save it!",
    "🚨🪴 URGENT: {name} needs water NOW. Thirsty since {since}.",
]


def normal_reminder(plant_name: str, reminder_number: int, max_reminders: int) -> str:
    template = random.choice(NORMAL_TEMPLATES)
    return template.format(name=plant_name, n=reminder_number, max=max_reminders)


def overdue_nag(plant_name: str, overdue_since: str) -> str:
    template = random.choice(OVERDUE_TEMPLATES)
    return template.format(name=plant_name, since=overdue_since)
