"""Only the details useful for an assisted handoff; no cards or identity documents."""
import re
from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, field_validator, model_validator

Text100 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
Carrier = Literal["AA", "UA", "DL", "BA", "NH", "JL", "OTHER"]


class PrivateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TravelerDetails(PrivateInput):
    given_names: Text100 = ""
    family_name: Text100 = ""
    email: Annotated[str, StringConstraints(strip_whitespace=True, max_length=254)] = ""
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=16)] = ""
    home_airport: Annotated[str, StringConstraints(pattern=r"^(?:[A-Z]{3})?$", max_length=3)] = ""
    country_of_residence: Annotated[str, StringConstraints(pattern=r"^(?:[A-Z]{2})?$", max_length=2)] = ""
    preferred_currency: Literal["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "INR"] = "USD"

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid contact email or leave it blank.")
        return value

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value):
        if value and not re.fullmatch(r"\+[1-9]\d{6,14}", value):
            raise ValueError("Use international format, such as +12025550123, or leave it blank.")
        return value


class PrivateBooking(PrivateInput):
    id: UUID
    trip_id: UUID | None = None
    airline: Carrier
    flight_number: Annotated[str, StringConstraints(pattern=r"^[A-Z0-9]{2,3}\d{1,4}[A-Z]?$", max_length=10)]
    departure_date: date
    origin: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
    destination: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
    booking_reference: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9-]{3,30}$")]
    original_seller: Literal["airline", "travel_agency", "other"] = "airline"
    seller_name: Text100 = ""

    @model_validator(mode="after")
    def validate_route(self):
        if self.origin == self.destination:
            raise ValueError("Origin and destination airports must differ.")
        return self


class VaultData(PrivateInput):
    traveler: TravelerDetails = Field(default_factory=TravelerDetails)
    bookings: list[PrivateBooking] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def unique_bookings(self):
        if len({booking.id for booking in self.bookings}) != len(self.bookings):
            raise ValueError("Saved booking IDs must be unique.")
        return self


class VaultPassword(PrivateInput):
    password: SecretStr

    @field_validator("password")
    @classmethod
    def password_length(cls, value):
        if not 12 <= len(value.get_secret_value()) <= 128:
            raise ValueError("Use a vault password between 12 and 128 characters.")
        return value


class VaultSave(PrivateInput):
    revision: UUID
    data: VaultData


class VaultPasswordChange(VaultPassword):
    current_password: SecretStr

    @field_validator('current_password')
    @classmethod
    def current_password_length(cls, value):
        return VaultPassword.password_length(value)


class AssistanceRequest(PrivateInput):
    booking_id: UUID
