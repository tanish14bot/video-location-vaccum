# Data Sources and Scraping Playbook

> Companion to `parameters.md`. This file answers one question: **where does the data come from, and how is it fetched legally and reproducibly?**
>
> Tool: [Scrapling](https://github.com/D4Vinci/Scrapling) (BSD-3-Clause), installed under `tools/Scrapling` and/or as the `scrapling` Python package.

---

## 0. Policy before any fetch

1. **Prefer an official API** over HTML scraping. Most of the sources below publish one.
2. **Respect `robots.txt`, rate limits, and terms of service.** Scrapling's `robots_txt_obey` option exists for this; enable it in spiders.
3. **Never bypass authentication, paywalls, or CAPTCHAs.** A source that requires a key requires the user's key.
4. **Cache every response to disk** and record `{url, fetched_at, http_status, sha256, license}`. Reproducibility depends on it.
5. **Attribute the source** in any published result.
6. **No personal data.** Aircraft positions are public; people are not.

---

## 1. What the pipeline needs

| Need | Shape | Preferred source type |
|---|---|---|
| Historical flight tracks for a date + region | position, altitude, velocity, timestamp, aircraft type | Official historical API or bulk archive |
| Aircraft type lookup | ICAO hex / callsign → type code → class | Public aircraft database API |
| Ground elevation | lat/lon → metres AMSL | DEM raster or point-query API |
| Street-level imagery / metadata | lat/lon → image or coverage info | Map imagery API |
| Optional: airfield locations | lat/lon | OpenStreetMap / OurAirports |

---

## 2. ADS-B / flight data

Historical, country-scale data is the hardest requirement. Live endpoints cannot reconstruct the past; a recorded archive is required.

| Source | Access | Historical? | Notes |
|---|---|---|---|
| OpenSky Network REST API | Free account, OAuth2 | Limited window on free tier | `/api/states/all?time=...`; research access for longer history |
| adsb.lol / adsb.fi / airplanes.live | Community, mostly live | Usually no | Useful for live snapshots and coverage checks |
| ADSB Exchange API | Paid | Yes | Common choice for historical bulk pulls |
| National/regional open data | Varies | Sometimes | Some civil aviation authorities publish archives |

**Minimum usable fields** (observed working schema): `flightid, registration, typecode, callsign, first_seen_ut, last_seen_ut, max_alt, sample_lat, sample_lon`.

**Bulk size warning:** a continent-scale day is tens of GB (for example, ~50 GB of parquet). Plan storage and use column pruning (`pyarrow.parquet.read_table(columns=[...])`).

### Scrapling pattern — point query / small region

```python
import json, time, hashlib, pathlib
from scrapling.fetchers import Fetcher

CACHE = pathlib.Path("cache/adsb"); CACHE.mkdir(parents=True, exist_ok=True)

def fetch_json(url, params=None, headers=None, pause=2.0):
    key = hashlib.sha256((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()[:16]
    out = CACHE / f"{key}.json"
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    page = Fetcher.get(url, params=params, headers=headers, stealthy_headers=True)
    if page.status != 200:
        raise RuntimeError(f"HTTP {page.status} for {url}")
    data = json.loads(page.body.decode("utf-8"))
    out.write_text(json.dumps(data), encoding="utf-8")
    (CACHE / f"{key}.meta.json").write_text(json.dumps({
        "url": url, "params": params, "fetched_at": time.time(),
        "sha256": hashlib.sha256(out.read_bytes()).hexdigest()
    }), encoding="utf-8")
    time.sleep(pause)
    return data
```

### Scrapling pattern — page with a table (only if no API exists)

```python
from scrapling.fetchers import Fetcher

page = Fetcher.get("https://example.org/flights?date=2026-01-01", stealthy_headers=True)
rows = []
for tr in page.css("table tbody tr"):
    cells = [c.css("::text").get(default="").strip() for c in tr.css("td")]
    if cells:
        rows.append(cells)
```

### When JavaScript is genuinely required

Use `StealthyFetcher` **only** where the site permits automation and no API exists. Prefer `record_requests=True` to capture the JSON the page itself calls, rather than parsing rendered HTML.

```python
from scrapling.fetchers import StealthySession

with StealthySession(headless=True, record_requests=True) as s:
    s.fetch("https://example.org/map")
    for r in s.network.search(limit=None):
        if "application/json" in (r.headers.get("content-type") or ""):
            print(r.url)
```

---

## 3. Aircraft type / class lookup

`typecode` alone does not say prop vs jet. Resolve it once, cache it, and pin the table version.

| Source | Use |
|---|---|
| OpenSky aircraft database | ICAO24 → registration, model, typecode |
| adsbdb / hexdb | Lightweight ICAO24 / callsign lookup |
| Public ICAO type-designator lists | Type code → description, engine type, category |

```python
def lookup_aircraft(icao24):
    return fetch_json(f"https://hexdb.io/api/v1/aircraft/{icao24.lower()}")
```

**Rule:** if the lookup misses, do **not** silently drop the flight. Mark the class `unknown` and run the search with it included, then test a known-class-only variant.

---

## 4. DEM / ground elevation

| Source | Coverage | Resolution | Access |
|---|---|---|---|
| Copernicus DEM GLO-30 | Global | 30 m | AWS Open Data / STAC |
| SRTM 1 arc-second | 60°N–56°S | ~30 m | NASA Earthdata |
| USGS 3DEP | United States | 10 m / 30 m | 3DEP image services, point query |
| OpenTopography | Global subsets | Varies | API key |

```python
# USGS 3DEP point query (identify endpoint in the service directory first)
def elevation_us(lat, lon):
    url = "https://epqs.nationalmap.gov/v1/json"
    return fetch_json(url, params={"x": lon, "y": lat, "units": "Meters", "wkid": 4326})
```

**Rule:** DEM must be the same vertical datum as the aircraft altitude source (usually AMSL). Record the DEM product and resolution next to every result.

---

## 5. Imagery for visual verification

| Source | Type | Access |
|---|---|---|
| Mapillary | Street-level photos + metadata | Free API token |
| KartaView | Street-level photos | Free API |
| Google Street View Static API | Street-level | Paid key; ToS restricts storage/derivatives |
| Bing Maps / Esri World Imagery | Aerial | Key or tile service |

**Rule:** check the imagery date. A feature match against an image taken after the video is not proof.

---

## 6. Scrapling CLI recipes

```bash
# Static page to clean markdown
scrapling extract get "https://example.org/page" out.md

# JSON endpoint to file
scrapling extract get "https://opensky-network.org/api/states/all?time=1700000000" states.json

# JS-rendered page (only where permitted)
scrapling extract fetch "https://example.org/map" out.md --wait-selector ".result"
```

Browser fetchers need a one-time browser install:

```bash
pip install "scrapling[fetchers]"
scrapling install
```

HTTP-only fetchers work without browsers.

### Tested minimal install (2026-11-04)

`scrapling 0.5` alone is not enough for `Fetcher`; the static engine imports `patchright` and `browserforge`. This set works:

```bash
python -m venv tools/scrapling-venv
tools/scrapling-venv/Scripts/pip install scrapling curl_cffi patchright browserforge
```

Verified live: `hexdb.io` aircraft lookup and `adsbdb.com` callsign lookup both return HTTP 200 through `Fetcher.get`. Browser fetchers additionally need `scrapling install` to download Chromium.

---

## 7. Provenance record (ship this with every result)

```yaml
sources:
  - kind: adsb
    provider: "<name>"
    access: "api-key | public | archive"
    query: "<url or archive path>"
    fetched_at: "<ISO-8601>"
    license: "<license or ToS note>"
  - kind: dem
    product: "<name>"
    resolution_m: 30
  - kind: imagery
    provider: "<name>"
    image_date: "<YYYY-MM-DD or unknown>"
```

If a result cannot name its sources and their dates, it is not reproducible.

---

## 8. What Scrapling does not solve

- **Paywalls and authentication.** A key is still required.
- **Historical archives that are not published.** Scraping live data cannot reconstruct a past day.
- **Coverage gaps.** No receiver, no record. Absence of flights is not absence of aircraft.
- **Licensing.** Scraping is a technical act; the license still governs redistribution.
