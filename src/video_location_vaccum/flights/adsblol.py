"""adsb.lol daily archive adapter.

adsb.lol publishes one GitHub release per day in ``adsblol/globe_history_<year>``
with tags like ``v2026.09.08-planes-readsb-prod-0``. The release is a split tar
of ``traces/xx/trace_full_<icao>.json`` gzip files. Each trace row is::

    [sec_after_timestamp, lat, lon, alt_ft, gs_kt, track_deg, flags,
     baro_rate_fpm, details, source, alt_geom_ft, geom_rate_fpm, ...]

This adapter streams the archive, filters to a region before building tracks,
and never loads the whole day into memory. First use downloads several GB; the
cache is reused.
"""

from __future__ import annotations

import gzip
import io
import json
import tarfile
from datetime import date
from pathlib import Path

import httpx
import numpy as np

from ..config import RegionConfig
from ..errors import DataUnavailable
from .types import AircraftClass, Flight, Track

GH_API = "https://api.github.com"
FT_TO_M = 0.3048
KT_TO_MPS = 0.514444


class _Cat(io.RawIOBase):
    """Read several split-tar files as one stream."""

    def __init__(self, paths: list[Path]) -> None:
        self._files = [path.open("rb") for path in paths]
        self._index = 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:  # type: ignore[no-untyped-def]
        while self._index < len(self._files):
            n = self._files[self._index].readinto(buffer)
            if n:
                return n
            self._files[self._index].close()
            self._index += 1
        return 0


class AdsbLolSource:
    name = "adsb.lol-archive"
    historical = True
    requires_key = False
    license = "ODbL-1.0; attribution and share-alike"

    def __init__(self, archive: str | Path | None = None, *, allow_download: bool = True) -> None:
        self.archive = archive
        self.allow_download = allow_download

    def available(self) -> bool:
        return self.archive is not None or self.allow_download

    # ------------------------------------------------------------------ resolve
    @staticmethod
    def release_tag(day: date) -> tuple[str, str]:
        return (
            f"adsblol/globe_history_{day.year}",
            f"v{day.year}.{day.month:02d}.{day.day:02d}-planes-readsb-prod-0",
        )

    def _assets(self, day: date) -> list[dict]:
        repo, tag = self.release_tag(day)
        url = f"{GH_API}/repos/{repo}/releases/tags/{tag}"
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.get(url, headers={"Accept": "application/vnd.github+json"})
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            raise DataUnavailable(
                f"adsb.lol has no archive for {day.isoformat()}",
                tried=[url],
                ask="check the date, or provide a local archive file",
            ) from exc
        assets = [a for a in data.get("assets", []) if a.get("name", "").startswith(tag)]
        if not assets:
            raise DataUnavailable(f"adsb.lol release {tag} has no assets")
        return assets

    def _download(self, day: date, cache_dir: Path) -> list[Path]:
        target = cache_dir / f"adsblol-{day.isoformat()}"
        target.mkdir(parents=True, exist_ok=True)
        assets = self._assets(day)
        paths: list[Path] = []
        with httpx.Client(timeout=httpx.Timeout(300.0, connect=30.0), follow_redirects=True) as client:
            for asset in assets:
                name = asset["name"]
                path = target / name
                expected = int(asset.get("size", 0))
                if path.exists() and (expected == 0 or path.stat().st_size == expected):
                    paths.append(path)
                    continue
                tmp = path.with_suffix(path.suffix + ".part")
                with client.stream("GET", asset["browser_download_url"]) as response:
                    response.raise_for_status()
                    with tmp.open("wb") as fh:
                        for chunk in response.iter_bytes(1 << 20):
                            fh.write(chunk)
                tmp.replace(path)
                paths.append(path)
        paths.sort(key=lambda p: p.name)
        return paths

    def _local_parts(self, cache_dir: Path | None) -> list[Path]:
        if self.archive is None:
            return []
        path = Path(self.archive)
        if path.is_dir():
            return sorted(
                p for p in path.iterdir() if p.is_file() and (".tar" in p.name or p.suffix == ".gz")
            )
        return [path]

    # -------------------------------------------------------------------- fetch
    def fetch(self, *, date: date, region: RegionConfig, cache_dir: Path | None = None) -> list[Flight]:
        parts = self._local_parts(cache_dir)
        if not parts and self.allow_download:
            if cache_dir is None:
                raise DataUnavailable(
                    "adsb.lol download requires a cache directory",
                    ask="set flights.cache_dir or provide a local archive",
                )
            parts = self._download(date, cache_dir)
        if not parts:
            raise DataUnavailable(
                "adsb.lol archive is not configured",
                tried=[self.name],
                ask=(
                    "set ADSB_LOL_ARCHIVE_URL to a daily archive URL, or set "
                    "flights.cache_dir so it can be downloaded"
                ),
            )
        flights = parse_archive(parts, region=region)
        if not flights:
            raise DataUnavailable(
                "no flights remained after region filtering",
                tried=[str(p) for p in parts],
                ask="widen the region or check the archive date",
            )
        return flights


