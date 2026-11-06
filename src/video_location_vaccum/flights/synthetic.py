"""Synthetic flight tracks for tests, demos, and calibration."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from ..geo.geodesy import destination_point
from .types import AircraftClass, Flight, Track


def straight_pass(
    *,
    start_lat: float,
    start_lon: float,
    bearing_deg: float,
    speed_mps: float,
    altitude_m: float,
    t0_s: float,
    duration_s: float,
    origin: datetime | None = None,
    flight_id: str = "synthetic-1",
    sample_hz: float = 1.0,
) -> Flight:
    """A constant-speed, constant-altitude straight track."""
    n = int(duration_s * sample_hz) + 1
    tt = np.linspace(0.0, duration_s, n)
    lat = np.empty(n)
    lon = np.empty(n)
    for i, dt in enumerate(tt):
        lat[i], lon[i] = destination_point(start_lat, start_lon, bearing_deg, speed_mps * dt)
    alt = np.full(n, altitude_m)
    origin = origin or datetime(2026, 1, 1, tzinfo=timezone.utc)
    epoch = origin.timestamp()
    track = Track.from_geodetic(epoch + t0_s + tt, lat, lon, alt)
    return Flight(
        flight_id=flight_id,
        track=track,
        callsign=flight_id,
        aircraft_class=AircraftClass.TURBOPROP,
        source="synthetic",
    )
