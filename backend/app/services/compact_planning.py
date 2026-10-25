"""Materialize AI-selected referenced places into a checked, reviewable schedule.

The model chooses places/days, never bookings. Scheduling and illustrative budget
allocation are deterministic. This is not a route, price, or availability service.
"""
from datetime import date, time, timedelta
from decimal import Decimal, ROUND_DOWN

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated, Literal

from app.schemas.planning import ItineraryPlan
from app.services.travel_quality import PLACES, resolve_place


class SelectedDay(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    date: str
    sights: list[str] = Field(max_length=6)
    lunch: str | None
    dinner: str | None


class PlaceSelection(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    days: list[SelectedDay] = Field(min_length=1, max_length=21)


Score = Annotated[int, Field(strict=True, ge=0, le=5)]


class RankedSelection(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    dates: list[str] = Field(min_length=1, max_length=21)
    sight_scores: dict[str, Score] = Field(max_length=100)
    lunch_scores: dict[str, Score] = Field(max_length=100)
    dinner_scores: dict[str, Score] = Field(max_length=100)
    sights_per_day: int = Field(ge=0, le=6)
    include_lunch: bool
    include_dinner: bool
    spending_style: Literal['economy', 'standard']


def ranked_selection(ranking, context):
    """Choose distinct positively AI-ranked places; never invent replacements."""
    available = {p['id']: p for p in context['place_references']['places']}
    dates = ranking.dates
    if len(dates) != len(set(dates)):
        raise HTTPException(422, 'Return each selected calendar date only once.')
    saved = [item for item in context.get('itinerary', []) if item.get('status', 'planned') == 'planned']
    reserved = set(context.get('draft_reserved_place_ids', []))
    fixed_ids = {place['id'] for item in saved if item['item_type'] == 'activity' and (place := resolve_place(SimplePlace(item))) is not None}
    remaining = {key: score for key, score in ranking.sight_scores.items() if score > 0 and key not in reserved
                 and (context['planning_constraints'].get('allow_repeated_sights') or key not in fixed_ids)}
    for scores, kind in ((ranking.sight_scores, 'activity'), (ranking.lunch_scores, 'food'), (ranking.dinner_scores, 'food')):
        if any(key not in available or available[key]['kind'] != kind for key in scores):
            raise HTTPException(422, 'Rank only the supplied IDs in their correct categories.')
    # A new full-trip request needs a sight on each otherwise-free day. This is
    # a minimum planning policy, not knowledge of flight arrival/departure times.
    count = max(1, ranking.sights_per_day) if context['planning_constraints'].get('cover_all_days') else ranking.sights_per_day
    needed = {day: max(0, count - sum(item['date'] == day and item['item_type'] == 'activity' for item in saved)) for day in dates}
    if sum(needed.values()) > len(remaining) and not context['planning_constraints'].get('allow_repeated_sights'):
        raise HTTPException(422, f'The requested schedule needs {sum(needed.values())} distinct new sightseeing IDs. Rank enough supplied choices positively or request fewer sights/days. Never reuse an attraction to fill a day.')
    used_food = set()
    days = []
    for day in dates:
        chosen = []
        for _ in range(needed[day]):
            if not remaining:
                raise HTTPException(422, 'The limited reference index has no remaining selected sights. Request fewer stops or explicitly allow repeats.')
            area = available[chosen[0]]['area'] if chosen else None
            key = max(remaining, key=lambda key: (available[key]['area'] == area if area else False, remaining[key], key))
            chosen.append(key)
            if not context['planning_constraints'].get('allow_repeated_sights'):
                del remaining[key]
        areas = {available[key]['area'] for key in chosen}
        meals = {}
        for meal, enabled, scores in [('lunch', ranking.include_lunch, ranking.lunch_scores), ('dinner', ranking.include_dinner, ranking.dinner_scores)]:
            from app.services.daily_planning import is_meal
            from app.schemas.trips import ItineraryInput
            if any(item['date'] == day and is_meal(ItineraryInput(**{k:v for k,v in item.items() if k in ItineraryInput.model_fields}), meal) for item in saved):
                meals[meal] = None
                continue
            if not enabled:
                meals[meal] = None
                continue
            choices = {key: score for key, score in scores.items() if score > 0 and meal in available[key].get('meal_periods', ['lunch', 'dinner'])}
            if not choices:
                raise HTTPException(422, f'No positively ranked referenced {meal} places are available. Ask for another supported meal plan.')
            fresh = {key: score for key, score in choices.items() if key not in used_food}
            choices = fresh or choices
            key = max(choices, key=lambda key: (available[key]['area'] in areas, choices[key], key))
            meals[meal] = key
            used_food.add(key)
        days.append({'date': day, 'sights': chosen, **meals})
    return PlaceSelection.model_validate({'days': days})


class SimplePlace:
    def __init__(self, item):
        self.title, self.location = item.get('title', ''), item.get('location', '')


def slot_time(minutes):
    return time(minutes // 60, minutes % 60)


def materialize(selection: PlaceSelection, trip, rules, *, economy=False, allocation_counts=None):
    catalog = {place['id']: place for place in PLACES if not place.get('quote_required')}
    existing = [item for item in trip.itinerary if item.status == 'planned']
    remaining = trip.budget - sum((item.estimated_cost for item in existing), Decimal(0))
    if remaining < 0:
        raise HTTPException(422, 'Saved planned spending already exceeds the budget. No new draft can fit.')
    chosen = []
    days_seen = set()
    if not rules.get('allow_repeated_sights'):
        all_sights = [key for day in selection.days for key in day.sights]
        repeated = sorted({key for key in all_sights if all_sights.count(key) > 1})
        if repeated:
            unused = [key for key, place in catalog.items() if place['kind'] == 'activity' and key not in all_sights
                      and (not rules.get('city_only') or place['city'] == rules['city_only'])]
            raise HTTPException(422, 'The selected sightseeing IDs repeat across days: ' + ', '.join(repeated) +
                '. Select each sight only once. Unused reference choices include: ' + ', '.join(unused) + '. Return the complete corrected selection.')
    for day in selection.days:
        try:
            parsed_day = date.fromisoformat(day.date)
        except ValueError:
            raise HTTPException(422, 'Choose dates from the saved trip for the place selection.') from None
        if parsed_day in days_seen or not trip.start_date <= parsed_day <= trip.end_date:
            raise HTTPException(422, 'The selected days must be distinct and inside the saved dates.')
        days_seen.add(parsed_day)
        stops = [(key, 'activity', None) for key in day.sights]
        if day.lunch:
            stops.append((day.lunch, 'food', 'lunch'))
        if day.dinner:
            stops.append((day.dinner, 'food', 'dinner'))
        for key, kind, meal in stops:
            place = catalog.get(key)
            if place is None or place['kind'] != kind:
                raise HTTPException(422, 'Choose a referenced place with the correct sightseeing or meal category.')
            if meal and meal not in place.get('meal_periods', ['lunch', 'dinner']):
                raise HTTPException(422, f'{place["name"]} is not a supported {meal} suggestion in this limited index.')
            # Do not reinsert an already saved visit as a new addition.
            if any(item.date == parsed_day and (matched := resolve_place(item)) and matched['id'] == key for item in existing):
                continue
            chosen.append((parsed_day, place, kind, meal))
    if not chosen:
        raise HTTPException(422, 'There are no new selected places to add around the saved activities.')
    counts = {kind: sum(row[2] == kind for row in chosen) for kind in ('activity', 'food')}
    # Explicit budget envelopes, not guessed venue prices or an exchange rate.
    # The remainder stays available for unlisted flights/lodging/other expenses.
    divisor = allocation_counts or counts
    fractions = [('activity', Decimal('.05') if economy else Decimal('.10')), ('food', Decimal('.10') if economy else Decimal('.20'))]
    allowances = {kind: ((remaining * fraction / max(divisor[kind], counts[kind])).quantize(Decimal('.01'), rounding=ROUND_DOWN)
                         if counts[kind] else Decimal(0)) for kind, fraction in fractions}
    blocks = [(item.date, item.start_time.hour * 60 + item.start_time.minute,
               item.end_time.hour * 60 + item.end_time.minute, resolve_place(item)) for item in existing]
    start_h, start_m = map(int, rules['start_time'].split(':'))
    end_h, end_m = map(int, rules['end_time'].split(':'))
    window_start, window_end = max(8 * 60, start_h * 60 + start_m), min(21 * 60, end_h * 60 + end_m)
    activities = []
    # Place lunch/dinner first so sightseeing cannot consume requested meal slots.
    # Then fill available sightseeing windows, keeping all saved blocks fixed.
    ordered = sorted(enumerate(chosen), key=lambda row: (row[1][0], 0 if row[1][3] == 'lunch' else 1 if row[1][3] == 'dinner' else 2, row[0]))
    for _, (day, place, kind, meal) in ordered:
        duration = 60 if meal else 90
        earliest = max(window_start, 11 * 60 if meal == 'lunch' else 17 * 60 if meal == 'dinner' else window_start)
        latest = min(window_end, 15 * 60 if meal == 'lunch' else 22 * 60 if meal == 'dinner' else window_end)
        preferred = [12 * 60] if meal == 'lunch' else [18 * 60] if meal == 'dinner' else [9 * 60, 14 * 60 + 30, 10 * 60 + 30, 16 * 60]
        candidates = list(dict.fromkeys([*preferred, *range(((earliest + 29) // 30) * 30, latest - duration + 1, 30)]))
        for start in candidates:
            end = start + duration
            if start < earliest or end > latest:
                continue
            conflict = False
            for other_day, other_start, other_end, other_place in blocks:
                if other_day != day:
                    continue
                buffer = 60 if other_place and other_place['area'] != place['area'] else 30
                if start < other_end + buffer and end + buffer > other_start:
                    conflict = True
                    break
            if not conflict:
                break
        else:
            raise HTTPException(422, f'The selected places cannot fit {day} with meals, saved blocks, and travel/rest buffers. Request fewer stops or a wider daily window.')
        blocks.append((day, start, end, place))
        activities.append({'date': day.isoformat(), 'start_time': slot_time(start).strftime('%H:%M'), 'end_time': slot_time(end).strftime('%H:%M'),
            'title': f'{meal.title()} at {place["name"]}' if meal else place['name'],
            'description': 'AI-selected place; backend-arranged planning slot. Cost is a group spending allowance, not a venue quote.',
            'location': f'{place["area"]}, {place["city"]}', 'estimated_cost': format(allowances[kind], '.2f'), 'item_type': kind})
    activities.sort(key=lambda item: (item['date'], item['start_time']))
    return ItineraryPlan(title=f'Places and days in {trip.destination}', summary='AI-selected places arranged by the backend for review.', activities=activities,
        notes=['Places and days were selected by local AI from the limited reference index. The backend arranged visit slots and conservative buffers; routes, hours, and availability are unverified.',
               f'Illustrative allowance formula: {"5%" if economy else "10%"} of the remaining saved budget is divided among proposed sightseeing stops; {"10%" if economy else "20%"} among proposed meals, rounded down to cents. A partial draft revision uses the full draft counts. These are spending envelopes, not venue prices or currency conversions.',
               'The unallocated remainder is not proof that flights or lodging are affordable. They, transfers, and other unlisted expenses are excluded. Confirm actual prices before travel.',
               'Flight arrival and departure times are unknown. Scheduling free time on those dates is an assumption; review it before approval. Nothing is booked or saved until you approve.'])
