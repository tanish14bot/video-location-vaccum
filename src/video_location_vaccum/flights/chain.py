"""Flight-source fallback chain."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from ..config import FlightsConfig, RegionConfig
from ..errors import DataUnavailable
from .adsblol import AdsbLolSource
from .local import LocalFlightSource
from .opensky import OpenSkySource
from .types import AircraftClass, Flight, FlightSource


def _cache_path(cache_dir: Path, day: date) -> Path:
    return cache_dir / f"flights-{day.isoformat()}.parquet"


def _write_cache(flights: list[Flight], path: Path) -> None:
    rows = []
    for f in flights:
        from ..geo.geodesy import geodetic_from_ecef

        lat, lon, alt = geodetic_from_ecef(f.track.ecef)
        for i in range(f.track.t.size):
            rows.append(
                {
                    "flight_id": f.flight_id,
                    "time": float(f.track.t[i]),
                    "lat": float(lat[i]),
                    "lon": float(lon[i]),
                    "alt_m": float(alt[i]),
                }
            )
    if rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_parquet(path, index=False)


def filter_by_class(flights: list[Flight], mode: str) -> list[Flight]:
    if mode == "all":
        return flights
    keep = {
        "props": {AircraftClass.PROP, AircraftClass.TURBOPROP, AircraftClass.UNKNOWN},
        "turboprops": {AircraftClass.TURBOPROP, AircraftClass.UNKNOWN},
        "jets": {AircraftClass.JET, AircraftClass.UNKNOWN},
    }[mode]
    # Unknown classes are kept on purpose: dropping an unlabelled true flight
    # is unrecoverable, while keeping it only costs candidates.
    return [f for f in flights if f.aircraft_class in keep]


def resolve_flights(
    cfg: FlightsConfig,
    *,
    region: RegionConfig,
    days: list[date],
    type_filter: str = "all",
) -> list[Flight]:
    """Return flights for every requested day, or raise with an actionable ask."""
    tried: list[str] = []
    sources: list[FlightSource] = []

    if cfg.user_file is not None:
        sources.append(LocalFlightSource(cfg.user_file, altitude_unit=cfg.altitude_unit))
    if cfg.cache_dir is not None:
        for day in days:
            p = _cache_path(cfg.cache_dir, day)
            if p.exists():
                sources.append(LocalFlightSource(p, altitude_unit="m"))
    if cfg.opensky_client_id and cfg.opensky_client_secret:
        sources.append(OpenSkySource(cfg.opensky_client_id, cfg.opensky_client_secret))
    if cfg.allow_mirrors:
        import os

        sources.append(AdsbLolSource(os.environ.get("ADSB_LOL_ARCHIVE_URL")))

    out: list[Flight] = []
    for day in days:
        got: list[Flight] | None = None
        for src in sources:
            if not src.available():  # type: ignore[attr-defined]
                tried.append(f"{src.name}:unavailable")  # type: ignore[attr-defined]
                continue
            try:
                got = src.fetch(date=day, region=region, cache_dir=cfg.cache_dir)  # type: ignore[attr-defined]
                break
            except Exception as exc:
                tried.append(f"{src.name}:{type(exc).__name__}")
                continue
        if got is None:
            raise DataUnavailable(
                f"no flight data for {day.isoformat()} in the requested region",
                tried=tried,
                ask=(
                    "provide a Parquet/CSV track file with columns "
                    "flight_id,time,lat,lon,alt_m (one row per position), or a dated "
                    "adsb.lol archive via ADSB_LOL_ARCHIVE_URL, or OpenSky credentials"
                ),
            )
        if cfg.cache_dir is not None:
            _write_cache(got, _cache_path(cfg.cache_dir, day))
        out.extend(got)

    return filter_by_class(out, type_filter)
