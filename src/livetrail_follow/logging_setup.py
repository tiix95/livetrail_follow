"""Logging configuration for livetrail-follow."""

import logging


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging with a timestamped format."""
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
