from __future__ import annotations

import numpy as np

from video_location_vaccum.audio.fit import fit_pass
from video_location_vaccum.model.doppler import StraightLinePass


def test_fit_recovers_synthetic_pass() -> None:
    c = 343.0
    truth = StraightLinePass(
        f0_hz=140.0,
        speed_mps=90.0,
        cpa_horizontal_m=1200.0,
        cpa_time_s=100.0,
        height_m=800.0,
    )
    rng = np.random.default_rng(7)
    t = np.arange(40.0, 160.0, 0.5)
    f = truth.frequency(t, c) + rng.normal(0.0, 0.15, t.size)
    result = fit_pass(t, f, c_mps=c, height_m=800.0)
    assert result.success
    assert abs(result.pass_.f0_hz - 140.0) / 140.0 < 0.02
    assert abs(result.pass_.speed_mps - 90.0) / 90.0 < 0.04
    assert abs(result.pass_.cpa_horizontal_m - 1200.0) / 1200.0 < 0.12
    assert abs(result.pass_.cpa_time_s - 100.0) < 3.0
    assert result.rmse_hz < 1.0


def test_heard_cpa_includes_delay() -> None:
    c = 343.0
    truth = StraightLinePass(
        f0_hz=140.0, speed_mps=90.0, cpa_horizontal_m=1200.0, cpa_time_s=100.0, height_m=800.0
    )
    result = fit_pass(
        np.arange(40.0, 160.0, 0.5), truth.frequency(np.arange(40.0, 160.0, 0.5), c), c_mps=c, height_m=800.0
    )
    slant = float(np.hypot(1200.0, 800.0))
    assert abs(result.heard_cpa_time(c) - (100.0 + slant / c)) < 0.5
    event = result.to_event(event_id=1, c_mps=c)
    assert abs(event.t_heard_s - result.heard_cpa_time(c)) < 1e-9
