"""Deterministic trip facts, explicit constraints, and honest reference coverage.

The reference index verifies only named identities/cities/areas recorded in its
sources. Unknown places remain unverified. No geocoder, exchange-rate service,
price/availability API or route engine is implied by these checks.
"""
import json
import re
import unicodedata
from datetime import date, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from fastapi import HTTPException

REFERENCE = json.loads((Path(__file__).resolve().parent.parent / 'data/place_references.json').read_text(encoding='utf-8'))
PLACES = REFERENCE['places']
QUALITY_INSTRUCTIONS = '''
Use calculated_facts for inclusive day counts and budget arithmetic. Saved dates,
destination, travelers and currency cannot be changed through chat. Flight arrival
and departure times are UNKNOWN unless the traveler explicitly supplies them. Do
not invent flight/check-in times; explain the assumption of free time on travel days.
planning_constraints are backend-enforced: keep all proposed objects in daily_window,
cover every saved date if cover_all_days, preserve restrictions when revising drafts.
Leave at least 30 minutes between stops, and 60 minutes between different reference
areas; those are conservative planning allowances, NOT verified routes. Cluster days
by area to reduce travel. Avoid repeat sights unless explicitly requested; repeated
meals are allowed only with an explanation, not as different attractions.
A DAILY WINDOW IS NOT ONE ACTIVITY'S DURATION. A sight normally takes 60-120 minutes,
and a meal 60 minutes. Do not schedule one sight for the whole 09:00-21:00 window.
For example a free day can use 09:00-10:30 for a sight, 12:00-13:00 for lunch,
14:30-16:00 for another sight and 18:00-19:00 for dinner. These are scheduling examples,
not business opening hours. Choose different free slots to respect saved blocks or
narrower requested windows. Do not put dining opening-hour ranges into activity times.
place_references is a LIMITED reviewed identity/city/area index, not live search.
For city-only plans choose exact referenced names, using their area and city. Do
not replace their neighborhood with a guess. Gion is in Kyoto; Omoide Yokocho is
in Shinjuku, Tokyo. For other places explicitly say their location is unverified.
No verified menu/admission prices, FX rates, operating hours or availability exist.
Never pair a luxury venue with a guessed cheap price. Suggest a different venue if
a credible quote is unavailable. Costs are illustrative whole-group spending
allowances in the saved currency, not restaurant prices or exchange conversions.
Say what is excluded: flights, lodging and transfers unless listed. The backend
calculates totals; don't invent a total in prose. Do not claim saved actions.
'''


def normalized(value):
    value = ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(c))
    return ' '.join(re.findall(r'\w+', value))


def contains(text, name):
    return f' {normalized(name)} ' in f' {normalized(text)} '


def known_destination_cities(destination):
    return {city for city, aliases in {'Tokyo': ('Tokyo', '東京'), 'Kyoto': ('Kyoto', '京都'),
        'Paris': ('Paris',), 'London': ('London',), 'Osaka': ('Osaka',), 'Rome': ('Rome',), 'New York': ('New York',)}.items()
        if any(contains(destination, alias) for alias in aliases)}


def resolve_place(item):
    # Prefer a specific name in the title over a broad neighborhood in location.
    for field in (item.title, item.location):
        matches = [(len(normalized(alias)), place) for place in PLACES for alias in place['aliases'] if contains(field, alias)]
        if matches:
            return max(matches, key=lambda match: match[0])[1]
    return None


def money(value):
    return format(Decimal(value).quantize(Decimal('.01'), rounding=ROUND_HALF_UP), 'f')


def trip_facts(context):
    start, end = date.fromisoformat(context['start_date']), date.fromisoformat(context['end_date'])
    days = (end - start).days + 1
    travelers = context.get('travelers', 1)
    budget = Decimal(context['budget'])
    return {'calendar_days_inclusive': days, 'calendar_dates': [(start + timedelta(days=n)).isoformat() for n in range(days)],
        'budget_scope': 'total_for_whole_group', 'budget_per_person_allowance': money(budget / travelers),
        'budget_per_day_group_allowance': money(budget / days), 'currency': context.get('currency', ''),
        'arrival_time': 'unknown_not_stored', 'departure_time': 'unknown_not_stored',
        'cost_basis': 'illustrative_group_allowances_not_verified_quotes', 'currency_conversion': 'none'}


