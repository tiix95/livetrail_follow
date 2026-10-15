"""Dataclasses used across livetrail-follow for structured internal data."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WebhookConfig:
    """Default webhook settings, used unless overridden per-runner."""

    endpoint: str
    module: str
    topic: str
    timeout_seconds: float
    max_retries: int
    retry_backoff_seconds: float


@dataclass(frozen=True)
class RunnerConfig:
    """A single runner to watch, as declared in the config file."""

    name: str
    url: str
    recipient: str
    module: str | None = None
    topic: str | None = None


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration."""

    webhook: WebhookConfig
    poll_interval_seconds: float
    state_file: Path
    runners: list[RunnerConfig]
    admin_recipient: str | None = None


@dataclass(frozen=True)
class RunnerTarget:
    """Identifiers extracted from a runner's public LiveTrail URL."""

    tenant: str
    runner_id: str
    race_id: str
    source_url: str


@dataclass(frozen=True)
class RunnerIdentity:
    """Basic runner identity, fetched once at startup to enrich notifications."""

    bib: int | None
    first_name: str
    last_name: str


@dataclass(frozen=True)
class TimingPoint:
    """A timing checkpoint on a race course."""

    point_id: int
    name: str
    short_name: str
    distance_m: int | None
    altitude_m: int | None


@dataclass(frozen=True)
class Passing:
    """A single checkpoint passing for a runner."""

    point_id: int
    date_time: str
    race_time_seconds: int
    rest_time_seconds: int

    def state_key(self) -> str:
        """Unique identity of this passing, used to detect new passings."""
        return f"{self.point_id}:{self.date_time}"


STATUS_WITHDRAWN = "WITHDRAWN"


@dataclass(frozen=True)
class RunnerDetail:
    """Detail payload for a runner, polled repeatedly."""

    passings: list[Passing]
    status: str
    race_finished: bool


@dataclass(frozen=True)
class NotificationPayload:
    """Payload sent as JSON to the webhook endpoint."""

    title: str
    message: str
    recipient: str
    module: str
    topic: str
    url: str
