from __future__ import annotations

import gzip
import io
import json
import tarfile
from datetime import date
from pathlib import Path

from video_location_vaccum.config import RegionConfig
from video_location_vaccum.flights.adsblol import AdsbLolSource, parse_archive


def test_release_tag() -> None:
    repo, tag = AdsbLolSource.release_tag(date(2026, 9, 8))
    assert repo == "adsblol/globe_history_2026"
    assert tag == "v2026.09.08-planes-readsb-prod-0"


def test_parse_synthetic_archive(tmp_path: Path) -> None:
    payload = {
        "icao": "abc123",
        "timestamp": 1789000000,
        "t": "PC12",
        "trace": [
            [0, 40.70, -73.60, 8000, 120, 90, 0, 0, {"flight": "TEST123"}],
            [1, 40.70, -73.59, 8000, 120, 90, 0, 0, {"flight": "TEST123"}],
            [2, 40.70, -73.58, 8000, 120, 90, 0, 0, {"flight": "TEST123"}],
        ],
    }
    raw = gzip.compress(json.dumps(payload).encode())
    tar_path = tmp_path / "day.tar"
    with tarfile.open(tar_path, "w") as tar:
        info = tarfile.TarInfo("traces/ab/trace_full_abc123.json")
        info.size = len(raw)
        tar.addfile(info, io.BytesIO(raw))

    region = RegionConfig(min_lat=40.0, min_lon=-74.0, max_lat=41.0, max_lon=-73.0)
    flights = parse_archive([tar_path], region=region)
    assert len(flights) == 1
    assert flights[0].flight_id == "abc123"
    assert flights[0].callsign == "TEST123"
    assert flights[0].track.t.size == 3
    assert flights[0].track.t[0] == 1789000000
