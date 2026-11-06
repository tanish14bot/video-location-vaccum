"""OpenStreetMap feature queries via Overpass.

This is a *lead generator*: it finds candidate blocks where several uncommon
features co-occur. It does not confirm a location.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from ..errors import DataUnavailable
from ..geo.geodesy import haversine_m

OVERPASS = "https://overpass-api.de/api/interpreter"


@dataclass
class OSMFeature:
    osm_type: str
    osm_id: int
    lat: float
    lon: float
    tags: dict[str, str] = field(default_factory=dict)
    distance_m: float = 0.0
    rarity: float = 0.0


def build_query(lat: float, lon: float, radius_m: float, tag_filters: dict[str, str]) -> str:
    if not tag_filters:
        raise ValueError("at least one tag filter is required")
    selectors = []
    for key, value in tag_filters.items():
        tag = f'["{key}"="{value}"]' if value else f'["{key}"]'
        selectors.append(f"node(around:{radius_m},{lat},{lon}){tag};")
        selectors.append(f"way(around:{radius_m},{lat},{lon}){tag};")
    body = "\n".join(selectors)
    return f"[out:json][timeout:30];\n(\n{body}\n);\nout center tags;"


def query_features(
    lat: float,
    lon: float,
    radius_m: float,
    tag_filters: dict[str, str],
    *,
    client: httpx.Client | None = None,
    cache_dir: Path | None = None,
) -> list[OSMFeature]:
    query = build_query(lat, lon, radius_m, tag_filters)
    cache_path = None
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        import hashlib

        key = hashlib.sha256(query.encode()).hexdigest()[:16]
        cache_path = cache_dir / f"overpass-{key}.json"
        if cache_path.exists():
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            return _parse(payload, lat, lon)

    own = client is None
    client = client or httpx.Client(timeout=60.0, follow_redirects=True)
    try:
        response = client.post(OVERPASS, data={"data": query})
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise DataUnavailable(
            "Overpass feature query failed",
            tried=["overpass-api.de"],
            ask="retry later, or provide a local OSM extract / a different Overpass endpoint",
        ) from exc
    finally:
        if own:
            client.close()

    if cache_path is not None:
        cache_path.write_text(json.dumps(payload), encoding="utf-8")
    return _parse(payload, lat, lon)


def _parse(payload: dict[str, Any], lat: float, lon: float) -> list[OSMFeature]:
    counts: dict[tuple[str, str], int] = {}
    raw: list[OSMFeature] = []
    for element in payload.get("elements", []):
        tags = element.get("tags", {}) or {}
        center = element.get("center") or {}
        flat = element.get("lat")
        flon = element.get("lon")
        if flat is None or flon is None:
            flat = center.get("lat")
            flon = center.get("lon")
        if flat is None or flon is None:
            continue
        feature = OSMFeature(
            osm_type=str(element.get("type", "?")),
            osm_id=int(element.get("id", 0)),
            lat=float(flat),
            lon=float(flon),
            tags={str(k): str(v) for k, v in tags.items()},
        )
        feature.distance_m = haversine_m(lat, lon, feature.lat, feature.lon)
        raw.append(feature)
        for key, value in feature.tags.items():
            counts[(key, value)] = counts.get((key, value), 0) + 1

    for feature in raw:
        # Rarer tags contribute more; a chain brand is common and less useful.
        feature.rarity = sum(1.0 / max(1, counts[(k, v)]) for k, v in feature.tags.items())
    raw.sort(key=lambda f: (-f.rarity, f.distance_m))
    return raw
