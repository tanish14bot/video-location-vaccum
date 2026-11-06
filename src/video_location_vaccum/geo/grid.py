"""Search grid construction and delayed-CPA geometry."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from ..config import RegionConfig
from ..flights.types import Flight, Track
from .geodesy import LocalFrame


@dataclass
class Grid:
    lats: NDArray[np.float64]
    lons: NDArray[np.float64]
    step_m: float
    region: RegionConfig

    @property
    def size(self) -> int:
        return int(self.lats.size * self.lons.size)

    def points(self) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        lon_grid, lat_grid = np.meshgrid(self.lons, self.lats)
        return lat_grid.ravel(), lon_grid.ravel()


def make_grid(region: RegionConfig, step_m: float) -> Grid:
    """Build a regular lat/lon grid with approximately ``step_m`` spacing."""
    if step_m <= 0:
        raise ValueError("step_m must be positive")
    mid_lat = 0.5 * (region.min_lat + region.max_lat)
    lat_step = step_m / 111_320.0
    lon_step = step_m / (111_320.0 * max(0.05, np.cos(np.radians(mid_lat))))
    lats = np.arange(region.min_lat, region.max_lat + 1e-12, lat_step)
    lons = np.arange(region.min_lon, region.max_lon + 1e-12, lon_step)
    # Guarantee at least one point and that the far edge is represented.
    if lats.size == 0 or lats[-1] < region.max_lat - 1e-9:
        lats = np.append(lats, region.max_lat)
    if lons.size == 0 or lons[-1] < region.max_lon - 1e-9:
        lons = np.append(lons, region.max_lon)
    return Grid(lats=lats, lons=lons, step_m=float(step_m), region=region)


@dataclass
class Cpa:
    t_cpa_s: float
    slant_m: float
    delayed_s: float
    horizontal_m: float


def cpa_at_point(
    frame: LocalFrame,
    track: Track,
    *,
    c_mps: float,
    coarse_stride: int = 1,
) -> Cpa:
    """Closest approach of a track to the origin of ``frame``.

    Uses a coarse minimum followed by parabolic interpolation on the range
    curve, which is accurate to well below the ADS-B sampling interval for a
    smooth pass.
    """
    enu = frame.enu_from_ecef(track.ecef)
    r = np.linalg.norm(enu, axis=1)
    if r.size < 3:
        idx = int(np.argmin(r))
        return Cpa(
            float(track.t[idx]),
            float(r[idx]),
            float(track.t[idx] + r[idx] / c_mps),
            float(np.hypot(enu[idx, 0], enu[idx, 1])),
        )

    step = max(1, int(coarse_stride))
    coarse_idx = int(np.argmin(r[::step])) * step
    lo = max(0, coarse_idx - step)
    hi = min(r.size - 1, coarse_idx + step)
    # Parabolic vertex through the three samples around the minimum.
    if hi - lo == 2:
        y0, y1, y2 = r[lo], r[lo + 1], r[lo + 2]
        denom = y0 - 2 * y1 + y2
        if abs(denom) > 1e-12:
            offset = 0.5 * (y0 - y2) / denom
            t0, t1 = track.t[lo], track.t[lo + 1]
            dt = t1 - t0
            t_cpa = t1 + offset * dt
            # Interpolate range at the vertex.
            pos, _ = track.state_at([t_cpa])
            slant = float(np.linalg.norm(frame.enu_from_ecef(pos[0])))
            horiz = float(np.linalg.norm(frame.enu_from_ecef(pos[0])[:2]))
            return Cpa(float(t_cpa), slant, float(t_cpa + slant / c_mps), horiz)
    idx = int(np.argmin(r))
    slant = float(r[idx])
    horiz = float(np.hypot(enu[idx, 0], enu[idx, 1]))
    return Cpa(float(track.t[idx]), slant, float(track.t[idx] + slant / c_mps), horiz)


@dataclass
class CandidatePair:
    point_index: int
    lat: float
    lon: float
    flight_a: str
    flight_b: str
    delta_s: float
    cpa_a: Cpa
    cpa_b: Cpa


def offset_pairs(
    *,
    grid: Grid,
    dem,
    flights: list[Flight],
    dt_s: float,
    dt_tol_s: float,
    c_mps: float,
    max_pairs: int | None = None,
    flight_pairs: list[tuple[Flight, Flight]] | None = None,
    slant_bands: list[tuple[float, float] | None] | None = None,
    velocity_bands: list[tuple[float, float] | None] | None = None,
) -> list[CandidatePair]:
    """Find grid points where a flight pair matches the measured offset and bands."""
    lats, lons = grid.points()
    if flight_pairs is not None:
        pairs_iter = flight_pairs
    else:
        pairs_iter = [
            (flights[i], flights[j]) for i in range(len(flights)) for j in range(i + 1, len(flights))
        ]

    out: list[CandidatePair] = []
    for point_index, (lat, lon) in enumerate(zip(lats, lons, strict=True)):
        elev = float(dem.elevation(lat, lon).height_m)
        frame = LocalFrame(float(lat), float(lon), elev)
        cache: dict[str, Cpa] = {}
        for fa, fb in pairs_iter:
            if fa.flight_id not in cache:
                cache[fa.flight_id] = cpa_at_point(frame, fa.track, c_mps=c_mps)
            if fb.flight_id not in cache:
                cache[fb.flight_id] = cpa_at_point(frame, fb.track, c_mps=c_mps)
            a = cache[fa.flight_id]
            b = cache[fb.flight_id]
            if a.delayed_s > b.delayed_s:
                fa, fb = fb, fa
                a, b = b, a
            delta = abs((b.delayed_s - a.delayed_s) - dt_s)
            if delta > dt_tol_s:
                continue
            if slant_bands is not None:
                if slant_bands[0] is not None and not (slant_bands[0][0] <= a.slant_m <= slant_bands[0][1]):
                    continue
                if slant_bands[1] is not None and not (slant_bands[1][0] <= b.slant_m <= slant_bands[1][1]):
                    continue
            if velocity_bands is not None:
                if velocity_bands[0] is not None and not _speed_in_band(fa, a.t_cpa_s, velocity_bands[0]):
                    continue
                if velocity_bands[1] is not None and not _speed_in_band(fb, b.t_cpa_s, velocity_bands[1]):
                    continue
            out.append(
                CandidatePair(
                    point_index=point_index,
                    lat=float(lat),
                    lon=float(lon),
                    flight_a=fa.flight_id,
                    flight_b=fb.flight_id,
                    delta_s=float(b.delayed_s - a.delayed_s),
                    cpa_a=a,
                    cpa_b=b,
                )
            )
            if max_pairs is not None and len(out) >= max_pairs:
                return out
    return out


def _speed_in_band(flight: Flight, t_cpa_s: float, band: tuple[float, float]) -> bool:
    _, vel = flight.track.state_at([t_cpa_s])
    speed = float(np.linalg.norm(vel[0]))
    return band[0] <= speed <= band[1]
