from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

UserRole = Literal["user", "admin", "super_admin"]


class AuthenticatedUser(BaseModel):
    user_id: str
    username: str
    display_name: str
    avatar_url: str | None = None
    role: UserRole
    is_active: bool
    password_must_change: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    display_name: str | None = None
    password: str

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("username is required.")
        if len(normalized) < 3 or len(normalized) > 32:
            raise ValueError("username must be between 3 and 32 characters.")
        if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for character in normalized):
            raise ValueError("username may only contain letters, digits, '_' or '-'.")
        return normalized

    @field_validator("display_name")
    @classmethod
    def normalize_register_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > 64:
            raise ValueError("display_name must be 64 characters or fewer.")
        if any(character in "\r\n\t\0" for character in normalized):
            raise ValueError("display_name may not contain control characters.")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 6:
            raise ValueError("password must be at least 6 characters.")
        if len(normalized) > 128:
            raise ValueError("password must be 128 characters or fewer.")
        return normalized


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("username is required.")
        if len(normalized) < 3 or len(normalized) > 32:
            raise ValueError("username must be between 3 and 32 characters.")
        if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for character in normalized):
            raise ValueError("username may only contain letters, digits, '_' or '-'.")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 6:
            raise ValueError("password must be at least 6 characters.")
        if len(normalized) > 128:
            raise ValueError("password must be 128 characters or fewer.")
        return normalized


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str
    new_password: str

    @field_validator("current_password", "new_password")
    @classmethod
    def normalize_password(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 6:
            raise ValueError("password must be at least 6 characters.")
        if len(normalized) > 128:
            raise ValueError("password must be 128 characters or fewer.")
        return normalized


class CurrentPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str

    @field_validator("current_password")
    @classmethod
    def normalize_password(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 6:
            raise ValueError("password must be at least 6 characters.")
        if len(normalized) > 128:
            raise ValueError("password must be 128 characters or fewer.")
        return normalized


class UpdateProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    avatar_url: str | None = None

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name is required.")
        if len(normalized) > 64:
            raise ValueError("display_name must be 64 characters or fewer.")
        if any(character in "\r\n\t\0" for character in normalized):
            raise ValueError("display_name may not contain control characters.")
        return normalized

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > 200_000:
            raise ValueError("avatar_url is too large.")
        if not (
            normalized.startswith("data:image/")
            or normalized.startswith("https://")
            or normalized.startswith("http://")
        ):
            raise ValueError("avatar_url must be an image data URL or HTTP URL.")
        return normalized


class AuthUserEnvelope(BaseModel):
    user: AuthenticatedUser


class LoginResponse(AuthUserEnvelope):
    must_change_password: bool


class AuthStatusResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ResetPasswordResponse(BaseModel):
    status: Literal["ok"] = "ok"
    temporary_password: str


class StoredAuthSession(BaseModel):
    auth_session_id: str
    user_id: str
    token_hash: str
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime


class AuthLoginResult(BaseModel):
    user: AuthenticatedUser
    raw_token: str
    expires_at: datetime


class AuthSessionCookie(BaseModel):
    key: str = "carbonrag_session"
    max_age_seconds: int = Field(default=7 * 24 * 60 * 60)
