"""Flight-track data structures and source protocol."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.interpolate import CubicSpline

from ..geo.geodesy import LocalFrame, ecef_from_geodetic


class AircraftClass(str, Enum):
    PROP = "prop"
    TURBOPROP = "turboprop"
    JET = "jet"
    HELICOPTER = "helicopter"
    MILITARY = "military"
    UNKNOWN = "unknown"


@dataclass
class Flight:
    """One aircraft track with optional identity metadata."""

    flight_id: str
    track: Track
    callsign: str | None = None
    registration: str | None = None
    typecode: str | None = None
    aircraft_class: AircraftClass = AircraftClass.UNKNOWN
    source: str = "unknown"

    def __post_init__(self) -> None:
        if self.track.t.size < 2:
            raise ValueError(f"flight {self.flight_id!r} needs at least 2 track points")


@dataclass
class Track:
    """Time-parameterised 3-D track in ECEF.

    Parameters
    ----------
    t:
        Seconds since an arbitrary epoch, strictly increasing.
    ecef:
        Positions in metres, shape (N, 3).
    vel:
        Optional velocities in m/s, shape (N, 3). If absent, the derivative of
        the interpolant is used.
    method:
        ``linear`` is robust and never overshoots; ``cubic`` is smoother but
        can ring on sparse or manoeuvring tracks.
    """

    t: NDArray[np.float64]
    ecef: NDArray[np.float64]
    vel: NDArray[np.float64] | None = None
    method: str = "linear"

    def __post_init__(self) -> None:
        self.t = np.asarray(self.t, dtype=float)
        self.ecef = np.asarray(self.ecef, dtype=float)
        if self.t.ndim != 1 or self.ecef.shape != (self.t.size, 3):
            raise ValueError("track arrays must be (N,), (N,3)")
        if self.t.size < 2:
            raise ValueError("track needs at least two points")
        if not np.all(np.diff(self.t) > 0):
            order = np.argsort(self.t)
            self.t = self.t[order]
            self.ecef = self.ecef[order]
            if self.vel is not None:
                self.vel = np.asarray(self.vel, dtype=float)[order]
        if self.vel is not None:
            self.vel = np.asarray(self.vel, dtype=float)
            if self.vel.shape != (self.t.size, 3):
                raise ValueError("velocity array must be (N,3)")

    @classmethod
    def from_geodetic(
        cls,
        t: ArrayLike,
        lat: ArrayLike,
        lon: ArrayLike,
        alt_m: ArrayLike,
        vel_enu: ArrayLike | None = None,
        method: str = "linear",
    ) -> Track:
        lat_a = np.asarray(lat, dtype=float)
        lon_a = np.asarray(lon, dtype=float)
        alt_a = np.asarray(alt_m, dtype=float)
        ecef = ecef_from_geodetic(lat_a, lon_a, alt_a)
        if vel_enu is None:
            return cls(np.asarray(t, dtype=float), ecef, None, method)
        frame = LocalFrame(float(lat_a[0]), float(lon_a[0]), float(alt_a[0]))
        vel_ecef = np.asarray(vel_enu, dtype=float) @ frame._rot
        return cls(np.asarray(t, dtype=float), ecef, vel_ecef, method)

    @property
    def t_min(self) -> float:
        return float(self.t[0])

    @property
    def t_max(self) -> float:
        return float(self.t[-1])

    def _interpolators(self) -> list[CubicSpline] | None:
        if self.method == "cubic" and self.t.size >= 4:
            return [CubicSpline(self.t, self.ecef[:, k]) for k in range(3)]
        return None

    def state_at(self, t_query: ArrayLike) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Position and velocity at query times, in the track's time base."""
        tq = np.atleast_1d(np.asarray(t_query, dtype=float))
        if self.method == "cubic" and self.t.size >= 4:
            splines = self._interpolators()
            assert splines is not None
            pos = np.stack([s(tq) for s in splines], axis=-1)
            vel = np.stack([s(tq, 1) for s in splines], axis=-1)
            return pos, vel
        pos = np.stack([np.interp(tq, self.t, self.ecef[:, k]) for k in range(3)], axis=-1)
        if self.vel is not None:
            vel = np.stack([np.interp(tq, self.t, self.vel[:, k]) for k in range(3)], axis=-1)
        elif self.t.size >= 3:
            v_raw = np.gradient(self.ecef, self.t, axis=0)
            vel = np.stack([np.interp(tq, self.t, v_raw[:, k]) for k in range(3)], axis=-1)
        else:
            v_raw = np.gradient(self.ecef, axis=0) / np.gradient(self.t)[:, None]
            vel = np.stack([np.interp(tq, self.t, v_raw[:, k]) for k in range(3)], axis=-1)
        return pos, vel


@runtime_checkable
class FlightSource(Protocol):
    """Protocol implemented by every flight-data adapter."""

    name: str
    historical: bool
    requires_key: bool
    license: str

    def available(self) -> bool: ...

    def fetch(self, *, date, region, cache_dir: Path | None = None) -> list[Flight]: ...