def constraints_for(request, conversation=None, previous=None):
    """Extract only explicit supported restrictions; the model still interprets intent.

    Carry prior restrictions through draft revisions. A latest explicit window
    replaces an earlier one. Unsupported phrasing is not claimed as validated.
    """
    rules = dict(previous or {})
    rules.setdefault('version', 1)
    rules.setdefault('start_time', '00:00')
    rules.setdefault('end_time', '23:59')
    rules.setdefault('avoid_repeats', False)
    rules.setdefault('allow_repeated_sights', False)
    rules.setdefault('cover_all_days', False)
    rules.setdefault('city_only', None)
    rules.setdefault('must_visit_areas', [])
    rules.setdefault('day_scope', None)
    rules.setdefault('economy_requested', False)
    texts = [m['content'] for m in (conversation or []) if m.get('role') == 'user']
    if not texts or texts[-1] != request:
        texts.append(request)
    clock = r'(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?'
    pattern = rf'(?:between|from)\s+{clock}\s*(?:and|to|[-–])\s*{clock}'
    for text in texts:
        text = text.casefold()
        if re.search(r'\b(?:cheaper|less expensive|lower.cost|budget.friendly|economy)\b|\b(?:reduce|lower|cut)\s+(?:the\s+)?(?:cost|spending|allowance)', text):
            rules['economy_requested'] = True
        if re.search(r'\b(?:original|standard)\s+(?:spending|allowances?|budget style)\b', text):
            rules['economy_requested'] = False
        match = re.search(pattern, text)
        if match:
            h1, m1, a1, h2, m2, a2 = match.groups()
            def clock_value(hour, minute, suffix):
                hour, minute = int(hour), int(minute or 0)
                if minute > 59 or (suffix and not 1 <= hour <= 12) or (not suffix and hour > 23):
                    raise HTTPException(422, 'Use a valid daily time window, such as between 09:00 and 21:00.')
                if suffix:
                    hour = hour % 12 + (12 if suffix.startswith('p') else 0)
                return f'{hour:02d}:{minute:02d}'
            start = clock_value(h1, m1, a1 or a2)
            end = clock_value(h2, m2, a2)
            if start >= end:
                raise HTTPException(422, 'The daily window must end after it starts on the same day. Split overnight plans by date.')
            rules.update(start_time=start, end_time=end)
        for city in ('Tokyo', 'Kyoto'):
            if re.search(rf'\b(?:stay|keep|remain)\s+(?:only\s+)?(?:within|in)\s+{city.casefold()}\b|\b{city.casefold()}[- ]only\b', text):
                rules['city_only'] = city
        if re.search(r'\b(?:include|visit|see|explore)\b', text):
            areas = set(rules['must_visit_areas'])
            for area in {p['area'] for p in PLACES}:
                if contains(text, area):
                    if re.search(rf'\b(?:skip|exclude|without|avoid|remove)\s+{re.escape(area.casefold())}\b', text):
                        areas.discard(area)
                    else:
                        areas.add(area)
            rules['must_visit_areas'] = sorted(areas)
        if re.search(r'\b(?:avoid|no|without)\s+(?:unnecessary\s+)?(?:repeats|duplicates|duplicate attractions)\b', text):
            rules['avoid_repeats'] = True
        if re.search(r'\b(?:allow repeats|repeat visits|revisit|visit again)\b', text):
            rules['avoid_repeats'] = False
            rules['allow_repeated_sights'] = True
        if re.search(r'\b(?:each|every|per)\s+day\b|\b(?:full|whole|entire)\s+trip\b|\b(?:[2-9]|two|three|four|five|six|seven|eight|nine)[- ]day\b', text):
            rules['cover_all_days'] = True
            rules['day_scope'] = None
        if re.search(r'\b(?:only|just|plan)\s+(?:the\s+)?(?:first|second|third|last|one|1)\s+day\b|\bonly\s+(?:may|june|july|august|september|october|november|december|january|february|march|april)\s+\d', text):
            rules['cover_all_days'] = False
            scoped = re.search(r'\b(?:only|just|plan)\s+(?:the\s+)?(first|second|third|last|one|1)\s+day\b', text)
            if scoped:
                rules['day_scope'] = scoped[1]
    return rules


