"""Small helpers that turn raw form text into clean, validated values."""
from datetime import date
from enum import Enum
from typing import Optional, Type


class FormError(Exception):
    """Raised when a submitted form is invalid. The message is shown to the user."""


def required(value: Optional[str], label: str) -> str:
    value = (value or "").strip()
    if not value:
        raise FormError(f"{label} is required.")
    return value


def optional_text(value: Optional[str]) -> str:
    return (value or "").strip()


def parse_date(value: Optional[str], label: str, is_required: bool = True) -> Optional[date]:
    value = (value or "").strip()
    if not value:
        if is_required:
            raise FormError(f"{label} is required.")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise FormError(f"{label} must be a valid date (YYYY-MM-DD).")


def parse_enum(enum_cls: Type[Enum], value: Optional[str], label: str):
    try:
        return enum_cls(value)
    except ValueError:
        allowed = ", ".join(e.value for e in enum_cls)
        raise FormError(f"{label} must be one of: {allowed}.")


def parse_int(value: Optional[str], label: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise FormError(f"{label} must be selected.")
