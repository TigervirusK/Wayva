"""Offline examples with named places; these are never presented as live AI/search."""

from datetime import time, timedelta
from decimal import Decimal

from fastapi import HTTPException

from app.models import Trip
from app.schemas.planning import ItineraryPlan
from app.services.daily_planning import DailyRequirements, is_meal


# Venue names are examples drawn from their official sites, not future availability.
# Each row keeps new stops in one neighborhood; saved stops remain untouched.
TOKYO = [
    {
        "aliases": ("asakusa", "sumida", "senso", "nakamise"),
        "sights": (("Senso-ji surroundings and Nakamise walk", "Nakamise-dori, Asakusa, Tokyo"),
                   ("Sumida Park riverside walk", "Sumida Park, Asakusa, Tokyo")),
        "lunch": ("Asakusa Mugitoro", "Asakusa Mugitoro, 2-2-4 Kaminarimon, Taito, Tokyo", "https://www.mugitoro.co.jp/"),
        "dinner": ("Asakusa Imahan Kokusai Street", "Asakusa Imahan, 3-1-12 Nishi-Asakusa, Taito, Tokyo", "https://www.asakusaimahan.co.jp/en/kokusai"),
        "dinner_multiplier": "2.25",
    },
    {
        "aliases": ("harajuku", "yoyogi", "omotesando", "meiji"),
        "sights": (("Yoyogi Park photography walk", "Yoyogi Park, Shibuya, Tokyo"),
                   ("Omotesando neighborhood stroll", "Omotesando, Shibuya, Tokyo")),
        "lunch": ("AFURI Harajuku", "AFURI Harajuku, 3-63-1 Sendagaya, Shibuya, Tokyo", "https://afuri.com/findus/index.html"),
        "dinner": ("MAiSEN Aoyama main restaurant", "MAiSEN Aoyama, 4-8-5 Jingumae, Shibuya, Tokyo", "https://mai-sen.com/restaurant/88dcd35dcaa3002752e73ee827e60e9a.pdf"),
        "dinner_multiplier": "1",
    },
    {
        "aliases": ("tsukiji", "ginza", "hibiya"),
        "sights": (("Tsukiji neighborhood exploration", "Tsukiji, Chuo, Tokyo"),
                   ("Ginza architecture and shopfront walk", "Ginza, Chuo, Tokyo")),
        "lunch": ("Tsukiji Outer Market", "Tsukiji Outer Market, Tsukiji 4-chome, Chuo, Tokyo", "https://www.tsukiji.or.jp/english/"),
        "dinner": ("Ginza Lion 7-chome", "Ginza Lion, 7-9-20 Ginza, Chuo, Tokyo", "https://www.ginzalion.jp/shop/brand/lion/shop1.html"),
        "dinner_multiplier": "1",
    },
]

KYOTO = [{
    "aliases": ("gion", "nishiki", "kamogawa", "higashiyama"),
    "sights": (("Nishiki neighborhood exploration", "Nishiki Market surroundings, Nakagyo, Kyoto"),
               ("Kamogawa riverside photography walk", "Kamogawa riverside near Shijo Bridge, Kyoto")),
    "lunch": ("Tobeian Nishiki", "Tobeian, Nishiki Market, Nakagyo, Kyoto", "https://tobeian.jp/en/"),
    "dinner": ("MARE Gion", "MARE Gion, Gion neighborhood, Higashiyama, Kyoto", "https://gion-mare.com/en/"),
    "dinner_multiplier": "1",
}]

# Illustrative spending allowances per traveler, NOT quoted menus or exchange rates.
MEAL_ALLOWANCES = {
    "USD": ("20", "40"), "EUR": ("20", "40"), "GBP": ("18", "35"),
    "JPY": ("3000", "6000"), "CAD": ("28", "55"), "AUD": ("30", "60"),
    "INR": ("1800", "3500"),
}


