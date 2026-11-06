from __future__ import annotations

import hashlib
from pathlib import Path

from video_location_vaccum.triage.provenance import provenance_report


def test_sha256_and_c2pa_status(tmp_path: Path) -> None:
    path = tmp_path / "clip.bin"
    path.write_bytes(b"video-location-vaccum provenance test")
    report = provenance_report(path)
    assert report["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert report["c2pa"]["status"] in {"checked", "not_checked", "error"}
    assert any("does not prove" in note for note in report["limits"])
