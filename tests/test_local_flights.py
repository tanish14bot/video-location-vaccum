from __future__ import annotations

from pathlib import Path

import pandas as pd

from video_location_vaccum.config import RegionConfig
from video_location_vaccum.demo import build_scene
from video_location_vaccum.flights.local import LocalFlightSource
from video_location_vaccum.geo.geodesy import geodetic_from_ecef


def test_local_adapter_keeps_full_pass_when_track_starts_outside_region(tmp_path: Path) -> None:
    scene = build_scene()
    rows = []
    for flight in scene.flights:
        lat, lon, alt = geodetic_from_ecef(flight.track.ecef)
        for i in range(flight.track.t.size):
            rows.append(
                {
                    "flight_id": flight.flight_id,
                    "time": float(flight.track.t[i]),
                    "lat": float(lat[i]),
                    "lon": float(lon[i]),
                    "alt_m": float(alt[i]),
                }
            )
    path = tmp_path / "flights.parquet"
    pd.DataFrame(rows).to_parquet(path, index=False)

    region = RegionConfig(
        min_lat=scene.lat - 0.02,
        max_lat=scene.lat + 0.02,
        min_lon=scene.lon - 0.02,
        max_lon=scene.lon + 0.02,
    )
    flights = LocalFlightSource(path, altitude_unit="m").fetch(date=scene_date(scene), region=region)
    assert len(flights) == 2
    for flight in flights:
        # The pass starts several km outside the box; it must not be clipped.
        assert flight.track.t.size >= 500
        assert flight.track.t.max() - flight.track.t.min() > 400


def scene_date(scene):
    from datetime import datetime, timezone

    return datetime.fromtimestamp(float(scene.flights[0].track.t[0]), tz=timezone.utc).date()
