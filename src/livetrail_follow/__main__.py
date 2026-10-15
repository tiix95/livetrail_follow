"""Entry point: python3 -m livetrail_follow."""

import argparse
import asyncio
import os
from pathlib import Path

from livetrail_follow.config import load_config
from livetrail_follow.logging_setup import configure_logging
from livetrail_follow.watcher import run

DEFAULT_CONFIG_PATH = Path("/etc/livetrail-follow/config.yml")


def _resolve_config_path(cli_arg: str | None) -> Path:
    """Resolve the config file path: CLI arg > env var > default."""
    if cli_arg:
        return Path(cli_arg)

    env_value = os.environ.get("LIVETRAIL_FOLLOW_CONFIG")
    if env_value:
        return Path(env_value)

    return DEFAULT_CONFIG_PATH


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="livetrail-follow",
        description="Watch LiveTrail runners and send webhook notifications on new checkpoint passings.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to the YAML config file (default: $LIVETRAIL_FOLLOW_CONFIG or /etc/livetrail-follow/config.yml)",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("LOG_LEVEL", "INFO"),
        help="Logging level (default: $LOG_LEVEL or INFO)",
    )
    return parser.parse_args()


def main() -> None:
    """Resolve config, configure logging and run the watcher daemon."""
    args = _parse_args()

    configure_logging(args.log_level)

    config_path = _resolve_config_path(args.config)
    config = load_config(config_path)

    asyncio.run(run(config))


if __name__ == "__main__":
    main()
