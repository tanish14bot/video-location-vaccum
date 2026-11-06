<!-- capability_id: cap.doppler.adsb-coarse-filter | revision: 2 | status: active -->

# ADS-B Coarse Filter: Delayed-CPA Timing and Range/Silence Funnel

## I — Interpretation

Translate "who heard whom" into clock-comparable **delayed CPA**, then ask escalating questions at every grid point in the search region. First, does the point's delayed-CPA list contain the **measured event offset** `dt` (± tolerance)? Second, do both events fall inside the measured velocity/range bands? Third, is the interval between them free of any other audible flight? Each answer removes candidates. One worked case uses `dt = 920 s`, a `10 km` radius, a `200 m` grid, and CONUS extent; substitute the offset measured from the user's audio, an audibility radius justified for that environment, and a grid fine enough for that radius. Expect airport points to dominate: route density, not truth, drives counts.

---

## A1 — Application Example

### Example 1 — 35k → 73k → 15k funnel

- **Type**: worked example.
- **Problem/input**: 200 m grid, CONUS single day, 10 km audible radius, `dt = 920 s`
- **How the methodology was used**: delayed-CPA lists → offset window → 35k retained; velocity/range bands → 73k band points (airport-dominated); silence → 15k
- **Conclusion**: Coarse filtering compresses a continent-day to a rankable magnitude; airport points dominate but are not winners
- **Result**: 15k candidates + airport-cluster diagnosis

### Example 2: Other locations / durations (generalized case)

- **Problem/input**: e.g. a 12-minute clip in Europe with a measured offset of 210 s and two events
- **How the methodology was used**: same pipeline with `dt = 210 s`, `R_audible` set for that environment, region = country polygon, date from metadata
- **Result**: candidate count scales with region area, day length, and `R_audible²`; report the count instead of the recording's numbers

---

## A2 — Future Trigger ★

### In what situation will the user need this skill?

1. The user already has event times/velocity bands and needs candidate points from flight data
2. The user needs to explain "why are all candidates around airports"
3. The user needs ranking inputs (candidate × flight-pair)

### Language signals

- "ADS-B / flight data / flight database location"
- "CPA / event offset / time filtering / delayed CPA"
- "why are all candidate points around airports"

### Distinction from adjacent skills

- vs `doppler-event-extraction`: coarse filtering is the database-side time computation; extraction is the audio-side measurement
- vs `locked-scoring`: coarse filtering produces the candidate set; scoring picks the winner inside it

---

## E — Execution

**Required input**: Flight data for the candidate date(s) and region (position/altitude/velocity/timestamp + aircraft type); search region; per-event `t_heard`, `dt`, velocity band, slant band; `c`, `R_audible`, `grid_step`, `type_filter`.
**Deliverable & completion**: Candidate-point table: lat/lon, satisfying flight-ID pair per point, delayed-CPA list, and the parameter set used.

1. **Pull data**
 - Pull all flights for the date range and region; apply `type_filter` explicitly (start broad, then test restricted classes)
 - Minimum fields: `flightid, registration, typecode, callsign, first_seen_ut, last_seen_ut, max_alt, sample_lat, sample_lon` (observed schema)
 - Completion: non-empty flight list with type labels
 - Stop condition: **If the DEM, `c`, or time base is unconfirmed → annotate the convention and pause ranking**
2. **Grid + delayed CPA**
 - Lay the coarse grid over the region → for each point, consider flights within `R_audible` → compute CPA → 3-D slant distance with DEM ground elevation → `delayed_CPA = CPA + slant / c`
 - Completion: every grid point has a delayed-CPA list
3. **Offset window**
 - Keep points whose delayed-CPA list contains a pair separated by the measured `dt ± dt_tol`
 - Completion: candidate count recorded, with region area and day length normalization
4. **Band + silence stack**
 - Keep only pairs inside both events' velocity and slant bands; drop points that would hear another flight during the quiet interval
 - Completion: final candidate set + airport-share note
5. **Sensitivity pass**
 - Re-run step 3–4 with `R_audible` ±50% and `dt_tol` halved/doubled; compare candidate sets
 - Completion: the winner's survival across variants is known before scoring

---

## B — Boundary ★

### Do not use this skill when

- No flight data → no geometry
- Only one event with unknown time → the offset window is impossible; use `single-event-known-time` or ask for time
- Treating `R_audible` as a physical law → it is an engineering assumption; justify and sensitivity-test it
- Treating a candidate count as a result → only ranking decides

### Failure modes to watch for

- ce05: mistaking airport clusters for signal (needs silence + scoring to win)
- ce06: ranking directly on the coarse grid (see `locked-scoring`)

### Method limitations

- **API/DEM/c undisclosed (nr-02/03)**: this card uses method names only, never invents a vendor
- **Silence thresholds undisclosed (nr-04)**: thresholds can shift candidate counts by orders; deliverables must state the values used
- Coverage varies by region, year, altitude, and receiver density; military/blocked traffic may be absent

### Easily confused neighboring methodologies

- `locked-scoring`: coarse filtering does not guarantee rank; ranking is the referee
- `single-event-known-time`: two-event path vs single-event path

---

## Related skills

- depends-on: `doppler-event-extraction`
- composes-with: `locked-scoring`, `single-event-known-time`

---

## Audit

- **Verified**: V1 ✓ / V2 ✓ / V3 ✓
- **Generalized**: 2026-11-04 (920 s / 10 km / 200 m / CONUS converted to parameters)

## Bundled resources

Paths are relative to this file; check preconditions before running anything.

- [resources/parameters.md](../../resources/parameters.md)
- [resources/data-sources.md](../../resources/data-sources.md)