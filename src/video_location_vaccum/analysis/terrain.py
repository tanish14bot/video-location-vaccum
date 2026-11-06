"""Terrain horizon profiles from a DEM."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from ..geo.dem import DemSample
from ..geo.geodesy import destination_point


class ElevationSource(Protocol):
    def elevation(self, lat: float, lon: float) -> DemSample: ...


@dataclass
class HorizonSample:
    azimuth_deg: float
    elevation_deg: float
    distance_m: float
    height_m: float


def horizon_profile(
    dem: ElevationSource,
    lat: float,
    lon: float,
    azimuths: list[float],
    *,
    max_distance_m: float = 20_000.0,
    step_m: float = 100.0,
) -> list[HorizonSample]:
    """Maximum terrain elevation angle along each azimuth.

    Earth curvature is ignored; at 20 km it is ~31 m, which is below the DEM
    disagreement in most terrain. State the limit when publishing.
    """
    base = dem.elevation(lat, lon).height_m
    out: list[HorizonSample] = []
    distances = np.arange(step_m, max_distance_m + step_m, step_m)
    for az in azimuths:
        best_angle = -90.0
        best_dist = 0.0
        best_h = base
        for dist in distances:
            plat, plon = destination_point(lat, lon, az, float(dist))
            h = dem.elevation(plat, plon).height_m
            angle = math.degrees(math.atan2(h - base, dist))
            if angle > best_angle:
                best_angle, best_dist, best_h = angle, float(dist), h
        out.append(HorizonSample(float(az), best_angle, best_dist, best_h))
    return out
