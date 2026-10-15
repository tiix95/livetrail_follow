"""Building notification payloads and sending them to the webhook endpoint."""

import asyncio
import logging
from dataclasses import asdict

import aiohttp

from livetrail_follow.models import (
    NotificationPayload,
    Passing,
    RunnerConfig,
    RunnerIdentity,
    TimingPoint,
    WebhookConfig,
)

logger = logging.getLogger(__name__)


def format_duration(seconds: int) -> str:
    """Format a duration in seconds as H:MM:SS."""
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


def build_passing_payload(
    runner_cfg: RunnerConfig,
    identity: RunnerIdentity | None,
    point: TimingPoint,
    passing: Passing,
    webhook_cfg: WebhookConfig,
) -> NotificationPayload:
    """Build the webhook payload for a newly detected checkpoint passing."""
    if identity is not None:
        display_name = f"{identity.first_name} {identity.last_name}".strip() or runner_cfg.name
    else:
        display_name = runner_cfg.name

    title = f"{display_name} - {point.name}"

    message_parts = [f"{display_name} a passé le point de contrôle {point.name}"]
    if point.distance_m is not None:
        distance_km = point.distance_m / 1000
        message_parts.append(f"à {distance_km:.1f} km")
    if passing.race_time_seconds > 0:
        message_parts.append(f"en {format_duration(passing.race_time_seconds)}")
    message = " ".join(message_parts) + "."

    module = runner_cfg.module or webhook_cfg.module
    topic = runner_cfg.topic or webhook_cfg.topic

    return NotificationPayload(
        title=title,
        message=message,
        recipient=runner_cfg.recipient,
        module=module,
        topic=topic,
        url=runner_cfg.url,
    )


def build_watch_started_payload(
    runner_cfg: RunnerConfig,
    webhook_cfg: WebhookConfig,
    admin_recipient: str,
) -> NotificationPayload:
    """Build the webhook payload sent to the admin when a runner's watch starts."""
    title = f"Suivi de {runner_cfg.name}"
    message = f"Suivi démarré pour {runner_cfg.name} ({runner_cfg.url})."

    module = runner_cfg.module or webhook_cfg.module
    topic = runner_cfg.topic or webhook_cfg.topic

    return NotificationPayload(
        title=title,
        message=message,
        recipient=admin_recipient,
        module=module,
        topic=topic,
        url=runner_cfg.url,
    )


def build_withdrawn_payload(
    runner_cfg: RunnerConfig,
    identity: RunnerIdentity | None,
    webhook_cfg: WebhookConfig,
) -> NotificationPayload:
    """Build the webhook payload sent when a runner withdraws from the race."""
    if identity is not None:
        display_name = f"{identity.first_name} {identity.last_name}".strip() or runner_cfg.name
    else:
        display_name = runner_cfg.name

    title = f"{display_name} - Abandon"
    message = f"{display_name} a abandonné la course."

    module = runner_cfg.module or webhook_cfg.module
    topic = runner_cfg.topic or webhook_cfg.topic

    return NotificationPayload(
        title=title,
        message=message,
        recipient=runner_cfg.recipient,
        module=module,
        topic=topic,
        url=runner_cfg.url,
    )


def build_finished_payload(
    runner_cfg: RunnerConfig,
    identity: RunnerIdentity | None,
    webhook_cfg: WebhookConfig,
) -> NotificationPayload:
    """Build the webhook payload sent when a runner finishes the race normally."""
    if identity is not None:
        display_name = f"{identity.first_name} {identity.last_name}".strip() or runner_cfg.name
    else:
        display_name = runner_cfg.name

    title = f"{display_name} - Arrivée"
    message = f"{display_name} a terminé la course."

    module = runner_cfg.module or webhook_cfg.module
    topic = runner_cfg.topic or webhook_cfg.topic

    return NotificationPayload(
        title=title,
        message=message,
        recipient=runner_cfg.recipient,
        module=module,
        topic=topic,
        url=runner_cfg.url,
    )


async def send_webhook(
    session: aiohttp.ClientSession,
    webhook_cfg: WebhookConfig,
    payload: NotificationPayload,
) -> bool:
    """POST the notification payload to the webhook endpoint, with retries.

    Returns True on success (2xx response), False if all retries are
    exhausted. Never raises: network/timeout errors are caught and logged.
    """
    timeout = aiohttp.ClientTimeout(total=webhook_cfg.timeout_seconds)
    body = asdict(payload)

    for attempt in range(1, webhook_cfg.max_retries + 1):
        try:
            async with session.post(webhook_cfg.endpoint, json=body, timeout=timeout) as resp:
                if 200 <= resp.status < 300:
                    return True
                logger.warning(
                    "Webhook attempt %d/%d failed with status %d for '%s'",
                    attempt,
                    webhook_cfg.max_retries,
                    resp.status,
                    payload.title,
                )
        except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError) as exc:
            logger.warning(
                "Webhook attempt %d/%d raised an error for '%s': %s",
                attempt,
                webhook_cfg.max_retries,
                payload.title,
                exc,
            )

        if attempt < webhook_cfg.max_retries:
            await asyncio.sleep(webhook_cfg.retry_backoff_seconds * attempt)

    logger.error(
        "Giving up sending webhook notification for '%s' after %d attempts",
        payload.title,
        webhook_cfg.max_retries,
    )
    return False
