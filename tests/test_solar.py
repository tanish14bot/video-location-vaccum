from __future__ import annotations

from datetime import datetime, timezone

from video_location_vaccum.analysis.solar import (
    hour_angle,
    latitude_band_from_shadow,
    night_at,
    shadow_ratio,
    solar_position,
)


def test_equinox_noon_at_equator() -> None:
    dt = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
    _, elevation, _ = solar_position(0.0, 0.0, dt)
    assert elevation > 80.0


def test_equinox_noon_at_45n() -> None:
    dt = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
    _, elevation, declination = solar_position(45.0, 0.0, dt)
    assert 40.0 < elevation < 50.0
    ratio = shadow_ratio(elevation)
    assert ratio is not None
    assert 0.8 < ratio < 1.3
    band = latitude_band_from_shadow(ratio, declination, hour_angle(dt, 0.0))
    assert any(abs(v - 45.0) < 6.0 for v in band)


def test_night_flag() -> None:
    dt = datetime(2026, 3, 20, 0, 0, tzinfo=timezone.utc)
    assert night_at(45.0, 0.0, dt)
