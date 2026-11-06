"""OpenSky Network adapter.

OpenSky's REST API is not a general historical archive: ``/tracks`` covers the
last 30 days, and ``/flights`` covers a bounded window. Longer history requires
Trino access under the user's own licence. This adapter says so plainly instead
of substituting live data.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import httpx
import numpy as np

from ..config import RegionConfig
from ..errors import DataUnavailable
from .types import Flight, Track

TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
API = "https://opensky-network.org/api"


class OpenSkySource:
    name = "opensky"
    historical = True
    requires_key = False
    license = "OpenSky terms; non-commercial research use, no redistribution"

    def __init__(self, client_id: str | None = None, client_secret: str | None = None) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None

    def available(self) -> bool:
        return True

    def supports(self, day: date) -> bool:
        age_days = (datetime.now(timezone.utc).date() - day).days
        return 0 <= age_days <= 30

    def _auth(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.client_id and self.client_secret:
            r = httpx.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=30.0,
            )
            r.raise_for_status()
            self._token = str(r.json()["access_token"])
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def fetch(self, *, date: date, region: RegionConfig, cache_dir: Path | None = None) -> list[Flight]:
        if not self.supports(date):
            raise DataUnavailable(
                f"OpenSky REST cannot serve {date.isoformat()} (older than 30 days)",
                tried=[self.name],
                ask=(
                    "provide a local Parquet/CSV track file, or use an OpenSky Trino / "
                    "ADS-B Exchange account for historical dates"
                ),
            )
        begin = int(datetime(date.year, date.month, date.day, tzinfo=timezone.utc).timestamp())
        end = begin + 3600  # one hour keeps the free window modest
        headers = self._auth()
        try:
            flights_resp = httpx.get(
                f"{API}/flights/all", params={"begin": begin, "end": end}, headers=headers, timeout=60.0
            )
            flights_resp.raise_for_status()
            rows = flights_resp.json()
        except Exception as exc:
            raise DataUnavailable(
                "OpenSky flight query failed",
                tried=[self.name],
                ask="check network/credentials, or provide a local flight file",
            ) from exc

        out: list[Flight] = []
        for row in rows[:200]:
            icao = row.get("icao24")
            if not icao:
                continue
            try:
                tr = httpx.get(
                    f"{API}/tracks/all",
                    params={"icao24": icao, "time": 0},
                    headers=headers,
                    timeout=30.0,
                )
                tr.raise_for_status()
                path = tr.json().get("path") or []
            except Exception:
                continue
            if len(path) < 2:
                continue
            t = np.array([p[0] for p in path], dtype=float)
            lat = np.array([p[1] for p in path], dtype=float)
            lon = np.array([p[2] for p in path], dtype=float)
            alt = np.array([p[3] if p[3] is not None else 0.0 for p in path], dtype=float)
            track = Track.from_geodetic(t, lat, lon, alt)
            if not self._touches_region(track, region):
                continue
            out.append(
                Flight(
                    flight_id=str(icao),
                    track=track,
                    callsign=row.get("callsign"),
                    source=self.name,
                )
            )
        if not out:
            raise DataUnavailable(
                "OpenSky returned no tracks intersecting the region for this date",
                tried=[self.name],
                ask="widen the region/date, or provide a local flight file",
            )
        return out

    @staticmethod
    def _touches_region(track: Track, region: RegionConfig) -> bool:
        from ..geo.geodesy import geodetic_from_ecef

        lat, lon, _ = geodetic_from_ecef(track.ecef)
        return bool(
            np.any(
                (lat >= region.min_lat)
                & (lat <= region.max_lat)
                & (lon >= region.min_lon)
                & (lon <= region.max_lon)
            )
        )
