"""Trip data is user-entered planning data, never a confirmed reservation."""

import re
from datetime import date as Date, datetime, time as Time
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, field_validator, model_validator

Currency = Literal["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "INR"]
TripStatus = Literal["planned", "active", "completed"]
ItemType = Literal["activity", "food", "transport", "accommodation", "other"]
ItemStatus = Literal["planned", "cancelled"]
TripText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


def money_value(value):
    if isinstance(value, Decimal):
        value = str(value)
    if not isinstance(value, str) or not re.fullmatch(r"\d+(?:\.\d{1,2})?", value):
        raise ValueError("Enter money as a nonnegative decimal string with at most two decimal places.")
    return value


Money = Annotated[
    Decimal,
    BeforeValidator(money_value),
    Field(ge=Decimal("0"), le=Decimal("10000000"), max_digits=10, decimal_places=2),
]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProfileInput(InputModel):
    display_name: DisplayName


class Profile(BaseModel):
    id: str
    display_name: str
    communication_style: Literal["friendly", "professional", "enthusiastic", "concise"]
    created_at: datetime


class ProfileCreated(BaseModel):
    profile: Profile
    token: str


class TripInput(InputModel):
    name: TripText
    destination: TripText
    departure_location: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] = ""
    start_date: Date
    end_date: Date
    travelers: Annotated[int, Field(strict=True, ge=1, le=50)]
    budget: Money
    currency: Currency
    status: TripStatus = "planned"

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def validate_date_format(cls, value):
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Use a date in YYYY-MM-DD format.")
        return value

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("The end date must be on or after the start date.")
        if (self.end_date - self.start_date).days + 1 > 366:
            raise ValueError("A trip can span at most 366 days.")
        return self


class ItineraryInput(InputModel):
    date: Date
    start_time: Time
    end_time: Time
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""
    location: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    estimated_cost: Money
    item_type: ItemType
    status: ItemStatus = "planned"

    @field_validator("date", mode="before")
    @classmethod
    def validate_date_format(cls, value):
        return TripInput.validate_date_format(value)

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def validate_time_format(cls, value):
        if not isinstance(value, str) or not re.fullmatch(r"\d{2}:\d{2}", value):
            raise ValueError("Use a local time in HH:MM format.")
        return value

    @model_validator(mode="after")
    def validate_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("The end time must be after the start time on the same day.")
        return self


class ItineraryItemResponse(BaseModel):
    id: str
    trip_id: str
    date: Date
    start_time: str
    end_time: str
    title: str
    description: str
    location: str
    estimated_cost: str
    item_type: ItemType
    status: ItemStatus


class TripSummary(BaseModel):
    id: str
    owner_id: str
    name: str
    destination: str
    departure_location: str
    start_date: Date
    end_date: Date
    travelers: int
    budget: str
    currency: Currency
    status: TripStatus
    created_at: datetime
    updated_at: datetime
    estimated_total: str
    remaining_budget: str
    item_count: int


class TripDetail(TripSummary):
    itinerary: list[ItineraryItemResponse]
