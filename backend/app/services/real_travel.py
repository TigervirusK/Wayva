"""Honest capability gates and a no-charge original-provider handoff.

These links are fixed official sites, never supplied by a model or user. No
credentials, booking references, names, or dates are placed in their URLs.
"""
from fastapi import HTTPException

AIRLINES = {
    "AA": ("American Airlines", "https://www.aa.com/manage-reservation/viewres/ui/app/"),
    "UA": ("United Airlines", "https://www.united.com/en/us/manageres/mytrips"),
    "DL": ("Delta Air Lines", "https://www.delta.com/"),
    "BA": ("British Airways", "https://www.britishairways.com/"),
    "NH": ("ANA", "https://www.ana.co.jp/en/us/plan-book/how-to-manage-your-booking/"),
    "JL": ("Japan Airlines", "https://www.jal.co.jp/en-us/my-booking.html"),
    "OTHER": ("Other airline", None),
}


def capabilities():
    # No adapter has been implemented or authenticated. A key or environment flag
    # must never turn any of these into an unsupported live-booking capability.
    return {
        "mode": "real", "access": "assisted_only", "provider_connected": False,
        "assisted_handoff": True, "encrypted_settings": True,
        "flight_monitoring": False, "live_flight_search": False, "rebooking": False,
        "provider_confirmation": False, "automatic_itinerary_repair": False,
        "external_changes": False, "production_account_ready": False,
        "message": "No authorized live provider is connected. Saved details are user-entered and unverified. No flight has been searched, purchased, changed, or confirmed.",
        "airlines": [{"code": key, "name": value[0]} for key, value in AIRLINES.items()],
        "stages": [
            {"id": "disruption", "label": "Disruption detected", "status": "not_connected", "reason": "A live flight-status provider and explicit tracking consent are required."},
            {"id": "options", "label": "Replacement options found", "status": "not_connected", "reason": "Authorized live inventory and verified current prices are required."},
            {"id": "approval", "label": "User approves", "status": "unavailable", "reason": "A current provider quote with full charges and conditions is required."},
            {"id": "submission", "label": "Booking submitted", "status": "unavailable", "reason": "Booking authority, production authentication, payment, and duplicate protection are required."},
            {"id": "confirmation", "label": "Booking confirmed", "status": "unavailable", "reason": "Only a verified provider confirmation can complete this stage."},
            {"id": "repair", "label": "Itinerary repaired", "status": "unavailable", "reason": "Confirmed replacement details and separate outcomes for dependent providers are required."},
        ],
    }


def assistance(data, booking_id: str):
    booking = next((item for item in data.bookings if str(item.id) == booking_id), None)
    if booking is None:
        raise HTTPException(404, "Saved booking details were not found in this private profile.")
    name, url = AIRLINES[booking.airline]
    seller = name if booking.original_seller == "airline" else booking.seller_name or "the original ticket seller"
    return {
        "booking_id": str(booking.id), "verification_status": "user_entered_unverified",
        "booking_status": "not_booked_by_triprescue", "provider_confirmed": False,
        "airline_name": name, "official_airline_url": url,
        "original_seller": seller, "contact_original_seller": booking.original_seller != "airline",
        "steps": [
            "Check the flight status on the airline's official website or app. Wayva has not detected a disruption.",
            f"Ask {seller} to retrieve your reservation and explain the authorized change or cancellation options.",
            "Check the exact replacement flights, total additional charges, baggage allowance, and fare conditions before approving anything with that provider.",
            "Wait for the airline or original seller to confirm the new ticket. These saved details do not verify or create a booking.",
            "Contact pickup, hotel, and activity providers separately. Their changes remain unconfirmed until each provider verifies them.",
        ],
        "disclosure": "This is an assisted manual handoff. Wayva does not submit forms, contact providers, or transmit your saved details when you open the link.",
    }