def parse_archive(parts: list[Path], *, region: RegionConfig) -> list[Flight]:
    """Stream a (possibly split) readsb tar and build region-filtered tracks."""
    # shortcut: single-threaded tar parse (~7 min for one global day); parallelize
    # only if daily batch runs become a requirement.
    margin_lat = 1.0
    margin_lon = 1.0 / max(0.1, np.cos(np.radians((region.min_lat + region.max_lat) / 2)))
    bbox = (
        region.min_lon - margin_lon,
        region.min_lat - margin_lat,
        region.max_lon + margin_lon,
        region.max_lat + margin_lat,
    )
    flights: list[Flight] = []
    stream = io.BufferedReader(_Cat(parts), 1 << 22)
    with tarfile.open(fileobj=stream, mode="r|") as tar:
        for member in tar:
            if not member.isfile() or "/trace_full_" not in member.name:
                continue
            handle = tar.extractfile(member)
            if handle is None:
                continue
            raw = handle.read()
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            flight = _parse_trace(obj, bbox)
            if flight is not None:
                flights.append(flight)
    return flights


def _parse_trace(obj: dict, bbox: tuple[float, float, float, float]) -> Flight | None:
    t0 = float(obj.get("timestamp") or 0.0)
    rows = obj.get("trace") or []
    lon0, lat0, lon1, lat1 = bbox
    t: list[float] = []
    lat: list[float] = []
    lon: list[float] = []
    alt: list[float] = []
    vel: list[tuple[float, float]] = []
    callsign = None
    type_code = obj.get("t")
    for row in rows:
        if len(row) < 4:
            continue
        details = row[8] if len(row) > 8 else None
        if isinstance(details, dict) and details.get("flight"):
            callsign = str(details["flight"]).strip()
        la, lo, a = row[1], row[2], row[3]
        if la is None or lo is None or a == "ground":
            continue
        if not (lat0 <= float(la) <= lat1 and lon0 <= float(lo) <= lon1):
            continue
        flags = int(row[6] or 0) if len(row) > 6 else 0
        alt_geom = row[10] if len(row) > 10 else None
        if flags & 8:
            alt_geom, a = a, None
        alt_ft = alt_geom if alt_geom is not None else a
        if alt_ft is None:
            continue
        t.append(t0 + float(row[0]))
        lat.append(float(la))
        lon.append(float(lo))
        alt.append(float(alt_ft) * FT_TO_M)
        gs = row[4] if len(row) > 4 else None
        track = row[5] if len(row) > 5 else None
        if gs is not None and track is not None:
            vel.append((float(gs) * KT_TO_MPS, float(track)))
    if len(t) < 2:
        return None
    order = np.argsort(t)
    t_arr = np.asarray(t)[order]
    lat_arr = np.asarray(lat)[order]
    lon_arr = np.asarray(lon)[order]
    alt_arr = np.asarray(alt)[order]
    vel_enu = None
    if len(vel) == len(t):
        v = np.asarray([vel[i] for i in order])
        heading = np.radians(v[:, 1])
        speed = v[:, 0]
        vel_enu = np.stack([speed * np.sin(heading), speed * np.cos(heading), np.zeros_like(speed)], axis=-1)
    track_obj = Track.from_geodetic(t_arr, lat_arr, lon_arr, alt_arr, vel_enu=vel_enu)
    return Flight(
        flight_id=str(obj.get("icao") or "unknown"),
        track=track_obj,
        callsign=callsign,
        typecode=type_code,
        aircraft_class=AircraftClass.UNKNOWN,
        source="adsb.lol-archive",
    )