def daily_demo_plan(trip: Trip, requirements: DailyRequirements) -> ItineraryPlan:
    destination = trip.destination.casefold()
    if any(city in destination for city in ("tokyo", "東京")):
        catalog = TOKYO
    elif any(city in destination for city in ("kyoto", "京都")):
        catalog = KYOTO
    else:
        raise HTTPException(503, "Real AI is not connected. Curated daily examples support Tokyo and Kyoto only; enable live AI for another destination.")
    activities = []
    planned = [item for item in trip.itinerary if item.status == "planned"]
    blocks = [(item.date, item.start_time, item.end_time) for item in planned]
    allowance = MEAL_ALLOWANCES[trip.currency]

    def add(day, title, location, description, item_type, cost, windows):
        for start, end in windows:
            # A half-hour transfer/rest buffer is a scheduling allowance, not routing data.
            start_minutes = start.hour * 60 + start.minute
            end_minutes = end.hour * 60 + end.minute
            if any(day == existing_day and start_minutes < existing_end.hour * 60 + existing_end.minute + 30
                   and end_minutes + 30 > existing_start.hour * 60 + existing_start.minute
                   for existing_day, existing_start, existing_end in blocks):
                continue
            blocks.append((day, start, end))
            activities.append({
                "date": day.isoformat(), "start_time": start.strftime("%H:%M"), "end_time": end.strftime("%H:%M"),
                "title": title, "description": description, "location": location,
                "estimated_cost": f"{cost:.2f}", "item_type": item_type,
            })
            return
        raise HTTPException(409, f"There is no free time for {title} on {day.isoformat()} around your saved activities. Your trip is unchanged; free up a time slot or request fewer stops.")

    days = (trip.end_date - trip.start_date).days + 1
    for offset in range(days):
        day = trip.start_date + timedelta(days=offset)
        saved = [item for item in planned if item.date == day]
        saved_text = " ".join(f"{item.title} {item.location}" for item in saved).casefold()
        cluster = next((row for row in catalog if any(alias in saved_text for alias in row["aliases"])), catalog[offset % len(catalog)])
        for meal, windows in (
            ("lunch", ((time(12), time(13)), (time(12, 30), time(13, 30)), (time(11, 30), time(12, 30)), (time(13), time(14)))),
            ("dinner", ((time(18), time(19)), (time(18, 30), time(19, 30)), (time(19), time(20)), (time(20), time(21)))),
        ):
            if not getattr(requirements, meal) or any(is_meal(item, meal) for item in saved):
                continue
            name, location, source = cluster[meal]
            base = Decimal(allowance[0 if meal == "lunch" else 1])
            multiplier = Decimal(cluster["dinner_multiplier"] if meal == "dinner" else "1")
            cost = base * multiplier * trip.travelers
            add(day, f"{meal.title()} at {name}", location,
                f"Curated meal idea; the cost is an illustrative group spending allowance, not this venue's menu price. Check dietary suitability, hours and availability: {source}",
                "food", cost, windows)
        missing = max(requirements.minimum_activities - sum(item.item_type == "activity" for item in saved), 0)
        for index in range(missing):
            # Prefer the other stop if one of the two is already saved.
            choices = [row for row in cluster["sights"] if row[0].casefold() not in saved_text]
            title, location = (choices or cluster["sights"])[index % len(choices or cluster["sights"])]
            add(day, title, location,
                "Curated outdoor neighborhood idea. Suggested time is unverified; allow extra transfer time from your saved stops and check access before travel.",
                "activity", Decimal("0"), ((time(9), time(10)), (time(14, 30), time(15, 30)),
                                            (time(16), time(17)), (time(10, 30), time(11, 30)), (time(8), time(9))))
    if not activities:
        raise HTTPException(422, "Your saved itinerary already contains the requested daily stops and meals. No duplicate suggestions were added.")
    existing_cost = sum((item.estimated_cost for item in planned), Decimal("0"))
    added_cost = sum((Decimal(item["estimated_cost"]) for item in activities), Decimal("0"))
    if existing_cost + added_cost > trip.budget:
        raise HTTPException(422, "These curated meal allowances exceed your remaining trip budget. Your itinerary is unchanged; enable live AI for a cheaper personalized plan, request fewer meals, or edit the budget.")
    activities.sort(key=lambda item: (item["date"], item["start_time"]))
    return ItineraryPlan(
        title=f"Daily stops and meals in {trip.destination}",
        summary="An offline curated example with your requested daily activities and meal places. Saved activities are preserved; only missing stops and meals are proposed. This is not live AI.",
        activities=activities,
        notes=[
            "Curated demonstration, not AI. Enable live AI for personalized places, dietary preferences, and more variety; this small catalog repeats neighborhoods on longer trips.",
            "Meal costs are illustrative spending allowances for the whole group in your trip currency, not verified menu prices or exchange-rate conversions. Outdoor walks have no admission allowance; paid attractions are excluded.",
            "Official venue links are provided for checking. No future opening hours, prices, availability, dietary suitability or exact travel times are verified; nothing is booked.",
            "New suggestions leave at least 30 minutes between stops. This is a planning buffer, not a verified route; check transport from your saved activities and allow more time as needed.",
            "Transport, flights, lodging and other meals are excluded from these estimates. Review the whole trip budget before approving.",
        ],
    )
