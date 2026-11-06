"""Terrain elevation with a provenance-aware fallback chain.

The single most important detail here is the vertical datum. Aircraft altitude
and DEM height are not automatically in the same frame; this module records the
datum it used and refuses to pretend the difference does not exist.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

import httpx

from ..errors import DataUnavailable


class VerticalDatum(str, Enum):
    ELLIPSOIDAL = "ellipsoidal"
    ORTHOMETRIC_EGM2008 = "orthometric_egm2008"
    ORTHOMETRIC_EGM96 = "orthometric_egm96"
    ORTHOMETRIC_NAVD88 = "orthometric_navd88"
    UNKNOWN = "unknown"


@dataclass
class DemSample:
    height_m: float
    datum: VerticalDatum
    resolution_m: float | None
    source: str
    confidence: str  # high | medium | low


class DemSource(Protocol):
    name: str
    requires_key: bool
    license: str

    def available(self) -> bool: ...

    def elevation(self, lat: float, lon: float) -> DemSample: ...


class ConstantDem:
    """Explicit flat-terrain assumption; only used when the user allows it."""

    name = "constant"
    requires_key = False
    license = "n/a"

    def __init__(self, height_m: float = 0.0, datum: VerticalDatum = VerticalDatum.UNKNOWN) -> None:
        self.height_m = float(height_m)
        self.datum = datum

    def available(self) -> bool:
        return True

    def elevation(self, lat: float, lon: float) -> DemSample:
        return DemSample(self.height_m, self.datum, None, self.name, "low")


class LocalRasterDem:
    """A local GeoTIFF/COG. Datum must be supplied by the caller."""

    name = "local-raster"
    requires_key = False
    license = "user-provided"

    def __init__(self, path: Path, datum: VerticalDatum = VerticalDatum.UNKNOWN) -> None:
        self.path = Path(path)
        self.datum = datum
        self._ds = None

    def available(self) -> bool:
        return self.path.exists()

    def _open(self):
        if self._ds is None:
            import rasterio

            self._ds = rasterio.open(self.path)
        return self._ds

    def elevation(self, lat: float, lon: float) -> DemSample:
        ds = self._open()
        value = next(ds.sample([(lon, lat)]))[0]
        if value is None or not math.isfinite(float(value)):
            raise DataUnavailable(
                f"DEM has no data at {lat:.5f},{lon:.5f}",
                ask="provide a DEM that covers this point, or allow a flat-terrain fallback",
            )
        return DemSample(
            float(value),
            self.datum,
            float(abs(ds.transform.a)) * 111_320.0,
            self.name,
            "high" if self.datum is not VerticalDatum.UNKNOWN else "medium",
        )


class UsgsEpqsDem:
    """USGS 3DEP point query (CONUS/HI/PR), keyless, NAVD88."""

    name = "usgs-3dep-epqs"
    requires_key = False
    license = "public-domain"
    endpoint = "https://epqs.nationalmap.gov/v1/json"

    def available(self) -> bool:
        return True

    def elevation(self, lat: float, lon: float) -> DemSample:
        try:
            r = httpx.get(
                self.endpoint,
                params={"x": lon, "y": lat, "units": "Meters", "wkid": 4326, "includeDate": "false"},
                timeout=20.0,
            )
            r.raise_for_status()
            value = float(r.json()["value"])
        except Exception as exc:
            raise DataUnavailable(
                f"USGS elevation query failed at {lat:.5f},{lon:.5f}",
                tried=[self.name],
                ask="provide a DEM file or allow a flat-terrain fallback",
            ) from exc
        return DemSample(value, VerticalDatum.ORTHOMETRIC_NAVD88, 10.0, self.name, "high")


class OpenMeteoDem:
    """Global Copernicus GLO-90 point query, keyless, 100 points/call."""

    name = "open-meteo-cop90"
    requires_key = False
    license = "CC-BY-4.0"
    endpoint = "https://api.open-meteo.com/v1/elevation"

    def available(self) -> bool:
        return True

    def elevation(self, lat: float, lon: float) -> DemSample:
        try:
            r = httpx.get(self.endpoint, params={"latitude": lat, "longitude": lon}, timeout=20.0)
            r.raise_for_status()
            value = float(r.json()["elevation"][0])
        except Exception as exc:
            raise DataUnavailable(
                f"Open-Meteo elevation query failed at {lat:.5f},{lon:.5f}",
                tried=[self.name],
                ask="provide a DEM file or allow a flat-terrain fallback",
            ) from exc
        return DemSample(value, VerticalDatum.ORTHOMETRIC_EGM2008, 90.0, self.name, "medium")


class DemChain:
    """Try sources in order; never silently return a fabricated height."""

    def __init__(self, sources: list[DemSource], *, allow_flat: bool = False) -> None:
        self.sources = sources
        self.allow_flat = allow_flat
        self._cache: dict[tuple[float, float], DemSample] = {}

    def elevation(self, lat: float, lon: float) -> DemSample:
        key = (round(lat, 6), round(lon, 6))
        if key in self._cache:
            return self._cache[key]
        tried: list[str] = []
        for src in self.sources:
            if not src.available():
                tried.append(f"{src.name}:unavailable")
                continue
            try:
                sample = src.elevation(lat, lon)
            except DataUnavailable:
                tried.append(f"{src.name}:failed")
                continue
            self._cache[key] = sample
            return sample
        if self.allow_flat:
            sample = DemSample(0.0, VerticalDatum.UNKNOWN, None, "flat-fallback", "low")
            self._cache[key] = sample
            return sample
        raise DataUnavailable(
            f"no elevation source could answer for {lat:.5f},{lon:.5f}",
            tried=tried,
            ask="provide a DEM (GeoTIFF) or explicitly allow a flat-terrain fallback",
        )
