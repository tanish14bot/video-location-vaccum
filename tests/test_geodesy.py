from __future__ import annotations

import numpy as np

from video_location_vaccum.geo.geodesy import (
    LocalFrame,
    destination_point,
    ecef_from_geodetic,
    geodetic_from_ecef,
    haversine_m,
)


def test_ecef_round_trip() -> None:
    lat = np.array([0.0, 39.7, -33.9, 60.2])
    lon = np.array([0.0, -105.0, 151.2, 24.9])
    h = np.array([0.0, 1600.0, 58.0, 12.0])
    ecef = ecef_from_geodetic(lat, lon, h)
    lat2, lon2, h2 = geodetic_from_ecef(ecef)
    assert np.allclose(lat, lat2, atol=1e-8)
    assert np.allclose(lon, lon2, atol=1e-8)
    assert np.allclose(h, h2, atol=1e-4)


def test_local_frame_east_is_east() -> None:
    frame = LocalFrame(39.7, -105.0, 1600.0)
    lat2, lon2 = destination_point(39.7, -105.0, 90.0, 1000.0)
    enu = frame.enu_from_geodetic(lat2, lon2, 1600.0)
    assert abs(enu[0] - 1000.0) < 5.0
    assert abs(enu[1]) < 2.0
    assert abs(enu[2]) < 2.0


def test_haversine_matches_enu_distance() -> None:
    frame = LocalFrame(39.7, -105.0, 1600.0)
    lat2, lon2 = destination_point(39.7, -105.0, 45.0, 5000.0)
    enu = frame.enu_from_geodetic(lat2, lon2, 1600.0)
    enu_dist = float(np.linalg.norm(enu[:2]))
    geo_dist = haversine_m(39.7, -105.0, lat2, lon2)
    assert abs(enu_dist - geo_dist) / geo_dist < 0.005