def reference_context(destination):
    cities = known_destination_cities(destination)
    if '東京' in destination:
        cities.add('Tokyo')
    if '京都' in destination:
        cities.add('Kyoto')
    return {'coverage': REFERENCE['scope'], 'reviewed_on': REFERENCE['reviewed_on'],
        'places': [{k: p[k] for k in ('id', 'name', 'city', 'area', 'kind')} | {'meal_periods': p.get('meal_periods', ['lunch', 'dinner'])}
                   for p in PLACES if p['city'] in cities and not p.get('quote_required')]}


def validate_quality(items, trip, rules):
    places, warnings = [], []
    known_cities = known_destination_cities(trip.destination)
    if rules.get('city_only') and known_cities and rules['city_only'] not in known_cities:
        raise HTTPException(422, 'The requested city-only restriction differs from the saved destination. Edit the saved trip or discuss an excursion explicitly; chat cannot silently change it.')
    allowed = {rules['city_only']} if rules.get('city_only') else known_cities
    existing = [item for item in trip.itinerary if item.status == 'planned']
    seen = {resolve_place(item)['id'] if resolve_place(item) else normalized(item.title) for item in existing}
    for index, item in enumerate(items):
        if not rules['start_time'] <= item.start_time.strftime('%H:%M') < item.end_time.strftime('%H:%M') <= rules['end_time']:
            raise HTTPException(422, f'The proposed activity on {item.date} must fit your {rules["start_time"]}–{rules["end_time"]} daily window. Your saved trip is unchanged.')
        duration = (item.end_time.hour * 60 + item.end_time.minute) - (item.start_time.hour * 60 + item.start_time.minute)
        if duration > (120 if item.item_type == 'food' else 240):
            raise HTTPException(422, f'{item.title} has an unrealistic visit duration. Use at most two hours for a meal or four hours for another stop; opening-hour ranges are not visit durations.')
        place = resolve_place(item)
        for other in PLACES:
            if allowed and other['city'] not in allowed and any(contains(f'{item.title} {item.location}', alias) for alias in other['aliases']):
                raise HTTPException(422, f'{other["name"]} is outside the requested destination ({other["city"]}). Request an explicitly identified excursion separately.')
        key = place['id'] if place else normalized(item.title)
        if key in seen:
            if rules.get('avoid_repeats'):
                raise HTTPException(422, f'The plan repeats {place["name"] if place else item.title}. Choose another place or explicitly allow repeat visits.')
            warnings.append('Repeated places need review; a repeated meal or neighborhood is not a new attraction.')
        seen.add(key)
        if place:
            if place.get('quote_required'):
                raise HTTPException(422, f'{place["name"]} requires a verified provider price/availability quote. A guessed low-cost allowance is not credible; choose another meal venue. No live quote service is connected.')
            if allowed and place['city'] not in allowed:
                raise HTTPException(422, f'{place["name"]} is in {place["city"]}, outside the requested destination. Request an explicitly identified excursion separately.')
            # Reject a recognized city/area contradicted by the supplied location.
            for city in ('Tokyo', 'Kyoto'):
                if contains(item.location, city) and city != place['city']:
                    raise HTTPException(422, f'{place["name"]} belongs to {place["city"]}, not the supplied city. Your saved trip is unchanged.')
            areas = {p['area'] for p in PLACES if p['city'] == place['city']}
            claimed = {area for area in areas if contains(item.location, area)}
            if claimed and place['area'] not in claimed:
                raise HTTPException(422, f'{place["name"]} is referenced in {place["area"]}, {place["city"]}. Correct the neighborhood before review.')
            if item.item_type == 'food' and place.get('meal_periods'):
                meal = 'lunch' if item.start_time < time(16) else 'dinner'
                if meal not in place['meal_periods']:
                    raise HTTPException(422, f'Use {place["name"]} as a {"/".join(place["meal_periods"])} idea in this reference index; choose another venue for {meal}. Hours still need checking.')
            area_only = place['id'] in {'asakusa', 'shibuya', 'shinjuku', 'akihabara', 'nakano', 'ikebukuro', 'kichijoji', 'roppongi', 'gion'} or not any(contains(item.title, alias) for alias in place['aliases'])
            places.append({'index': index, 'status': 'area_reference' if area_only else 'reference_matched', 'name': place['name'], 'city': place['city'],
                           'area': place['area'], 'source_url': place['source'], 'reviewed_on': REFERENCE['reviewed_on']})
        else:
            if rules.get('city_only'):
                raise HTTPException(422, 'A place could not be matched to the limited destination reference index. Use its listed names for a city-only draft, or discuss unverified ideas without a strict geographic claim.')
            places.append({'index': index, 'status': 'unverified', 'name': item.title, 'city': None, 'area': None, 'source_url': None, 'reviewed_on': None})
            warnings.append('Some places are unverified: check their identity and location before travel.')
        if re.search(r'\b(?:flight|airport arrival|airport pickup|hotel check[- ]?in)\b', normalized(item.title)):
            warnings.append('Arrival/departure times are unknown. These travel-related times are assumptions, not confirmed bookings.')
    # Compare new items with saved blocks without rejecting unchanged saved-to-saved gaps.
    blocks = sorted([(i, True) for i in items] + [(i, False) for i in existing], key=lambda row: (row[0].date, row[0].start_time))
    for (first, new_first), (second, new_second) in zip(blocks, blocks[1:]):
        if first.date != second.date or not (new_first or new_second):
            continue
        gap = (second.start_time.hour * 60 + second.start_time.minute) - (first.end_time.hour * 60 + first.end_time.minute)
        if gap < 30:
            raise HTTPException(422, f'Leave a travel/rest buffer of at least 30 minutes between {first.title} and {second.title} on {first.date}. This is a planning allowance, not a verified route.')
        a, b = resolve_place(first), resolve_place(second)
        if a and b and a['city'] != b['city']:
            raise HTTPException(422, 'Inter-city travel in one day needs a verified route and transport plan. Keep one city per day in this reference-based planner.')
        if a and b and a['area'] != b['area'] and gap < 60:
            raise HTTPException(422, f'Leave a conservative 60-minute buffer between different reference areas ({a["area"]} and {b["area"]}), or group nearby stops. This is not a route-time estimate.')
    if rules.get('cover_all_days'):
        scheduled = {item.date for item in [*existing, *items]}
        current = trip.start_date
        while current <= trip.end_date:
            if current not in scheduled:
                raise HTTPException(422, f'The full-trip request is missing {current.isoformat()}. The saved dates cover {(trip.end_date - trip.start_date).days + 1} calendar days inclusive.')
            current += timedelta(days=1)
    visited = {p['area'] for i in [*existing, *items] if (p := resolve_place(i)) is not None}
    missing = set(rules.get('must_visit_areas', [])) - visited
    if missing:
        raise HTTPException(422, 'The requested areas are missing from the draft: ' + ', '.join(sorted(missing)) + '. Your saved itinerary is unchanged.')
    return places, list(dict.fromkeys(warnings))


def quality_report(items, trip, rules):
    places, warnings = validate_quality(items, trip, rules)
    categories = {kind: sum((i.estimated_cost for i in items if i.item_type == kind), Decimal(0)) for kind in ('activity', 'food', 'transport', 'accommodation', 'other')}
    return {'version': 1, 'trip_days': (trip.end_date - trip.start_date).days + 1,
        'travelers': trip.travelers, 'cost_basis': 'illustrative_group_allowances', 'currency_conversion': 'none',
        'arrival_departure_times': 'unknown', 'by_category': {k: money(v) for k, v in categories.items()},
        'places': places, 'warnings': warnings, 'daily_window': f'{rules["start_time"]}–{rules["end_time"]}',
        'buffer_policy': '30-minute minimum; 60 minutes between different reference areas. Planning allowances, not verified routes.',
        'exclusions': 'Only listed planned items are counted. Flights, lodging, other meals and transfers are excluded unless explicitly listed; no exchange rate is applied.'}
