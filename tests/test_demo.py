from __future__ import annotations

from pathlib import Path

import pytest

from video_location_vaccum.demo import run_demo


@pytest.mark.slow
def test_synthetic_end_to_end_recovers_truth(tmp_path: Path) -> None:
    result = run_demo(tmp_path / "demo", use_detected=False)
    assert result["error_m"] < 50.0, result
    assert len(result["top5"]) >= 1


@pytest.mark.slow
def test_synthetic_time_unknown_recovers_truth(tmp_path: Path) -> None:
    result = run_demo(tmp_path / "demo-unknown", use_detected=False, known_start=False)
    assert result["error_m"] < 50.0, result


@pytest.mark.slow
def test_synthetic_detected_path_recovers_truth(tmp_path: Path) -> None:
    result = run_demo(tmp_path / "demo-detected", use_detected=True)
    assert result["error_m"] < 300.0, result
    assert len(result["ridges"]) >= 2
