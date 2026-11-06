from __future__ import annotations

from pathlib import Path

import pytest

from video_location_vaccum.defense.leakage import analyze_leakage
from video_location_vaccum.defense.sanitize import sanitize_file
from video_location_vaccum.demo import build_scene


@pytest.mark.slow
def test_notch_removes_detected_ridge(tmp_path: Path) -> None:
    import soundfile as sf

    scene = build_scene()
    clip = scene.audio[int(90 * scene.sr) : int(170 * scene.sr)]
    source = tmp_path / "clip.wav"
    sf.write(source, clip, scene.sr)

    before = analyze_leakage(source)
    assert before.event_count >= 1

    out = tmp_path / "notched.wav"
    result = sanitize_file(source, out, mode="notch", width_hz=25.0)
    assert out.exists()
    assert result.manifest["warning"]
    after = analyze_leakage(out)
    assert after.event_count == 0
    assert after.risk == "none"

    import soundfile as sf2

    info = sf2.info(str(out))
    assert abs(info.duration - 80.0) < 0.2
