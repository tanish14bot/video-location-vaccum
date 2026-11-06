from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from video_location_vaccum.analysis.viability import assess_viability
from video_location_vaccum.demo import build_scene


@pytest.mark.slow
def test_viability_dual_event(tmp_path: Path) -> None:
    import soundfile as sf

    scene = build_scene()
    path = tmp_path / "scene.wav"
    sf.write(path, scene.audio, scene.sr)
    report = assess_viability(path)
    assert report.curve_count >= 2
    assert report.verdict == "multiple-events"
    assert report.event_offset_s is not None and report.event_offset_s > 30


@pytest.mark.slow
def test_viability_noise_is_visual_only(tmp_path: Path) -> None:
    import soundfile as sf

    rng = np.random.default_rng(0)
    path = tmp_path / "noise.wav"
    sf.write(path, rng.normal(0, 0.01, 8000 * 20), 8000)
    report = assess_viability(path)
    assert report.curve_count == 0
    assert report.verdict == "visual-only"
