"""Polling loop: watches a single runner and dispatches webhook notifications."""

import asyncio
import logging
from pathlib import Path

import aiohttp

from livetrail_follow.livetrail_client import LiveTrailClient, parse_runner_url
from livetrail_follow.models import (
    AppConfig,
    RunnerConfig,
    RunnerIdentity,
    STATUS_WITHDRAWN,
    TimingPoint,
    WebhookConfig,
)
from livetrail_follow.notifier import (
    build_finished_payload,
    build_passing_payload,
    build_watch_started_payload,
    build_withdrawn_payload,
    send_webhook,
)
from livetrail_follow.state import load_state, save_state

logger = logging.getLogger(__name__)


async def _get_points(
    client: LiveTrailClient,
    race_id: str,
    tenant: str,
    points_cache: dict[str, dict[int, TimingPoint]],
    points_lock: asyncio.Lock,
) -> dict[int, TimingPoint]:
    """Fetch and cache timing points for a race_id, shared across runners.

    Uses a double-checked locking pattern so concurrent runners racing on the
    same race_id only trigger a single HTTP fetch.
    """
    if race_id not in points_cache:
        async with points_lock:
            if race_id not in points_cache:
                points_cache[race_id] = await client.fetch_points(race_id, tenant)
    return points_cache[race_id]


async def watch_runner(
    client: LiveTrailClient,
    session: aiohttp.ClientSession,
    runner_cfg: RunnerConfig,
    webhook_cfg: WebhookConfig,
    poll_interval_seconds: float,
    state: dict[str, set[str]],
    state_lock: asyncio.Lock,
    state_path: Path,
    points_cache: dict[str, dict[int, TimingPoint]],
    points_lock: asyncio.Lock,
    admin_recipient: str | None,
) -> None:
    """Watch a single runner forever, notifying on every new checkpoint passing."""
    target = parse_runner_url(runner_cfg.url)

    identity: RunnerIdentity | None
    try:
        identity = await client.fetch_identity(target)
    except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError) as exc:
        logger.warning(
            "Could not fetch identity for runner '%s', falling back to configured name: %s",
            runner_cfg.name,
            exc,
        )
        identity = None

    points = await _get_points(client, target.race_id, target.tenant, points_cache, points_lock)

    runner_key = f"{target.race_id}:{target.runner_id}"
    known_keys = state.setdefault(runner_key, set())

    logger.info("Started watching runner '%s' (%s)", runner_cfg.name, runner_key)

    if admin_recipient:
        watch_started_payload = build_watch_started_payload(
            runner_cfg, webhook_cfg, admin_recipient
        )
        await send_webhook(session, webhook_cfg, watch_started_payload)

    while True:
        try:
            detail = await client.fetch_detail(target)
        except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError) as exc:
            logger.warning("Failed to fetch detail for runner '%s': %s", runner_cfg.name, exc)
            await asyncio.sleep(poll_interval_seconds)
            continue

        logger.info("Polled runner '%s': status=%s", runner_cfg.name, detail.status)

        for passing in detail.passings:
            key = passing.state_key()
            if key in known_keys:
                continue

            point = points.get(passing.point_id) or TimingPoint(
                point_id=passing.point_id,
                name=f"Checkpoint {passing.point_id}",
                short_name="",
                distance_m=None,
                altitude_m=None,
            )
            payload = build_passing_payload(runner_cfg, identity, point, passing, webhook_cfg)
            sent = await send_webhook(session, webhook_cfg, payload)

            # Only mark as known and persist on success, so a failed send is
            # retried on the next poll cycle.
            if sent:
                known_keys.add(key)
                async with state_lock:
                    save_state(state_path, state)

        if detail.race_finished:
            if detail.status == STATUS_WITHDRAWN:
                logger.info("Runner '%s' withdrew from the race, stopping watch", runner_cfg.name)
                payload = build_withdrawn_payload(runner_cfg, identity, webhook_cfg)
                await send_webhook(session, webhook_cfg, payload)
            else:
                logger.info("Runner '%s' finished the race, stopping watch", runner_cfg.name)
                payload = build_finished_payload(runner_cfg, identity, webhook_cfg)
                await send_webhook(session, webhook_cfg, payload)
            return

        await asyncio.sleep(poll_interval_seconds)


async def run(config: AppConfig) -> None:
    """Load state, open a shared session and watch all configured runners."""
    state = load_state(config.state_file)

    async with aiohttp.ClientSession(trust_env=True) as session:
        client = LiveTrailClient(session)
        points_cache: dict[str, dict[int, TimingPoint]] = {}
        points_lock = asyncio.Lock()
        state_lock = asyncio.Lock()

        tasks = [
            watch_runner(
                client,
                session,
                runner_cfg,
                config.webhook,
                config.poll_interval_seconds,
                state,
                state_lock,
                config.state_file,
                points_cache,
                points_lock,
                config.admin_recipient,
            )
            for runner_cfg in config.runners
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for runner_cfg, result in zip(config.runners, results):
            if isinstance(result, BaseException):
                logger.error(
                    "Watcher for runner '%s' crashed: %s",
                    runner_cfg.name,
                    result,
                    exc_info=result,
                )
