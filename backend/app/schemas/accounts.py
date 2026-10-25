"""Account inputs; API errors must never echo submitted passwords."""
from typing import Annotated

from pydantic import BaseModel, ConfigDict, SecretStr, StrictBool, StringConstraints, field_validator

Username = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,29}$")]


class SignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: Username
    password: SecretStr

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value):
        return value.lower()

    @field_validator("password")
    @classmethod
    def password_limit(cls, value):
        if not 1 <= len(value.get_secret_value()) <= 128:
            raise ValueError("Enter a password of at most 128 characters.")
        return value


def strong_password(value):
    password = value.get_secret_value()
    if len(password) < 15 or len(password) > 128 or not password.strip():
        raise ValueError("Use a password or passphrase between 15 and 128 characters.")
    if password.casefold() in {"passwordpassword", "password123456789", "123456789012345", "qwertyuiopasdfgh"}:
        raise ValueError("Choose a less common password or a longer unique passphrase.")
    return value


class Register(SignIn):
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] = ""
    link_current_profile: StrictBool = False

    @field_validator("password")
    @classmethod
    def registration_password(cls, value):
        return strong_password(value)


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: SecretStr
    new_password: SecretStr

    @field_validator("current_password")
    @classmethod
    def current_limit(cls, value):
        return SignIn.password_limit(value)

    @field_validator("new_password")
    @classmethod
    def new_limit(cls, value):
        return strong_password(value)
