"""Strict normalized evidence types shared by the four work areas."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TypeAlias, cast

Scalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = Scalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
MAX_IDENTIFIER_LENGTH: int = 200


class ValidationError(ValueError):
    """An observation is incomplete, conflicting, stale, or invalid."""


def mapping(value: JsonValue, field: str) -> JsonObject:
    """
    Require a JSON object at the input boundary.

    :param value: Decoded JSON value.
    :param field: Diagnostic field name.
    :return: Validated object.
    """
    if not isinstance(value, dict):
        raise ValidationError(f"{field} must be an object")
    return value


def identifier(value: JsonValue, field: str) -> str:
    """
    Require a nonempty bounded identifier without control characters.

    :param value: Input field.
    :param field: Diagnostic field name.
    :return: Validated text.
    """
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > MAX_IDENTIFIER_LENGTH
    ):
        raise ValidationError(
            f"{field} must be nonempty text (max {MAX_IDENTIFIER_LENGTH})"
        )
    if any(ord(character) < 32 for character in value):
        raise ValidationError(f"{field} contains a control character")
    return value


def number(value: JsonValue, field: str, minimum: float = 0.0) -> float:
    """
    Require a finite numeric measurement with its documented lower bound.

    :param value: Input measurement.
    :param field: Diagnostic field name.
    :param minimum: Inclusive minimum in the field's unit.
    :return: Validated number.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field} must be numeric")
    result: float = float(value)
    if not math.isfinite(result) or result < minimum:
        raise ValidationError(f"{field} must be finite and >= {minimum}")
    return result


def timestamp(value: JsonValue, field: str) -> datetime:
    """
    Parse a timezone-aware ISO timestamp without guessing a timezone.

    :param value: ISO 8601 text.
    :param field: Diagnostic field name.
    :return: UTC instant.
    """
    text: str = identifier(value, field)
    try:
        result: datetime = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValidationError(f"{field} must be ISO 8601") from error
    if result.tzinfo is None:
        raise ValidationError(f"{field} must include timezone")
    return result.astimezone(timezone.utc)


@dataclass(frozen=True)
class Evidence:
    """One adapter record, before cross-source process abstraction."""

    id: str
    kind: str
    source_id: str
    session_id: str
    sequence: int
    source_time: datetime
    confidence: float
    values: dict[str, Scalar]
    raw: JsonObject


def parse_evidence(
    raw: JsonObject, now: datetime, max_age: float, clock_skew: float
) -> Evidence:
    """
    Reject unhealthy, malformed, stale, future, or nonfinite adapter evidence.

    :param raw: Source record.
    :param now: Edge ingestion time.
    :param max_age: Maximum age in seconds.
    :param clock_skew: Allowed future offset in seconds.
    :return: Validated evidence with the original source timestamp.
    """
    source_time: datetime = timestamp(raw.get("source_time"), "source_time")
    age: float = (now - source_time).total_seconds()
    if age > max_age or age < -clock_skew:
        raise ValidationError(
            "source_time is stale or ahead of the permitted clock offset"
        )
    if raw.get("health") != "ok" or raw.get("quality") != "valid":
        raise ValidationError(
            "unhealthy or invalid evidence is unknown, not completion"
        )
    sequence: JsonValue = raw.get("sequence")
    if type(sequence) is not int or sequence < 0:
        raise ValidationError("sequence must be a nonnegative integer")
    confidence: float = number(raw.get("confidence"), "confidence")
    if confidence > 1:
        raise ValidationError("confidence must be <= 1")
    values: JsonObject = mapping(raw.get("values"), "values")
    for key, value in values.items():
        if isinstance(value, (dict, list)):
            raise ValidationError(f"values.{key} must be scalar")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValidationError(f"values.{key} must be finite")
    return Evidence(
        identifier(raw.get("id"), "id"),
        identifier(raw.get("kind"), "kind"),
        identifier(raw.get("source_id"), "source_id"),
        identifier(raw.get("session_id"), "session_id"),
        sequence,
        source_time,
        confidence,
        cast(dict[str, Scalar], values),
        raw,
    )
