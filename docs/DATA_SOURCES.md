# Data Sources and Fallback Chain

The method needs flight tracks, ground elevation, and optionally aircraft type
and imagery. No data is bundled. Each adapter declares its license, auth, and
historical coverage.

## Fallback chain

```
user-provided file
  → local cache
    → keyed API (user's own credentials)
      → free archive / mirror
        → ask the user for a file
```

The pipeline **never substitutes live data for a past date**. When every source
fails it raises `DataUnavailable` with the exact schema it needs.

## Flight data

| Source | Access | Historical | License / notes |
|---|---|---|---|
| User file | Parquet / CSV / JSON | any | user-controlled; preferred |
| Local cache | normalized Parquet | any previously fetched | project cache |
| OpenSky REST | free account / OAuth2 | tracks: last 30 days | non-commercial; no redistribution |
| OpenSky Trino | approved account | 2013+ | research/commercial license required |
| adsb.lol daily archive | no key | 2023+ | ODbL 1.0; attribution + share-alike |
| ADS-B Exchange | paid contract | 2016+ | commercial; no redistribution |
| EUROCONTROL ADRR | research account | 2015+, 12-month delay | research terms |
| FAA SWIM | account | live only | not a historical source |

### adsb.lol daily archive (free historical)

- Repo: `adsblol/globe_history_<year>`
- Tag: `v<YYYY.MM.DD>-planes-readsb-prod-0` (e.g. `v2026.09.08-planes-readsb-prod-0`)
- Assets: split tar (`.tar.aa`, `.tar.ab`), **several GB per day** (global)
- Contents: `traces/xx/trace_full_<icao>.json`, gzip JSON
- Trace row: `[sec_after_timestamp, lat, lon, alt_ft, gs_kt, track_deg, flags, ...]`
- License: **ODbL 1.0** (attribution + share-alike)

`AdsbLolSource` resolves the release, downloads the parts into
`flights.cache_dir/adsblol-<date>/`, streams the tar, and filters to the region
before building tracks. The first run downloads several GB; later runs reuse the
cache. If `cache_dir` is not set, the adapter asks for a local archive.

### Practical volume

| Source | One CONUS day |
|---|---|
| Normalized Parquet (10 columns) | ~0.5–1.5 GiB |
| adsb.lol traces (gzip) | ~1 GB |
| OpenSky state vectors | ~3–4 GiB |
| ADS-B Exchange high-resolution | ~8–20 GB |
| OpenSky full decoded tables | ~50 GiB |

Use Parquet + ZSTD, partition by date/hour, and filter at read time.

### Minimum schema

```
flight_id, time, lat, lon, alt_m
```

Optional: `callsign, registration, typecode, aircraft_class, gs_mps, track_deg`.

`LocalFlightSource` validates units. It does not guess whether altitude is feet
or metres; pass `altitude_unit`.

## Terrain / DEM

| Source | Coverage | Resolution | Vertical datum | Access |
|---|---|---|---|---|
| Copernicus GLO-30 | global land | 30 m | EGM2008 | AWS Open Data, anonymous |
| Copernicus GLO-90 | global land | 90 m | EGM2008 | AWS / Open-Meteo |
| SRTM GL1 | 60°N–56°S | 30 m | EGM96 | NASA Earthdata login |
| USGS 3DEP | US | 10 m / 30 m | NAVD88 | keyless point query / S3 |
| Open-Meteo | global | 90 m | EGM2008 (inferred) | keyless, 10k calls/day |
| User raster | any | any | must be declared | local GeoTIFF/COG |

**Datum warning.** Orthometric DEM height and ellipsoidal aircraft altitude
differ by 8–53 m in CONUS. The difference is not a rounding error. `DemSample`
records the datum; unknown datum lowers confidence and widens uncertainty.

## Aircraft type

| Source | Use |
|---|---|
| OpenSky aircraft database | ICAO24 → registration/model/typecode |
| adsbdb | callsign / ICAO24 lookup |
| hexdb | lightweight ICAO24 lookup |
| Public ICAO type-designator lists | type code → class/engine |

If the lookup misses, the flight stays `unknown`. It is **not** dropped: an
unlabelled true flight is unrecoverable, while an extra candidate only costs time.

## Imagery

| Source | Type | Notes |
|---|---|---|
| Mapillary | street-level | free token; open license |
| KartaView | street-level | free |
| Google Street View Static | street-level | paid; storage/derivative restrictions |
| Esri / Bing | aerial | key / tile service |

Check the **imagery date**. A match against a later image is not proof.

## Legal classification

| Class | Steps | Rule |
|---|---|---|
| Green | user file, cache, ask user | no third-party terms |
| Green + attribution | adsb.lol archive | ODbL: attribute, share-alike |
| Yellow — evaluation | ADS-B Exchange samples | do not build a public archive |
| Yellow — non-commercial | adsb.fi, airplanes.live | 1 req/s, no bulk |
| Red — credentials | OpenSky Trino, ADSBX, EUROCONTROL, SWIM | user's own account; never bundle keys |

## Scrapling

Scrapling is optional, for endpoints without a client library. Rules:

- prefer the official API;
- respect `robots.txt` and rate limits;
- never bypass authentication or CAPTCHAs;
- cache every response and record `{url, fetched_at, sha256, license}`;
- use `Fetcher` for static/JSON; use a browser only when JavaScript is genuinely
  required and permitted.

Tested minimal install for the HTTP fetcher:

```bash
python -m venv tools/scrapling-venv
tools/scrapling-venv/Scripts/pip install scrapling curl_cffi patchright browserforge
```

Browser fetchers additionally need `scrapling install`.

## Provenance record

Every run should ship:

```yaml
sources:
  - kind: flights
    provider: "<name>"
    license: "<license>"
    query: "<url or file>"
    fetched_at: "<ISO-8601>"
  - kind: dem
    product: "<name>"
    vertical_datum: "EGM2008"
    resolution_m: 30
  - kind: imagery
    provider: "<name>"
    image_date: "<YYYY-MM-DD or unknown>"
```

If a result cannot name its sources and their dates, it is not reproducible.
