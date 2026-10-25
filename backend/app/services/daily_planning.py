"""Small, explicit requirements for reviewed daily plans, shared by demo and AI."""

from dataclasses import dataclass
from datetime import time, timedelta
import re

from fastapi import HTTPException

from app.models import Trip
from app.schemas.trips import ItineraryInput


@dataclass(frozen=True)
class DailyRequirements:
    minimum_activities: int = 0
    lunch: bool = False
    dinner: bool = False

    @property
    def requested(self) -> bool:
        return bool(self.minimum_activities or self.lunch or self.dinner)


def user_context(conversation: list[dict[str, str]] | None) -> list[str]:
    """Only recent traveler words inform a proposal, never assistant instructions."""
    return [message["content"][-2000:] for message in (conversation or [])[-10:]
            if message.get("role") == "user" and isinstance(message.get("content"), str)][-3:]


def daily_requirements(request: str, conversation: list[dict[str, str]] | None = None) -> DailyRequirements:
    texts = user_context(conversation)
    if not texts or texts[-1] != request:
        texts = (texts + [request])[-3:]
    combined = " ".join(texts).casefold()
    current = request.casefold()
    daily = bool(re.search(r"\b(each|every|per)\s+day\b|\bdaily\b|day[ -]by[ -]day", combined))
    noun = r'(?:activities|stops|places|trips|visits|sights|sightseeing)'
    quantity = re.search(rf'\b(two|three|four|five|six|[2-6])\s+(?:(?:interesting|sightseeing|different|relaxed)\s+)?{noun}\b', combined)
    multiple = bool(re.search(rf'\b(?:multiple|several|more)\s+(?:(?:interesting|sightseeing|different)\s+)?{noun}\b', combined))
    amounts = {'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6}
    count = amounts.get(quantity[1], int(quantity[1]) if quantity and quantity[1].isdigit() else 2) if quantity else 2
    minimum = count if daily and (quantity or multiple) else 0
    if re.search(r"\b(only|just|one|1)\s+(?:activity|stop|place|trip)\s+(?:each|every|per)\s+day\b", current):
        minimum = 1
    meals = {}
    for meal in ("lunch", "dinner"):
        meals[meal] = bool(re.search(rf"\b{meal}\b", combined))
        if re.search(rf"\b(?:no|without|skip|exclude)\s+{meal}\b|\b(?:don['’]?t|do not)\s+(?:add|include|plan|suggest)\s+{meal}\b", current):
            meals[meal] = False
    # An individual addition must not turn into an all-days meal obligation.
    if re.search(r'\b(?:one|single|a)\s+(?:lunch|dinner|meal)\b|\b(?:only|just)\s+(?:the\s+)?(?:first|second|last|one)\s+day\b', current):
        return DailyRequirements()
    return DailyRequirements(minimum, **meals)


def is_meal(item, meal: str) -> bool:
    if item.item_type != "food":
        return False
    title = item.title.casefold()
    if re.search(r"\b(breakfast|snack|coffee|dessert)\b", title) and not re.search(rf"\b{meal}\b", title):
        return False
    other_meal = "dinner" if meal == "lunch" else "lunch"
    if re.search(rf"\b{other_meal}\b", title) and not re.search(rf"\b{meal}\b", title):
        return False
    start, end = ((time(11), time(15)) if meal == "lunch" else (time(17), time(22)))
    return start <= item.start_time < item.end_time <= end


def validate_daily_coverage(items: list[ItineraryInput], trip: Trip, requirements: DailyRequirements) -> None:
    """Do not accept a pretty plan that silently drops explicitly requested days/meals."""
    if not requirements.requested:
        return
    combined = [item for item in trip.itinerary if item.status == "planned"] + items
    day = trip.start_date
    while day <= trip.end_date:
        scheduled = [item for item in combined if item.date == day]
        if sum(item.item_type == "activity" for item in scheduled) < requirements.minimum_activities:
            raise HTTPException(422, f"The proposal does not include enough activities on {day.isoformat()}. Your saved trip is unchanged; ask for a fresh daily plan or free up time.")
        for meal in ("lunch", "dinner"):
            if getattr(requirements, meal) and not any(is_meal(item, meal) for item in scheduled):
                raise HTTPException(422, f"The proposal is missing {meal} on {day.isoformat()}. Your saved trip is unchanged; ask for a fresh plan with a place for every requested meal.")
        day += timedelta(days=1)
    for item in items:
        if item.item_type == "food" and any(getattr(requirements, meal) and is_meal(item, meal) for meal in ("lunch", "dinner")):
            if not item.location.strip() or item.location.strip().casefold() == trip.destination.strip().casefold():
                raise HTTPException(422, "A meal suggestion needs a specific restaurant or food-market location, not just the destination. Your saved trip is unchanged; request a fresh plan.")
