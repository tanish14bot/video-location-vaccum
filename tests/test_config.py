from __future__ import annotations

from datetime import date

import pytest

from video_location_vaccum.config import EventConfig, RegionConfig, RunConfig, SearchConfig


def _region() -> RegionConfig:
    return RegionConfig(min_lat=39.0, min_lon=-106.0, max_lat=40.0, max_lon=-105.0)


def test_grid_must_be_within_audible_radius() -> None:
    with pytest.raises(ValueError):
        SearchConfig(region=_region(), date=date(2026, 1, 1), r_audible_m=10_000, grid_step_m=20_000)


def test_date_order() -> None:
    with pytest.raises(ValueError):
        SearchConfig(region=_region(), date=date(2026, 1, 2), date_end=date(2026, 1, 1))


def test_event_band_order() -> None:
    with pytest.raises(ValueError):
        EventConfig(id=1, t_heard_s=10, f0_hz=100, velocity_band_mps=(200, 100))


def test_doppler_mode_requires_search() -> None:
    with pytest.raises(ValueError):
        RunConfig.model_validate(
            {
                "input": {"audio": "a.wav"},
                "triage": {"mode": "doppler"},
            }
        )


def test_dates_expand() -> None:
    cfg = SearchConfig(region=_region(), date=date(2026, 1, 1), date_end=date(2026, 1, 3))
    assert len(cfg.dates) == 3
