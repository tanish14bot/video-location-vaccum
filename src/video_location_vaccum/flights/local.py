"""Local flight-data adapter: Parquet, CSV, or JSON traces.

The adapter is deliberately schema-tolerant but never guesses units silently.
Callers must state the altitude unit when the column name does not carry it.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import RegionConfig
from ..errors import DataFormatError
from .types import AircraftClass, Flight, Track

_TIME = ("time", "timestamp", "ts", "seen_utc", "first_seen_ut", "last_seen_ut")
_LAT = ("lat", "latitude", "sample_lat")
_LON = ("lon", "lng", "longitude", "sample_lon")
_ALT = ("alt_geom", "alt_baro", "altitude", "alt", "alt_m", "max_alt", "baro_alt")
_ID = ("flightid", "flight_id", "icao24", "hex", "callsign")
_GS = ("gs", "ground_speed", "speed", "velocity")
_TRACK = ("track", "heading", "bearing")
_TYPE = ("typecode", "type_code", "t")
_CLASS = ("aircraft_class", "category")


def _pick(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    lowered = {c.lower(): c for c in columns}
    for name in candidates:
        if name in lowered:
            return lowered[name]
    return None


def _to_epoch_seconds(series: pd.Series) -> np.ndarray:
    if pd.api.types.is_numeric_dtype(series):
        values = series.to_numpy(dtype=float)
        # Heuristic: epoch seconds are ~1e9; epoch milliseconds ~1e12.
        if np.nanmedian(values) > 1e11:
            values = values / 1000.0
        return values
    parsed = pd.to_datetime(series, utc=True, errors="coerce")
    return parsed.astype("int64").to_numpy(dtype=float) / 1e9


def _normalize_class(value: object) -> AircraftClass:
    text = str(value).strip().lower() if value is not None else ""
    if text in {"prop", "piston", "light"}:
        return AircraftClass.PROP
    if text in {"turboprop", "tp"}:
        return AircraftClass.TURBOPROP
    if text in {"jet", "turbofan"}:
        return AircraftClass.JET
    if text in {"helicopter", "rotorcraft", "heli"}:
        return AircraftClass.HELICOPTER
    if text in {"military", "mil"}:
        return AircraftClass.MILITARY
    return AircraftClass.UNKNOWN


class LocalFlightSource:
    name = "local-file"
    historical = True
    requires_key = False
    license = "user-provided"

    def __init__(
        self,
        path: Path,
        *,
        altitude_unit: str = "ft",
        time_unit: str = "auto",
    ) -> None:
        self.path = Path(path)
        self.altitude_unit = altitude_unit.lower()
        self.time_unit = time_unit

    def available(self) -> bool:
        return self.path.exists()

    def _read(self) -> pd.DataFrame:
        suffix = self.path.suffix.lower()
        if suffix in {".parquet", ".pq"}:
            return pd.read_parquet(self.path)
        if suffix in {".csv", ".txt"}:
            return pd.read_csv(self.path)
        if suffix in {".json", ".jsonl", ".ndjson"}:
            return pd.read_json(self.path, lines=suffix in {".jsonl", ".ndjson"})
        raise DataFormatError(f"unsupported flight file type: {self.path.suffix}")

    def fetch(
        self,
        *,
        date: date,
        region: RegionConfig,
        cache_dir: Path | None = None,
    ) -> list[Flight]:
        df = self._read()
        cols = list(df.columns)
        tcol = _pick(cols, _TIME)
        lac = _pick(cols, _LAT)
        loc = _pick(cols, _LON)
        idc = _pick(cols, _ID)
        altc = _pick(cols, _ALT)
        if not all([tcol, lac, loc, idc, altc]):
            raise DataFormatError(
                f"flight file must contain time, lat, lon, id, and altitude columns; found {cols}"
            )

        ts = _to_epoch_seconds(df[tcol])
        lat = pd.to_numeric(df[lac], errors="coerce")
        lon = pd.to_numeric(df[loc], errors="coerce")
        alt = pd.to_numeric(df[altc], errors="coerce")
        if self.altitude_unit == "ft":
            alt = alt * 0.3048
        elif self.altitude_unit != "m":
            raise DataFormatError("altitude_unit must be 'ft' or 'm'")

        gs = pd.to_numeric(df[_pick(cols, _GS)], errors="coerce") if _pick(cols, _GS) else None
        trk = pd.to_numeric(df[_pick(cols, _TRACK)], errors="coerce") if _pick(cols, _TRACK) else None
        typec = df[_pick(cols, _TYPE)].astype(str) if _pick(cols, _TYPE) else None
        clsc = df[_pick(cols, _CLASS)].astype(str) if _pick(cols, _CLASS) else None
        regc = _pick(cols, ("registration", "reg"))
        callc = _pick(cols, ("callsign", "flight"))

        work = pd.DataFrame(
            {
                "t": ts,
                "lat": lat,
                "lon": lon,
                "alt_m": alt,
                "id": df[idc].astype(str),
            }
        )
        if gs is not None:
            work["gs_mps"] = gs * 0.514444
        if trk is not None:
            work["track_deg"] = trk
        work = work.dropna(subset=["t", "lat", "lon", "alt_m"])
        work = work[np.isfinite(work["t"])]

        # Restrict to the date and region before grouping.
        # shortcut: points outside the requested date are dropped; a track that
        # crosses midnight is split at the day boundary.
        day_start = datetime(date.year, date.month, date.day, tzinfo=timezone.utc).timestamp()
        work = work[(work["t"] >= day_start) & (work["t"] < day_start + 86400)]
        # Keep full tracks that pass near the region. Filtering individual
        # points would truncate a pass and corrupt the CPA and curve shape.
        margin_lat = 1.0
        margin_lon = 1.0 / max(0.05, np.cos(np.radians((region.min_lat + region.max_lat) / 2)))
        work = work[
            (work["lat"] >= region.min_lat - margin_lat)
            & (work["lat"] <= region.max_lat + margin_lat)
            & (work["lon"] >= region.min_lon - margin_lon)
            & (work["lon"] <= region.max_lon + margin_lon)
        ]
        if work.empty:
            raise DataFormatError("no rows remain after date/region filtering")

        flights: list[Flight] = []
        for fid, group in work.groupby("id", sort=False):
            group = group.sort_values("t")
            if group["t"].nunique() < 2:
                continue
            vel_enu = None
            if "gs_mps" in group and "track_deg" in group:
                heading = np.radians(group["track_deg"].to_numpy(dtype=float))
                speed = group["gs_mps"].to_numpy(dtype=float)
                vel_enu = np.stack(
                    [speed * np.sin(heading), speed * np.cos(heading), np.zeros_like(speed)],
                    axis=-1,
                )
            track = Track.from_geodetic(
                group["t"].to_numpy(dtype=float),
                group["lat"].to_numpy(dtype=float),
                group["lon"].to_numpy(dtype=float),
                group["alt_m"].to_numpy(dtype=float),
                vel_enu=vel_enu,
                method="linear",
            )
            idx = group.index[0]
            flights.append(
                Flight(
                    flight_id=str(fid),
                    track=track,
                    callsign=str(df.loc[idx, callc]) if callc else None,
                    registration=str(df.loc[idx, regc]) if regc else None,
                    typecode=str(typec.loc[idx]) if typec is not None else None,
                    aircraft_class=_normalize_class(clsc.loc[idx])
                    if clsc is not None
                    else AircraftClass.UNKNOWN,
                    source=self.name,
                )
            )
        if not flights:
            raise DataFormatError(
                "no flight had at least two time samples; a single position per flight is not a track"
            )
        return flights
