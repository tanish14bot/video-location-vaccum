"""WGS-84 geodesy and local tangent-plane conversions.

All positions are handled in ECEF internally and in a local East-North-Up
frame for geometry. This avoids the flat-earth errors that dominate at the
10 km scale used by the acoustic method.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

WGS84_A = 6_378_137.0
WGS84_F = 1.0 / 298.257_223_563
WGS84_B = WGS84_A * (1.0 - WGS84_F)
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)


def ecef_from_geodetic(lat_deg: ArrayLike, lon_deg: ArrayLike, h_m: ArrayLike) -> NDArray[np.float64]:
    """Geodetic (lat, lon, ellipsoidal height) -> ECEF metres."""
    lat = np.radians(np.asarray(lat_deg, dtype=float))
    lon = np.radians(np.asarray(lon_deg, dtype=float))
    h = np.asarray(h_m, dtype=float)
    sin_lat = np.sin(lat)
    cos_lat = np.cos(lat)
    n = WGS84_A / np.sqrt(1.0 - WGS84_E2 * sin_lat * sin_lat)
    x = (n + h) * cos_lat * np.cos(lon)
    y = (n + h) * cos_lat * np.sin(lon)
    z = (n * (1.0 - WGS84_E2) + h) * sin_lat
    return np.stack(np.broadcast_arrays(x, y, z), axis=-1)


def geodetic_from_ecef(
    ecef: ArrayLike,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """ECEF metres -> geodetic (lat, lon, ellipsoidal height)."""
    p = np.asarray(ecef, dtype=float)
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    lon = np.arctan2(y, x)
    r = np.hypot(x, y)
    lat = np.arctan2(z, r * (1.0 - WGS84_E2))
    for _ in range(6):
        sin_lat = np.sin(lat)
        n = WGS84_A / np.sqrt(1.0 - WGS84_E2 * sin_lat * sin_lat)
        h = r / np.cos(lat) - n
        lat = np.arctan2(z, r * (1.0 - WGS84_E2 * n / (n + h)))
    sin_lat = np.sin(lat)
    n = WGS84_A / np.sqrt(1.0 - WGS84_E2 * sin_lat * sin_lat)
    h = r / np.cos(lat) - n
    return np.degrees(lat), np.degrees(lon), h


class LocalFrame:
    """East-North-Up frame anchored at an observer position."""

    def __init__(self, lat_deg: float, lon_deg: float, height_m: float) -> None:
        self.lat = float(lat_deg)
        self.lon = float(lon_deg)
        self.height = float(height_m)
        self.origin_ecef = np.asarray(ecef_from_geodetic(self.lat, self.lon, self.height), dtype=float)
        self._rot = self._rotation(self.lat, self.lon)

    @staticmethod
    def _rotation(lat_deg: float, lon_deg: float) -> NDArray[np.float64]:
        lat = np.radians(lat_deg)
        lon = np.radians(lon_deg)
        sl, cl = np.sin(lat), np.cos(lat)
        so, co = np.sin(lon), np.cos(lon)
        return np.array(
            [
                [-so, co, 0.0],
                [-sl * co, -sl * so, cl],
                [cl * co, cl * so, sl],
            ],
            dtype=float,
        )

    def enu_from_ecef(self, ecef: ArrayLike) -> NDArray[np.float64]:
        delta = np.asarray(ecef, dtype=float) - self.origin_ecef
        return delta @ self._rot.T

    def ecef_from_enu(self, enu: ArrayLike) -> NDArray[np.float64]:
        return np.asarray(enu, dtype=float) @ self._rot + self.origin_ecef

    def vector_ecef_to_enu(self, vec_ecef: ArrayLike) -> NDArray[np.float64]:
        """Rotate an ECEF vector (not a position) into ENU."""
        return np.asarray(vec_ecef, dtype=float) @ self._rot.T

    def enu_from_geodetic(
        self, lat_deg: ArrayLike, lon_deg: ArrayLike, h_m: ArrayLike
    ) -> NDArray[np.float64]:
        return self.enu_from_ecef(ecef_from_geodetic(lat_deg, lon_deg, h_m))

    def geodetic_from_enu(
        self, enu: ArrayLike
    ) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
        return geodetic_from_ecef(self.ecef_from_enu(enu))


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres (spherical approximation)."""
    r = 6_371_008.8
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return float(2 * r * np.arcsin(np.sqrt(a)))


def destination_point(lat: float, lon: float, bearing_deg: float, distance_m: float) -> tuple[float, float]:
    """Point reached from (lat, lon) along a bearing, on a sphere."""
    r = 6_371_008.8
    d = distance_m / r
    b = np.radians(bearing_deg)
    p1 = np.radians(lat)
    l1 = np.radians(lon)
    p2 = np.arcsin(np.sin(p1) * np.cos(d) + np.cos(p1) * np.sin(d) * np.cos(b))
    l2 = l1 + np.arctan2(np.sin(b) * np.sin(d) * np.cos(p1), np.cos(d) - np.sin(p1) * np.sin(p2))
    return float(np.degrees(p2)), float((np.degrees(l2) + 180) % 360 - 180)
