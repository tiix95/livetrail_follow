"""Persisted state: which passings have already been notified, per runner."""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def load_state(path: Path) -> dict[str, set[str]]:
    """Load the notified-passings state from a JSON file.

    Returns an empty dict if the file does not exist yet. The file maps
    "{race_id}:{runner_id}" to a list of already-notified passing state_key()
    strings, which is loaded here into a set per runner.
    """
    if not path.is_file():
        return {}

    raw_text = path.read_text(encoding="utf-8")
    raw_data = json.loads(raw_text)
    return {runner_key: set(keys) for runner_key, keys in raw_data.items()}


def save_state(path: Path, state: dict[str, set[str]]) -> None:
    """Atomically persist the notified-passings state to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    serializable = {runner_key: sorted(keys) for runner_key, keys in state.items()}
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)
