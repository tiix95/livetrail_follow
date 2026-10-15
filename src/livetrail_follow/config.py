"""Loading and validating the YAML configuration file."""

import logging
from pathlib import Path
from typing import Any

import yaml

from livetrail_follow.livetrail_client import parse_runner_url
from livetrail_follow.models import AppConfig, RunnerConfig, WebhookConfig

logger = logging.getLogger(__name__)

# Defaults for optional webhook settings.
_DEFAULT_TIMEOUT_SECONDS = 10.0
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_RETRY_BACKOFF_SECONDS = 5.0
_DEFAULT_POLL_INTERVAL_SECONDS = 30.0


def _require(data: dict[str, Any], key: str, context: str) -> Any:
    """Return data[key] or raise a clear ValueError if missing/empty."""
    value = data.get(key)
    if value in (None, ""):
        raise ValueError(f"Missing required field '{key}' in {context}")
    return value


def _build_webhook_config(data: dict[str, Any]) -> WebhookConfig:
    if not isinstance(data, dict):
        raise ValueError("Config section 'webhook' must be a mapping")

    endpoint = _require(data, "endpoint", "webhook config")
    module = _require(data, "module", "webhook config")
    topic = _require(data, "topic", "webhook config")

    return WebhookConfig(
        endpoint=endpoint,
        module=module,
        topic=topic,
        timeout_seconds=float(data.get("timeout_seconds", _DEFAULT_TIMEOUT_SECONDS)),
        max_retries=int(data.get("max_retries", _DEFAULT_MAX_RETRIES)),
        retry_backoff_seconds=float(
            data.get("retry_backoff_seconds", _DEFAULT_RETRY_BACKOFF_SECONDS)
        ),
    )


def _build_runner_config(data: dict[str, Any], index: int) -> RunnerConfig:
    if not isinstance(data, dict):
        raise ValueError(f"Runner entry #{index} must be a mapping")

    context = f"runner entry #{index}"
    name = _require(data, "name", context)
    url = _require(data, "url", context)
    recipient = _require(data, "recipient", context)

    # Validate eagerly so a bad runner URL fails fast at startup.
    parse_runner_url(url)

    return RunnerConfig(
        name=name,
        url=url,
        recipient=recipient,
        module=data.get("module"),
        topic=data.get("topic"),
    )


def load_config(path: Path) -> AppConfig:
    """Parse and validate the YAML config file, raising ValueError on bad input."""
    if not path.is_file():
        raise ValueError(f"Config file not found: {path}")

    raw_text = path.read_text(encoding="utf-8")
    raw_data = yaml.safe_load(raw_text)

    if not isinstance(raw_data, dict):
        raise ValueError(f"Config file {path} must contain a YAML mapping at the top level")

    webhook_data = raw_data.get("webhook")
    if webhook_data is None:
        raise ValueError(f"Missing required section 'webhook' in config file {path}")
    webhook = _build_webhook_config(webhook_data)

    runners_data = raw_data.get("runners")
    if not runners_data:
        raise ValueError(f"Config file {path} must declare at least one runner in 'runners'")
    if not isinstance(runners_data, list):
        raise ValueError("Config section 'runners' must be a list")

    runners = [
        _build_runner_config(runner_data, index)
        for index, runner_data in enumerate(runners_data)
    ]

    state_file_raw = _require(raw_data, "state_file", f"config file {path}")
    state_file = Path(state_file_raw)

    poll_interval_seconds = float(
        raw_data.get("poll_interval_seconds", _DEFAULT_POLL_INTERVAL_SECONDS)
    )

    admin_recipient = raw_data.get("admin_recipient")

    return AppConfig(
        webhook=webhook,
        poll_interval_seconds=poll_interval_seconds,
        state_file=state_file,
        runners=runners,
        admin_recipient=admin_recipient,
    )
