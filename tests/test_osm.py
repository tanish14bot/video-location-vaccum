from __future__ import annotations

from video_location_vaccum.analysis.osm import _parse, build_query


def test_build_query_contains_tag_and_radius() -> None:
    query = build_query(39.7, -105.0, 500, {"amenity": "school"})
    assert "around:500" in query
    assert '["amenity"="school"]' in query


def test_parse_ranks_rarer_features_first() -> None:
    payload = {
        "elements": [
            {
                "type": "node",
                "id": 1,
                "lat": 39.7001,
                "lon": -105.0,
                "tags": {"amenity": "school", "name": "A"},
            },
            {
                "type": "node",
                "id": 2,
                "lat": 39.7002,
                "lon": -105.0,
                "tags": {"amenity": "school", "name": "B"},
            },
            {
                "type": "node",
                "id": 3,
                "lat": 39.7003,
                "lon": -105.0,
                "tags": {"amenity": "school", "name": "A"},
            },
        ]
    }
    features = _parse(payload, 39.7, -105.0)
    assert len(features) == 3
    assert features[0].distance_m <= features[-1].distance_m
    assert all(f.osm_type == "node" for f in features)
