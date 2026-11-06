from __future__ import annotations

import numpy as np

from video_location_vaccum.analysis.aircraft import harmonic_analysis


def test_harmonic_analysis_finds_prop_tone() -> None:
    sr = 8000
    t = np.arange(sr * 2) / sr
    y = (
        0.5 * np.sin(2 * np.pi * 120 * t)
        + 0.25 * np.sin(2 * np.pi * 240 * t)
        + 0.1 * np.sin(2 * np.pi * 360 * t)
    )
    y += np.random.default_rng(0).normal(0, 0.01, y.size)
    result = harmonic_analysis(y, sr)
    assert result.blade_pass_hz is not None
    assert abs(result.blade_pass_hz - 120.0) < 3.0
    assert result.harmonic_count >= 2
    assert "prop" in result.class_hint
