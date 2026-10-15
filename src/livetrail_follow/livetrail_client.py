"""HTTP client for the LiveTrail v3 API, and runner URL parsing."""

import logging
import re
from urllib.parse import urlparse, parse_qs

import aiohttp

from livetrail_follow import __version__
from livetrail_follow.models import Passing, RunnerDetail, RunnerIdentity, RunnerTarget, TimingPoint

logger = logging.getLogger(__name__)

API_BASE_URL = "https://api.v3.livetrail.net/api"

# Matches /{lang}/{year}/runners/{id}, e.g. /en/2026/runners/3892
_RUNNER_PATH_RE = re.compile(r"^/(?P<lang>[^/]+)/(?P<year>\d{4})/runners/(?P<runner_id>[^/]+)/?$")

USER_AGENT = f"livetrail-follow/{__version__}"


def parse_runner_url(url: str) -> RunnerTarget:
    """Extract tenant, runner_id and race_id from a runner's public page URL.

    Raises ValueError (including the offending URL) if the path does not
    match /{lang}/{year}/runners/{id} or the raceId query param is missing.
    """
    parsed = urlparse(url)

    if not parsed.hostname:
        raise ValueError(f"Cannot extract hostname from runner URL: {url}")
    slug = parsed.hostname.split(".")[0]

    match = _RUNNER_PATH_RE.match(parsed.path)
    if not match:
        raise ValueError(
            f"Runner URL path must look like /{{lang}}/{{year}}/runners/{{id}}, got: {url}"
        )
    year = match.group("year")
    runner_id = match.group("runner_id")

    query = parse_qs(parsed.query)
    race_ids = query.get("raceId")
    if not race_ids or not race_ids[0]:
        raise ValueError(f"Missing required 'raceId' query parameter in runner URL: {url}")
    race_id = race_ids[0]

    tenant = f"{slug}_{year}"

    return RunnerTarget(tenant=tenant, runner_id=runner_id, race_id=race_id, source_url=url)


class LiveTrailClient:
    """Thin async wrapper around the LiveTrail v3 API."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    def _headers(self, tenant: str) -> dict[str, str]:
        return {"X-Tenant": tenant, "User-Agent": USER_AGENT}

    async def fetch_identity(self, target: RunnerTarget) -> RunnerIdentity:
        """Fetch basic runner identity. Meant to be called once per runner."""
        url = f"{API_BASE_URL}/events/runners/{target.runner_id}"
        async with self._session.get(url, headers=self._headers(target.tenant)) as resp:
            resp.raise_for_status()
            data = await resp.json()

        return RunnerIdentity(
            bib=data.get("bib"),
            first_name=data.get("firstName", ""),
            last_name=data.get("lastName", ""),
        )

    async def fetch_detail(self, target: RunnerTarget) -> RunnerDetail:
        """Fetch runner detail, including passings. Meant to be polled repeatedly."""
        url = f"{API_BASE_URL}/events/runners/{target.runner_id}/detail"
        async with self._session.get(url, headers=self._headers(target.tenant)) as resp:
            resp.raise_for_status()
            data = await resp.json()

        passings = [
            Passing(
                point_id=passing["pointId"],
                date_time=passing["dateTime"],
                race_time_seconds=passing.get("raceTime") or 0,
                rest_time_seconds=passing.get("restTime") or 0,
            )
            for passing in data.get("passings", [])
        ]

        return RunnerDetail(
            passings=passings,
            status=data.get("status", ""),
            race_finished=bool(data.get("raceFinished", False)),
        )

    async def fetch_points(self, race_id: str, tenant: str) -> dict[int, TimingPoint]:
        """Fetch the list of timing points for a race, keyed by point_id."""
        url = f"{API_BASE_URL}/events/points"
        params = {"raceId": race_id}
        async with self._session.get(url, params=params, headers=self._headers(tenant)) as resp:
            resp.raise_for_status()
            data = await resp.json()

        points: dict[int, TimingPoint] = {}
        for item in data:
            point_id = item["pointId"]
            points[point_id] = TimingPoint(
                point_id=point_id,
                name=item.get("name", f"Checkpoint {point_id}"),
                short_name=item.get("shortName", ""),
                distance_m=item.get("distance"),
                altitude_m=item.get("altitude"),
            )
        return points
