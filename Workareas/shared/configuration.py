"""Explicit per-station configuration; no hidden host assignments."""

from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MAX_AGE_SECONDS: float = 30.0
MAX_CLOCK_OFFSET_SECONDS: float = 0.250
MIN_VALIDATION_F1: float = 0.90
MIN_MESSAGE_AVAILABILITY: float = 0.99
POLICY_VERSION: str = "workarea-cards-v1"


@dataclass(frozen=True)
class Commissioning:
    """Locally approved validation evidence, required for authority."""

    report: Path
    approved_by: str
    macro_f1: float
    message_availability: float
    clock_offset_seconds: float
    mandatory_lifecycle_coverage: float
    false_completions: int
    safety_approved: bool
    privacy_approved: bool


@dataclass(frozen=True)
class BrokerConfig:
    """One authenticated site broker; credentials are read from local files."""

    host: str
    username: str
    password_file: Path
    ca_file: Path
    port: int = 8883


@dataclass(frozen=True)
class StationConfig:
    """Settings constructed by the station entry point."""

    station: str
    database: Path
    sources: dict[str, str] = field(default_factory=dict)
    port: int = 8410
    token_file: Path | None = None
    broker: BrokerConfig | None = None
    commissioning: Commissioning | None = None
    max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS
    max_clock_offset_seconds: float = MAX_CLOCK_OFFSET_SECONDS
    minimum_confidence: float = 1.0
    policy_version: str = POLICY_VERSION
