from __future__ import annotations

from video_location_vaccum.analysis.terrain import horizon_profile
from video_location_vaccum.geo.dem import ConstantDem


def test_flat_horizon() -> None:
    dem = ConstantDem(100.0)
    profile = horizon_profile(dem, 39.7, -105.0, [0.0, 90.0], max_distance_m=1000, step_m=200)
    assert len(profile) == 2
    for point in profile:
        assert abs(point.elevation_deg) < 0.01
