from __future__ import annotations

import struct
from pathlib import Path

from video_location_vaccum.analysis.metadata import _parse_iso6709, extract_metadata, parse_bext


def test_parse_bext() -> None:
    data = bytearray(602)
    data[0:4] = b"Test"
    data[256:264] = b"Recorder"
    data[320:330] = b"2026-01-02"
    data[330:338] = b"03:04:05"
    data[338:346] = struct.pack("<Q", 123456)
    data[346:348] = struct.pack("<H", 1)
    parsed = parse_bext(bytes(data))
    assert parsed["originator"] == "Recorder"
    assert parsed["origination_date"] == "2026-01-02"
    assert parsed["time_reference"] == 123456


def test_parse_iso6709() -> None:
    assert _parse_iso6709("+39.7392-104.9903/") == (39.7392, -104.9903)
    assert _parse_iso6709("+39.7-105.0+1600/") == (39.7, -105.0)


def test_extract_metadata_plain_wav(tmp_path: Path) -> None:
    import soundfile as sf

    path = tmp_path / "a.wav"
    sf.write(path, [0.0] * 800, 8000)
    report = extract_metadata(path)
    assert "notes" in report.to_dict()
    assert "riff" in report.sources
