from __future__ import annotations

from pathlib import Path

from video_location_vaccum.analysis.clues import analyze_audio
from video_location_vaccum.config import RunConfig
from video_location_vaccum.demo import build_scene
from video_location_vaccum.triage.video import is_audio, write_audio_worksheet


def test_audio_only_config_is_valid() -> None:
    cfg = RunConfig.model_validate({"input": {"audio": "clip.wav"}})
    assert cfg.input.audio is not None
    assert cfg.input.video is None


def test_audio_detection() -> None:
    assert is_audio(Path("a.wav"))
    assert is_audio(Path("a.FLAC"))
    assert not is_audio(Path("a.mp4"))


def test_audio_worksheet_and_clues(tmp_path: Path) -> None:
    import soundfile as sf

    scene = build_scene()
    clip = scene.audio[: int(20 * scene.sr)]
    path = tmp_path / "clip.wav"
    sf.write(path, clip, scene.sr)

    report = analyze_audio(path)
    assert report.duration_s > 15
    assert report.sample_rate == 8000
    assert report.hum.hint
    assert report.metadata

    worksheet = write_audio_worksheet(
        out_dir=tmp_path,
        audio=path,
        media={"sha256": "abc", "size_bytes": path.stat().st_size},
        question="where?",
    )
    text = worksheet.read_text(encoding="utf-8")
    assert "Audio-only" in text
    assert "video-location-vaccum events" in text
